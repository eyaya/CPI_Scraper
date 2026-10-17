"""Parser for the BCC (DR Congo) price-statistics page (Tier 2, HTML payload).

CENTRAL-BANK FALLBACK: the NSO (INS-RDC) is WAF-blocked, so the CPI comes from
the Banque Centrale du Congo, which republishes INS's series and credits it
('Institut National de la Statistique'). BCC's 2026 site rebuild replaced the old
`ipc_annuel_bcc.xlsx` workbook (now 404) with a Next.js data explorer whose
series are SERVER-RENDERED into the page: the React flight payload, pushed in
`self.__next_f.push([1,"…"])` chunks, carries a `series` array of metadata and a
`periods` array of

    {"period": "2026-08", "frequency": "monthly",
     "values": {"inflation--indice-global": 506.47, …}}

so no API call and no scraping of rendered HTML is needed — we join the chunks,
JSON-unescape them and read the two arrays straight out.

The page mixes MONTHLY and WEEKLY frequencies in one `periods` array. Only three
series are monthly — the all-items index, its month-on-month rate and its
year-on-year rate — and those are what we emit, keyed to COICOP 00. The twelve
COICOP functions BCC also publishes are WEEKLY percentage series (period keys
like '2026-08-S3'), which the CPI schema's monthly `period` cannot express
without aggregating them, so they are left out rather than re-estimated; the same
goes for the weekly national/Kinshasa indices and the cumulative rates.

Neither BCC nor INS states the index base on this page, so `base_period` is left
blank rather than guessed.
"""
from __future__ import annotations
import json
import re
import pandas as pd

_GEOGRAPHY = "National"
_ALL_ITEMS = "Indice global"
_PERIOD = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_BLOB = re.compile(
    r'self\.__next_f\.push\(\[1,\s*("(?:[^"\\]|\\.)*")\]\)', re.S)
# series id -> (measure, unit) for the monthly series we emit
_SERIES = {
    "inflation--indice-global": ("index", "Index"),
    "inflation--inflation-mensuelle": ("inflation_mom", "percent"),
    "inflation--glissement-annuel": ("inflation_yoy", "percent"),
}


def _flight_text(html: str) -> str:
    """The page's React flight payload, chunks joined and JSON-unescaped."""
    blobs = _BLOB.findall(html)
    if not blobs:
        raise ValueError("BCC: no Next.js flight payload in the page")
    return "".join(json.loads(b) for b in blobs)


def _array_after(text: str, key: str):
    """Parse the JSON array that follows `"<key>":` , by bracket matching (the
    payload is one long line, so a regex would have to be balanced anyway)."""
    i = text.find(f'"{key}":[')
    if i < 0:
        raise ValueError(f"BCC: '{key}' array not found in the payload")
    start = text.index("[", i)
    depth, in_str, esc = 0, False, False
    for j in range(start, len(text)):
        c = text[j]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:j + 1])
    raise ValueError(f"BCC: '{key}' array is unterminated")


def parse(html_path: str) -> pd.DataFrame:
    with open(html_path, "r", encoding="utf-8", errors="replace") as fh:
        text = _flight_text(fh.read())

    labels = {s["id"]: (s.get("labelFr") or s.get("labelEn") or "")
              for s in _array_after(text, "series") if s.get("id")}
    periods = _array_after(text, "periods")

    records = []
    for entry in periods:
        period = str(entry.get("period") or "")
        if entry.get("frequency") != "monthly" or not _PERIOD.match(period):
            continue                       # weekly rows ('2026-08-S3') are skipped
        for sid, value in (entry.get("values") or {}).items():
            spec = _SERIES.get(sid)
            if spec is None or value is None:
                continue
            measure, unit = spec
            records.append(("00", labels.get(sid) or _ALL_ITEMS, period, measure,
                            round(float(value), 4), unit, ""))

    got = {r[3] for r in records}
    if "index" not in got:
        raise ValueError(f"BCC: no monthly index series found (measures: {sorted(got)})")

    out = pd.DataFrame.from_records(
        records,
        columns=["coicop_code", "coicop_label", "period", "measure", "value",
                 "unit", "base_period"])
    out["coicop_label"] = _ALL_ITEMS
    out["geography"] = _GEOGRAPHY
    out["frequency"] = "monthly"
    return out.drop_duplicates(["coicop_code", "period", "measure"])
