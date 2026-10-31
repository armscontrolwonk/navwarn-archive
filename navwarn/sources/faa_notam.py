"""Aviation NOTAMs from FAA NOTAM Search exports (worldwide, searched by flight information region).
The FAA search site blocks scripts, so this source is fed by hand:
  1. Search https://notams.aim.faa.gov/notamSearch/nsapp.html#/ for the FIR codes you want
     (lists in inbox/faa_notam/README.md).
  2. Select all, download as Excel.
  3. Put the .xlsx (or a .csv saved from it) in inbox/faa_notam/ and commit.
The next run parses it and moves it to raw/faa_notam/. Records stay active until their C) time."""
from __future__ import annotations
import csv, re, zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from .. import inbox
from ..http import now_iso
from ..model import Warning
from ..notam import parse_notam, _faa_date

NAME = "faa_notam"
CADENCE_DAYS = None          # hand-fed: never flagged stale
WITHDRAW_MISSING = False     # an export only covers the FIRs searched; absence means nothing
PARSER_VERSION = 4          # v2: extra.starts_at; v3: shared parser, kind, schedule, attributed_to; v4: extra.areas

M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def _col(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]+", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n - 1


def read_xlsx(path: str) -> list[list[str]]:
    """Minimal .xlsx reader (first sheet, values as text) so no third-party package is needed."""
    with zipfile.ZipFile(path) as z:
        shared = []
        if "xl/sharedStrings.xml" in z.namelist():
            for si in ET.fromstring(z.read("xl/sharedStrings.xml")).iter(M + "si"):
                shared.append("".join(t.text or "" for t in si.iter(M + "t")))
        sheet = sorted(n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n))[0]
        rows = []
        for row in ET.fromstring(z.read(sheet)).iter(M + "row"):
            cells = {}
            for c in row.iter(M + "c"):
                v, t = c.find(M + "v"), c.get("t")
                if t == "s" and v is not None:
                    val = shared[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(M + "t"))
                else:
                    val = v.text if v is not None else ""
                cells[_col(c.get("r"))] = val
            rows.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])
        return rows


def read_rows(path: str) -> list[list[str]]:
    if path.lower().endswith(".xlsx"):
        return read_xlsx(path)
    csv.field_size_limit(10 ** 8)
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
        return list(csv.reader(f))


def parse_file(path: str, raw_path: str) -> list[Warning]:
    rows = read_rows(path)
    hdr = next((i for i, r in enumerate(rows) if len(r) >= 7 and r[0].strip() == "Location" and "NOTAM" in r[1]), None)
    if hdr is None:
        return []
    fetched_at = now_iso()
    m = re.search(r"Query ran at UTC:\s*(\d{2})_(\d{2})_(\d{4})_(\d{2})(\d{2})(\d{2})", rows[0][0] if rows and rows[0] else "")
    if m:
        mo, d, y, hh, mi, ss = m.groups()
        fetched_at = f"{y}-{mo}-{d}T{hh}:{mi}:{ss}Z"
    out = {}
    for r in rows[hdr + 1:]:
        if len(r) < 7 or not r[0].strip():
            continue
        w = parse_notam(r[0], r[1], _faa_date(r[3]), r[6],
                        {"name": NAME, "url": "https://notams.aim.faa.gov/notamSearch/", "raw_path": raw_path,
                         "fetched_at": fetched_at, "parser_version": PARSER_VERSION})
        if w:
            out[w.id] = w
    return list(out.values())


def run() -> list[Warning]:
    return inbox.process(NAME, parse_file)
