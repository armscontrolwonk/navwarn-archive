"""One-time pull of NGA's historical broadcast-warning archive (back to 1977, ~100k records).
NGA's portal has been in maintenance since about March 2026 and the API answers 503, so this is
retried daily by .github/workflows/nga-archive.yml until every series is saved.
Writes archive/nga/<series>-<year>.jsonl and raw/nga_archive/<series>.json.gz.
    python -m navwarn.nga_archive [4 12 A P C]"""
from __future__ import annotations
import gzip, json, os, sys
from collections import defaultdict
from .http import fetch, save_raw, now_iso
from .parse import parse_dtg, parse_positions, parse_cancels, parse_expiry

API = "https://msi.nga.mil/api/publications/broadcast-warn?output=json&status=all&navArea={area}"
SERIES = {"4": "navarea-04", "12": "navarea-12", "A": "hydrolant", "P": "hydropac", "C": "hydroarc"}


def done(series: str) -> bool:
    return os.path.exists(os.path.join("raw", "nga_archive", f"{series}.json.gz"))


def pull(area: str, fetched_at: str) -> None:
    series = SERIES[area]
    raw = fetch(API.format(area=area), timeout=300)
    recs = json.loads(raw)["broadcast-warn"]          # maintenance page is HTML, so this raises
    if not recs:
        raise RuntimeError("empty response")
    by_year = defaultdict(list)
    for r in recs:
        text = r.get("text") or ""
        year = int(r["msgYear"])
        cancel_at = parse_dtg(r["cancelDate"]) if r.get("cancelDate") else None
        by_year[year].append({
            "id": f"{series}/{year}/{r['msgNumber']}", "series": series, "number": str(r["msgNumber"]),
            "year": year, "issued_at": parse_dtg(r.get("issueDate") or ""), "subject": text.split("\n", 1)[0][:200],
            "text": text, "positions": parse_positions(text), "cancels": parse_cancels(text),
            "expires_at": parse_expiry(text), "status": "active" if r.get("status") == "A" else "cancelled",
            "cancelled_at": cancel_at, "authority": r.get("authority"), "subregion": r.get("subregion"),
            "source": {"name": "nga_archive", "url": API.format(area=area), "fetched_at": fetched_at, "parser_version": 1}})
    os.makedirs("archive/nga", exist_ok=True)
    for year, rows in sorted(by_year.items()):
        rows.sort(key=lambda x: int(x["number"]))
        with open(f"archive/nga/{series}-{year}.jsonl", "w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    # original response kept verbatim, gzipped (mtime=0 so identical bytes give identical files).
    # Written last: its presence marks the series as done.
    save_raw("nga_archive", f"{series}.json.gz", gzip.compress(raw, mtime=0))
    print(f"{series}: {len(recs)} records, years {min(by_year)}-{max(by_year)}")


def main(areas: list[str]) -> int:
    """Pull each series not yet archived. A failure on one series doesn't stop the others.
    Always exits 0 so a scheduled retry job stays green while NGA is down."""
    fetched_at = now_iso()
    todo = [a for a in (areas or list(SERIES)) if not done(SERIES[a])]
    if not todo:
        print("all NGA series already archived; nothing to do")
    for area in todo:
        try:
            pull(area, fetched_at)
        except Exception as e:  # noqa: BLE001
            print(f"{SERIES[area]}: not available yet ({type(e).__name__}: {str(e)[:120]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
