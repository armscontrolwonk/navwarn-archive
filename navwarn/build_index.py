"""Build index/active.json (what the site reads) and mark stale sources in index/sources.json.
A source is stale when its newest warning is older than its cadence, or its last fetch failed
longer ago than its cadence. Warnings from stale sources and self-expired warnings are kept on
disk but left out of active.json."""
from __future__ import annotations
import json, os
from datetime import datetime, timezone, timedelta
from . import store
from .http import now_iso

SOURCES_PATH = os.path.join("index", "sources.json")
ACTIVE_PATH = os.path.join("index", "active.json")


def _dt(s): return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) if s else None


def main() -> int:
    now = datetime.now(timezone.utc)
    with open(SOURCES_PATH, encoding="utf-8") as f:
        status = json.load(f)
    for name, s in status["sources"].items():
        cadence = timedelta(days=s.get("cadence_days", 7))
        newest, last_ok = _dt(s.get("newest_issued_at")), _dt(s.get("last_ok"))
        s["stale"] = (newest is None or now - newest > cadence) or (last_ok is None or now - last_ok > cadence)
    stale = {n for n, s in status["sources"].items() if s["stale"]}
    active, counts = [], {"active": 0, "withdrawn": 0, "expired": 0, "stale_source": 0}
    for rec in store.iter_records():
        if rec.get("status") != "active":
            counts["withdrawn"] += 1
            continue
        if rec.get("expires_at") and _dt(rec["expires_at"]) < now:
            counts["expired"] += 1
            continue
        if rec["source"]["name"] in stale:
            counts["stale_source"] += 1
            continue
        counts["active"] += 1
        active.append({k: rec.get(k) for k in
                       ("id", "series", "number", "year", "issued_at", "expires_at", "subject", "text",
                        "positions", "cancels", "first_seen")} | {"source": rec["source"]["name"],
                                                                 "url": rec["source"]["url"]})
    active.sort(key=lambda r: r.get("issued_at") or "", reverse=True)
    status.update(indexed=now_iso(), counts=counts)
    with open(SOURCES_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=1, sort_keys=True); f.write("\n")
    with open(ACTIVE_PATH, "w", encoding="utf-8") as f:
        json.dump({"generated": now_iso(), "warnings": active}, f, ensure_ascii=False); f.write("\n")
    print("index:", counts, "stale sources:", sorted(stale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
