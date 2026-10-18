"""Polite fetching: honest user agent, timeouts, conditional GET, raw bytes saved verbatim."""
from __future__ import annotations
import json, os, time, urllib.request, urllib.error
from datetime import datetime, timezone

UA = os.environ.get("NAVWARN_UA", "navwarn-archive/0.1 (+https://github.com/; archive bot, low cadence)")
RAW_DIR = os.environ.get("NAVWARN_RAW", "raw")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url: str, timeout: int = 60, retries: int = 2) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    last = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"fetch failed {url}: {last}")


def save_raw(source: str, name: str, data: bytes) -> str:
    """Overwrite one raw file per source/name. Git history is the changelog."""
    d = os.path.join(RAW_DIR, source)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name)
    with open(path, "wb") as f:
        f.write(data)
    return path


def fetch_raw(source: str, name: str, url: str, **kw) -> tuple[bytes, str]:
    data = fetch(url, **kw)
    return data, save_raw(source, name, data)
