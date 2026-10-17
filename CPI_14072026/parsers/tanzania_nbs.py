"""Parser for the Tanzania NBS monthly NCPI release PDF (Tier 3).

NBS publishes the National CPI (COICOP-2018, base Jan–Dec 2020 = 100) as a
monthly PDF. Its 'Main Groups' table shows, per division, the index for three
months (year-ago, previous, current) plus 1-/12-month % changes:

  S/N | Main Groups | Weight | Febr. 2025 | Jan. 2026 | Febr. 2026 | 1M% | 12M%
  1..13 | Food … / Alcoholic … / …          (13 divisions, stacked in one cell)
  TOTAL – ALL ITEMS | 100.0 | 118.28 | 121.41 | 122.01 | …

pdfplumber returns the 13 division rows collapsed into a single row whose cells
each hold the 13 values newline-separated; the S/N column and the index columns
each split into 13 aligned parts (the label column wraps, so we key on S/N =
COICOP division number and use canonical labels). The 'All Items' total is a
separate row. We emit the index for each of the three dated columns.

THE BACK SERIES (added 2026-10-12). Beside each release NBS posts "CPI
Summary <Month YYYY>.xls" with one sheet per year of the REBASED series
("2021_REBASED SERIES" .. "2026_REBASED SERIES"; COICOP-2018, weights
2017/18 price-updated to 2020 -- the same series as the release). Each sheet
holds the previous December and the twelve months: the ALL ITEMS INDEX, the
13 divisions' indices, and the all-items INFLATION RATE (12-month). Read when
passed as an extra; division indices + all-items index + all-items y/y
inflation. "Annual Average" columns and the "Other Selected Groups" blocks
are not taken. Where a release and the workbook both cover a month, the
release's printed figure is kept.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

from ..coicop import DIVISIONS

_BASE_PERIOD = "Jan-Dec 2020 = 100"
_MONTHS = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
           "jun": "06", "jul": "07", "aug": "08", "sep": "09", "oct": "10",
           "nov": "11", "dec": "12"}
_HDR = re.compile(r"([A-Za-z]{3})[a-z]*\.?,?\s*(20\d\d)")


def _period(cell) -> str | None:
    if not isinstance(cell, str):
        return None
    m = _HDR.search(cell.replace("\n", " "))
    return f"{m.group(2)}-{_MONTHS[m.group(1).lower()]}" if m and m.group(1).lower() in _MONTHS else None


def _num(s) -> float | None:
    if isinstance(s, (int, float)):
        return float(s)
    if isinstance(s, str) and re.fullmatch(r"\d+\.\d+", s.strip()):
        return float(s.strip())
    return None


def _parse_summary(xls_path: str) -> pd.DataFrame:
    xl = pd.ExcelFile(xls_path)
    records = []
    for sheet in xl.sheet_names:
        if "REBASED SERIES" not in sheet.upper():
            continue
        raw = pd.read_excel(xl, sheet, header=None)
        if "COICOP, 2018" not in str(raw.iat[0, 0]):
            raise ValueError(f"Tanzania CPI summary {sheet!r}: not the COICOP-2018 series")
        months = {}
        for c in range(3, raw.shape[1]):
            v = raw.iat[1, c]
            if hasattr(v, "year") and not isinstance(v, str):
                months[c] = f"{v.year}-{v.month:02d}"
        for r in range(2, raw.shape[0]):
            label = str(raw.iat[r, 1]).strip()
            if label == "Other Selected Groups":
                break
            sn = raw.iat[r, 0]
            if label.upper() == "INFLATION RATE":
                code, meas = "00", "inflation_yoy"
            elif label.upper() == "ALL ITEMS INDEX":
                code, meas = "00", "index"
            elif pd.notna(sn) and str(sn).strip().isdigit() and 1 <= int(sn) <= 13:
                code, meas = f"{int(sn):02d}", "index"
            else:
                continue
            for c, period in months.items():
                v = pd.to_numeric(raw.iat[r, c], errors="coerce")
                if pd.notna(v):
                    records.append({
                        "coicop_code": code,
                        "coicop_label": "All items" if code == "00" else label,
                        "geography": "National", "period": period,
                        "measure": meas, "value": float(v),
                        "unit": "percent" if meas == "inflation_yoy" else "Index",
                        "base_period": "" if meas == "inflation_yoy" else _BASE_PERIOD,
                        "frequency": "monthly"})
    out = pd.DataFrame.from_records(records)
    if out.empty or out.loc[out.measure == "index", "coicop_code"].nunique() != 14:
        raise ValueError("Tanzania CPI summary: expected All items + 13 divisions")
    # a December is printed twice (last column of its year, first of the next);
    # the two are the same published figure, kept once
    return out.drop_duplicates(["coicop_code", "period", "measure"], keep="last")


def parse(pdf_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    release = _parse_release(pdf_path)
    series = [_parse_summary(p) for p in (extras or [])
              if p.lower().endswith((".xls", ".xlsx"))]
    if not series:
        return release
    out = pd.concat([*series, release], ignore_index=True)
    return out.drop_duplicates(["coicop_code", "period", "measure"],
                               keep="last").reset_index(drop=True)


def _parse_release(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for tb in page.extract_tables():
                flat = " ".join(str(c) for r in tb for c in r if c).lower()
                if "food and non" not in flat or "clothing" not in flat or "main group" not in flat:
                    continue
                hdr = next((r for r in tb if any(_period(c) for c in r)), None)
                if hdr is None:
                    continue
                pcols = {j: p for j, c in enumerate(hdr) if (p := _period(c))}

                records = []
                for r in tb:
                    sn = [x.strip() for x in (str(r[0]).split("\n") if r and r[0] else []) if x.strip()]
                    rowtext = " ".join(str(c) for c in r if c).lower()
                    if len(sn) >= 13 and all(x.isdigit() for x in sn[:13]):
                        for ci, period in pcols.items():
                            vals = str(r[ci]).split("\n") if ci < len(r) and r[ci] else []
                            for k, s in enumerate(sn[:13]):
                                v = _num(vals[k]) if k < len(vals) else None
                                if v is not None and 1 <= int(s) <= 13:
                                    code = f"{int(s):02d}"
                                    records.append((code, DIVISIONS.get(code, ""), period, v))
                    elif "all items" in rowtext and "less" not in rowtext:
                        for ci, period in pcols.items():
                            v = _num(r[ci]) if ci < len(r) else None
                            if v is not None:
                                records.append(("00", "All items", period, v))

                if len({c for c, *_ in records if c != "00"}) >= 13:
                    out = pd.DataFrame.from_records(
                        records, columns=["coicop_code", "coicop_label", "period", "value"])
                    out = out.drop_duplicates(["coicop_code", "period"])
                    out["geography"] = "National"
                    out["measure"] = "index"
                    out["unit"] = "Index"
                    out["base_period"] = _BASE_PERIOD
                    out["frequency"] = "monthly"
                    return out

    raise ValueError("Tanzania NCPI 'Main Groups' table not found in release")
