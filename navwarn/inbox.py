"""Hand-fed sources. Drop files in inbox/<source>/; each run parses them and moves every file that
produced records to raw/<source>/<UTC timestamp>-<name>, so the original is kept verbatim.
Files that yield nothing stay in the inbox and are reported, so a wrong file is never lost silently."""
from __future__ import annotations
import glob, os, shutil
from datetime import datetime, timezone

SKIP = {".gitkeep", "README.md"}


def pending(source: str) -> list[str]:
    return sorted(p for p in glob.glob(os.path.join("inbox", source, "*"))
                  if os.path.isfile(p) and os.path.basename(p) not in SKIP)


def archive(source: str, path: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
    dest_dir = os.path.join("raw", source)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, f"{stamp}-{os.path.basename(path)}")
    shutil.move(path, dest)
    return dest


def process(source: str, parse_file) -> list:
    """parse_file(path, raw_path) -> list[Warning]. Returns all records from all usable files."""
    out, rejected = [], []
    for path in pending(source):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%MZ")
        raw_path = os.path.join("raw", source, f"{stamp}-{os.path.basename(path)}")
        recs = parse_file(path, raw_path)
        if recs:
            archive(source, path)
            out += recs
        else:
            rejected.append(os.path.basename(path))
    if rejected:
        print(f"[{source}] left in inbox, no records found: {', '.join(rejected)}")
    return out
