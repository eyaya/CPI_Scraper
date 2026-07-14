"""Parser for the Egypt CPI, from the Central Bank of Egypt (CBE) monthly
'Monetary Policy Inflation Note' PDF (Tier 3).

CAPMAS is Egypt's NSO, but its own outputs are hard to collect programmatically:
the open-data catalog (censusinfo.capmas.gov.eg) is frozen at 2020 and the main
site is a JS shell. The CBE republishes CAPMAS's **urban** CPI monthly, in
English, with a clean, stable by-division table — so that is the robust source.

The note carries several cuts, which we key apart on the `geography` column
(the tidy schema has no dedicated series/scope dimension):

* Urban        — 'Table 2. Consumer Price Index: Major Components' (base Average
                 2018/2019 = 100): per COICOP-1999 division, the index level,
                 month-on-month % and year-on-year %. This is the headline CPI.
* Urban core   — the 'Core CPI' summary row of Table 2 (all-items core), same
                 three measures. Core is computed on the urban CPI.
* Rural        — cover-page prose, annual (YoY) headline all-items only.
* Nationwide   — cover-page prose, annual (YoY) headline all-items only.

Each structured cut yields three measures for the report month (index /
inflation_mom / inflation_yoy) plus the year-ago index level (Table 2's second
index column), so one PDF also gives a month of index history — as NISR Rwanda
does. Division/core labels wrap across lines in the PDF, so we flatten the table
page and read the five numbers around each row. The rural/nationwide prose gives
the current month's and prior month's YoY, so we emit both. Egypt uses 12
divisions + All items = 13.
"""
from __future__ import annotations
import os
import re
import pdfplumber
import pandas as pd

# COICOP-1999 division -> (code, published label, anchor phrase in Table 2).
# The anchor is a distinctive leading fragment of the division's label; it must
# not collide with any 'Select aggregates' row (e.g. 'Food excl. fruits...').
_DIVISIONS = [
    ("00", "All items",                                                  r"Headline"),
    ("01", "Food and non-alcoholic beverages",                           r"Food and non-alcoholic"),
    ("02", "Tobacco and alcoholic beverages",                            r"Tobacco and alcoholic"),
    ("03", "Clothing and footwear",                                      r"Clothing and footwear"),
    ("04", "Housing, water, electricity, gas and other fuels",           r"Housing, water"),
    ("05", "Furnishings, household equipment and routine maintenance",   r"Furnishings"),
    ("06", "Medical care",                                               r"Medical care"),
    ("07", "Transportation",                                             r"Transportation"),
    ("08", "Communications",                                             r"Communications"),
    ("09", "Recreation and culture",                                     r"Recreation and culture"),
    ("10", "Education",                                                  r"Education"),
    ("11", "Hotels, cafes and restaurants",                              r"Hotels, cafes"),
    ("12", "Miscellaneous goods and services",                           r"Miscellaneous goods"),
]

_NUM = re.compile(r"-?\d+(?:\.\d+)?")
_MON_ABBR = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
             "jun": "06", "jul": "07", "aug": "08", "sep": "09", "oct": "10",
             "nov": "11", "dec": "12"}
_MON_FULL = {"january": "01", "february": "02", "march": "03", "april": "04",
             "may": "05", "june": "06", "july": "07", "august": "08",
             "september": "09", "october": "10", "november": "11",
             "december": "12"}
_TITLE_DATE = re.compile(
    r"(january|february|march|april|may|june|july|august|september|october|"
    r"november|december)\s+(\d{4})", re.IGNORECASE)

_BASE_PERIOD = "Average 2018/2019 = 100"


def _period(path: str, first_page_text: str) -> str:
    """Report month as YYYY-MM. Prefer the filename (inf_<mon>_<year>...),
    falling back to the '... : <Month> <Year>' on the note's cover page."""
    m = re.search(r"inf_([a-z]{3})_(\d{4})", os.path.basename(path), re.IGNORECASE)
    if m and m.group(1).lower() in _MON_ABBR:
        return f"{m.group(2)}-{_MON_ABBR[m.group(1).lower()]}"
    m = _TITLE_DATE.search(first_page_text)
    if not m:
        raise ValueError("could not determine report month/year")
    return f"{m.group(2)}-{_MON_FULL[m.group(1).lower()]}"


def _shift(period: str, years: int = 0, months: int = 0) -> str:
    y, m = (int(x) for x in period.split("-"))
    idx = (y * 12 + (m - 1)) - years * 12 - months
    return f"{idx // 12}-{idx % 12 + 1:02d}"


