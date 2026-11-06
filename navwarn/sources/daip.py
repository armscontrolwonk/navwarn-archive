"""Aviation NOTAMs from the DoD Aeronautical Information Portal (DAIP, https://www.daip.jcs.mil/daip/mobile/index).
DAIP carries the same international NOTAM feed as FAA NOTAM Search but answers ordinary scripts.
Ported from the China-Strategic scraper (notam_daip.py).

Its certificates chain to DoD roots that normal trust stores lack; navwarn/certs/dod_ca.pem holds the public DoD
root and intermediate certificates from DISA (dl.dod.cyber.mil, unclass-certificates_pkcs7_DoD.zip), so the
connection is still fully verified. If DoD rotates its CAs, refresh that file from the same zip.

Every NOTAM returned is kept verbatim in raw/daip/notams.jsonl (one line per NOTAM, sorted, so git stores only
what changed). Normalized records are kept for the kinds that matter here: route closures, rockets and debris,
firing, restricted/danger/prohibited areas and exercises (Q codes QR*, QW*, QARLC/QARLT, plus text keywords),
minus fireworks, balloons, parachuting and similar noise."""
from __future__ import annotations
import http.cookiejar, json, os, re, ssl, time, urllib.request
from ..http import UA, save_raw, now_iso
from ..notam import parse_notam

NAME = "daip"
BASE = "https://www.daip.jcs.mil/daip/"
CADENCE_DAYS = 2
PARSER_VERSION = 2          # v2: extra.areas
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CA = os.path.join(HERE, "certs", "dod_ca.pem")
FIRS = os.path.join(HERE, "daip_firs.txt")
BATCH = 50

# Filters from the China-Strategic scraper, widened from China to every region queried
REL = re.compile(r"ROCKET|AEROSPACE|(?<!AIR )(?<!BLOCKED-)\bSPACE\b(?![ -]BASED)|LAUNCH|DEBRIS|MISSILE|FIRING|FRNG|SHOOTING|MILITARY|MIL EXER|EXER|DANGER AREA|"
                 r"RESTRICTED AREA|PROHIBITED|TEMPO(RARY)? (DANGER|RESTRICTED)|SPECIAL RESTRICTED|/QR[A-Z]{3}/|/QW[A-Z]{3}/")
ROUTE = re.compile(r"/QAR(LC|LT)/|ATS RTE.{0,80}CLSD")
NOISE = re.compile(r"MODEL ROCKET|FIREWORK|BIRD|KITE|LASER LIGHT|BALLOON|RADIOSONDE|\bSONDE\b|"
                   r"PARA(CHUTE|GLID)|AEROBATIC|AIR SHOW|AIRSHOW|"
                   r"/QW[PLAGBV][A-Z]{2}/")   # Q codes: parachuting, laser, air display, glider, aerobatics, formation flight
MON = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
CREATED_RE = re.compile(r"CREATED:\s*(\d\d) (\w{3}) (\d{4}) (\d\d):(\d\d)")


def firs() -> list[str]:
    out = []
    for line in open(FIRS, encoding="utf-8"):
        if not line.lstrip().startswith("#"):
            out += [c for c in line.split() if re.fullmatch(r"[A-Z]{4}", c) and c not in out]
    return out


def opener():
    ctx = ssl.create_default_context(cafile=CA)
    op = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),
                                     urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    op.addheaders = [("User-Agent", UA)]
    op.open(BASE + "mobile/index", timeout=60).read()          # sets the session cookie the query needs
    return op


def query(op, locs: list[str]) -> dict:
    body = json.dumps({"locs": " ".join(locs), "type": "LOCATION", "radius": "10", "sort": "Criticality"}).encode()
    req = urllib.request.Request(BASE + "mobile/query", data=body, headers={"Content-Type": "application/json"})
    d = json.loads(op.open(req, timeout=180).read())
    if d.get("error"):
        raise RuntimeError(f"DAIP error: {d['error']}")
    return d


def run():
    codes = firs()
    op = opener()
    items, per_fir = {}, {}
    for i in range(0, len(codes), BATCH):          # any failed batch raises, so a partial pull never withdraws records
        d = query(op, codes[i:i + BATCH])
        for g in d.get("group") or []:
            for n in g.get("notams") or []:
                per_fir[n.get("code")] = len(n.get("list") or [])
                for x in n.get("list") or []:
                    if x.get("id"):
                        items.setdefault(x.get("key") or f"{n.get('code')}_{x['id']}",
                                         {"key": x.get("key"), "fir": n.get("code"), "id": x["id"], "rawtext": x.get("rawtext") or ""})
        time.sleep(2)
    fetched_at = now_iso()
    lines = [json.dumps(items[k], ensure_ascii=False, sort_keys=True) for k in sorted(items)]
    raw_path = save_raw(NAME, "notams.jsonl", ("\n".join(lines) + "\n").encode("utf-8"))
    save_raw(NAME, "per_fir.json", (json.dumps(per_fir, indent=1, sort_keys=True) + "\n").encode())
    src = {"name": NAME, "url": BASE + "mobile/index", "raw_path": raw_path, "fetched_at": fetched_at,
           "parser_version": PARSER_VERSION}
    out = {}
    for it in items.values():
        raw = it["rawtext"].replace("\r", "")
        msg = raw.split("\n\nCREATED:")[0].strip()
        if not (REL.search(msg) or ROUTE.search(msg)) or NOISE.search(msg):
            continue
        a = re.search(r"\bA\)\s*([A-Z]{4})", msg)
        cr = CREATED_RE.search(raw)
        issued = (f"{cr.group(3)}-{MON[cr.group(2)]:02d}-{cr.group(1)}T{cr.group(4)}:{cr.group(5)}:00Z"
                  if cr and cr.group(2) in MON else None)
        w = parse_notam(a.group(1) if a else it["fir"], it["id"], issued, msg, src)
        if w:
            w.extra["queried_fir"] = it["fir"]
            out[w.id] = w
    print(f"[{NAME}] {len(items)} NOTAMs in {len(per_fir)} of {len(codes)} regions; {len(out)} kept after filters")
    return list(out.values())
