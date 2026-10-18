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

Python 3.11+, standard library only.

```bash
python -m navwarn.run                 # all sources
python -m navwarn.run ukho            # one source
python -m navwarn.build_index         # rebuild index/*.json
python -m http.server 8000            # then open http://localhost:8000
python -m navwarn.nga_archive         # one-time, ~100k historical records
```

## Run in the cloud

`.github/workflows/scrape.yml` runs every 6 hours on GitHub Actions and commits whatever changed.
Enable GitHub Pages on the main branch (root) to publish `index.html`.

## Sources (v1)

| module | covers | notes |
|---|---|---|
| ukho | NAVAREA I, UK coastal (WZ) | server-rendered HTML |
| kystverket | NAVAREA XIX | simple report page |
| ccg | NAVAREA XVII/XVIII + all Canadian coastal series | ~35 HTML pages per run |
| nga_daily | NAVAREA IV, XII | NGA text bulletins; flagged stale when NGA stops updating |

A source is marked stale when its newest warning is older than its expected cadence; its warnings
stay on disk but drop out of `active.json` until it recovers.

## Adding a source

Copy `navwarn/sources/kystverket.py`, implement `run()` returning `Warning` objects, add the module
name to `SOURCES` in `navwarn/run.py`. Save the raw bytes first; parse second.
