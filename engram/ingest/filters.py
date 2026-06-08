"""Decide which repo files to index. Conservative: skip anything binary,
oversized, secret-bearing, vendored, or a lockfile."""

import os

MAX_BYTES = 1_000_000  # 1 MB

# v1: conservative — a repo with hand-written source in build/dist/target/ is also skipped.
_SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".venv",
              "__pycache__", ".next", ".cache", "target"}
_SKIP_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml",
               "poetry.lock", "composer.lock", "Cargo.lock"}
_BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
               ".woff", ".woff2", ".ttf", ".eot", ".zip", ".gz", ".tar",
               ".mp4", ".mov", ".mp3", ".wasm", ".so", ".dylib", ".o", ".pyc"}


def should_index(path: str, size_bytes: int, sample_bytes: bytes) -> bool:
    """`sample_bytes` is the first chunk of the file (for binary detection)."""
    if size_bytes > MAX_BYTES:
        return False
    parts = path.replace("\\", "/").split("/")
    if any(p in _SKIP_DIRS for p in parts):
        return False
    name = parts[-1]
    if name in _SKIP_NAMES:
        return False
    if name == ".env" or name.startswith(".env."):
        return False
    if os.path.splitext(name)[1].lower() in _BINARY_EXT:
        return False
    if b"\x00" in sample_bytes:  # null byte -> binary
        return False
    return True
