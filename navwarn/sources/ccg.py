"""Canadian Coast Guard NAVWARNs (includes NAVAREA XVII/XVIII and all coastal series).
HTML search, 50 per page (~35 pages). One bulk fetch per run; raw pages saved as one concatenated file."""
from __future__ import annotations
import re, time
from datetime import datetime, timezone
from ..http import fetch, save_raw, now_iso
from ..model import Warning
from ..parse import parse_positions, strip_html

NAME = "ccg"
BASE = "https://nis.ccg-gcc.gc.ca"
URL = BASE + "/public/rest/messages/en/search?status=published&maxHits=50&page={page}"
CADENCE_DAYS = 3
PARSER_VERSION = 1
SERIES = "ccg"

CARD_RE = re.compile(
    r'<a href="/public/rest/messages/en/message/(\d+)">.*?gridViewTitle">(.*?)</div>\s*'
    r'<div class="[^"]*font-section-smaller">\s*(.*?)\s*</div>.*?'
    r'<span class="mouse-event-auto">\s*([A-Z]{2}-[A-Z]-\d+-\d{2})\s*</span>\s*'
    r'<div class="[^"]*gridViewDescription[^"]*">(.*?)</div>', re.S)
TOTAL_RE = re.compile(r"from ([\d,]+) total results")
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC")


def _iso(s: str) -> str | None:
    m = DATE_RE.search(s or "")
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if m else None


def parse_page(html: str, raw_path: str, fetched_at: str) -> list[Warning]:
    out = []
    for msg_id, title, dates, ref, desc in CARD_RE.findall(html):
        title = re.sub(r"\s+", " ", strip_html(title)).strip()
        desc = strip_html(desc).strip()
        dates_t = strip_html(dates)
        d = DATE_RE.findall(dates_t)
        yy = ref.rsplit("-", 1)[-1]
        year = 2000 + int(yy)
        number = ref.rsplit("-", 1)[0]          # NW-C-4301
        text = f"{title}\n{desc}".strip()
        out.append(Warning(
            id=f"{SERIES}/{year}/{number}", series=SERIES, number=number, year=year,
            issued_at=_iso(d[0] + " UTC") if d else None, subject=title[:200], text=text,
            positions=parse_positions(text), cancels=[],
            expires_at=_iso(d[1] + " UTC") if len(d) > 1 else None,
            source={"name": NAME, "url": f"{BASE}/public/rest/messages/en/message/{msg_id}",
                    "raw_path": raw_path, "fetched_at": fetched_at, "parser_version": PARSER_VERSION},
            extra={"ccg_id": msg_id, "ccg_series": number.split("-")[1]}))
    return out


def run() -> list[Warning]:
    fetched_at = now_iso()
    pages, out, page, total = [], [], 1, None
    while True:
        html = fetch(URL.format(page=page)).decode("utf-8", "replace")
        # keep only the results grid; the surrounding form is ~1 MB of area <option>s per page
        start = html.find('<div class="container-fluid">')
        end = html.find('<div class="visible-lt800">', start)
        pages.append(f"<!-- page {page} fetched {fetched_at} -->\n{html[start:end] if start > 0 else html}")
        if total is None:
            m = TOTAL_RE.search(html)
            total = int(m.group(1).replace(",", "")) if m else 0
        out += parse_page(html, "raw/ccg/search.html", fetched_at)
        if page * 50 >= total or page > 200:
            break
        page += 1
        time.sleep(1)
    save_raw(NAME, "search.html", "\n".join(pages).encode("utf-8"))
    return out
