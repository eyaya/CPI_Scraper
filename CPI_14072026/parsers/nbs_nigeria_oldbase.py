"""NBS Nigeria CPI on the OLD base (November 2009 = 100), COICOP-1999.

NBS rebased its CPI in 2024 (base 2024 = 100, COICOP 2018); the current
workbook (`nbs_nigeria.py`) starts in January 2023. The LAST workbook published
on the old base -- `cpi_1NewNov_2024.xlsx` (microdata catalogue 154, download
1117) -- carries the whole old-base national series, sheet 'Table2'
("Composite Consumer Price Index (Base November 2009 = 100)"), from JANUARY
1995: All items + the 12 COICOP-1999 divisions, monthly.

NOT CHAINED. The CPI merge key is coicop_code / geography / period / measure,
WITHOUT base_period, so the two bases cannot both hold the same month. The
old-base series is therefore emitted only for months BEFORE the new series
begins (`before`, passed by the caller as the new workbook's first month), and
every row carries base_period "November 2009 = 100". Old-base months that the
rebased series also covers (2023-01 .. 2024-11) are published by NBS but not
collected here, so a reader never sees two bases for one month. The series
breaks at that point; it is not one index.

Divisions are COICOP-1999 (12), so codes 08 and 12 mean "Communication" and
"Miscellaneous goods & services" here, not COICOP-2018's "Information and
communication" / "Insurance and financial services"; `coicop_label` carries
NBS's own name on every row.

CROSS-CHECK: All items Jan 1995 = 14.36; Nov 2024 = 847.14 (old base).
"""
from __future__ import annotations
import re
import pandas as pd

SHEET = "Table2"
BASE = "November 2009 = 100"
_MONTHS = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
           "jun": "06", "jul": "07", "aug": "08", "sep": "09", "oct": "10",
           "nov": "11", "dec": "12"}

# COICOP-1999 divisions, matched on NBS's header text.
_RULES = [
    ("00", lambda s: s == "all items"),
    ("01", lambda s: s.startswith("food & non") or s.startswith("food and non")),
    ("02", lambda s: s.startswith("alcoholic")),
    ("03", lambda s: s.startswith("clothing")),
    ("04", lambda s: s.startswith("housing")),
    ("05", lambda s: s.startswith("furnishings")),
    ("06", lambda s: s.startswith("health")),
    ("07", lambda s: s.startswith("transport")),
    ("08", lambda s: s.startswith("communication")),
    ("09", lambda s: s.startswith("recreation")),
    ("10", lambda s: s.startswith("education")),
    ("11", lambda s: s.startswith("restaurant")),
    ("12", lambda s: s.startswith("miscellaneous")),
]


def _clean(h) -> str:
    return re.sub(r"\s+", " ", str(h).replace("\n", " ")).strip()


def is_old_base(xlsx_path: str) -> bool:
    """True when the workbook's Table2 is the November-2009-base series."""
    try:
        df = pd.read_excel(xlsx_path, sheet_name=SHEET, header=None, nrows=2,
                           dtype=object)
    except Exception:                                      # noqa: BLE001
        return False
    return "november 2009" in " ".join(str(v) for v in df.iloc[0].tolist()).lower()


def parse(xlsx_path: str, before: str | None = None) -> pd.DataFrame:
    df = pd.read_excel(xlsx_path, sheet_name=SHEET, header=None, dtype=object)
    header = df.iloc[1]
    codemap: dict[str, tuple[int, str]] = {}
    for j, h in header.items():
        if h is None or (isinstance(h, float) and pd.isna(h)):
            continue
        s = _clean(h)
        low = s.lower()
        for code, pred in _RULES:
            if code not in codemap and pred(low):
                codemap[code] = (j, s.rstrip("."))
                break
    if len(codemap) < len(_RULES):
        missing = [c for c, _ in _RULES if c not in codemap]
        raise ValueError(f"NBS old-base Table2: division columns not found: {missing}")

    records, year = [], None
    for i in range(2, len(df)):
        y, m = df.iat[i, 0], df.iat[i, 1]
        if pd.notna(y) and re.fullmatch(r"\d{4}(\.0)?", str(y).strip()):
            year = str(y).strip()[:4]
        if pd.isna(m) or year is None:
            continue
        mkey = str(m).strip().lower()[:3]
        if mkey not in _MONTHS:
            continue
        period = f"{year}-{_MONTHS[mkey]}"
        if before and period >= before:
            continue
        for code, (j, label) in codemap.items():
            v = pd.to_numeric(df.iat[i, j], errors="coerce")
            # A 0 is NBS's empty-cell placeholder, not a published index (the
            # validator rightly refuses a zero CPI): skip it, never keep it.
            if pd.notna(v) and v != 0:
                records.append({"coicop_code": code, "coicop_label": label,
                                "geography": "National", "period": period,
                                "value": float(v)})
    if not records:
        raise ValueError("NBS old-base Table2: no rows read")
    out = pd.DataFrame.from_records(records)
    out["measure"] = "index"
    out["unit"] = "Index"
    out["base_period"] = BASE
    out["frequency"] = "monthly"
    return out
