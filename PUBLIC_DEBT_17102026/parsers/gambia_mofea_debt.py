"""The Gambia -- Ministry of Finance and Economic Affairs (MoFEA), quarterly
"Debt Bulletin" (mofea.gov.gm, WordPress uploads, 2023 Q3 onward).

PUBLISHER: MoFEA (the Directorate of Loans and Debt Management) -- an accepted
official national compiler under this indicator's source policy.

COVERAGE: central government public debt -- external debt, domestic debt
securities (at book value) and the domestic standard loan owed to SSHFC.

THE BULLETIN'S TABLES CHANGE FROM ISSUE TO ISSUE, so each table below is read
wherever it appears, by its own caption, and an issue carrying none of them
contributes nothing (and says so):

* "Composition of the public debt portfolio, end-<Month> <year>" (2026 Q2
  onward): each component in GMD billion and US$ billion, % of total and
  % of GDP.
* "DEBT TO GDP COMPARISON FOR Q<n> OF <year> TO Q<n> OF <year>" (2026 Q1):
  domestic, external and total debt for two quarters, and debt/GDP. The table
  prints no unit; its total (140.46 for 2026 Q1) is the bulletin's own "GMD
  140.46 billion" in its text, so the unit is GMD billion.
* "External Debt Stock by Creditor Category" (US$ billion and % of external
  debt) and "External Debt by Interest Type" (US$ MILLION and %).

DATING: a quarter is read from the table's own caption, or from the
bulletin's "<FIRST|SECOND|THIRD|FOURTH> QUARTER <year>" title where the table
carries none. Year-end figures sit under their quarter (YYYY-Q4).

PUBLISHED INCONSISTENCY KEPT: the 2026 Q2 bulletin's text gives debt/GDP of
68.98% while its Table 1 prints 68.96%; the table is collected.

NOT READ: bulletins before 2026 (their portfolio tables are laid out
differently in every issue); debt service, disbursements, issuance and
maturity-profile tables (not stocks); the creditor-by-creditor list.

CROSS-CHECK (printed): end-June 2026 total public debt GMD 141.41bn / US$1.96bn,
external 62.61% of total, 68.96% of GDP; 2026 Q1 total 140.46 (debt/GDP
68.52); 2025 Q4 total 140.32 (70.97); 2026 Q1 multilateral US$0.86bn (71%).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_Q = {"first": 1, "second": 2, "third": 3, "fourth": 4}
_MQ = {m: (i - 1) // 3 + 1 for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
_N = r"\d[\d,]*\.\d+"
SERIES = "MoFEA quarterly debt bulletin"


def _issue_quarter(text: str) -> str:
    m = re.search(r"(FIRST|SECOND|THIRD|FOURTH)\s+QUARTER[^\n\d]{0,30}(20\d\d)", text, re.I)
    if not m:
        m2 = re.search(r"\bQ([1-4])[\s-]*(20\d\d)", text)
        if not m2:
            raise ValueError("Gambia bulletin: cannot date the issue")
        return f"{m2.group(2)}-Q{m2.group(1)}"
    return f"{m.group(2)}-Q{_Q[m.group(1).lower()]}"


def _f(s: str) -> float:
    return float(s.replace(",", "").rstrip("%"))


def _rec(comp, period, measure, value, unit, code):
    return dict(component=comp, period=period, frequency="quarterly",
                measure=measure, value=value, unit=unit, series_code=code)


def _composition(text: str) -> list[dict]:
    m = re.search(r"Composition of the public debt portfolio, end-([A-Za-z]+)\s+(20\d\d)", text)
    if not m:
        return []
    period = f"{m.group(2)}-Q{_MQ[m.group(1).lower()]}"
    out = []
    body = text[m.end():].split("Note", 1)[0]
    for ln in body.splitlines():
        r = re.match(rf"^(.+?)\s+({_N})\s+({_N})\s+({_N})\s+({_N})\s*$", ln.strip())
        if not r:
            continue
        lab = r.group(1).strip()
        gmd, usd, pct, gdp = (_f(r.group(i)) for i in range(2, 6))
        code = SERIES + ": composition"
        out += [_rec(lab, period, "stock", gmd, "GMD billion", code),
                _rec(lab, period, "stock", usd, "USD billion", code),
                _rec(lab, period, "share", pct, "percent", code),
                _rec(lab, period, "share_of_gdp", gdp, "percent", code)]
    if not any(o["component"].lower().startswith("total public debt") for o in out):
        raise ValueError("Gambia composition table: no Total public debt row")
    return out


def _gdp_comparison(text: str) -> list[dict]:
    if not re.search(r"DEBT TO GDP COMPARISON", text, re.I):
        return []
    out, code = [], SERIES + ": debt to GDP comparison"
    for m in re.finditer(rf"(20\d\d)\s*\(\s*Q\s*([1-4])\s*\)\s+({_N})\s+({_N})\s+({_N})\s+({_N})",
                         text):
        period = f"{m.group(1)}-Q{m.group(2)}"
        dom, ext, tot, gdp = (_f(m.group(i)) for i in range(3, 7))
        if abs(dom + ext - tot) > 0.02:
            raise ValueError(f"Gambia {period}: domestic + external != total")
        out += [_rec("Domestic debt", period, "stock", dom, "GMD billion", code),
                _rec("External debt", period, "stock", ext, "GMD billion", code),
                _rec("Total debt stock", period, "stock", tot, "GMD billion", code),
                _rec("Total debt stock", period, "share_of_gdp", gdp, "percent", code)]
    return out


def _external_tables(text: str, period: str) -> list[dict]:
    out = []
    specs = [
        (r"External Debt Stock by Creditor Category", "USD billion",
         SERIES + ": external debt by creditor category"),
        (r"External Debt by Interest Type", "USD million",
         SERIES + ": external debt by interest type"),
    ]
    for cap, unit, code in specs:
        m = re.search(cap, text, re.I)
        if not m:
            continue
        for ln in text[m.end():].splitlines()[1:8]:
            r = re.match(rf"^(.+?)\s+({_N}|\d[\d,]*)\s+({_N}|\d+)%\s*$", ln.strip())
            if not r:
                if re.match(r"^(Table|T\s?able)\b", ln.strip(), re.I):
                    break
                continue
            lab = r.group(1).strip()
            out += [_rec(lab, period, "stock", _f(r.group(2)), unit, code),
                    _rec(lab, period, "share", _f(r.group(3)), "percent", code)]
    return out


def _parse_one(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    period = _issue_quarter(text)
    rows = _composition(text) + _gdp_comparison(text) + _external_tables(text, period)
    if not rows:
        print(f"[gambia_mofea] {path}: none of the known tables -- skipped")
    return rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [*(extras or []), path]:          # the current issue last: it wins
        rows += _parse_one(p)
    if not rows:
        raise ValueError("Gambia: no debt table read from the current bulletin")
    df = pd.DataFrame(rows)
    key = ["component", "period", "frequency", "measure", "unit", "series_code"]
    return df.drop_duplicates(key, keep="last").reset_index(drop=True)
