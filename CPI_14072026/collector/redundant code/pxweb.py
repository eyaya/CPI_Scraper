"""Minimal PxWeb API client (Tier 1).

Many African NSO 'StatsBank' portals run PxWeb, which exposes a JSON API: GET a
table URL for metadata, POST a selection query for data (json-stat2). Used by
Ghana GSS StatsBank; reusable for any other PxWeb NSO.
"""
from __future__ import annotations
import json
import requests

from .fetch import HEADERS, TIMEOUT


def build_query(dimensions: dict[str, list[str]], fmt: str = "json-stat2") -> dict:
    """`dimensions` maps a PxWeb variable code to the values to select; the
    special value ['*'] means 'all values' for that variable."""
    query = []
    for code, values in dimensions.items():
        if values == ["*"]:
            sel = {"filter": "all", "values": ["*"]}
        else:
            sel = {"filter": "item", "values": values}
        query.append({"code": code, "selection": sel})
    return {"query": query, "response": {"format": fmt}}


def fetch(table_url: str, dimensions: dict[str, list[str]],
          verify: bool = True) -> bytes:
    """POST the query and return the raw json-stat2 response bytes (kept as the
    retained source document for API sources)."""
    q = build_query(dimensions)
    headers = {**HEADERS, "Content-Type": "application/json"}
    r = requests.post(
        table_url, headers=headers, data=json.dumps(q),
        timeout=TIMEOUT, verify=verify,
    )
    r.raise_for_status()
    return r.content
