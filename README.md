# navwarn-archive

Pulls in-force navigational warnings from national NAVAREA coordinators on a schedule, keeps the raw
pages verbatim, normalizes each warning into one JSON file, and serves a static map/list from the
same repository. No servers, no database: git history is the archive.

See [SCOPE.md](SCOPE.md) for the source survey and design rationale.

## Layout

```
navwarn/sources/*.py   one module per source: run() -> list[Warning]
raw/<source>/          last fetched page per source, overwritten each run (history = git log)
warnings/<series>/<year>/<number>.json   one record per warning, never deleted
archive/nga/*.jsonl    one-time pull of NGA's 1977-2024 back catalog
index/active.json      what index.html reads;   index/sources.json   per-source health + staleness
index.html             static site (GitHub Pages, repo root)
```

## Run locally

The GitHub job owns `raw/`, `warnings/` and `index/`. Data you generate locally is for testing;
discard it (`git checkout -- raw warnings index && git clean -fd raw warnings index`) rather than
committing it, and `git pull` before you change code.

Python 3.11+, standard library only.

```bash
python -m navwarn.run                 # all sources
python -m navwarn.run ukho            # one source
python -m navwarn.build_index         # rebuild index/*.json
python -m http.server 8000            # then open http://localhost:8000
python -m navwarn.nga_archive         # one-time history pull; retried daily in CI while NGA is down
```

## Run in the cloud

`.github/workflows/scrape.yml` runs every 6 hours on GitHub Actions and commits whatever changed.
`.github/workflows/nga-archive.yml` retries NGA's 1977-2024 history pull daily until all five series
are saved. NGA's portal has answered 503 (maintenance) since about March 2026.
Enable GitHub Pages on the main branch (root) to publish `index.html`.

## Sources (v1)

| module | covers | notes |
|---|---|---|
| ukho | NAVAREA I, UK coastal (WZ) | server-rendered HTML |
| kystverket | NAVAREA XIX | simple report page |
| amsa | NAVAREA X, AUSCOAST areas A-H | one page, full text; rig and special-vessel tables kept raw only |
| ccg | Canadian coastal series only (NAVAREA XVII/XVIII are not on this site) | ~35 HTML pages per run |
| nga_daily | NAVAREA IV, XII | NGA text bulletins; flagged stale when NGA stops updating |

A source is marked stale when its newest warning is older than its expected cadence; its warnings
stay on disk but drop out of `active.json` until it recovers.

## Adding a source

Copy `navwarn/sources/kystverket.py`, implement `run()` returning `Warning` objects, add the module
name to `SOURCES` in `navwarn/run.py`. Save the raw bytes first; parse second.