def _self_consistent(nums: list[str]) -> bool:
    """A Table-2 row is [weight, index_a_year_ago, index_now, mom%, yoy%].
    Validate the arithmetic (index_now/index_ago-1 == yoy) to identify the
    right five numbers when the PDF linearises a label away from its row."""
    if len(nums) != 5:
        return False
    w, ip, ic, _mom, yoy = (float(x) for x in nums)
    if not (0 < ip < 5000 and 0 < ic < 5000):
        return False
    return abs((ic / ip - 1.0) * 100.0 - yoy) < 0.6


def _core_row(flat: str) -> list[str]:
    """The 'Core CPI' summary row. Its five numbers sit just before OR just
    after the label depending on the month's layout, and the adjacent block on
    one side is the (also self-consistent) 'Services' row — so we disambiguate
    by core's large basket weight (~73%)."""
    i = flat.find("Core CPI")
    if i < 0:
        raise ValueError("'Core CPI' row not found in Table 2")
    before = _NUM.findall(flat[max(0, i - 80):i])[-5:]
    after = _NUM.findall(flat[i:i + 80])[:5]
    for cand in (before, after):
        if _self_consistent(cand) and 55.0 < float(cand[0]) < 90.0:
            return cand
    raise ValueError(f"could not read a valid Core CPI row (before={before}, after={after})")


def _prose_yoy(first_page_text: str, phrase: str) -> list[float] | None:
    """From the cover-page sentence containing `phrase` (e.g. 'rural headline
    inflation'), return the two annual-inflation figures it states (this month,
    then the prior month), or None if the sentence isn't present/parseable."""
    flat = re.sub(r"\s+", " ", first_page_text)
    m = re.search(re.escape(phrase) + r"(.*?)(?:\.\s|$)", flat, re.IGNORECASE)
    if not m:
        return None
    vals = re.findall(r"(-?\d+(?:\.\d+)?)\s*(?:percent|%)", m.group(1))
    if len(vals) < 2:
        return None
    return [float(vals[0]), float(vals[1])]


def parse(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        first = pdf.pages[0].extract_text() or ""
        table_text = None
        for page in pdf.pages:
            t = page.extract_text() or ""
            if "Major Components" in t and "Headline" in t:
                table_text = t
                break
    if table_text is None:
        raise ValueError("'Table 2. ... Major Components' page not found")

    period = _period(pdf_path, first)
    prev_year = _shift(period, years=1)
    prev_month = _shift(period, months=1)

    flat = re.sub(r"\s+", " ", table_text.replace("\n", " "))
    # divisions live above the 'Select aggregates' block; core is read separately
    body = flat[:flat.find("Select aggregates")] if "Select aggregates" in flat else flat

    records = []  # (code, label, geography, period, measure, value, unit, base)

    def index_and_rates(code, label, geo, idx_prev, idx_cur, mom, yoy):
        records.append((code, label, geo, period, "index", idx_cur, "Index", _BASE_PERIOD))
        records.append((code, label, geo, period, "inflation_mom", mom, "percent", ""))
        records.append((code, label, geo, period, "inflation_yoy", yoy, "percent", ""))
        records.append((code, label, geo, prev_year, "index", idx_prev, "Index", _BASE_PERIOD))

    # --- Urban: the 13 headline divisions (fail loud; this is the core deliverable)
    for code, label, anchor in _DIVISIONS:
        m = re.search(anchor, body, re.IGNORECASE)  # wording capitalisation varies by month
        if not m:
            raise ValueError(f"division {code} ({anchor!r}) not found in Table 2")
        nums = _NUM.findall(body[m.end():])[:5]
        if len(nums) < 5:
            raise ValueError(f"division {code}: expected 5 numbers, got {nums}")
        _w, ip, ic, mom, yoy = (float(x) for x in nums)
        index_and_rates(code, label, "Urban", ip, ic, mom, yoy)

    # --- Urban core: the 'Core CPI' summary row (all-items core)
    _w, ip, ic, mom, yoy = (float(x) for x in _core_row(flat))
    index_and_rates("00", "All items (core)", "Urban core", ip, ic, mom, yoy)

    # --- Rural / Nationwide: YoY headline only, from cover-page prose (best
    #     effort — the good urban+core data must not fail if the wording drifts)
    for geo, phrase in (("Rural", "rural headline inflation"),
                        ("Nationwide", "nationwide headline inflation")):
        yoys = _prose_yoy(first, phrase)
        if yoys is None:
            print(f"[Egypt] note: {geo} headline YoY not found in prose; skipped")
            continue
        cur, prev = yoys
        records.append(("00", "All items", geo, period, "inflation_yoy", cur, "percent", ""))
        records.append(("00", "All items", geo, prev_month, "inflation_yoy", prev, "percent", ""))

    out = pd.DataFrame.from_records(
        records,
        columns=["coicop_code", "coicop_label", "geography", "period", "measure",
                 "value", "unit", "base_period"],
    )
    out["frequency"] = "monthly"
    return out
