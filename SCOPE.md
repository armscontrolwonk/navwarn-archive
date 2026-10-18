# Navigational warnings archive: scoping notes (2026-10-09)

## 1. What to collect, and what to leave out of v1

Collect the IMO/IHO **World-Wide Navigational Warning Service (WWNWS)**: 21 NAVAREAs, each run by one national coordinator, plus NGA's HYDROLANT / HYDROPAC / HYDROARC series. Every warning in this system is a short NAVTEX-style text with a fixed skeleton defined by the IMO/IHO/WMO Joint Manual on MSI: area, serial/year, date-time group, body with positions as `DD-MM.mN DDD-MM.mW`, and cancellation lines. The wrapper (HTML, CSV, PDF, JSON, email) varies by country; the payload does not.

Leave out of v1:
- **Aviation NOTAMs.** Different system (ICAO), already structured, FAA NOTAM API needs a key. Add later as a separate layer. Military exercise / missile warnings appear in both systems; cross-linking them is a v2 feature, not a reason to merge the pipelines.
- **Coastal / local warnings** (UK WZ, AUSCOAST, Canadian local series). Keep them only where they ride along free in the same fetch (Canada, UK).
- **Commercial aggregators** (sealagom.com, navareas.com, nautoshark). They prove it is doable but their terms almost certainly forbid redistribution. Don't build on them.

## 2. Source survey (probed 2026-10-09 with plain curl, no browser)

| NAVAREA | Coordinator | What I found | Access tier |
|---|---|---|---|
| IV, XII, HYDRO* | NGA (US) | JSON API `msi.nga.mil/api/publications/broadcast-warn` responds but is **frozen: newest record 2024-05-10**, 386 "active" items, all 2021-2024. Independently confirmed by an open-source project on 2026-10-07. The archive it still serves is huge (NAVAREA IV back to 1977, ~20k records; HYDROPAC ~82k). Daily in-force text bulletins at `msi.nga.mil/apology_objects/DailyMemIV.txt` / `DailyMemXII.txt` show "IN FORCE AS OF 05 MAR" 2026, so also possibly stale. The `/navwarnings` page returns a WAF 403 to curl. NGA email subscription is the live channel. | A (archive, one-time grab) / D (email) |
| I | UKHO | `msi.admiralty.co.uk/RadioNavigationalWarnings` returns 200 with warning text server-rendered in the HTML (NAVAREA I 225/26 etc. visible). No robots.txt. | B |
| XVII, XVIII + Canadian coastal | Canadian Coast Guard | `nis.ccg-gcc.gc.ca/public/rest/...` is HTML (406 on JSON Accept). Search supports status published/cancelled, date ranges, areas; **CSV export up to 2,000 rows**; email subscription with CSV attachment. | A (CSV) / D |
| XIX | Kystverket (Norway) | English warnings page returns 200. Site states it is a convenience copy of the broadcast. | B |
| XI | Japan Coast Guard | Old `navarea11_en.html` is 404. Another project reads the list from a `warnings.cgi` endpoint. Needs re-discovery. | B (unverified) |
| X | AMSA (Australia) | MSI page returns 200 but warning text is not inline (loaded from a sub-site or JS). Weekly in-force bulletin Thursdays 0000 UTC; **automated email** available. | B/D |
| XIV | Maritime NZ | **403 even with a browser user agent.** Weekly in-force bulletin Mondays 0900 UTC over EGC. | C, use email or ask |
| II | SHOM (France) | Old `NavareaIIenVigueur.txt` is 404; new location not found yet. | C (moved) |
| VIII | Indian NHO | WordPress page "NAVAREA VIII Warnings Inforce" at hydrobharat.gov.in, plus bimonthly PDFs. | B (HTML + PDF) |
| III | IHM (Spain) | Weekly bulletin, in-force list on website, Spanish + English. Not probed. | C (unverified, likely PDF) |
| V | DHN (Brazil) | Weekly in-force bulletin Wednesdays. Not probed. | C (unverified) |
| XV | SHOA (Chile) | "Radioavisos" page updated daily. Not probed. | C (unverified) |
| VII | SANHO (South Africa) | In-force summary and full text on SANHO site. Not probed. | C (unverified) |
| VI, IX, XVI, XIII, XX, XXI | Argentina, Pakistan, Peru, Russia x3 | Not surveyed. Russia's three areas are the hardest; aggregators advertise them as a selling point. | C |
| (bonus) Portugal coastal | Instituto Hidrográfico | Publishes **S-124** warnings via an OGC API Features endpoint (`api-features.hidrografico.pt`), GeoJSON-like, EU high-value dataset with a DOI. DNS didn't resolve from here today. The only true structured open feed found. | A |

