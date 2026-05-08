"""Picsum random-image download + image pipeline integration for demo seeding."""
from __future__ import annotations

import warnings
from typing import Final

import httpx

PICSUM_BASE: Final = "https://picsum.photos"
DEFAULT_W: Final = 1280
DEFAULT_H: Final = 720
TIMEOUT_S: Final = 5.0
MAX_FAILURES: Final = 10


class SeedAbort(RuntimeError):
    """Raised when accumulated Picsum failures exceed MAX_FAILURES."""


def _fetch_picsum(seed: int, *, w: int = DEFAULT_W, h: int = DEFAULT_H) -> bytes | None:
    """Download one image. Returns JPEG bytes, or None on any failure."""
    url = f"{PICSUM_BASE}/{w}/{h}?random={seed}"
    try:
        resp = httpx.get(url, timeout=TIMEOUT_S, follow_redirects=True)
        resp.raise_for_status()
        return resp.content
    except httpx.HTTPError as e:
        warnings.warn(f"Picsum fetch failed (seed={seed}): {e}", stacklevel=2)
        return None
