import fastapi
from kokoro_onnx import Kokoro
import uvicorn
from pydantic import BaseModel
import gc
import sys

app = fastapi.FastAPI(title="Kokoro Runtime Server")
kokoro = None

class TTSRequest(BaseModel):
    text: str
    voice: str = "af_heart"
    speed: float = 1.0

@app.on_event("startup")
def load_model():
    global kokoro
    import os
    model_file = "kokoro-v1.0.onnx"
    voices_file = "voices-v1.0.bin"
    if not os.path.exists(model_file) or not os.path.exists(voices_file):
        print(
            f"ERROR: Kokoro TTS model weights not found ({model_file} and/or {voices_file}). "
            "Please run './download_models.sh' in servers/tts/ to download the model files.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        kokoro = Kokoro(model_file, voices_file)
        print("Model loaded successfully.")
    except Exception as e:
        print(f"Failed to load model: {e}", file=sys.stderr)
        sys.exit(1)

@app.post("/tts")
def tts(request: TTSRequest):
    text = request.text
    if len(text) > 5000:
        return fastapi.Response(content="Text exceeds strict 5000 char limit", status_code=400)
    
    if len(text) > 1000:
        return fastapi.Response(content="Text exceeds 1000 char limit per request", status_code=400)

    try:
        samples, sample_rate = kokoro.create(text, voice=request.voice, speed=request.speed, lang="en-us")
        
        # Memory management / context deletion
        del text
        del request
        gc.collect()

        import soundfile as sf
        import io
        
        buf = io.BytesIO()
        sf.write(buf, samples, sample_rate, format='WAV')
        buf.seek(0)
        
        # Memory management / context deletion
        del samples
        gc.collect()

        return fastapi.Response(content=buf.read(), media_type="audio/wav")
    except Exception as e:
        return fastapi.Response(content=f"Error generating audio: {str(e)}", status_code=500)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8050)
