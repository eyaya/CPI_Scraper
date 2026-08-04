"""Parser for the Statistics Botswana monthly CPI report PDF (Tier 3).

Statistics Botswana publishes a monthly CPI report; its 'Table 3: National
Consumer Price Group And Section Indices' (base December 2018 = 100) gives the
index by COICOP-1999 group for several months:

  GROUP SECTION | WEIGHTS | Mar 2026 | Feb 2026 | Dec 2025 | Sep 2025 | Mar 2025
  1  Food & Non-Alcoholic … | 13.55 | 160.6 | 159.2 | 156.6 | 155.3 | 151.8
  …
  All-Items (National)      | 100.0 | …

The column headers render right-to-left in the PDF ('HTNOM 6202 SIHT RAM' =
'MAR THIS 2026 MONTH'), so we reverse each header cell to read its month/year.
Group rows carry an integer code (1..12); section rows (1.1, 1.2, …) are skipped;
'All-Items' is All items (00). The table spans two pages — the continuation has
no header, so the period columns are carried forward. We emit the index for each
dated column (so one report yields several months).
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_BASE_PERIOD = "Dec 2018 = 100"
_MONTHS = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
           "jun": "06", "jul": "07", "aug": "08", "sep": "09", "oct": "10",
           "nov": "11", "dec": "12"}
# Botswana's 12 groups are COICOP-1999; the group number maps straight to a code.
_LABELS = {
    "01": "Food & non-alcoholic beverages", "02": "Alcoholic beverages & tobacco",
    "03": "Clothing & footwear", "04": "Housing, water, electricity, gas & other fuels",
    "05": "Furnishing, household equipment & routine maintenance", "06": "Health",
    "07": "Transport", "08": "Communication", "09": "Recreation & culture",
    "10": "Education", "11": "Restaurants & hotels", "12": "Miscellaneous goods & services",
}


def _period(cell) -> str | None:
    if not isinstance(cell, str):
        return None
    rev = cell.replace("\n", " ")[::-1]          # headers are rendered right-to-left
    yr = re.search(r"20\d\d", rev)
    mon = next((_MONTHS[t[:3].lower()] for t in re.findall(r"[A-Za-z]{3,}", rev)
                if t[:3].lower() in _MONTHS), None)
    return f"{yr.group()}-{mon}" if yr and mon else None


def _num(s) -> float | None:
    if isinstance(s, (int, float)):
        return float(s)
    if isinstance(s, str) and re.fullmatch(r"\d+\.\d+", s.strip()):
        return float(s.strip())
    return None


def parse(pdf_path: str) -> pd.DataFrame:
    records: list[tuple] = []
    pcols: dict[int, str] = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # restrict to the 'Table 3' pages (header + its continuation), so the
            # period columns can't leak onto unrelated tables (e.g. Table 6 rates)
            if "national consumer price group" not in (page.extract_text() or "").lower():
                continue
            for tb in page.extract_tables():
                for r in tb:
                    cand = {j: p for j, c in enumerate(r) if (p := _period(c))}
                    if len(cand) >= 3:
                        pcols = cand      # Table 3's header; carried to the continuation page
                        break
                if not pcols:
                    continue
                for r in tb:
                    c0 = str(r[0]).strip() if r and r[0] else ""
                    rowtext = " ".join(str(c) for c in r if c).lower()
                    if re.fullmatch(r"\d{1,2}", c0) and 1 <= int(c0) <= 12:
                        code, label = f"{int(c0):02d}", None
                    elif "all-items" in rowtext or "all items" in rowtext:
                        code, label = "00", "All items"
                    else:
                        continue
                    label = label or _LABELS.get(code, "")
                    for j, period in pcols.items():
                        v = _num(r[j] if j < len(r) else None)
                        if v is not None:
                            records.append((code, label, period, v))
            if "00" in {c for c, *_ in records} and len({c for c, *_ in records if c != "00"}) >= 12:
                break

    divisions = {c for c, *_ in records if c != "00"}
    if "00" not in {c for c, *_ in records} or len(divisions) < 12:
        raise ValueError(f"Botswana CPI 'Table 3' incomplete: got {sorted(set(c for c,*_ in records))}")

    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "value"])
    out = out.drop_duplicates(["coicop_code", "period"])
    out["geography"] = "National"
    out["measure"] = "index"
    out["unit"] = "Index"
    out["base_period"] = _BASE_PERIOD
    out["frequency"] = "monthly"
    return out
