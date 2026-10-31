"""Kystverket (Norwegian Coastal Administration): NAVAREA XIX in force. Simple ASP.NET report page."""
from __future__ import annotations
import re
from ..http import fetch_raw, now_iso
from ..model import Warning
from ..parse import parse_dtg, parse_positions, parse_cancels, parse_expiry, strip_html, area_extra

NAME = "kystverket"
URL = "https://kyvreports.kystverket.no/NavcoReport/navareaxixvarsler.aspx"
CADENCE_DAYS = 8
PARSER_VERSION = 2          # v2: extra.areas
SERIES = "navarea-19"

BLOCK_RE = re.compile(r"Number:\s*(\d+)/(\d{2})\s*Date:\s*(.+?)\s*Warning:\s*(.*?)(?=\nNumber:|\Z)", re.S)


def parse(html: str, raw_path: str, fetched_at: str) -> list[Warning]:
    text = strip_html(html)
    text = "\n".join(l.strip() for l in text.splitlines() if l.strip())
    out = []
    for num, yy, dtg, body in BLOCK_RE.findall(text):
        year = 2000 + int(yy)
        body = body.strip()
        lines = [l for l in body.splitlines() if l.strip()]
        subject = lines[1] if len(lines) > 1 else (lines[0] if lines else "")
        out.append(Warning(
            id=f"{SERIES}/{year}/{int(num)}", series=SERIES, number=str(int(num)), year=year,
            issued_at=parse_dtg(dtg), subject=subject[:200], text=body,
            positions=parse_positions(body), cancels=parse_cancels(body), expires_at=parse_expiry(body),
            source={"name": NAME, "url": URL, "raw_path": raw_path, "fetched_at": fetched_at,
                    "parser_version": PARSER_VERSION},
            extra=area_extra(body)))
    return out


def run() -> list[Warning]:
    data, path = fetch_raw(NAME, "navareaxixvarsler.html", URL)
    return parse(data.decode("utf-8", "replace"), path, now_iso())
