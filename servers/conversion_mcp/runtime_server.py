import os
import sys
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from pathlib import Path
from uuid import uuid4
import urllib.parse
import subprocess
import shutil
import tarfile
import zipfile
import json
import csv
import httpx
from PIL import Image
import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.paths import safe_path, output_dir, PathNotAllowed
from common.netguard import check_url, BlockedURL

app = FastAPI(title="Conversion Runtime")
OUTPUTS_DIR = output_dir(Path(__file__).resolve().parent)


class ConvertReq(BaseModel):
    file_url: str
    from_format: str
    to_format: str


class ArchiveReq(BaseModel):
    file_urls: Optional[List[str]] = None
    file_url: Optional[str] = None
    format: str


DOC_FROM = {"html", "htm", "txt", "md", "doc", "docx", "odt", "rtf", "pptx", "xlsx"}
DOC_TO = {"pdf", "docx", "odt", "html", "txt"}

DATA_FROM = {"json", "csv", "xlsx"}
DATA_TO = {"json", "csv", "xlsx"}

IMAGE_FORMATS = {"png", "jpg", "jpeg", "webp", "bmp", "gif", "tiff"}

AUDIO_FORMATS = {"wav", "mp3", "ogg", "flac", "m4a", "aac"}

VIDEO_FORMATS = {"mp4", "webm", "mkv", "mov", "gif"}

ARCHIVE_FORMATS = {"zip", "tar", "tar.gz", "7z"}


def _fetch_input(file_url: str) -> Path:
    if not file_url or not isinstance(file_url, str):
        raise HTTPException(status_code=400, detail="file_url is required and must be a string")
    url_lower = file_url.lower()
    if url_lower.startswith("http://") or url_lower.startswith("https://"):
        try:
            check_url(file_url)
        except BlockedURL as e:
            raise HTTPException(status_code=403, detail=str(e))
        try:
            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                with client.stream("GET", file_url) as resp:
                    if resp.status_code != 200:
                        raise HTTPException(status_code=400, detail=f"Download failed with status {resp.status_code}")
                    parsed_path = Path(urllib.parse.urlparse(file_url).path)
                    suffix = parsed_path.suffix if parsed_path.suffix else ".tmp"
                    temp_dir = OUTPUTS_DIR / f"dl_{uuid4().hex}"
                    temp_dir.mkdir(parents=True, exist_ok=True)
                    target = temp_dir / (parsed_path.name if parsed_path.name else f"input{suffix}")
                    downloaded = 0
                    max_bytes = 100 * 1024 * 1024  # 100 MB
                    with open(target, "wb") as f:
                        for chunk in resp.iter_bytes(chunk_size=65536):
                            downloaded += len(chunk)
                            if downloaded > max_bytes:
                                raise HTTPException(status_code=400, detail="Downloaded file exceeds 100 MB limit")
                            f.write(chunk)
                    return target
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch {file_url}: {e}")
    else:
        try:
            p = safe_path(file_url, must_exist=True)
        except PathNotAllowed as e:
            raise HTTPException(status_code=403, detail=str(e))
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        if not p.is_file():
            raise HTTPException(status_code=400, detail=f"Local path is not a file: {file_url}")
        return p


def _get_out_dir() -> Path:
    out = OUTPUTS_DIR / uuid4().hex
    out.mkdir(parents=True, exist_ok=True)
    return out


@app.post("/document_convert")
def document_convert(req: ConvertReq):
    from_fmt = req.from_format.strip().lower()
    to_fmt = req.to_format.strip().lower()
    if from_fmt not in DOC_FROM:
        raise HTTPException(status_code=400, detail=f"Unsupported document input format: {from_fmt}")
    if to_fmt not in DOC_TO:
        raise HTTPException(status_code=400, detail=f"Unsupported document output format: {to_fmt}")

    inp_path = _fetch_input(req.file_url)
    OUT = _get_out_dir()
    profile_dir = OUT / f"lo_profile_{uuid4().hex}"

    try:
        cmd = [
            "soffice",
            f"-env:UserInstallation=file://{profile_dir}",
            "--headless",
            "--convert-to",
            to_fmt,
            "--outdir",
            str(OUT),
            str(inp_path)
        ]
        res = subprocess.run(cmd, timeout=120, capture_output=True, text=True)
        expected_file = OUT / f"{inp_path.stem}.{to_fmt}"
        if expected_file.exists():
            return {"result": str(expected_file.resolve())}
        candidates = list(OUT.glob(f"*.{to_fmt}"))
        if candidates:
            return {"result": str(candidates[0].resolve())}
        err = res.stderr or res.stdout or "soffice produced no output"
        raise HTTPException(status_code=500, detail=f"soffice conversion failed: {err}")
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)


