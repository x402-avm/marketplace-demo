"""File serving and upload handling with strict path isolation."""

import os
import uuid
from pathlib import Path
from typing import List
from fastapi import UploadFile, HTTPException
from fastapi.responses import FileResponse

from app.config import ALGO_ROOT

SERVERS_DIR = ALGO_ROOT / "servers"
TESTS_OUTPUTS_DIR = SERVERS_DIR / "tests" / "outputs"
UPLOADS_DIR = TESTS_OUTPUTS_DIR / "uploads"
MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25 MB


def get_allowed_roots() -> List[str]:
    roots = []
    real_tests_outputs = os.path.realpath(str(TESTS_OUTPUTS_DIR))
    roots.append(real_tests_outputs)

    if SERVERS_DIR.is_dir():
        for item in SERVERS_DIR.iterdir():
            if item.is_dir():
                domain_outputs = item / "outputs"
                roots.append(os.path.realpath(str(domain_outputs)))

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for r in roots:
        if r not in seen:
            seen.add(r)
            deduped.append(r)
    return deduped


def validate_path(path_str: str, must_exist: bool = True) -> str:
    """
    Validate that path resolves inside servers/*/outputs/ or servers/tests/outputs/.
    Follows and checks symlinks via os.path.realpath.
    Rejects symlink escapes, traversal (../), and paths outside allowed roots with 403.
    """
    if not path_str or not str(path_str).strip():
        raise HTTPException(status_code=403, detail="path not allowed")

    if "\x00" in path_str:
        raise HTTPException(status_code=400, detail="invalid path")

    real_path = os.path.realpath(os.path.expanduser(path_str.strip()))
    roots = get_allowed_roots()

    allowed = any(
        real_path == root or real_path.startswith(root + os.sep)
        for root in roots
    )

    if not allowed:
        raise HTTPException(status_code=403, detail="path not allowed")

    if must_exist and not os.path.isfile(real_path):
        raise HTTPException(status_code=404, detail="file not found")

    return real_path


async def save_uploaded_file(file: UploadFile) -> str:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    clean_name = Path(file.filename or "upload.bin").name
    target_name = f"{uuid.uuid4().hex[:12]}_{clean_name}"
    target_path = UPLOADS_DIR / target_name

    total_bytes = 0
    with open(target_path, "wb") as out_f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            total_bytes += len(chunk)
            if total_bytes > MAX_UPLOAD_SIZE:
                target_path.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="file too large, max 25 MB")
            out_f.write(chunk)

    if total_bytes == 0:
        target_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="empty file")

    return str(target_path.resolve())


def serve_file(path_str: str) -> FileResponse:
    real_path = validate_path(path_str, must_exist=True)
    return FileResponse(real_path)
