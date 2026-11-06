"""Shared ICAO NOTAM parsing (Q line, A-G fields, positions, circles) used by every NOTAM source."""
from __future__ import annotations
import html, re
from datetime import datetime, timezone
from .model import Warning
from .parse import parse_areas

HEAD_RE = re.compile(r"^\s*([A-Z]\d{4}/\d{2})\s+NOTAM([NRC])(?:\s+([A-Z]\d{4}/\d{2}))?")
Q_RE = re.compile(r"Q\)\s*([A-Z]{4})/(Q[A-Z]{2,4})/([A-Z ]*)/([A-Z ]*)/([A-Z ]*)/(\d{3})/(\d{3})/"
                  r"(?:(\d{2})(\d{2})([NS])(\d{3})(\d{2})([EW])(\d{3})?)?")       # some Q lines omit the position
B_RE = re.compile(r"B\)\s*(\d{10})")
C_RE = re.compile(r"C\)\s*(\d{10}|PERM)")
E_RE = re.compile(r"E\)\s*(.*?)(?=\n?\s*[FG]\)\s|\Z)", re.S)
D_RE = re.compile(r"\bD\)\s*(.*?)(?=\s*E\))", re.S)
# "CONDUCTED BY CHINA", "ROCKET LAUNCH BY JAPAN" -> who the text says is responsible
BY_RE = re.compile(r"\b(?:CONDUCTED|LAUNCH(?:ED)?)\s+BY\s+([A-Z][A-Z .'-]{1,40}?)(?=[.,;:\n]|\s{2}|\s+(?:WILL|IN|AT|FROM|ON|WI)\b|$)")
# Kinds, in priority order (from the China scraper's notam_store.py)
KIND = [("route", re.compile(r"/QAR(LC|LT)/|ATS RTE.{0,80}CLSD", re.I)),
        ("rocket", re.compile(r"(?<!MODEL )ROCKET(?!RY)|AEROSPACE|(?<!AIR )(?<!BLOCKED-)\bSPACE\b(?![ -]BASED)|\bLAUNCH|DEBRIS|RE-?ENTRY|SPLASH", re.I)),
        ("firing", re.compile(r"/QWM[A-Z]{2}/|MISSILE|\bFIRING|\bFRNG|SHOOTING|\bGUN\b", re.I)),
        ("drone", re.compile(r"/QWU[A-Z]{2}/|UNMANNED|\bUAVS?\b|\bUAS\b|DRONE", re.I)),
        ("restricted", re.compile(r"PROHIBITED AREA|RESTRICTED AREA|DANGER AREA|DNG ZONE|/QR[A-Z]{3}/", re.I)),
        ("exercise", re.compile(r"/QWE[A-Z]{2}/|\bEXER|MIL(ITARY)? (EXER|ACT|OPS|TRAINING|FLT)", re.I)),
        ("aip", re.compile(r"TRIGGER NOTAM|AIP [A-Z]+ (AMENDMENT|SUP)|REF AIP", re.I))]


def kind(text: str) -> str:
    for k, rx in KIND:
        if rx.search(text):
            return k
    return "other"


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


def notam_circles(text: str) -> list[tuple]:
    """[(lat, lon, radius_nm, (start, end))] for each "RADIUS 2KM CENTRE 570549N0835809E" in the text."""
    out = []
    for m in CIRCLE_RE.finditer(text or ""):
        r, unit, la, lo = m.groups()
        p = notam_positions(f"{la} {lo}")
        if p:
            out.append((p[0][0], p[0][1], round(float(r) / (1.852 if unit.upper() == "KM" else 1), 2), m.span()))
    return out


def parse_notam(loc: str, number: str, issued_at: str | None, text: str, source: dict) -> Warning | None:
    """One ICAO-format NOTAM -> Warning. source = {name, url, raw_path, fetched_at, parser_version}."""
    text = html.unescape(text or "").replace("\r", "").strip()
    h = HEAD_RE.match(text)
    num = (h.group(1) if h else number).strip()
    m = re.match(r"([A-Z])(\d{4})/(\d{2})$", num)
    if not m:
        return None
    letter, n, yy = m.groups()
    year = 2000 + int(yy)
    loc = loc.strip().upper()
    series = f"notam-{loc.lower()}"
    ntype = h.group(2) if h else "N"
    cancels = []
    if h and h.group(3):
        rl, rn, ryy = re.match(r"([A-Z])(\d{4})/(\d{2})", h.group(3)).groups()
        cancels.append(f"{series}/{2000 + int(ryy)}/{rl}{rn}")
    e = E_RE.search(text)
    body = (e.group(1) if e else text).strip()
    extra = {"location": loc, "notam_type": {"N": "new", "R": "replace", "C": "cancel"}[ntype]}
    q = Q_RE.search(text)
    if q:
        fir, qcode, _traffic, _purpose, _scope, lo, hi, la_d, la_m, ns, lo_d, lo_m, ew, radius = q.groups()
        extra.update(fir=fir, qcode=qcode, lower_fl=int(lo), upper_fl=int(hi))
        if la_d and radius and int(radius) < 999:
            extra["q_circle"] = {"lat": round(_dd(la_d, la_m, None, ns), 4),
                                 "lon": round(_dd(lo_d, lo_m, None, ew), 4), "radius_nm": int(radius)}
    d = D_RE.search(text)
    if d:
        extra["schedule"] = re.sub(r"\s+", " ", d.group(1)).strip()
    extra["kind"] = kind(text)
    by = BY_RE.search(body)
    if by:
        extra["attributed_to"] = by.group(1).strip()
    for k, v in FG_RE.findall(text):
        extra["lower" if k == "F" else "upper"] = v.strip()
    circles = [{"lat": la, "lon": lo, "radius_nm": r} for la, lo, r, _ in notam_circles(body)]
    if circles:
        extra["circles"] = circles
    positions = notam_positions(body)
    if len(positions) >= 3 and not circles:
        extra["shape"] = "polygon"
    areas = parse_areas(body, notam_positions, notam_circles)
    if areas:
        extra["areas"] = areas
    b, c = B_RE.search(text), C_RE.search(text)
    if b:
        extra["starts_at"] = _yymmddhhmm(b.group(1))
    return Warning(
        id=f"{series}/{year}/{letter}{n}", series=series, number=f"{letter}{n}", year=year,
        issued_at=issued_at or (_yymmddhhmm(b.group(1)) if b else None),
        subject=body.splitlines()[0][:200] if body else "", text=text.strip(),
        positions=positions, cancels=cancels,
        expires_at=_yymmddhhmm(c.group(1)) if c and c.group(1) != "PERM" else None,
        source=dict(source),
        extra=extra)