@app.post("/data_convert")
def data_convert(req: ConvertReq):
    from_fmt = req.from_format.strip().lower()
    to_fmt = req.to_format.strip().lower()
    if from_fmt not in DATA_FROM:
        raise HTTPException(status_code=400, detail=f"Unsupported data input format: {from_fmt}")
    if to_fmt not in DATA_TO:
        raise HTTPException(status_code=400, detail=f"Unsupported data output format: {to_fmt}")

    inp_path = _fetch_input(req.file_url)
    OUT = _get_out_dir()
    out_file = OUT / f"{inp_path.stem}.{to_fmt}"

    try:
        if from_fmt == "json":
            with open(inp_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                records = [raw]
            elif isinstance(raw, list):
                records = [r if isinstance(r, dict) else {"value": r} for r in raw]
            else:
                records = [{"value": raw}]
        elif from_fmt == "csv":
            with open(inp_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                records = list(reader)
        elif from_fmt == "xlsx":
            wb = openpyxl.load_workbook(inp_path, data_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                records = []
            else:
                headers = [str(c) if c is not None else f"col_{i}" for i, c in enumerate(rows[0])]
                records = []
                for r in rows[1:]:
                    row_dict = {headers[i]: r[i] for i in range(min(len(headers), len(r)))}
                    records.append(row_dict)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse input {from_fmt} file: {e}")

    try:
        if to_fmt == "csv":
            fieldnames = []
            for r in records:
                for k in r.keys():
                    if k not in fieldnames:
                        fieldnames.append(k)
            with open(out_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(records)
        elif to_fmt == "json":
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(records, f, indent=2, default=str)
        elif to_fmt == "xlsx":
            wb = openpyxl.Workbook()
            ws = wb.active
            if records:
                fieldnames = []
                for r in records:
                    for k in r.keys():
                        if k not in fieldnames:
                            fieldnames.append(k)
                ws.append(fieldnames)
                for r in records:
                    ws.append([r.get(k) for k in fieldnames])
            wb.save(out_file)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write output {to_fmt} file: {e}")

    return {"result": str(out_file.resolve())}


@app.post("/image_convert")
def image_convert(req: ConvertReq):
    from_fmt = req.from_format.strip().lower()
    to_fmt = req.to_format.strip().lower()
    if from_fmt not in IMAGE_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported image input format: {from_fmt}")
    if to_fmt not in IMAGE_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported image output format: {to_fmt}")

    inp_path = _fetch_input(req.file_url)
    OUT = _get_out_dir()
    out_file = OUT / f"{inp_path.stem}.{to_fmt}"

    try:
        with Image.open(inp_path) as img:
            target_fmt = to_fmt.upper()
            if target_fmt in ("JPG", "JPEG"):
                target_fmt = "JPEG"
                if img.mode != "RGB":
                    img = img.convert("RGB")
            img.save(out_file, format=target_fmt)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image conversion failed: {e}")

    return {"result": str(out_file.resolve())}


@app.post("/audio_convert")
def audio_convert(req: ConvertReq):
    from_fmt = req.from_format.strip().lower()
    to_fmt = req.to_format.strip().lower()
    if from_fmt not in AUDIO_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported audio input format: {from_fmt}")
    if to_fmt not in AUDIO_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported audio output format: {to_fmt}")

    inp_path = _fetch_input(req.file_url)
    OUT = _get_out_dir()
    out_file = OUT / f"{inp_path.stem}.{to_fmt}"

    codec_args = []
    if to_fmt == "mp3":
        codec_args = ["-c:a", "libmp3lame", "-q:a", "4"]
    elif to_fmt == "ogg":
        codec_args = ["-c:a", "libvorbis"]

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(inp_path)] + codec_args + [str(out_file)]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if res.returncode != 0:
        raise HTTPException(status_code=500, detail=f"ffmpeg audio conversion failed: {res.stderr}")
    if not out_file.exists():
        raise HTTPException(status_code=500, detail="ffmpeg produced no output audio file")

    return {"result": str(out_file.resolve())}


@app.post("/video_convert")
def video_convert(req: ConvertReq):
    from_fmt = req.from_format.strip().lower()
    to_fmt = req.to_format.strip().lower()
    if from_fmt not in VIDEO_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported video input format: {from_fmt}")
    if to_fmt not in VIDEO_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported video output format: {to_fmt}")

    inp_path = _fetch_input(req.file_url)
    OUT = _get_out_dir()
    out_file = OUT / f"{inp_path.stem}.{to_fmt}"

    codec_args = []
    if to_fmt == "webm":
        codec_args = ["-c:v", "libvpx-vp9", "-b:v", "1M", "-deadline", "realtime", "-cpu-used", "8", "-c:a", "libopus"]
    elif to_fmt == "gif":
        codec_args = ["-vf", "fps=10,scale=320:-1"]

    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(inp_path)] + codec_args + [str(out_file)]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if res.returncode != 0:
        raise HTTPException(status_code=500, detail=f"ffmpeg video conversion failed: {res.stderr}")
    if not out_file.exists():
        raise HTTPException(status_code=500, detail="ffmpeg produced no output video file")

    return {"result": str(out_file.resolve())}


@app.post("/archive_create")
def archive_create(req: ArchiveReq):
    fmt = req.format.strip().lower()
    if fmt not in ARCHIVE_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported archive format: {fmt}")
    if not req.file_urls:
        raise HTTPException(status_code=400, detail="file_urls list is required")

    fetched_paths = [_fetch_input(u) for u in req.file_urls]
    OUT = _get_out_dir()
    out_file = OUT / f"archive.{fmt}"

    try:
        if fmt == "zip":
            with zipfile.ZipFile(out_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for f in fetched_paths:
                    zf.write(f, arcname=f.name)
        elif fmt in ("tar", "tar.gz"):
            mode = "w:gz" if fmt == "tar.gz" else "w"
            with tarfile.open(out_file, mode) as tf:
                for f in fetched_paths:
                    tf.add(f, arcname=f.name)
        elif fmt == "7z":
            cmd = ["7z", "a", str(out_file)] + [str(f) for f in fetched_paths]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode != 0:
                raise HTTPException(status_code=500, detail=f"7z failed: {res.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Archive creation failed: {e}")

    return {"result": str(out_file.resolve())}


@app.post("/archive_extract")
def archive_extract(req: ArchiveReq):
    fmt = req.format.strip().lower()
    if fmt not in ARCHIVE_FORMATS:
        raise HTTPException(status_code=400, detail=f"Unsupported archive format: {fmt}")
    if not req.file_url:
        raise HTTPException(status_code=400, detail="file_url is required")

    inp_path = _fetch_input(req.file_url)
    OUT = _get_out_dir()
    extracted_dir = OUT / "extracted"
    extracted_dir.mkdir(parents=True, exist_ok=True)

    try:
        if fmt == "zip":
            with zipfile.ZipFile(inp_path, "r") as zf:
                for member in zf.infolist():
                    fname = member.filename
                    p = Path(fname)
                    if fname.startswith("/") or fname.startswith("\\") or p.is_absolute() or ".." in p.parts:
                        raise HTTPException(status_code=400, detail=f"Zip-slip detected: {fname}")
                    target_path = (extracted_dir / fname).resolve()
                    if not target_path.is_relative_to(extracted_dir.resolve()):
                        raise HTTPException(status_code=400, detail=f"Zip-slip detected: {fname}")
                zf.extractall(extracted_dir)
        elif fmt in ("tar", "tar.gz"):
            with tarfile.open(inp_path, "r:*") as tf:
                for member in tf.getmembers():
                    mname = member.name
                    p = Path(mname)
                    if mname.startswith("/") or mname.startswith("\\") or p.is_absolute() or ".." in p.parts:
                        raise HTTPException(status_code=400, detail=f"Tar-slip detected: {mname}")
                    target_path = (extracted_dir / mname).resolve()
                    if not target_path.is_relative_to(extracted_dir.resolve()):
                        raise HTTPException(status_code=400, detail=f"Tar-slip detected: {mname}")
                tf.extractall(extracted_dir)
        elif fmt == "7z":
            cmd = ["7z", "x", f"-o{extracted_dir}", str(inp_path)]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if res.returncode != 0:
                raise HTTPException(status_code=500, detail=f"7z extract failed: {res.stderr}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Archive extraction failed: {e}")

    return {"result": str(extracted_dir.resolve())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8091)
