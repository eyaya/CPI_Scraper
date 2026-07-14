"""Parser for the Stats SA CPI (COICOP) time-series workbook (P0141).

Layout (wide time series):
  - Row 1: H-codes. H03=series code, H04=product group, H13=geography,
    H17=unit, H18=base period, H25=frequency; then one MO<MM><YYYY> column
    per month.
  - Each data row = one CPI series across all months.

National CPI by COICOP division = rows where H13 == 'Total country' and the
series code is All-items (CPT00000) or a division (CPTdd000, dd = 01..13).
"""
from __future__ import annotations
import re
import pandas as pd

# CPT + 2-digit division + "000"; CPT00000 = All items.
_DIVISION_CODE = re.compile(r"^CPT(00000|(0[1-9]|1[0-3])000)$")
_MONTH_COL = re.compile(r"^MO(\d{2})(\d{4})$")


def parse(xlsx_path: str) -> pd.DataFrame:
    df = pd.read_excel(xlsx_path, sheet_name=0, header=0, dtype=str)

    month_cols = [c for c in df.columns if _MONTH_COL.match(str(c))]
    if not month_cols:
        raise ValueError("no MO<MM><YYYY> month columns found")

    nat = df[
        (df["H13"] == "Total country")
        & (df["H03"].astype(str).str.match(_DIVISION_CODE))
    ].copy()
    if nat.empty:
        raise ValueError("no Total-country division rows matched")

    # division code = 2 digits after 'CPT'
    nat["coicop_code"] = nat["H03"].str[3:5]
    nat["coicop_label"] = nat["H04"].str.strip()
    nat["unit"] = nat["H17"]
    nat["base_period"] = nat["H18"]
    nat["frequency"] = nat["H25"]

    id_cols = ["coicop_code", "coicop_label", "unit", "base_period", "frequency"]
    long = nat.melt(
        id_vars=id_cols,
        value_vars=month_cols,
        var_name="_mo",
        value_name="value",
    )

    # MO052026 -> 2026-05
    mo = long["_mo"].str.extract(_MONTH_COL)
    long["period"] = mo[1] + "-" + mo[0]
    long["geography"] = "Total country"
    long = long.drop(columns=["_mo"])

    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long = long.dropna(subset=["value"]).reset_index(drop=True)
    long["measure"] = "index"
    return long
