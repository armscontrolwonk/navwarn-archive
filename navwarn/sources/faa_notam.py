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

NAME = "faa_notam"
CADENCE_DAYS = None          # hand-fed: never flagged stale
WITHDRAW_MISSING = False     # an export only covers the FIRs searched; absence means nothing
PARSER_VERSION = 2          # v2: extra.starts_at from B)

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


HEAD_RE = re.compile(r"^\s*([A-Z]\d{4}/\d{2})\s+NOTAM([NRC])(?:\s+([A-Z]\d{4}/\d{2}))?")
Q_RE = re.compile(r"Q\)\s*([A-Z]{4})/(Q[A-Z]{2,4})/([A-Z ]*)/([A-Z ]*)/([A-Z ]*)/(\d{3})/(\d{3})/"
                  r"(\d{2})(\d{2})([NS])(\d{3})(\d{2})([EW])(\d{3})?")
B_RE = re.compile(r"B\)\s*(\d{10})")
C_RE = re.compile(r"C\)\s*(\d{10}|PERM)")
E_RE = re.compile(r"E\)\s*(.*?)(?=\n?\s*[FG]\)\s|\Z)", re.S)
FG_RE = re.compile(r"\b([FG])\)\s*([^\n]+?)(?=\s+[FG]\)|\s*$)", re.M)

# 461624N 0233528W | 5848N03016E | 412155.5N 0473153.2E
NPOS_RE = re.compile(r"(?<!\d)(\d{2})(\d{2})(\d{2}(?:\.\d+)?)?([NS])\s*(\d{3})(\d{2})(\d{2}(?:\.\d+)?)?([EW])(?!\w)")
CIRCLE_RE = re.compile(r"(?:CIRCLE\s+)?RADIUS\s*(?:OF\s*)?(\d+(?:\.\d+)?)\s*(KM|NM)\s*(?:OF\s+)?(?:CENTRE|CENTER|CENTRED|CENTERED)?\s*(?:AT\s*)?"
                       r"(\d{6}(?:\.\d+)?[NS])\s*(\d{7}(?:\.\d+)?[EW])", re.I)


def _yymmddhhmm(s: str) -> str | None:
    try:
        return datetime.strptime(s, "%y%m%d%H%M").replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _faa_date(s: str) -> str | None:     # "12/02/2021 0828"
    try:
        return datetime.strptime(s.strip(), "%m/%d/%Y %H%M").replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


def _dd(d, m, s, hemi) -> float:
    v = int(d) + int(m) / 60 + (float(s) / 3600 if s else 0)
    return -v if hemi in "SW" else v


def notam_positions(text: str) -> list[list[float]]:
    out = []
    for la_d, la_m, la_s, ns, lo_d, lo_m, lo_s, ew in NPOS_RE.findall(text or ""):
        lat, lon = _dd(la_d, la_m, la_s, ns), _dd(lo_d, lo_m, lo_s, ew)
        if abs(lat) <= 90 and abs(lon) <= 180:
            out.append([round(lat, 5), round(lon, 5)])
    return out


def parse_notam(loc: str, number: str, issue: str, text: str, raw_path: str, fetched_at: str) -> Warning | None:
    text = (text or "").replace("\r", "")
    h = HEAD_RE.match(text)
    num = (h.group(1) if h else number).strip()
    m = re.match(r"([A-Z])(\d{4})/(\d{2})$", num)
    if not m:
        return None
    letter, n, yy = m.groups()
    year = 2000 + int(yy)
    loc = loc.strip().upper()
    series = f"notam-{loc.lower()}"
    kind = h.group(2) if h else "N"
    cancels = []
    if h and h.group(3):
        rl, rn, ryy = re.match(r"([A-Z])(\d{4})/(\d{2})", h.group(3)).groups()
        cancels.append(f"{series}/{2000 + int(ryy)}/{rl}{rn}")
    e = E_RE.search(text)
    body = (e.group(1) if e else text).strip()
    extra = {"location": loc, "notam_type": {"N": "new", "R": "replace", "C": "cancel"}[kind]}
    q = Q_RE.search(text)
    if q:
        fir, qcode, _traffic, _purpose, _scope, lo, hi, la_d, la_m, ns, lo_d, lo_m, ew, radius = q.groups()
        extra.update(fir=fir, qcode=qcode, lower_fl=int(lo), upper_fl=int(hi))
        if radius and int(radius) < 999:
            extra["q_circle"] = {"lat": round(_dd(la_d, la_m, None, ns), 4),
                                 "lon": round(_dd(lo_d, lo_m, None, ew), 4), "radius_nm": int(radius)}
    for k, v in FG_RE.findall(text):
        extra["lower" if k == "F" else "upper"] = v.strip()
    circles = []
    for r, unit, la, lo in CIRCLE_RE.findall(body):
        p = notam_positions(f"{la} {lo}")
        if p:
            circles.append({"lat": p[0][0], "lon": p[0][1], "radius_nm": round(float(r) / (1.852 if unit.upper() == "KM" else 1), 2)})
    if circles:
        extra["circles"] = circles
    positions = notam_positions(body)
    if len(positions) >= 3 and not circles:
        extra["shape"] = "polygon"
    b, c = B_RE.search(text), C_RE.search(text)
    if b:
        extra["starts_at"] = _yymmddhhmm(b.group(1))
    return Warning(
        id=f"{series}/{year}/{letter}{n}", series=series, number=f"{letter}{n}", year=year,
        issued_at=_faa_date(issue) or (_yymmddhhmm(b.group(1)) if b else None),
        subject=body.splitlines()[0][:200] if body else "", text=text.strip(),
        positions=positions, cancels=cancels,
        expires_at=_yymmddhhmm(c.group(1)) if c and c.group(1) != "PERM" else None,
        source={"name": NAME, "url": "https://notams.aim.faa.gov/notamSearch/", "raw_path": raw_path,
                "fetched_at": fetched_at, "parser_version": PARSER_VERSION},
        extra=extra)


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
        w = parse_notam(r[0], r[1], r[3], r[6], raw_path, fetched_at)
        if w:
            out[w.id] = w
    return list(out.values())


def run() -> list[Warning]:
    return inbox.process(NAME, parse_file)
