"""Normalized warning record. Field names lean on IHO S-124 so future S-124 feeds map directly."""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Warning:
    id: str                      # "<series>/<year>/<number>" e.g. "navarea-01/2026/225"
    series: str                  # navarea-01, navarea-19, hydropac, uk-wz, ccg ...
    number: str                  # "225" or "NW-C-4301"
    year: int
    issued_at: Optional[str]     # ISO 8601 UTC or None
    subject: str                 # first meaningful line
    text: str                    # verbatim body
    positions: list = field(default_factory=list)   # [[lat, lon], ...]
    cancels: list = field(default_factory=list)     # ids this warning cancels
    expires_at: Optional[str] = None                # self-cancel DTG if stated
    source: dict = field(default_factory=dict)      # {name, url, raw_path, fetched_at, parser_version}
    extra: dict = field(default_factory=dict)       # source-specific fields (areas, categories, ...)

    def to_dict(self) -> dict:
        return asdict(self)
