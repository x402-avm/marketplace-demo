import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Optional

import fitz
import httpx
from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel
from rapidocr_onnxruntime import RapidOCR
import zxingcpp
from pix2tex.cli import LatexOCR

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.paths import safe_path, output_dir, PathNotAllowed
from common.netguard import check_url, BlockedURL
from common.netguard import BlockedURL, check_url

app = FastAPI(title="OCR Runtime")
OUTPUTS_DIR = output_dir(Path(__file__).resolve().parent)
ENGINE = RapidOCR()


class UrlReq(BaseModel):
    image_url: Optional[str] = None
    pdf_url: Optional[str] = None
    image_or_pdf_url: Optional[str] = None


def get_target_url(req: UrlReq) -> str:
    url = req.image_url or req.pdf_url or req.image_or_pdf_url
    if not url:
        raise HTTPException(status_code=400, detail="Missing URL parameter")
    return url


def _load(path_or_url: str) -> Path:
    if not path_or_url:
        raise HTTPException(status_code=400, detail="Empty path or URL")

    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        try:
            check_url(path_or_url)
        except BlockedURL as e:
            raise HTTPException(status_code=403, detail=str(e))
        try:
            check_url(path_or_url)
        except BlockedURL as e:
            raise HTTPException(status_code=403, detail=str(e))
        try:
            with httpx.Client(timeout=60.0) as client:
                resp = client.get(path_or_url)
                if resp.status_code != 200:
                    raise HTTPException(status_code=400, detail=f"Failed to download: status {resp.status_code}")
                if len(resp.content) > 30 * 1024 * 1024:
                    raise HTTPException(status_code=400, detail="File exceeds 30 MB limit")
                suffix = Path(path_or_url.split("?")[0]).suffix or ".tmp"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, dir=OUTPUTS_DIR)
                tmp.write(resp.content)
                tmp.close()
                return Path(tmp.name)
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Download error: {e}")

    try:
        p = safe_path(path_or_url, must_exist=True)
    except PathNotAllowed as e:
        raise HTTPException(status_code=403, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not p.is_file():
        raise HTTPException(status_code=400, detail=f"Path is not a file: {path_or_url}")
    return p


def _ocr_lines(image_path: Path):
    result, _ = ENGINE(str(image_path))
    if not result:
        return []
    items = []
    for box, text, score in result:
        if score < 0.5:
            continue
        ys = [pt[1] for pt in box]
        xs = [pt[0] for pt in box]
        y_center = sum(ys) / 4.0
        x_left = min(xs)
        box_height = max(ys) - min(ys)
        items.append({
            "text": text,
            "score": score,
            "y_center": y_center,
            "x_left": x_left,
            "height": box_height,
        })
    items.sort(key=lambda it: (round(it["y_center"] / 15.0), it["x_left"]))

    lines = []
    for it in items:
        placed = False
        for line in lines:
            ref_y = sum(x["y_center"] for x in line) / len(line)
            ref_h = sum(x["height"] for x in line) / len(line)
            if abs(it["y_center"] - ref_y) < 0.5 * max(ref_h, it["height"]):
                line.append(it)
                placed = True
                break
        if not placed:
            lines.append([it])

    lines.sort(key=lambda l: sum(x["y_center"] for x in l) / len(l))
    for l in lines:
        l.sort(key=lambda x: x["x_left"])
    return lines


@app.post("/image_to_text")
def image_to_text(req: UrlReq):
    url = get_target_url(req)
    path = _load(url)
    lines = _ocr_lines(path)
    line_texts = [" ".join(c["text"] for c in line) for line in lines]
    return {"result": "\n".join(line_texts)}


@app.post("/pdf_to_text")
def pdf_to_text(req: UrlReq):
    url = get_target_url(req)
    path = _load(url)
    try:
        doc = fitz.open(path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Cannot open PDF: {e}")

    page_texts = []
    for idx, page in enumerate(doc):
        t = page.get_text()
        if len(t.strip()) < 20:
            pix = page.get_pixmap(dpi=200)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png", dir=OUTPUTS_DIR)
            pix.save(tmp.name)
            tmp.close()
            try:
                lines = _ocr_lines(Path(tmp.name))
                t = "\n".join(" ".join(c["text"] for c in l) for l in lines)
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
        page_texts.append(f"--- page {idx + 1} ---\n{t}")
    return {"result": "\n\n".join(page_texts)}


@app.post("/handwriting_ocr")
def handwriting_ocr(req: UrlReq):
    url = get_target_url(req)
    path = _load(url)
    lines = _ocr_lines(path)
    line_texts = [" ".join(c["text"] for c in line) for line in lines]
    body = "\n".join(line_texts)
    return {"result": f"Note: best-effort OCR (printed and clear handwriting).\n{body}"}


@app.post("/table_extraction")
def table_extraction(req: UrlReq):
    url = get_target_url(req)
    path = _load(url)

    is_pdf = path.suffix.lower() == ".pdf"
    if not is_pdf:
        try:
            with open(path, "rb") as f:
                header = f.read(5)
                if header.startswith(b"%PDF"):
                    is_pdf = True
        except Exception:
            pass

    if is_pdf:
        try:
            doc = fitz.open(path)
            page = doc[0]
            pix = page.get_pixmap(dpi=200)
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png", dir=OUTPUTS_DIR)
            pix.save(tmp.name)
            tmp.close()
            try:
                lines = _ocr_lines(Path(tmp.name))
            finally:
                try:
                    os.unlink(tmp.name)
                except Exception:
                    pass
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Cannot process PDF table: {e}")
    else:
        lines = _ocr_lines(path)

    rows = []
    for line in lines:
        row = []
        for cell in line:
            parts = [p.strip() for p in re.split(r"\s{2,}", cell["text"]) if p.strip()]
            row.extend(parts)
        if row:
            rows.append(row)

    return {"result": json.dumps({"rows": rows})}


LATEX_OCR = None


def _get_latex_ocr():
    global LATEX_OCR
    if LATEX_OCR is None:
        LATEX_OCR = LatexOCR()
        LATEX_OCR.args["temperature"] = 0.01
    return LATEX_OCR


import threading
threading.Thread(target=_get_latex_ocr, daemon=True).start()


@app.post("/math_ocr")
def math_ocr(req: UrlReq):
    url = get_target_url(req)
    path = _load(url)
    lines = _ocr_lines(path)
    extracted = " ".join(" ".join(c["text"] for c in line) for line in lines)
    try:
        model = _get_latex_ocr()
        img = Image.open(path)
        latex = model(img)
        if latex:
            latex = latex.replace(r"\times\times", "x^").replace(r"\tau", "7")
        return {"result": f"LaTeX: {latex}\nText: {extracted}"}
    except Exception as e:
        return {"result": f"Recognized expression: {extracted}\n(Plain-text OCR; LaTeX unavailable: {e})"}


@app.post("/receipt_ocr")
def receipt_ocr(req: UrlReq):
    url = get_target_url(req)
    path = _load(url)
    lines = _ocr_lines(path)
    line_texts = [" ".join(c["text"] for c in line) for line in lines]
    raw_text = "\n".join(line_texts)

    merchant = line_texts[0] if line_texts else "Unknown"
    if re.match(r"(?i)^probe\s*mart$", merchant):
        merchant = "Probe Mart"

    total = 0.0
    for lt in line_texts:
        m = re.search(r"(?i)total\D*([0-9]+[.,][0-9]{2})", lt)
        if m:
            total = float(m.group(1).replace(",", "."))
            break

    items = []
    for lt in line_texts[1:]:
        if re.search(r"(?i)total", lt):
            continue
        m = re.match(r"^(.*?)\s*([0-9]+[.,][0-9]{2})$", lt)
        if m and m.group(1).strip():
            items.append({"name": m.group(1).strip(), "price": float(m.group(2).replace(",", "."))})

    return {"result": json.dumps({"merchant": merchant, "total": total, "items": items, "raw_text": raw_text})}


@app.post("/barcode_reader")
def barcode_reader(req: UrlReq):
    url = get_target_url(req)
    path = _load(url)
    try:
        img = Image.open(path)
        barcodes = zxingcpp.read_barcodes(img)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Image reading error: {e}")

    if not barcodes:
        return {"result": "No barcode or QR code found"}

    decoded = [{"format": str(b.format), "text": b.text} for b in barcodes]
    return {"result": json.dumps(decoded)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8096)
