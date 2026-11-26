"""Russian coastal navigational warnings (ПРИП, e.g. ПРИП МУРМАНСК 206/26), pasted by hand.
Paste one or more PRIP texts, in the original Cyrillic, into a UTF-8 .txt file in inbox/prip/ and
commit. Coordinates use С/Ю for N/S and В/З for E/W. Records stay active until their
self-cancel time (ОТМ ЭТОТ НР ...) or until a later PRIP cancels them (ОТМ ... NNN/YY)."""
from __future__ import annotations
import re
from datetime import datetime, timezone
from .. import inbox
from ..http import now_iso
from ..model import Warning
from ..parse import parse_areas, navarea_circles

NAME = "prip"
CADENCE_DAYS = None
WITHDRAW_MISSING = False
PARSER_VERSION = 2          # v2: extra.areas

TRANSLIT = dict(zip("АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ",
                    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s",
                     "t", "u", "f", "kh", "ts", "ch", "sh", "shch", "", "y", "", "e", "yu", "ya"]))
MONTHS = {"ЯНВ": 1, "ФЕВ": 2, "МАР": 3, "АПР": 4, "МАЙ": 5, "МАЯ": 5, "ИЮН": 6, "ИЮЛ": 7, "АВГ": 8,
          "СЕН": 9, "ОКТ": 10, "НОЯ": 11, "ДЕК": 12}

HEAD_RE = re.compile(r"ПРИП\s+([А-ЯЁ][А-ЯЁ\- ]*?)\s+(\d{1,4})/(\d{2})")
POS_RE = re.compile(r"(\d{1,2})-(\d{1,2}(?:\.\d+)?)\s*([СЮ])\s+(\d{1,3})-(\d{1,2}(?:\.\d+)?)\s*([ВЗ])")
SELF_CANCEL_RE = re.compile(r"ОТМ\s+ЭТОТ\s+НР\s+(\d{2})(\d{2})(\d{2})\s+([А-ЯЁ]{3})")
CANCEL_RE = re.compile(r"ОТМ\s+(?!ЭТОТ)(?:ПРИП\s+)?([А-ЯЁ]+\s+)?(\d{1,4})/(\d{2})")


def translit(s: str) -> str:
    return "".join(TRANSLIT.get(ch, ch) for ch in s.upper()).lower().replace(" ", "-")


def positions(text: str) -> list[list[float]]:
    out = []
    for la_d, la_m, ns, lo_d, lo_m, ew in POS_RE.findall(text):
        lat = int(la_d) + float(la_m) / 60
        lon = int(lo_d) + float(lo_m) / 60
        out.append([round(-lat if ns == "Ю" else lat, 4), round(-lon if ew == "З" else lon, 4)])
    return out


def parse_text(text: str, raw_path: str, fetched_at: str) -> list[Warning]:
    text = text.replace("\r", "")
    # a "ПРИП X NNN/YY" inside a cancellation line ("ОТМ ПРИП ...") is a reference, not a new warning
    heads = [h for h in HEAD_RE.finditer(text)
             if not re.search(r"ОТМ\s*$", text[text.rfind("\n", 0, h.start()) + 1:h.start()])]
    out = {}
    for i, h in enumerate(heads):
        region, num, yy = h.group(1).strip(), int(h.group(2)), int(h.group(3))
        # the bulletin repeats the header ("ПРИП МУРМАНСК 206/26 ПРИП МУРМАНСК 206 ..."); skip the echo
        if i and heads[i - 1].group(1).strip() == region and int(heads[i - 1].group(2)) == num \
                and not text[heads[i - 1].end():h.start()].strip():
            continue
        body = text[h.start(): heads[i + 1].start() if i + 1 < len(heads) else len(text)].strip()
        body = body.split("=")[0].strip() if "=" in body else body
        year = 2000 + yy
        series = f"prip-{translit(region)}"
        wid = f"{series}/{year}/{num}"
        if wid in out:
            continue
        expires = None
        m = SELF_CANCEL_RE.search(body)
        if m and m.group(4)[:3] in MONTHS:
            dd, hh, mi, mon = int(m.group(1)), int(m.group(2)), int(m.group(3)), MONTHS[m.group(4)[:3]]
            try:
                expires = datetime(year, mon, dd, hh, mi, tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                pass
        cancels = [f"prip-{translit(r.strip()) if r else translit(region)}/{2000 + int(cy)}/{int(cn)}"
                   for r, cn, cy in CANCEL_RE.findall(body)]
        lines = [l.strip() for l in body.splitlines() if l.strip()]
        subject = next((l for l in lines[1:] if re.match(r"^\d+\.", l)), lines[0] if lines else "")
        pos = positions(body)
        out[wid] = Warning(
            id=wid, series=series, number=str(num), year=year, issued_at=None, subject=subject[:200], text=body,
            positions=pos, cancels=cancels, expires_at=expires,
            source={"name": NAME, "url": None, "raw_path": raw_path, "fetched_at": fetched_at,
                    "parser_version": PARSER_VERSION},
            extra={"region": region, **({"shape": "polygon"} if len(pos) >= 3 and "РАЙОНЕ" in body else {}),
                   **({"areas": areas} if (areas := parse_areas(body, positions, lambda t: navarea_circles(t, positions))) else {})})
    return list(out.values())


def parse_file(path: str, raw_path: str) -> list[Warning]:
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return parse_text(f.read(), raw_path, now_iso())


def run() -> list[Warning]:
    return inbox.process(NAME, parse_file)
