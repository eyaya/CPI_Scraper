"""Fallback parser for Kenya: Central Bank of Kenya (CBK) headline inflation.

The primary Kenya source is the KNBS monthly CPI PDF (by division). When KNBS is
unreachable, this fallback scrapes CBK's inflation-rates page — an HTML table of
the monthly headline series:

  Year | Month | Annual Average | 12-Month Inflation
  2026 | June  | 4.88           | 6.41

CBK publishes only the headline (all-items) figure, not a division breakdown, so
this is a deliberately degraded fallback: we emit the 12-month (year-on-year)
inflation for All items (00) across the full series. No index level / no
divisions — hence the descriptor's fallback sets expect_divisions: 1.
"""
from __future__ import annotations
import re
from bs4 import BeautifulSoup
import pandas as pd

_MONTHS = {"january": "01", "february": "02", "march": "03", "april": "04",
           "may": "05", "june": "06", "july": "07", "august": "08",
           "september": "09", "october": "10", "november": "11", "december": "12"}


def parse(html_path: str) -> pd.DataFrame:
    with open(html_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f.read(), "html.parser")

    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header = [c.get_text(" ", strip=True).lower() for c in rows[0].find_all(["th", "td"])]
        yr = next((i for i, h in enumerate(header) if h == "year"), None)
        mo = next((i for i, h in enumerate(header) if h == "month"), None)
        yoy = next((i for i, h in enumerate(header)
                    if "inflation" in h and ("12" in h or "month" in h)), None)
        if yr is None or mo is None or yoy is None:
            continue

        records = []
        for tr in rows[1:]:
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) <= max(yr, mo, yoy):
                continue
            month = _MONTHS.get(cells[mo].strip().lower())
            v = pd.to_numeric(cells[yoy].replace("%", "").strip(), errors="coerce")
            if not (re.fullmatch(r"\d{4}", cells[yr].strip()) and month) or pd.isna(v):
                continue
            records.append(("00", "All items", f"{cells[yr].strip()}-{month}",
                            "inflation_yoy", round(float(v), 4)))

        if records:
            out = pd.DataFrame.from_records(
                records, columns=["coicop_code", "coicop_label", "period", "measure", "value"])
            out = out.drop_duplicates(["coicop_code", "period", "measure"])
            out["geography"] = "National"
            out["unit"] = "percent"
            out["base_period"] = ""
            out["frequency"] = "monthly"
            return out

    raise ValueError("CBK inflation table not found")
