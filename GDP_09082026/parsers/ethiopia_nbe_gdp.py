"""Parser for the National Bank of Ethiopia annual report GDP table (PDF).

Ethiopia's GDP is compiled by the Ministry of Planning and Development and
published in the NBE Annual Report ('Table 1.1: Sectoral Contributions to GDP and
GDP Growth', in billions of Birr, real terms base 2015/16). The table gives, by
Ethiopian fiscal year (2017/18 … 2024/25):

  Agriculture / Industry / Services   -> real value added by sector (level, constant)
  Total, Real GDP                     -> aggregate real GDP (level, constant)
  Growth in Real GDP                  -> real GDP growth (%)
  Per capita GDP (USD, Nominal)       -> per-capita (USD)
  Share in GDP (%) by sector          -> sector shares (%)

Periods are Ethiopian fiscal years, labelled here by the START year (2017/18 ->
2017). Some labels wrap onto the line above their figures ('Real GDP', 'Per
capita GDP (USD)') and the sector names repeat in the shares block, so the page is
split at 'Share in GDP' and a pending-label is carried for value-only lines. Units
billion Birr (levels), percent (growth/share), USD (per capita). Verified: Real
GDP 2024/25 = 2,842.3 billion Birr, growth 9.2%. Nothing derived.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]

_FY_RE = re.compile(r"(20\d\d)/\d{2}")
_NUM_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")
_SECTORS = {"agriculture", "industry", "services"}


def _nums(line):
    return [float(x.replace(",", "")) for x in _NUM_RE.findall(line)]


def parse(pdf_path: str) -> pd.DataFrame:
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        page = next((p for p in pdf.pages
                     if re.search(r"sectoral contributions to gdp",
                                  p.extract_text() or "", re.I)), None)
        if page is None:
            raise ValueError("NBE GDP table (Table 1.1) not found")
        text = page.extract_text() or ""
        hdr = next((l for l in text.split("\n") if len(_FY_RE.findall(l)) >= 5), "")
        periods = [m.group(1) for m in _FY_RE.finditer(hdr)]
        n = len(periods)
        if n < 5:
            raise ValueError("no fiscal-year header on NBE GDP table")

        def emit(label, vals, measure, approach, basis, unit, base):
            for period, v in zip(periods, vals[-n:]):
                rows.append({
                    "approach": approach, "category": label, "category_group": "",
                    "series_code": "", "geography": "National", "period": period,
                    "frequency": "annual", "price_basis": basis,
                    "seasonal_adjustment": "nsa", "measure": measure,
                    "value": v, "unit": unit, "base_period": base,
                })

        # one pass; a sector line is a level (>100 bn Birr) or a share (<100 %)
        # by magnitude, which sidesteps the mis-positioned 'Share in GDP' label.
        pending = ""
        for line in text.split("\n"):
            vals = _nums(line)
            label = _NUM_RE.split(line)[0].strip(" .:-") if vals else line.strip()
            if not vals or len(vals) < n:
                if re.search(r"[A-Za-z]{3}", line) and not vals:
                    pending = re.sub(r"\s+", " ", line).strip()
                continue
            lab = label if re.search(r"[A-Za-z]{3}", label) else pending
            low = lab.lower()
            pending = ""
            if "growth in per capita" in low or "population" in low or "fisim" in low:
                continue
            sector = next((s for s in _SECTORS if s in low), None)
            if sector:
                if max(abs(v) for v in vals[-n:]) < 100:
                    emit(sector.title(), vals, "share", "production", "current", "percent", "")
                else:
                    emit(sector.title(), vals, "level", "production", "constant", "billion Birr", "2015/16")
            elif low in ("total", "real gdp"):
                emit(lab, vals, "level", "aggregate", "constant", "billion Birr", "2015/16")
            elif "growth in real gdp" in low:
                emit("Real GDP", vals, "growth_yoy", "aggregate", "constant", "percent", "2015/16")
            elif "per capita gdp" in low or low == "(nominal)":
                emit("GDP per capita", vals, "per_capita", "aggregate", "current", "USD", "")

    if not rows:
        raise ValueError("no GDP rows parsed from NBE Ethiopia report")
    return pd.DataFrame.from_records(rows)[_OUT_COLS].drop_duplicates(
        ["approach", "category", "period", "measure", "price_basis"])