Tiers: **A** machine-readable, **B** server-rendered HTML you can fetch and parse, **C** blocked, moved or unverified, **D** email push.

## 3. Design that absorbs both problems (bot-blocking, format variance)

**Archive first, parse second.** Every fetch saves the raw bytes exactly as received (HTML, CSV, PDF, JSON, .eml). Normalization is a separate step that reads from the archive and can be re-run forever. Consequences:
- A parser bug never loses data. You fix the parser and replay.
- Format variance becomes a per-source parser you can write lazily. Day one can be "raw only" for half the sources.
- Each normalized record carries `parser_version` and a pointer to its raw file.

**One acquisition strategy per source, chosen from:**
1. Direct fetch (tiers A, B). Low cadence (every 6 h is plenty; most in-force bulletins are weekly). Honest user agent with a contact email. Send `If-None-Match` / `If-Modified-Since`.
2. Email subscription (tier D, and the fallback for tier C). Nearly every coordinator offers one. The office pushes to you, so bot-blocking is irrelevant. Ingest from a dedicated mailbox over IMAP on the same cron.
3. Ask. NAVAREA coordinators are small offices with a public email. For 403 sites (NZ) a one-line request for a feed or permission usually works, and the self-assessment reports they file with IHO show they want the data used.
Don't try to defeat a WAF. If a site blocks you and has no email route, mark the source "manual" and move on.

**Normalized schema (small on purpose, field names borrowed from IHO S-124 so future S-124 feeds drop straight in):**

```
id            "navarea-04/2026/207"  (series, year, number)
series        NAVAREA IV | HYDROPAC | NAVAREA I | WZ | ...
number, year
issued_at     ISO 8601, from the date-time group
cancelled_at  ISO 8601 or null
cancels       ["navarea-04/2026/180", ...]
subject       first line of body
text          full body, verbatim
positions     [[lat, lon], ...] parsed from DD-MM.mN DDD-MM.mW
geometry      GeoJSON or null (point/polygon/line when derivable)
source        { name, url, fetched_at, raw_path, parser_version }
```

## 4. Storage: the lightest option that still counts as "for posterity"

**Recommendation: a git repository with a scheduled GitHub Actions job ("git scraping").**

```
raw/
  ukho/navarea-1.html          <- one file per source, overwritten each run
  ccg/navwarn.csv
  nga/DailyMemIV.txt
  mail/<msgid>.eml
warnings/
  navarea-04/2026/207.json     <- one file per warning, immutable after cancel
  navarea-01/2026/225.json
index/
  active.json                  <- built in CI, what the site reads
  warnings.sqlite              <- optional, built in CI for search
```

Why this is the lightest:
- **Zero servers, zero cost.** Actions cron + GitHub Pages hosts the scraper and the site. The site is static and reads `index/active.json`.
- **History is free.** Overwrite the raw file each run and commit only if it changed. `git log -p raw/ukho/navarea-1.html` is the complete changelog of NAVAREA I. Don't write timestamped snapshot files; git already deduplicates and the tree stays small.
- **Posterity-grade by default.** A public repo is mirrored by Software Heritage automatically, can get a Zenodo DOI per release, and anyone can `git clone` the whole archive. No bucket, no database to migrate.
- **Scale is fine.** The NGA back-catalog (~100k short texts) is roughly 100 to 200 MB of JSON once; daily deltas are kilobytes.

Alternatives, in case the repo constraint bites:
- Cloudflare Workers cron + R2 (free tier) with Email Workers for the mailbox route. More moving parts, but no commit-size ceiling.
- SQLite file (sqlite-utils + Datasette) pushed to object storage. Great for querying, worse for diffing.
- Parquet partitions in S3. Only worth it if someone wants to run analytics across years.

## 5. Suggested v1 (one weekend)

1. Repo skeleton, Actions cron every 6 h, Python with `requests`, one module per source exposing `fetch() -> bytes` and `parse(bytes) -> list[Warning]`.
2. One-time grab of the NGA archive (`status=all` for 4, 12, A, P, C) into `warnings/`. That alone is a historically useful dataset back to 1977.
3. Live sources: UKHO (I), Canada CSV (XVII/XVIII), Kystverket (XIX), NGA daily text bulletins (IV/XII) with a staleness alarm.
4. Mailbox ingest: subscribe the project address to NGA, AMSA (X), Canada, and ask Maritime NZ (XIV).
5. Static site: table + map of active warnings from `index/active.json`, per-warning permalink to the JSON and the raw file it came from.
6. Then re-discover Japan (XI) and SHOM (II), and start on the PDF-only offices one at a time.

Staleness alarm matters: NGA's JSON froze silently for two years and the mobile apps built on it never noticed. Alert when a source's newest warning is older than its normal cadence.
