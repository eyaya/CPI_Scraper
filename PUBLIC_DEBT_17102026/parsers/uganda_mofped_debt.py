"""Uganda — Ministry of Finance, Planning and Economic Development (MoFPED),
Debt Policy and Investment Department: Annual Debt Statistical Bulletin and
Public Debt Portfolio Analysis (end-June of each fiscal year).

PUBLISHER: MoFPED (an accepted official compiler under the public-debt source
policy). The bulletin credits its tables to "MoFPED, DPID" and, for domestic
debt, the Bank of Uganda.

COVERAGE: the bulletin's headline stocks are CENTRAL GOVERNMENT public debt --
Table 4 is headed "Central Government External Debt" and Table 20 "Central
Government Domestic Debt". Guaranteed debt and SOE / local-government
liabilities are reported separately (Tables 12-14) and are NOT in the totals
read here.

TWO TABLES ARE READ:

* Table 1 "Key Macroeconomic Indicators": Total / External / Domestic debt
  stock, each in US$ billions and in Shs billions, for the three end-June
  columns printed (Jun-24, Jun-25, Jun-26 in the June 2026 edition). The
  external stock includes the SDR allocation drawdown of USD 242 million
  (footnote 1).
* Table 2 "Public Debt Cost and Risk Indicators": "Nominal debt as % GDP"
  for External, Domestic and Total, two end-June columns -> share_of_gdp. The
  GDP is UBOS's preliminary annual GDP (footnote 2); the ratio is read as
  published, never recomputed.

QUARTERLY BULLETINS are read too (see `parse`): their columns are the last
three quarter-ends, dated the same way ("Mar-26" -> "2026-03").

DATING: each figure is an END-JUNE stock (Uganda's fiscal year ends 30 June),
so the period is the reference month, "YYYY-06", with frequency monthly -- a
point-in-time month-end stock, not an annual flow. Edition after edition
accumulate by merge-on-write; a later edition's restatement of an earlier
June wins.

READ WITH PyMuPDF: pdfplumber renders Table 1 as one character per line (the
table is a rotated text frame); PyMuPDF returns each cell on its own line.

NOT READ: Table 3 (creditor type) and 3b are IMAGES with no text layer;
Tables 15-16 (domestic stock by maturity and by holder) carry three bases per
year (cost / nominal / face value) and are deferred; debt service, issuance
and risk indicators other than the % of GDP have no measure here.

CHECKS: External + Domestic = Total in both currencies for every column
(within the table's own rounding); a Table 1 row that does not yield exactly
one value per printed column raises.

CROSS-CHECK (June 2026 edition): total debt Jun-26 US$ 37.1 bn / Shs 136,063
bn; external US$ 16.30 bn / Shs 59,740 bn; domestic Shs 76,323 bn; nominal
debt % GDP Jun-26 54.3 (external 23.9, domestic 30.5).
"""
from __future__ import annotations

import re

import fitz  # PyMuPDF
import pandas as pd

_COL = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-(\d{2})$")
_MON = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct",
     "Nov", "Dec"], 1)}
_T1_ROWS = [
    ("Total Debt Stock (Billions US $)", "Total public debt", "USD billion"),
    ("External Debt Stock (US $ Billions)", "External debt", "USD billion"),
    ("Domestic Debt Stock (US $ Billions)", "Domestic debt", "USD billion"),
    ("Total Debt Stock (Shs Billions)", "Total public debt", "UGX billion"),
    ("External Debt Stock(Shs Billions)", "External debt", "UGX billion"),
    ("Domestic Debt Stock (Shs Billions)", "Domestic debt", "UGX billion"),
]


def _num(s: str) -> float:
    return float(s.replace(",", "").strip())


def _period(lab: str) -> str:
    m = _COL.match(lab)
    return f"20{m.group(2)}-{_MON[m.group(1)]:02d}"


def _lines(doc, caption: str, row: str) -> list[str]:
    # The caption also sits in the table of contents, so the page must carry
    # one of the table's own row labels too. `caption` is a regex: the annual
    # editions caption the tables "Table 1. Annual Key Macroeconomic
    # Indicators" and "Table 2. Annual Public Debt Cost and Risk Indicators"
    # (June 2024: "Table 21: Annual ..."), the 2026 editions without "Annual".
    for page in doc:
        t = page.get_text()
        if re.search(caption, t) and row in t:
            return [ln.strip() for ln in t.splitlines() if ln.strip()]
    raise ValueError(f"MoFPED bulletin: {caption!r} not found")


