"""AMSA (JRCC Australia): NAVAREA X + AUSCOAST coastal warnings, full text, one page.
The MSI publication page lists every warning in force as SECURITE ... NNNN blocks.
Drill-rig and special-vessel tables (Parts 4-5) stay in the raw file; not normalized yet."""
from __future__ import annotations
import re
from ..http import fetch_raw, now_iso
from ..model import Warning
from ..parse import parse_dtg, parse_positions, parse_cancels, parse_expiry, strip_html, area_extra

NAME = "amsa"
URL = "https://www.operations.amsa.gov.au/AMSA.Web.MSIPublication/Home"
CADENCE_DAYS = 8          # in-force summary is reissued weekly on Thursdays
PARSER_VERSION = 2          # v2: extra.areas

SECTION_RE = re.compile(r"<p>\s*(Part \d+\.[^<]*|AUSCOAST coastal warning - area ([A-Z])[^<]*)</p>", re.I)
BLOCK_RE = re.compile(r"SECURITE(.*?)NNNN", re.S)
HEAD_RE = re.compile(r"^FM\s+[A-Z ]+?\s+(\d{6}Z\s+[A-Z]{3}\s+\d{2})\s*\n(NAVAREA X|AUSCOAST)(?:\s+WARNING)?\s+(\d+)/(\d{2})\s*\n", re.I)


def parse(html: str, raw_path: str, fetched_at: str) -> list[Warning]:
    # walk the page in order so each block knows which AUSCOAST area section it sits in
    marks = [(m.start(), m.group(2)) for m in SECTION_RE.finditer(html)]
    out: dict[str, Warning] = {}
    for m in BLOCK_RE.finditer(html):
        area = next((a for pos, a in reversed(marks) if pos < m.start()), None)
        text = strip_html(m.group(1)).strip()
        text = "\n".join(l.strip() for l in text.splitlines() if l.strip())
        h = HEAD_RE.match(text + "\n")
        if not h:
            continue
        dtg, kind, num, yy = h.groups()
        series = "navarea-10" if kind.upper() == "NAVAREA X" else "auscoast"
        year = 2000 + int(yy)
        body = text[h.end():].strip()
        wid = f"{series}/{year}/{int(num)}"
        if wid in out:                      # one AUSCOAST warning is repeated under each area it covers
            if area and area not in out[wid].extra.setdefault("auscoast_areas", []):
                out[wid].extra["auscoast_areas"].append(area)
            continue
        out[wid] = (Warning(
            id=wid, series=series, number=str(int(num)), year=year,
            issued_at=parse_dtg(dtg), subject=body.splitlines()[0][:200] if body else "", text=body,
            positions=parse_positions(body), cancels=parse_cancels(body), expires_at=parse_expiry(body),
            source={"name": NAME, "url": URL, "raw_path": raw_path, "fetched_at": fetched_at,
                    "parser_version": PARSER_VERSION},
            extra={**({"auscoast_areas": [area]} if area else {}), **area_extra(body)}))
    return list(out.values())


def run() -> list[Warning]:
    data, path = fetch_raw(NAME, "MSIPublication.html", URL)
    return parse(data.decode("utf-8", "replace"), path, now_iso())
