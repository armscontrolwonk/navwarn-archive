"""One-time pull of NGA's historical broadcast-warning archive (frozen at 2024-05-10, back to 1977).
Writes archive/nga/<series>-<year>.jsonl, one normalized record per line. ~100k records, run once.
    python -m navwarn.nga_archive [4 12 A P C]"""
from __future__ import annotations
import json, os, sys
from collections import defaultdict
from .http import fetch, save_raw, now_iso
from .parse import parse_dtg, parse_positions, parse_cancels, parse_expiry

API = "https://msi.nga.mil/api/publications/broadcast-warn?output=json&status=all&navArea={area}"
SERIES = {"4": "navarea-04", "12": "navarea-12", "A": "hydrolant", "P": "hydropac", "C": "hydroarc"}


def main(areas: list[str]) -> int:
    fetched_at = now_iso()
    for area in areas or list(SERIES):
        series = SERIES[area]
        raw = fetch(API.format(area=area), timeout=300)
        save_raw("nga_archive", f"{series}.json", raw)
        recs = json.loads(raw)["broadcast-warn"]
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
        print(f"{series}: {len(recs)} records, years {min(by_year)}-{max(by_year)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
