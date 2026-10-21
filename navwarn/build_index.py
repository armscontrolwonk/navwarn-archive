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


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _circle(lat, lon, radius_nm, n=36):
    import math
    pts = []
    for i in range(n + 1):
        a = 2 * math.pi * i / n
        dlat = radius_nm / 60 * math.cos(a)
        dlon = radius_nm / 60 * math.sin(a) / max(math.cos(math.radians(lat)), 0.01)
        pts.append((lat + dlat, lon + dlon))
    return pts


def _ring(pts):
    return " ".join(f"{lon},{lat},0" for lat, lon in pts)


def write_kml(active: list, path: str) -> None:
    """All warnings in force as one KML for Google Earth or QGIS, one folder per series."""
    by_series = {}
    for w in active:
        by_series.setdefault(w["series"], []).append(w)
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>',
           '<name>Warnings in force</name>',
           '<Style id="a"><LineStyle><color>ff2b44e0</color><width>2</width></LineStyle>'
           '<PolyStyle><color>402b44e0</color></PolyStyle></Style>']
    for series, ws in sorted(by_series.items()):
        out.append(f"<Folder><name>{_esc(series)}</name>")
        for w in ws:
            ex, pos = w.get("extra") or {}, w.get("positions") or []
            geoms = []
            if ex.get("shape") == "polygon" and len(pos) >= 3:
                ring = pos + [pos[0]] if pos[0] != pos[-1] else pos
                geoms.append(f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{_ring(ring)}</coordinates></LinearRing></outerBoundaryIs></Polygon>")
            for c in ex.get("circles", []):
                geoms.append(f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{_ring(_circle(c['lat'], c['lon'], c['radius_nm']))}</coordinates></LinearRing></outerBoundaryIs></Polygon>")
            if not geoms:
                geoms = [f"<Point><coordinates>{lon},{lat},0</coordinates></Point>" for lat, lon in pos]
            if not geoms and ex.get("q_circle"):
                q = ex["q_circle"]
                geoms.append(f"<Polygon><outerBoundaryIs><LinearRing><coordinates>{_ring(_circle(q['lat'], q['lon'], q['radius_nm']))}</coordinates></LinearRing></outerBoundaryIs></Polygon>")
            if not geoms:
                continue
            desc = _esc(f"{w.get('issued_at') or ''} to {w.get('expires_at') or 'until cancelled'}\n\n{w.get('text') or ''}")
            out.append(f"<Placemark><name>{_esc(w['id'])}</name><styleUrl>#a</styleUrl><description>{desc}</description>"
                       f"<MultiGeometry>{''.join(geoms)}</MultiGeometry></Placemark>")
        out.append("</Folder>")
    out.append("</Document></kml>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def main() -> int:
    now = datetime.now(timezone.utc)
    with open(SOURCES_PATH, encoding="utf-8") as f:
        status = json.load(f)
    for name, s in status["sources"].items():
        if s.get("cadence_days", 7) is None:          # hand-fed source: nothing to be late for
            s["stale"] = False
            continue
        cadence = timedelta(days=s.get("cadence_days", 7))
        newest, last_ok = _dt(s.get("newest_issued_at")), _dt(s.get("last_ok"))
        s["stale"] = (newest is None or now - newest > cadence) or (last_ok is None or now - last_ok > cadence)
    stale = {n for n, s in status["sources"].items() if s["stale"]}
    records = list(store.iter_records())
    # a warning listed as cancelled (or replaced) by any record still in force is no longer in force
    cancelled = {c for r in records if r.get("status") == "active" for c in r.get("cancels", [])}
    active, counts = [], {"active": 0, "withdrawn": 0, "expired": 0, "stale_source": 0, "cancelled": 0}
    for rec in records:
        if rec.get("status") != "active":
            counts["withdrawn"] += 1
            continue
        if rec.get("expires_at") and _dt(rec["expires_at"]) < now:
            counts["expired"] += 1
            continue
        if rec["id"] in cancelled:
            counts["cancelled"] += 1
            continue
        if rec["source"]["name"] in stale:
            counts["stale_source"] += 1
            continue
        counts["active"] += 1
        active.append({k: rec.get(k) for k in
                       ("id", "series", "number", "year", "issued_at", "expires_at", "subject", "text",
                        "positions", "cancels", "first_seen", "extra")} | {"source": rec["source"]["name"],
                                                                 "url": rec["source"]["url"]})
    active.sort(key=lambda r: r.get("issued_at") or "", reverse=True)
    status.update(indexed=now_iso(), counts=counts)
    with open(SOURCES_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=1, sort_keys=True); f.write("\n")
    with open(ACTIVE_PATH, "w", encoding="utf-8") as f:
        json.dump({"generated": now_iso(), "warnings": active}, f, ensure_ascii=False); f.write("\n")
    write_kml(active, os.path.join("index", "active.kml"))
    print("index:", counts, "stale sources:", sorted(stale))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
