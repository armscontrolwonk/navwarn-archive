"""Shared parsers: date-time groups and lat/lon positions in the forms coordinators actually use."""
from __future__ import annotations
import re
from datetime import datetime, timezone

MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1)}

# 091012 UTC Oct 26  |  040658Z MAR 26  |  091012Z OCT 2026
DTG_RE = re.compile(r"\b(\d{2})(\d{2})(\d{2})\s*(?:Z|UTC)\s+([A-Za-z]{3})\s+(\d{2}|\d{4})\b")


def parse_dtg(s: str, default_year: int | None = None) -> str | None:
    m = DTG_RE.search(s or "")
    if not m:
        return None
    dd, hh, mi, mon, yy = m.groups()
    mon_n = MONTHS.get(mon.upper())
    if not mon_n:
        return None
    year = int(yy) if len(yy) == 4 else 2000 + int(yy)
    try:
        return datetime(year, mon_n, int(dd), int(hh), int(mi), tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None


# "CANCEL THIS MSG 160736Z MAR 26."  -> expiry
SELF_CANCEL_RE = re.compile(r"CANCEL\s+THIS\s+(?:MSG|MESSAGE)\s+(\d{6}Z?\s*(?:UTC\s+)?[A-Z]{3}\s+\d{2,4})", re.I)

# "CANCEL NAVAREA I 220/26"  "CANCEL NAVAREA XIX 106/26"  "CANCEL HYDROPAC 1234/26"
CANCEL_REF_RE = re.compile(
    r"CANCEL\s+(?:NAVAREA\s+([IVX]+|\d+)|(HYDROPAC|HYDROLANT|HYDROARC|WZ|AUSCOAST)(?:\s+WARNING)?)\s*(\d{1,4})/(\d{2})", re.I)

ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
         "XI": 11, "XII": 12, "XIII": 13, "XIV": 14, "XV": 15, "XVI": 16, "XVII": 17, "XVIII": 18,
         "XIX": 19, "XX": 20, "XXI": 21}


def navarea_series(label: str) -> str:
    """'I' | 'XIX' | '4' -> 'navarea-01' | 'navarea-19' | 'navarea-04'"""
    label = label.strip().upper()
    n = ROMAN.get(label) or int(label)
    return f"navarea-{n:02d}"


def parse_cancels(text: str) -> list[str]:
    out = []
    for m in CANCEL_REF_RE.finditer(text or ""):
        area, other, num, yy = m.groups()
        series = navarea_series(area) if area else {"WZ": "uk-wz", "AUSCOAST": "auscoast"}.get(other.upper(), other.lower())
        out.append(f"{series}/{2000 + int(yy)}/{int(num)}")
    return out


def parse_expiry(text: str) -> str | None:
    m = SELF_CANCEL_RE.search(text or "")
    return parse_dtg(m.group(1)) if m else None


# 64-33.50N 006-04.80E | 46-40N 053-10W | 47° 35.514'N 058° 53.839'W | 46 47.5N 071 12.0W
POS_RE = re.compile(
    r"(\d{1,2})\s*[-°\s]\s*(\d{1,2}(?:\.\d+)?)\s*'?\s*([NS])\b[,\s]*"
    r"(\d{1,3})\s*[-°\s]\s*(\d{1,2}(?:\.\d+)?)\s*'?\s*([EW])\b")


def parse_positions(text: str) -> list[list[float]]:
    out = []
    for m in POS_RE.finditer(text or ""):
        la_d, la_m, ns, lo_d, lo_m, ew = m.groups()
        lat = int(la_d) + float(la_m) / 60
        lon = int(lo_d) + float(lo_m) / 60
        if lat > 90 or lon > 180:
            continue
        if ns == "S":
            lat = -lat
        if ew == "W":
            lon = -lon
        out.append([round(lat, 4), round(lon, 4)])
    return out


def strip_html(s: str) -> str:
    import html as _h
    s = re.sub(r"<script.*?</script>|<style.*?</style>", "", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return _h.unescape(s)