def _table1(doc) -> list[dict]:
    lines = _lines(doc, r"Table 1[.:]\s+(?:Annual\s+)?Key Macroeconomic Indicators",
                   "Total Debt Stock (Shs Billions)")
    cols = [ln for ln in lines if _COL.match(ln)]
    # The column heads are printed once, above the first block.
    cols = list(dict.fromkeys(cols))
    if len(cols) < 2:
        raise ValueError(f"MoFPED Table 1: column heads {cols}")
    periods = [_period(c) for c in cols]
    out, got = [], {}
    for label, comp, unit in _T1_ROWS:
        try:
            i = lines.index(label)
        except ValueError:
            raise ValueError(f"MoFPED Table 1: row {label!r} not found")
        vals = [_num(v) for v in lines[i + 1:i + 1 + len(periods)]]
        got[(comp, unit)] = vals
        for p, v in zip(periods, vals):
            out.append({"component": comp, "period": p, "frequency": "monthly",
                        "measure": "stock", "value": v, "unit": unit,
                        "series_code": "MoFPED DSB Table 1"})
    for unit, tol in (("USD billion", 0.15), ("UGX billion", 2)):
        for j, p in enumerate(periods):
            t = got[("Total public debt", unit)][j]
            s = got[("External debt", unit)][j] + got[("Domestic debt", unit)][j]
            if abs(s - t) > tol:
                raise ValueError(f"MoFPED Table 1 {p} {unit}: external + "
                                 f"domestic = {s}, total {t}")
    return out


def _table2(doc) -> list[dict]:
    lines = _lines(doc, r"Table 21?[.:]\s+(?:Annual\s+)?Public Debt Cost and Risk Indicators",
                   "Nominal debt as % GDP")
    # PyMuPDF gives one cell per line: the end-June heads ("Jun-25",
    # "Jun-26"), then the row label printed twice (category | indicator
    # column), then External / Domestic / Total for each head in turn.
    # Table 2 prints no month heads of its own in the QUARTERLY bulletins; the
    # page's month labels arrive in first-appearance order, which is not the
    # column order. The columns run chronologically (the Dec 2025 issue's first
    # column, 51.3, is June 2025 -- its footnote says so, and the June 2026
    # annual prints the same), so the periods are SORTED.
    periods = sorted(_period(ln) for ln in dict.fromkeys(l for l in lines if _COL.match(l)))
    i = max(j for j, ln in enumerate(lines) if ln == "Nominal debt as % GDP")
    nums = [float(x) for x in lines[i + 1:i + 1 + 3 * len(periods)]]
    if len(periods) < 1 or len(nums) != 3 * len(periods):
        raise ValueError(f"MoFPED Table 2: {nums} for periods {periods}")
    for j in range(len(periods)):
        ext, dom, tot = nums[3 * j:3 * j + 3]
        if abs(ext + dom - tot) > 0.15:
            raise ValueError(f"MoFPED Table 2 {periods[j]}: {ext} + {dom} != {tot}")
    out = []
    for j, p in enumerate(periods):
        for k, comp in enumerate(("External debt", "Domestic debt",
                                  "Total public debt")):
            out.append({"component": comp, "period": p, "frequency": "monthly",
                        "measure": "share_of_gdp", "value": nums[3 * j + k],
                        "unit": "percent", "series_code": "MoFPED DSB Table 2"})
    return out


def _parse_one(path: str) -> list[dict]:
    with fitz.open(path) as doc:
        return _table1(doc) + _table2(doc)


_KEY = ["component", "period", "measure", "unit"]


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """The primary (newest) bulletin must parse whole. BACK ISSUES -- the
    QUARTERLY bulletins (Dec 2025, Mar 2026) and the June 2025 and June 2024
    ANNUAL editions, which print Tables 1-2 in the same layout -- are read
    newest first, and an issue failing either table is skipped WHOLE with a
    message (Sep 2025 prints its Total rows blank and Table 2 without column
    heads; Mar 2025 prints Table 1 with labels and values interleaved; the
    Dec 2021-Dec 2023 issues are image scans, not OCR'd). Where two issues print
    the same month, the issue listed earlier (newer) wins and the difference
    is printed."""
    frames = [pd.DataFrame(_parse_one(path))]
    for p in extras or []:
        try:
            frames.append(pd.DataFrame(_parse_one(p)))
        except (ValueError, IndexError) as e:
            print(f"  [uganda] back issue skipped ({p.replace(chr(92), '/').rsplit('/', 1)[-1]}): {e}")
    df = pd.concat(frames, ignore_index=True)
    first = df.drop_duplicates(_KEY, keep="first")
    diff = df.merge(first, on=_KEY, suffixes=("", "_kept"))
    diff = diff[(diff["value"] - diff["value_kept"]).abs() > 1e-9]
    for _, r in diff.iterrows():
        print(f"  [uganda] revision {r['component']} {r['period']} {r['unit']}: "
              f"{r['value']} -> {r['value_kept']} (newer issue kept)")
    return first.reset_index(drop=True)
