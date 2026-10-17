"""Zambia -- Bank of Zambia, "Statistics Fortnightly", Table 17 "Treasury
Bills Transactions & Outstanding Balances" and Table 18 "GRZ Bonds
Transactions & Outstanding Balances" (K'000).

PUBLISHER: Bank of Zambia. COVERAGE: central government DOMESTIC MARKETABLE
SECURITIES only -- Treasury bills and GRZ bonds outstanding. This is NOT total
public debt: external debt, loans and arrears are not in these tables, and
Table 18's own note says "The Outstanding GRZ Bond does not include the mega
bonds, which were loans advanced to Government by the Bank of Zambia". Neither
BoZ nor the Ministry of Finance and National Planning publishes a public-debt
STOCK table on its site (checked 2026-10-08: BoZ's Drupal file store has no
debt file; MoFNP's posts are restructuring announcements).

COLLECTED, from the monthly block of each table (Table 17 heads it "Monthly
Totals"; the weekly block that follows is not read): the outstanding balance by tenor and in total --
Table 17's last five columns (91 / 182 / 273 / 364 days, total = j+k+l+m)
and Table 18's last seven (2 / 3 / 5 / 7 / 10 / 15 year, TOTAL). Sales,
maturities, settlement values and off-tender figures are FLOWS and are not
collected. Each issue prints January of two years back to date, so history
accumulates on merge. Every month is checked: the tenors sum to the printed
total (to K 1 thousand).

Units "ZMW thousand" (the tables' "K' 000"), values as printed with their
two decimals.

CROSS-CHECK (Vol 33 No 19): T-bills outstanding January 2024 total
45 561 870.19 (as the February opening balance confirms); GRZ bonds
outstanding January 2024 TOTAL 180 072 699.97 (15-year 41 015 029.07).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_UNIT = "ZMW thousand"
_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}
_NUM = re.compile(r"-?\d{1,3}(?:,\d{3})*\.\d{2}")
# key -> [(caption, stock tenors as printed)], comp, code, full row width.
# Issues to 2021 caption Table 18 "GRZ BOND TRANSACTIONS & OUTSTANDING
# GOVERNMENT BONDS" and head its shortest stock column "24 months"; from 2022
# it is "GRZ BONDS TRANSACTIONS & OUTSTANDING BALANCES" and "2 year". Each is
# kept as printed. ROW WIDTH: a monthly row prints every column (Table 17: 14
# numbers -- opening balance, four sales, total sales, settlement cost,
# maturities, off-tender, four outstanding tenors, total; Table 18: 19 -- six
# tenors' sales and maturities, then seven stocks). A SHORTER row is a month
# printed before its balances were final (December 2023 in Vol 30 No 26: the
# flows only); its last numbers are flows, so it is skipped, never read.
_TABLES = {
    "Table 17": ([("TREASURY BILLS TRANSACTIONS & OUTSTANDING BALANCES",
                   ["91 days", "182 days", "273 days", "364 days", "total"])],
                 "Treasury bills outstanding", "BoZ SF T17", 14),
    "Table 18": ([("GRZ BONDS TRANSACTIONS & OUTSTANDING BALANCES",
                   ["2 year", "3 year", "5 year", "7 year", "10 year", "15 year",
                    "total"]),
                  ("GRZ BOND TRANSACTIONS & OUTSTANDING GOVERNMENT BONDS",
                   ["24 months", "3 year", "5 year", "7 year", "10 year",
                    "15 year", "total"])],
                 "GRZ bonds outstanding", "BoZ SF T18", 19),
}


def _read(text: str, tenors, comp, code, width):
    # The monthly block runs from the first year line (Table 17 heads it
    # "Monthly Totals", Table 18 does not) to "Week-ending".
    out, year = [], None
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("Week-ending") or s.startswith("Note"):
            break
        if re.fullmatch(r"20\d\d", s):
            year = int(s)
            continue
        m = re.match(r"^([A-Za-z]+)\s", s)
        if not (m and m.group(1).lower() in _MONTHS and year):
            continue
        nums = [float(v.replace(",", "")) for v in _NUM.findall(s)]
        if len(nums) < width:
            print(f"  [zambia] {code} {year} {m.group(1)}: {len(nums)} of {width} "
                  f"columns printed (balances not yet final) -- skipped")
            continue
        stocks = dict(zip(tenors, nums[-len(tenors):]))
        if abs(sum(v for k, v in stocks.items() if k != "total") - stocks["total"]) > 1.0:
            raise ValueError(f"{code} {year}-{m.group(1)}: tenors do not sum to total")
        period = f"{year}-{_MONTHS[m.group(1).lower()]:02d}"
        for t, v in stocks.items():
            out.append({"component": f"{comp}: {t}" if t != "total" else f"{comp}: total",
                        "period": period, "frequency": "monthly", "measure": "stock",
                        "value": v, "unit": _UNIT, "series_code": code})
    return out


def _parse_pdf(path: str) -> pd.DataFrame:
    recs = []
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    for key, (variants, comp, code, width) in _TABLES.items():
        hit = next(((t, tenors) for t in pages for title, tenors in variants
                    if title in t and key in t), None)
        if hit is None:
            raise ValueError(f"BoZ: {key} ({variants[0][0]}) not found")
        got = _read(hit[0], hit[1], comp, code, width)
        if len(got) < 12 * len(hit[1]):
            raise ValueError(f"BoZ {key}: only {len(got) // len(hit[1])} months read")
        recs += got
    return pd.DataFrame(recs)


_KEY = ["component", "period", "unit", "series_code"]


def parse(path: str, extras=None) -> pd.DataFrame:
    """The primary (newest) issue must parse. BACK ISSUES (extras), newest
    first: year-end Statistics Fortnightly PDFs -- each prints its tables from
    January (or July) two years back -- and BoZ's FORTNIGHTLY TIMESERIES
    workbook, whose Table 17 / Table 18 sheets carry the monthly blocks from
    2009 to mid-2016/2017 (parsers/zambia_boz_timeseries.py).

    THE NEWEST PRINTING OF A MONTH OWNS THAT MONTH'S TABLE: a month printed
    by several issues is taken whole from the newest (the order given), and
    the older printings of that table-month are dropped -- not merged row by
    row, which would file one month's bonds under both "24 months" (issues to
    2021) and "2 year" (from 2022). Value differences on rows both printings
    share are printed as revisions."""
    from .zambia_boz_timeseries import parse_workbook
    frames = [_parse_pdf(path)]
    for p in extras or []:
        name = p.replace(chr(92), "/").rsplit("/", 1)[-1]
        try:
            frames.append(parse_workbook(p) if p.lower().endswith(".xlsx")
                          else _parse_pdf(p))
        except ValueError as e:
            print(f"  [zambia] back issue skipped ({name}): {e}")
    owned, kept = set(), []
    for f in frames:
        tm = set(zip(f["series_code"], f["period"]))
        kept.append(f[[k not in owned for k in zip(f["series_code"], f["period"])]])
        owned |= tm
    first = pd.concat(kept, ignore_index=True)
    df = pd.concat(frames, ignore_index=True)
    if first.duplicated(_KEY).any():
        raise ValueError("BoZ: an issue prints the same month twice")
    diff = df.merge(first, on=_KEY, suffixes=("", "_kept"))
    diff = diff[(diff["value"] - diff["value_kept"]).abs() > 0.005]
    for _, r in diff.iterrows():
        print(f"  [zambia] revision {r['component']} {r['period']}: "
              f"{r['value']} -> {r['value_kept']} (newer printing kept)")
    return first.reset_index(drop=True)
