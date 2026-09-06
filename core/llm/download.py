# core/llm/download.py
"""Download and inspect GGUF weights. Never fetches executables."""

from __future__ import annotations

import hashlib
import os
import struct
import urllib.request
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import urlparse

from core.llm.catalog import ModelSpec, models_dir

_ALLOWED_HOSTS = (
    "huggingface.co",
    "cdn-lfs.huggingface.co",
    "hf.co",
    "github.com",
    "objects.githubusercontent.com",
)


class DownloadError(RuntimeError):
    pass


def is_gguf(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.read(4) == b"GGUF"
    except OSError:
        return False


def gguf_info(path: Path) -> dict:
    with path.open("rb") as f:
        magic = f.read(4)
        if magic != b"GGUF":
            raise DownloadError("Not a GGUF file")
        version = struct.unpack("<I", f.read(4))[0]
        n_tensors = struct.unpack("<Q", f.read(8))[0]
        n_kv = struct.unpack("<Q", f.read(8))[0]
        architecture = ""
        name = ""
        for _ in range(min(n_kv, 64)):
            key = _read_string(f)
            if key is None:
                break
            type_raw = f.read(4)
            if len(type_raw) < 4:
                break
            vtype = struct.unpack("<I", type_raw)[0]
            if vtype == 8:
                value = _read_string(f) or ""
                if key == "general.architecture":
                    architecture = value
                if key == "general.name":
                    name = value
            else:
                _skip_value(f, vtype)
        return {
            "architecture": architecture,
            "name": name,
            "version": version,
            "tensor_count": n_tensors,
        }


def download_model(
    spec: ModelSpec,
    *,
    dest_dir: Optional[Path] = None,
    opener: Optional[Callable] = None,
    progress: Optional[Callable[[int, Optional[int]], None]] = None,
) -> Path:
    dest = models_dir(dest_dir) / spec.filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and is_gguf(dest):
        return dest

    _validate_url(spec.download_url)
    tmp = dest.with_suffix(dest.suffix + ".download")
    req = urllib.request.Request(
        spec.download_url,
        headers={"User-Agent": "Agent-Core/0.2.0"},
        method="GET",
    )
    open_fn = opener or urllib.request.urlopen
    with open_fn(req, timeout=600) as resp, tmp.open("wb") as out:
        total = resp.headers.get("Content-Length")
        expected = int(total) if total and total.isdigit() else None
        copied = 0
        while True:
            chunk = resp.read(1024 * 256)
            if not chunk:
                break
            out.write(chunk)
            copied += len(chunk)
            if progress:
                progress(copied, expected)
    size = tmp.stat().st_size
    if spec.sha256:
        digest = hashlib.sha256(tmp.read_bytes()).hexdigest()
        if digest != spec.sha256.lower():
            tmp.unlink(missing_ok=True)
            raise DownloadError("SHA-256 mismatch")
    if spec.approximate_bytes and size > 64 and size < spec.approximate_bytes / 4:
        tmp.unlink(missing_ok=True)
        raise DownloadError("Downloaded file is unexpectedly small")
    if not is_gguf(tmp):
        tmp.unlink(missing_ok=True)
        raise DownloadError("Not a GGUF weight file")
    os.replace(tmp, dest)
    return dest


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme == "file":
        return
    if parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost"):
        return
    if parsed.scheme != "https":
        raise DownloadError("Downloads must use HTTPS")
    host = (parsed.hostname or "").lower()
    if not any(host == h or host.endswith("." + h) for h in _ALLOWED_HOSTS):
        raise DownloadError(f"Host not in allow-list: {host}")


def _read_string(f) -> Optional[str]:
    raw = f.read(8)
    if len(raw) < 8:
        return None
    length = struct.unpack("<Q", raw)[0]
    if length > 4096:
        return None
    data = f.read(length)
    if len(data) < length:
        return None
    return data.decode("utf-8", errors="replace")


def _skip_value(f, vtype: int) -> None:
    if vtype in (0, 1, 7):
        f.read(1)
    elif vtype in (2, 3):
        f.read(2)
    elif vtype in (4, 5, 6):
        f.read(4)
    elif vtype == 8:
        _read_string(f)
    elif vtype in (10, 11, 12):
        f.read(8)
    elif vtype == 9:
        t = f.read(4)
        n = f.read(8)
        if len(t) < 4 or len(n) < 8:
            return
        elem = struct.unpack("<I", t)[0]
        count = min(struct.unpack("<Q", n)[0], 256)
        if elem == 8:
            for _ in range(count):
                _read_string(f)
        else:
            width = {0: 1, 1: 1, 7: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4}.get(elem, 8)
            f.read(int(count) * width)
