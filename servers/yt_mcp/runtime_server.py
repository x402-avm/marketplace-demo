import os
import sys
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common.paths import safe_path, output_dir, PathNotAllowed

app = FastAPI()
OUTPUTS_DIR = output_dir(Path(__file__).resolve().parent)


class DownloadRequest(BaseModel):
    url: str
    format: str = "video"  # "video" or "audio"


class TranscriptRequest(BaseModel):
    video_id: str


@app.post("/download")
def download_video(req: DownloadRequest):
    url = req.url
    if not (url.startswith("http://") or url.startswith("https://")):
        path_to_check = url[7:] if url.startswith("file://") else url
        try:
            safe_path(path_to_check)
        except PathNotAllowed as e:
            raise HTTPException(status_code=403, detail=str(e))
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

    ydl_opts = {
        'outtmpl': str(OUTPUTS_DIR / '%(title)s.%(ext)s'),
        'format': 'bestvideo+bestaudio/best' if req.format == 'video' else 'bestaudio/best',
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web']
            }
        },
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(req.url, download=True)
            filename = ydl.prepare_filename(info)
            if not os.path.exists(filename):
                stem = Path(filename).stem
                for cand in OUTPUTS_DIR.glob(f"{stem}.*"):
                    if cand.is_file():
                        filename = str(cand)
                        break
            return {"status": "success", "title": info.get("title", ""), "file": filename}
    except HTTPException:
        raise
    except Exception as e:
        err_msg = str(e)
        if any(term in err_msg for term in ["HTTP Error 403", "Sign in to confirm", "Too Many Requests", "refused", "bot"]):
            raise HTTPException(status_code=500, detail=f"YouTube refused the download: {err_msg}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transcript")
def get_transcript(req: TranscriptRequest):
    if req.video_id.startswith("/"):
        try:
            safe_path(req.video_id)
        except PathNotAllowed as e:
            raise HTTPException(status_code=403, detail=str(e))
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

    try:
        transcript = YouTubeTranscriptApi().fetch(req.video_id).to_raw_data()
        return {"status": "success", "transcript": transcript}
    except HTTPException:
        raise
    except Exception as e:
        return {"status": "transcript_unavailable", "video_id": req.video_id, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8075)
