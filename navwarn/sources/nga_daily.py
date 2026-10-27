"""NGA daily in-force text bulletins for NAVAREA IV and XII.
NOTE: NGA's JSON API froze in May 2024 and these text bulletins showed March 2026 in Oct 2026,
so the staleness check matters here more than anywhere."""
from __future__ import annotations
import re
from ..http import fetch_raw, now_iso
from ..model import Warning
from ..parse import parse_dtg, parse_positions, parse_cancels, parse_expiry, area_extra

NAME = "nga_daily"
URLS = {"navarea-04": "https://msi.nga.mil/apology_objects/DailyMemIV.txt",
        "navarea-12": "https://msi.nga.mil/apology_objects/DailyMemXII.txt"}
CADENCE_DAYS = 8
PARSER_VERSION = 2          # v2: extra.areas

MSG_SPLIT = re.compile(r"\n(?=\d{6}Z [A-Z]{3} \d{2}\s*\n)")
HEAD_RE = re.compile(r"^(\d{6}Z [A-Z]{3} \d{2})\s*\nNAVAREA\s+([IVX]+)\s+(\d+)/(\d{2})\(([^)]*)\)\.?\s*\n", re.S)


def parse(text: str, series: str, url: str, raw_path: str, fetched_at: str) -> list[Warning]:
    out = []
    text = text.replace("\r", "")
    for chunk in MSG_SPLIT.split(text):
        m = HEAD_RE.match(chunk.strip() + "\n")
        if not m:
            continue
        dtg, _area, num, yy, subregion = m.groups()
        body = chunk.strip()[m.end():].strip()
        year = 2000 + int(yy)
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        out.append(Warning(
            id=f"{series}/{year}/{int(num)}", series=series, number=str(int(num)), year=year,
            issued_at=parse_dtg(dtg), subject=" ".join(lines[:2])[:200], text=body,
            positions=parse_positions(body), cancels=parse_cancels(body), expires_at=parse_expiry(body),
            source={"name": NAME, "url": url, "raw_path": raw_path, "fetched_at": fetched_at,
                    "parser_version": PARSER_VERSION},
            extra={"subregion": subregion, **area_extra(body)}))
    return out


def run() -> list[Warning]:
    out = []
    for series, url in URLS.items():
        data, path = fetch_raw(NAME, url.rsplit("/", 1)[-1], url)
        out += parse(data.decode("utf-8", "replace"), series, url, path, now_iso())
    return out
