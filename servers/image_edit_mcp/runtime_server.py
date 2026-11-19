import os
import sys
import uuid
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.paths import safe_path, output_dir, PathNotAllowed

app = FastAPI()
OUTPUTS_DIR = output_dir(Path(__file__).resolve().parent)


class CompressRequest(BaseModel):
    image_path: str
    quality: int = 60


class ResizeRequest(BaseModel):
    image_path: str
    width: int
    height: int


@app.post("/compress")
async def compress(req: CompressRequest):
    try:
        resolved = safe_path(req.image_path, must_exist=True)
    except PathNotAllowed as e:
        raise HTTPException(status_code=403, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        img = Image.open(resolved)
        out_path = OUTPUTS_DIR / f"compressed_{uuid.uuid4().hex[:8]}.jpg"
        img.convert("RGB").save(str(out_path), quality=req.quality)
        return {"output_path": str(out_path.resolve())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/resize")
async def resize(req: ResizeRequest):
    try:
        resolved = safe_path(req.image_path, must_exist=True)
    except PathNotAllowed as e:
        raise HTTPException(status_code=403, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    try:
        img = Image.open(resolved)
        img_resized = img.resize((req.width, req.height))
        out_path = OUTPUTS_DIR / f"resized_{uuid.uuid4().hex[:8]}.png"
        img_resized.save(str(out_path))
        return {"output_path": str(out_path.resolve())}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8114)
