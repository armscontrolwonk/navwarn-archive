"""UKHO Radio Navigational Warnings: NAVAREA I + UK coastal (WZ). Server-rendered HTML table."""
from __future__ import annotations
import re
from ..http import fetch_raw, now_iso
from ..model import Warning
from ..parse import parse_dtg, parse_positions, parse_cancels, parse_expiry, navarea_series, strip_html, area_extra

NAME = "ukho"
URL = "https://msi.admiralty.co.uk/RadioNavigationalWarnings"
CADENCE_DAYS = 8          # weekly in-force bulletin; stale if nothing newer than this
PARSER_VERSION = 2          # v2: extra.areas

ROW_RE = re.compile(
    r'<h2 id="Details_Reference_\d+"[^>]*>\s*(.*?)\s*</h2>\s*'
    r'<h3 id="Details_DateTimeGroupRnwFormat_\d+"[^>]*>\s*(.*?)\s*</h3>\s*'
    r'<pre id="Details_Description_\d+"[^>]*>(.*?)</pre>', re.S)
REF_RE = re.compile(r"^(NAVAREA\s+([IVX]+)|WZ)\s+(\d+)/(\d{2})$", re.I)


def parse(html: str, raw_path: str, fetched_at: str) -> list[Warning]:
    out = []
    for ref, dtg, body in ROW_RE.findall(html):
        ref = strip_html(ref).strip()
        m = REF_RE.match(ref)
        if not m:
            continue
        _, area, num, yy = m.groups()
        series = navarea_series(area) if area else "uk-wz"
        year = 2000 + int(yy)
        text = strip_html(body).strip()
        out.append(Warning(
            id=f"{series}/{year}/{int(num)}", series=series, number=str(int(num)), year=year,
            issued_at=parse_dtg(strip_html(dtg)), subject=text.splitlines()[0][:200] if text else "",
            text=text, positions=parse_positions(text), cancels=parse_cancels(text),
            expires_at=parse_expiry(text),
            source={"name": NAME, "url": URL, "raw_path": raw_path, "fetched_at": fetched_at,
                    "parser_version": PARSER_VERSION},
            extra=area_extra(text)))
    return out


def run() -> list[Warning]:
    data, path = fetch_raw(NAME, "RadioNavigationalWarnings.html", URL)
    return parse(data.decode("utf-8", "replace"), path, now_iso())
