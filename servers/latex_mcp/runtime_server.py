import os
import re
import sys
import uuid
import subprocess
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.paths import safe_path, output_dir, PathNotAllowed

app = FastAPI()
OUTPUTS_DIR = output_dir(Path(__file__).resolve().parent)


class LatexRequest(BaseModel):
    latex_string: str


@app.post("/compile")
def compile_latex(req: LatexRequest):
    # Security check: if latex_string is a file path or includes files, validate via safe_path
    latex_str = req.latex_string or ""
    try:
        if latex_str.strip().startswith("/"):
            safe_path(latex_str.strip())
        for m in re.finditer(r'\\(?:input|include|includegraphics)\s*\{([^}]+)\}', latex_str):
            safe_path(m.group(1))
    except PathNotAllowed as e:
        raise HTTPException(status_code=403, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    run_dir = OUTPUTS_DIR / str(uuid.uuid4())
    run_dir.mkdir(parents=True, exist_ok=True)
    tex_path = run_dir / "document.tex"

    with open(tex_path, "w") as f:
        f.write(req.latex_string)

    try:
        subprocess.run(
            ["pdflatex", "-interaction=nonstopmode", "-output-directory", str(run_dir), str(tex_path)],
            check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=f"pdflatex failed: {e.stderr.decode('utf-8', errors='replace')} {e.stdout.decode('utf-8', errors='replace')}"
        )
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="pdflatex command not found")

    pdf_path = run_dir / "document.pdf"
    if not pdf_path.exists():
        raise HTTPException(status_code=500, detail="PDF was not generated")

    return {"pdf_path": str(pdf_path.resolve())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8087)
