import os
import sys
import subprocess
import uuid
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.paths import safe_path, output_dir, PathNotAllowed

app = FastAPI()
OUTPUTS_DIR = output_dir(Path(__file__).resolve().parent)


class TrimRequest(BaseModel):
    video_path: str
    start_sec: float
    end_sec: float


@app.post("/trim")
async def trim(req: TrimRequest):
    if req.start_sec < 0 or req.end_sec <= req.start_sec:
        raise HTTPException(status_code=400, detail="Invalid start/end: start >= 0 and end > start required")

    try:
        resolved = safe_path(req.video_path, must_exist=True)
    except PathNotAllowed as e:
        raise HTTPException(status_code=403, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    out_path = OUTPUTS_DIR / f"trimmed_{uuid.uuid4().hex[:8]}.mp4"
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel", "error",
        "-ss", str(req.start_sec),
        "-i", str(resolved),
        "-t", str(req.end_sec - req.start_sec),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-c:a", "aac",
        str(out_path)
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if proc.returncode != 0:
        raise HTTPException(status_code=500, detail=proc.stderr or "ffmpeg failed")

    return {"output_path": str(out_path.resolve())}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8119)
