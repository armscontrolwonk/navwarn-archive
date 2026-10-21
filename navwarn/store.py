"""One JSON file per warning under warnings/<series>/<year>/<number>.json.
Records are created on first sight, touched on every sight, and marked withdrawn when a
successfully fetched source no longer lists them. Nothing is ever deleted."""
from __future__ import annotations
import json, os, glob
from .model import Warning

WARN_DIR = os.environ.get("NAVWARN_WARNINGS", "warnings")


def _path(wid: str) -> str:
    series, year, num = wid.split("/")
    return os.path.join(WARN_DIR, series, year, f"{num}.json")


def load(wid: str) -> dict | None:
    p = _path(wid)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save(rec: dict) -> None:
    p = _path(rec["id"])
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(rec, f, indent=1, ensure_ascii=False, sort_keys=True)
        f.write("\n")


def iter_records():
    for p in sorted(glob.glob(os.path.join(WARN_DIR, "*", "*", "*.json"))):
        with open(p, encoding="utf-8") as f:
            yield json.load(f)


def upsert(warnings: list[Warning], source_name: str, now: str, withdraw: bool = True) -> dict:
    """Returns counts {new, updated, withdrawn}."""
    seen, stats = set(), {"new": 0, "updated": 0, "withdrawn": 0}
    for w in warnings:
        seen.add(w.id)
        rec = w.to_dict()
        old = load(w.id)
        if old is None:
            rec.update(first_seen=now, last_seen=now, status="active")
            stats["new"] += 1
        else:
            if old.get("text") != rec["text"]:
                old.setdefault("revisions", []).append(
                    {"seen": old["last_seen"], "text": old["text"], "issued_at": old.get("issued_at")})
                stats["updated"] += 1
            old.update({k: v for k, v in rec.items() if k not in ("first_seen",)})
            old.update(last_seen=now, status="active")
            old.pop("withdrawn_at", None)
            rec = old
        save(rec)
    for rec in (iter_records() if withdraw else ()):
        if rec.get("status") == "active" and rec.get("source", {}).get("name") == source_name and rec["id"] not in seen:
            rec.update(status="withdrawn", withdrawn_at=now)
            save(rec)
            stats["withdrawn"] += 1
    return stats
