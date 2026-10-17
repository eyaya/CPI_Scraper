"""Parser for the Rwanda NISR monthly CPI PDF (Tier 3).

Unlike Kenya, NISR publishes index LEVELS by division. 'Annex 3: Consumer Price
Index, All Rwanda' (the national aggregate) is a table:

  Code Categories Weights May-25 Apr-26 May-26 on Apr.2026 on May.2025 1m 12m
  00 GENERAL INDEX 100% 208.2 232.3 233.8 0.6% 12.3% 0.6% 12.3%
  01 Food and non-alcoholic beverages 39% 262.8 280.0 282.7 ...

Three index columns (prev-year, prev-month, current) => three periods of data
per report. We keep division-level rows only (2-digit codes 00..12; sub-items
like '01.1.1' are skipped). Base Feb 2014 = 100. COICOP-1999 (12 divisions).

THE BACK SERIES (added 2026-10-12). Beside every monthly report NISR posts
"CPI_time_series_<Month>_<YYYY>.xls" whose "All Rwanda" sheet (Table D) holds
the whole series on the SAME base -- "Base: 2014; Reference: February
2014=100" -- monthly from February 2009: one row per COICOP code, one column
per month. It is read when passed as an extra (`.xls`/`.xlsx`). Division rows
only (2-digit codes), as for the PDF. Where the report and the workbook both
cover a month, the REPORT's printed (rounded) figure is kept -- it is the
headline publication -- and the workbook's unrounded values fill every other
month. The workbook's own labels are kept as printed.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_MON = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
        "jun": "06", "jul": "07", "aug": "08", "sep": "09", "oct": "10",
        "nov": "11", "dec": "12"}

# canonical fallback labels (division 05's label wraps across lines in the PDF)
_LABELS = {
    "00": "General index",
    "01": "Food and non-alcoholic beverages",
    "02": "Alcoholic beverages, tobacco and narcotics",
    "03": "Clothing and footwear",
    "04": "Housing, water, electricity, gas and other fuels",
    "05": "Furnishings, household equipment and routine household maintenance",
    "06": "Health", "07": "Transport", "08": "Communication",
    "09": "Recreation and culture", "10": "Education",
    "11": "Restaurants and hotels", "12": "Miscellaneous goods and services",
}

_HDR_RE = re.compile(r"\b([A-Za-z]{3})-(\d{2})\b")
# division row: 2-digit code, optional label, weight%, then 3 index numbers
_ROW_RE = re.compile(
    r"^(\d{2})\s+(.*?)\s*(\d+)%\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\b"
)


def _parse_series(xls_path: str) -> pd.DataFrame:
    raw = pd.read_excel(xls_path, sheet_name="All Rwanda", header=None)
    base_txt = " ".join(str(v) for v in raw.iloc[:4, 3].dropna())
    if "February 2014=100" not in base_txt.replace(" =", "=").replace("= ", "="):
        raise ValueError(f"Rwanda CPI series: unexpected base {base_txt!r}")
    hdr = next(i for i in range(10) if str(raw.iat[i, 4]).strip() == "Weights")
    months = {}
    for c in range(5, raw.shape[1]):
        v = raw.iat[hdr, c]
        if isinstance(v, pd.Timestamp) or hasattr(v, "year"):
            months[c] = f"{v.year}-{v.month:02d}"
    if len(months) < 24:
        raise ValueError("Rwanda CPI series: month header not found")
    records = []
    for r in range(hdr + 1, raw.shape[0]):
        code = str(raw.iat[r, 2]).strip()
        if code not in _LABELS:
            continue
        label = str(raw.iat[r, 3]).strip()
        for c, period in months.items():
            v = pd.to_numeric(raw.iat[r, c], errors="coerce")
            if pd.notna(v):
                records.append({"coicop_code": code, "coicop_label": label,
                                "geography": "National", "period": period,
                                "measure": "index", "value": float(v)})
    out = pd.DataFrame.from_records(records)
    if out["coicop_code"].nunique() != 13:
        raise ValueError(f"Rwanda CPI series: codes {sorted(out.coicop_code.unique())}")
    out["unit"] = "Index"
    out["base_period"] = "Feb 2014 = 100"
    out["frequency"] = "monthly"
    return out


def parse(pdf_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    report = _parse_report(pdf_path)
    series = [_parse_series(p) for p in (extras or [])
              if p.lower().endswith((".xls", ".xlsx"))]
    if not series:
        return report
    out = pd.concat([*series, report], ignore_index=True)
    # the report's printed figure wins over the workbook's for the same month
    return out.drop_duplicates(["coicop_code", "period", "measure"],
                               keep="last").reset_index(drop=True)


def _parse_report(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        text = None
        for page in pdf.pages:
            t = page.extract_text() or ""
            if "All Rwanda" in t and "GENERAL INDEX" in t:
                text = t
                break
    if text is None:
        raise ValueError("'All Rwanda' annex not found")

    lines = text.splitlines()

    periods = None
    for ln in lines:
        found = _HDR_RE.findall(ln)
        if len(found) >= 3:
            periods = [f"20{yy}-{_MON[mon.lower()]}" for mon, yy in found[:3]]
            break
    if not periods:
        raise ValueError("index-column period header not found")

    records = []
    for ln in lines:
        m = _ROW_RE.match(ln.strip())
        if not m:
            continue
        code = m.group(1)
        if code not in _LABELS:            # keep divisions 00..12 only
            continue
        label = m.group(2).strip() or _LABELS[code]
        idx_vals = [m.group(4), m.group(5), m.group(6)]
        for period, val in zip(periods, idx_vals):
            records.append({
                "coicop_code": code,
                "coicop_label": label,
                "geography": "National",     # 'All Rwanda'
                "period": period,
                "measure": "index",
                "value": float(val),
            })

    out = pd.DataFrame.from_records(records)
    out["unit"] = "Index"
    out["base_period"] = "Feb 2014 = 100"
    out["frequency"] = "monthly"
    return out
