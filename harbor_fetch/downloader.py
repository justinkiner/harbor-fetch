"""Stream file downloads from a URL to disk, with MD5 verification helpers."""

import hashlib
from pathlib import Path

import requests

_CHUNK_SIZE = 64 * 1024  # 64 KB


def md5_of_file(path: Path) -> str:
    """Return the lowercase hex MD5 digest of an existing file."""
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def download_file(url: str, dest: Path) -> None:
    """Stream-download *url* to *dest*, creating parent directories as needed."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=120) as resp:
        resp.raise_for_status()
        with dest.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
