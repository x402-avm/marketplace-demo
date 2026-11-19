import os
import sys
from pathlib import Path


import uvicorn
from app.config import SERVER_HOST, SERVER_PORT
from app.main import app

# Ensure port is strictly in 10000-10100
if not (10000 <= SERVER_PORT <= 10100):
    raise ValueError(f"Port {SERVER_PORT} is outside required range [10000, 10100].")

if __name__ == "__main__":
    uvicorn.run(
        "runtime_server:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=False,
        log_level="info"
    )
