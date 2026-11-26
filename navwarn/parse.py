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


# ---------- sub-areas: "A." "(1)" "1.-" "А." "AREA 2:" "1ST AREA" ----------
CYR = "АБВГДЕЖЗИКЛМНОПРСТУФХЦЧШЩЭЮЯ"
# a list marker at the start of a line, or mid-line right after punctuation ("... AMSL. 5. CIRCLE ...")
MARK_RE = re.compile(
    r"(?:(?P<bol>^)|(?<=[.;,:])[ \t]+)[ \t]*(?:\((?P<pn>\d{1,2})\)|(?P<n>\d{1,2})(?:\.-?|\))(?!\d)|"
    r"\((?P<pl>[A-Z])\)|(?P<l>[A-Z]{1,2})[.)](?=\s|\d)|\((?P<pc>[" + CYR + r"])\)|(?P<c>[" + CYR + r"])[.)](?=\s|\d))", re.M)
NAME_RE = re.compile(
    r"\b(?:(?P<o>\d)(?:ST|ND|RD|TH)[ \t]+(?P<on>AREA|ROUTE|ZONE)|(?P<nn>AREA|ZONE|SECTOR|ROUTE|РАЙОН)[ \t]+(?:NR\.?[ \t]*)?"
    r"(?P<id>[A-Z]|[" + CYR + r"]|\d{1,2})(?!\w))(?=[ \t]*(?:[:.)-]|\n|BOUND|\d))")
CORRIDOR_RE = re.compile(r"EITHER SIDE|TRACK\s?LINE|LINE\s+(?:JOINING|CONNECTING)|ПО\s+ЛИНИИ|ЛИНИЯ", re.I)
BOUND_RE = re.compile(r"BOUND(?:ED)?\s+(?:BY|WI)|\bAREAS?\s*:|\bWI(?:THIN)?\s+(?:THE\s+)?(?:AREA|COORD)|AREAS?\s+(?:AS\s+FLW|BOUNDED)|"
                      r"РАЙОН(?:Е|АХ)\b|ОГРАНИЧЕНН", re.I)
LINE_RE = re.compile(r"JOINING|\bALONG\b|CABLE|PIPELINE|\bROUTE\b", re.I)
VERTEX_CTX_RE = re.compile(r"\bAREA\s+BOUND|BOUNDED\s+BY|JOINING|\bLINE\b|РАЙОНЕ\b", re.I)
PLURAL_RE = re.compile(r"\bAREAS\b|РАЙОНАХ", re.I)

# "WITHIN 2NM OF 12-34.5S 123-45.6E" | "5 MILE RADIUS OF ..." | "РАДИУСОМ 5 МИЛЬ ОТ ..."
NM_PER = {"NM": 1, "MILE": 1, "МИЛ": 1, "KM": 1 / 1.852, "КМ": 1 / 1.852, "CABLE": .1, "КАБ": .1}
NAV_CIRCLE_RE = re.compile(
    r"(?:WITHIN\s+(?P<r1>\d+(?:\.\d+)?)\s*(?P<u1>NM|KM|CABLE|(?:NAUTICAL\s+)?MILE)S?\s+(?:RADIUS\s+)?OF|"
    r"(?P<r2>\d+(?:\.\d+)?)\s*(?P<u2>NM|KM|CABLE|(?:NAUTICAL\s+)?MILE)S?\s+RADIUS(?:\s+(?:OF|CENT(?:ER|RE)D?\s+(?:ON|AT)))?|"
    r"РАДИУС\w*\s+(?P<r3>\d+(?:[.,]\d+)?)\s*(?P<u3>МИЛ|КАБ|КМ)\w*(?:\s+(?:ОТ|С\s+ЦЕНТРОМ|ЦЕНТР\w*))?)"
    r"\s+(?:(?:POSITION|POSN|PSN|ТОЧКИ)\s+)?", re.I)


def navarea_circles(text: str, positions=None):
    """[(lat, lon, radius_nm, (start, end))] for circles written out in a warning's text."""
    positions = positions or parse_positions
    out = []
    for m in NAV_CIRCLE_RE.finditer(text or ""):
        end = _first_pos_end(text, m.end(), positions)     # the centre is the first position after the phrase
        if end is None:
            continue
        lat, lon = positions(text[m.end():end])[0]
        r = m.group("r1") or m.group("r2") or m.group("r3")
        u = (m.group("u1") or m.group("u2") or m.group("u3")).upper().split()[-1]
        per = next((v for k, v in NM_PER.items() if u.startswith(k)), 1)
        out.append((lat, lon, round(float(r.replace(",", ".")) * per, 2), (m.start(), end)))
    return out


def _first_pos_end(text, start, positions):
    """End offset of the first position at or after start (positions() is re-run on growing prefixes)."""
    for i in range(start + 1, min(len(text), start + 60) + 1):
        if positions(text[start:i]):
            return i
    return None


