"""python -m navwarn.run [source ...]   Fetch, archive raw, normalize, upsert. Never raises on one bad source."""
from __future__ import annotations
import importlib, json, os, sys, traceback
from .http import now_iso
from . import store

SOURCES = ["ukho", "kystverket", "nga_daily", "ccg"]
STATUS_PATH = os.path.join("index", "sources.json")


def main(argv: list[str]) -> int:
    names = argv or SOURCES
    now = now_iso()
    status = {}
    if os.path.exists(STATUS_PATH):
        with open(STATUS_PATH, encoding="utf-8") as f:
            status = json.load(f).get("sources", {})
    failures = 0
    for name in names:
        mod = importlib.import_module(f"navwarn.sources.{name}")
        entry = status.get(name, {})
        try:
            warnings = mod.run()
            stats = store.upsert(warnings, name, now)
            newest = max((w.issued_at for w in warnings if w.issued_at), default=None)
            entry.update(last_ok=now, last_error=None, count=len(warnings), newest_issued_at=newest,
                         cadence_days=getattr(mod, "CADENCE_DAYS", 7), **{f"last_{k}": v for k, v in stats.items()})
            print(f"[{name}] ok {len(warnings)} warnings, newest {newest}, {stats}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            entry.update(last_error=f"{now} {type(e).__name__}: {e}")
            print(f"[{name}] FAILED: {e}", file=sys.stderr)
            traceback.print_exc()
        status[name] = entry
    os.makedirs("index", exist_ok=True)
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump({"updated": now, "sources": status}, f, indent=1, sort_keys=True)
        f.write("\n")
    return 1 if failures == len(names) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
