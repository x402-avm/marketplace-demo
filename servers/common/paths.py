"""File-path allow-list and output directory utilities for MCP servers."""

import os
from pathlib import Path

SERVERS = Path(__file__).resolve().parents[1]


class PathNotAllowed(ValueError):
    """Raised when a path is outside the allowed directories."""
    pass


def allowed_roots() -> list[Path]:
    """Return all allowed base directory roots."""
    roots: list[Path] = []

    fixtures = (SERVERS / "tests" / "fixtures").resolve()
    if fixtures.exists():
        roots.append(fixtures)

    outputs = (SERVERS / "tests" / "outputs").resolve()
    if outputs.exists():
        roots.append(outputs)

    # Every SERVERS/<dir>/outputs that exists
    if SERVERS.is_dir():
        for item in SERVERS.iterdir():
            if item.is_dir():
                domain_outputs = item / "outputs"
                if domain_outputs.is_dir():
                    roots.append(domain_outputs.resolve())

    # Extra roots from MCP_FILE_ROOTS environment variable
    extra_roots = os.environ.get("MCP_FILE_ROOTS", "")
    if extra_roots:
        for p in extra_roots.split(os.pathsep):
            clean = p.strip()
            if clean:
                roots.append(Path(clean).expanduser().resolve())

    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for r in roots:
        if r not in seen:
            seen.add(r)
            deduped.append(r)
    return deduped


def safe_path(p: str, must_exist: bool = True) -> Path:
    """Validate that path p is within one of the allowed roots."""
    if not p or not str(p).strip():
        raise PathNotAllowed(
            f"path not allowed: {p!r} (allowed roots: tests/fixtures, tests/outputs, <domain>/outputs, MCP_FILE_ROOTS)"
        )

    r = Path(p).expanduser().resolve()
    roots = allowed_roots()

    allowed = any(r == root or root in r.parents for root in roots)
    if not allowed:
        raise PathNotAllowed(
            f"path not allowed: {p} (allowed roots: tests/fixtures, tests/outputs, <domain>/outputs, MCP_FILE_ROOTS)"
        )

    if must_exist and not r.exists():
        raise FileNotFoundError(f"file not found: {p}")

    return r


def output_dir(domain_dir) -> Path:
    """Ensure <domain>/outputs directory exists and return its resolved Path."""
    out = Path(domain_dir).resolve() / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    return out.resolve()