def _marks(text: str) -> dict:
    """Candidate list markers by family: {family: [(start, end, ordinal, label, noun)]}."""
    fam = {}
    for m in MARK_RE.finditer(text):
        g = {k: v for k, v in m.groupdict().items() if v and k != "bol"}
        k, v = next(iter(g.items()))
        if m.group("bol") is None and k in ("l", "pl", "c", "pc") and not re.match(r"\s*\d", text[m.end():]):
            continue                    # mid-line letters only when a position follows ("... ; B. 12-34N ...")
        if k in ("n", "pn"):
            ordinal = int(v)
        elif k in ("l", "pl"):
            ordinal = sum((ord(ch) - 64) * 26 ** i for i, ch in enumerate(reversed(v)))     # A=1 ... Z=26, AA=27
        else:
            ordinal = CYR.index(v) + 1
        family = {"n": "num", "pn": "pnum", "l": "let", "pl": "plet", "c": "cyr", "pc": "pcyr"}[k]
        fam.setdefault(family, []).append((m.start(), m.end(), ordinal, v, ""))
    for m in NAME_RE.finditer(text):
        v, noun = (m.group("o"), m.group("on")) if m.group("o") else (m.group("id"), m.group("nn"))
        ordinal = int(v) if v.isdigit() else CYR.index(v) + 1 if v in CYR else ord(v) - 64
        fam.setdefault("name", []).append((m.start(), m.end(), ordinal, v, noun.upper()))
    return fam


def _run(marks: list) -> list:
    """Keep the markers that count up 1, 2, 3 ... (per noun for "AREA 1 / ROUTE 1" style), allowing one skipped
    number. A family whose markers mostly break the count ("B. VERTICAL LIMITS" under every item) is no list."""
    want, out = {}, []
    for mk in marks:
        w = want.get(mk[4], 1)
        if w <= mk[2] <= w + (1 if w > 1 else 0):
            want[mk[4]] = mk[2] + 1
            out.append(mk)
    if len(marks) - len(out) > len(out):
        return []
    nouns = {mk[4] for mk in out}
    return [(s, e, o, f"{n} {v}" if len(nouns) > 1 else v, n) for s, e, o, v, n in out]


def _shape(text: str, ctx: str, pts: list) -> str:
    closed = len(pts) >= 4 and pts[0] == pts[-1]
    for t in (text, ctx):
        if CORRIDOR_RE.search(t) and len(pts) >= 2:
            return "line"
        if BOUND_RE.search(t) and len(pts) >= 3:
            return "polygon"
        if LINE_RE.search(t) and len(pts) >= 2 and not closed:
            return "line"
        if closed:                      # a ring that closes is an area unless its own text says otherwise
            return "polygon"
    return "points"


def _leaf(text: str, label: str, ctx: str, positions, circles) -> list[dict]:
    out, blank = [], list(text)
    for lat, lon, r, (s, e) in circles(text):
        out.append({"label": label, "shape": "circle", "positions": [[lat, lon]], "radius_nm": r})
        blank[s:e] = " " * (e - s)
    rest = "".join(blank)
    pts = positions(rest)
    if pts:
        out.insert(0, {"label": label, "shape": _shape(rest, ctx, pts), "positions": pts})
    return out


def _split(text: str, label: str, ctx: str, positions, circles, depth: int = 0) -> list[dict]:
    best = None
    for family, marks in _marks(text).items() if depth < 3 else ():
        run = _run(marks)
        if len(run) < 2:
            continue
        pre = text[:run[0][0]]
        segs = [text[a[1]:b[0] if b else len(text)] for a, b in zip(run, run[1:] + [None])]
        withpos = [s for s in segs if positions(s)]
        if len(withpos) + bool(positions(pre)) < 2:
            continue
        # "AREA BOUND BY: A. pt  B. pt  C. pt" letters the corners of one area, not separate areas
        if (all(len(positions(s)) == 1 and not circles(s) for s in withpos) and not positions(pre)
                and VERTEX_CTX_RE.search(ctx + pre) and not PLURAL_RE.search(ctx + pre)):
            continue
        if best is None or run[0][0] < best[0][0][0]:
            best = (run, pre, segs)
    if best is None:
        return _leaf(text, label, ctx, positions, circles)
    run, pre, segs = best
    out = _leaf(pre, label, ctx, positions, circles)
    for mk, seg in zip(run, segs):
        sub = f"{label}.{mk[3]}" if label else mk[3]
        out += _split(seg, sub, ctx + "\n" + pre, positions, circles, depth + 1)
    return out


def parse_areas(text: str, positions=None, circles=None) -> list[dict]:
    """Separate areas when a warning describes more than one: [{label, shape, positions, radius_nm?}].
    shape is polygon (text says the area is bounded, or the ring closes), line (trackline, joining,
    either side of a line), circle, or points. Empty when the text describes a single area."""
    positions = positions or parse_positions
    circles = circles or (lambda t: navarea_circles(t, positions))
    areas = _split(text or "", "", "", positions, circles)
    return areas if len(areas) >= 2 else []


def area_extra(text: str) -> dict:
    """{"areas": [...]} for a warning that describes several areas, else {}."""
    areas = parse_areas(text)
    return {"areas": areas} if areas else {}
