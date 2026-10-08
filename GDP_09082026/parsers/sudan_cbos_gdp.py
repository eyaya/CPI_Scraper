"""Sudan — GDP of the Central Bureau of Statistics (CBS), as republished in
the Central Bank of Sudan's (CBOS) English Annual Report, Chapter 7 "National
Accounts".

CENTRAL-BANK FALLBACK. CBS has no reachable website (cbs.gov.sd does not
resolve), and the Wayback Machine was offline when this source was built. CBOS
reprints CBS's national accounts unchanged, every table footed "Source:
Central Bureau of Statistics" -- the same sanctioned route as Sudan's CPI
(CBOS review, Table 20). CBOS's English annual reports stop at 2018 (the 58th
report); the newest edition available is therefore the primary file.

TERRITORY: these are post-2011 figures for the Republic of the Sudan, i.e.
EXCLUDING South Sudan.

Each report covers its year (preliminary) and the year before (amended):

* Table 7-1  GDP at CONSTANT 1981/82 prices by economic activity -- value (SDG
             million), real growth (%) and share (%) -- plus the GDP deflator
             and GDP at current prices (a cross-reference to Table 7-3);
* Table 7-2  real GDP growth rates over five years;
* Table 7-3  GDP at CURRENT prices by economic activity -- value, nominal
             growth, share;
* Table 7-4  GDP at current prices by EXPENDITURE -- value, nominal growth,
             share.

THE CONSTANT-PRICE LEVELS ARE TINY (GDP 2018: 36.7 SDG million at 1981/82
prices) because the base predates two currency redenominations; they are
published so and kept. Values in parentheses are negative.

ONE FIGURE, ONE ROW: GDP at current prices appears in 7-1, 7-3 and 7-4 and
2017-18 real growth in 7-1 and 7-2; each repeat is checked equal and emitted
once (7-3 / 7-1). Where reports overlap (a year preliminary in one edition,
amended in the next) the NEWEST edition wins.

IDENTITIES CHECKED (current prices): the three sectors sum to GDP; industry's
and services' sub-activities sum to their sector; consumption = government +
private; investment = capital formation + change in inventory; net foreign
transactions = exports - imports; consumption + investment + net = GDP.

OLDER EDITIONS NOT YET READ: the 2015 and 2016 reports carry the same four
tables but wrap labels differently ("Agriculture, Livestock, Forests &" /
"Fisheries" with values split across the wrap); `parse` accepts them as extras
and skips any that fails its checks, announcing it. They would add 2013-2016.

LABELS AS PRINTED, truncations included ("Exports of goods and", "Transport,
Communication and Saving").

CROSS-CHECK (2018 report): GDP 2018 current 1,176,630.0; real growth 2018
2.8%; GDP deflator 2018 32,074.0; private consumption 2018 1,010,751.3.
"""
from __future__ import annotations

import re

import fitz
import pandas as pd

_UNIT = "SDG million"
_BASE = "Constant 1981/82 prices"
_NUM = re.compile(r"^\(?-?\d[\d,]*(?:\.\d+)?\)?\*{0,4}$")
_CAPS = {
    "7-1": r"Gross\s+Domestic\s+Product\s+at\s+Constant\s+Prices\s+by\s+Economic\s+Activities",
    "7-2": r"GDP\s+Growth\s+Rates?\s+During\s+the\s+Period",
    "7-3": r"Gross\s+Domestic\s+Product\s+at\s+Current\s+Prices\s+by\s+Economic\s+Activities",
    "7-4": r"Gross\s+Domestic\s+Product\s+at\s+Current\s+Prices\s+by\s+Expenditure",
}


def _num(t: str) -> float:
    neg = t.startswith("(")
    v = float(t.strip("()*").replace(",", ""))
    return -v if neg else v


def _tokens(doc, code: str) -> list[str] | None:
    """Cells of a table, one per line in PyMuPDF, from its caption to Source."""
    pat = re.compile(_CAPS[code], re.I)
    for page in doc:
        text = page.get_text()
        flat = re.sub(r"\s+", " ", text)
        if not (pat.search(flat) and "Source" in text and "Bureau" in text):
            continue
        cells = [c.strip() for c in text.splitlines() if c.strip()]
        # start after the caption's last line, end at the Source line
        start = next(i for i, c in enumerate(cells)
                     if pat.search(re.sub(r"\s+", " ", " ".join(cells[max(0, i - 2):i + 1]))))
        end = next(i for i in range(start, len(cells)) if cells[i].startswith("Source"))
        out = cells[start + 1:end]
        # "( | 44.2 | )" -> "(44.2)"
        joined, i = [], 0
        while i < len(out):
            if out[i] == "(" and i + 2 < len(out) and out[i + 2] == ")":
                joined.append(f"({out[i + 1]})")
                i += 3
            else:
                joined.append(out[i])
                i += 1
        return joined
    return None


def _years(toks):
    return [re.sub(r"\D", "", t) for t in toks if re.fullmatch(r"(19|20)\d\d\*{0,2}", t)]


def _rows(toks, width, short_rows=False):
    """(label, [numbers]) after the header, `width` numbers per row (2 for the
    deflator / current-GDP cross-reference rows of 7-1)."""
    i = next(i for i, t in enumerate(toks) if re.fullmatch(r"Share\s*%?|%", t)
             and i > 3 and not any(re.fullmatch(r"Share.*|%", x) for x in toks[i + 1:i + 2]))
    label, nums, rows = [], [], []
    for t in toks[i + 1:]:
        if _NUM.match(t):
            nums.append(_num(t))
            short = short_rows and re.match(r"GDP (Deflator|at Current)", " ".join(label))
            if len(nums) == (2 if short else width):
                lab = re.sub(r"\s+", " ", " ".join(label)).strip(" *")
                # the column header ("Value Growth Rate % Share %") reaches the
                # first row's label in the text layer
                lab = re.sub(r"^(?:Value Growth Rate ?% Share ?%? ?)+", "", lab).strip()
                rows.append((lab, nums))
                label, nums = [], []
        else:
            if nums:
                raise ValueError(f"CBOS: row {' '.join(label)!r} cut short at {nums}")
            label.append(t)
    return rows


def _check(cond, msg):
    if not cond:
        raise ValueError(f"CBOS GDP: {msg}")


def _row(approach, cat, code, year, basis, measure, value, unit):
    return dict(approach=approach, category=cat, category_group=f"Table {code}",
                series_code=f"T{code}", period=year, frequency="annual",
                price_basis=basis, measure=measure, value=value, unit=unit,
                base_period=_BASE if (basis == "constant" and measure == "level") else "")


_SECTORS = ("Agriculture", "Processing Industries, Handcraft", "Services")


def _report(path: str) -> list[dict]:
    doc = fitz.open(path)
    out = []
    t71, t73, t74, t72 = (_tokens(doc, c) for c in ("7-1", "7-3", "7-4", "7-2"))
    _check(t73 and t74, f"{path}: tables 7-3 / 7-4 not found")
    years = _years(t73)[:2]
    _check(len(years) == 2, f"{path}: years {years}")
    gdp_cur = {}
    for code, toks, appr in (("7-3", t73, "production"), ("7-4", t74, "expenditure")):
        rows = _rows(toks, 6)
        vals = {}
        for lab, n in rows:
            vals[lab] = n
            is_gdp = lab.startswith("GDP at Current")
            if is_gdp and code == "7-4":
                _check(all(abs(gdp_cur[y] - n[3 * j]) < 0.05 for j, y in enumerate(years)),
                       "7-4 GDP differs from 7-3")
                continue
            for j, y in enumerate(years):
                a = "aggregate" if is_gdp else appr
                if is_gdp:
                    gdp_cur[y] = n[3 * j]
                out.append(_row(a, lab, code, y, "current", "level", n[3 * j], _UNIT))
                out.append(_row(a, lab, code, y, "current", "growth_yoy", n[3 * j + 1], "percent"))
                out.append(_row(a, lab, code, y, "current", "share", n[3 * j + 2], "percent"))
        # identities
        for j, y in enumerate(years):
            v = lambda prefix: next(n[3 * j] for lab, n in rows if lab.startswith(prefix))
            if code == "7-3":
                _check(abs(sum(v(s) for s in _SECTORS) - gdp_cur[y]) < 1.5,
                       f"7-3 {y}: sectors do not sum to GDP")
                ind = [n[3 * j] for lab, n in rows if lab.startswith(("Processing Industries and",
                       "Mining", "Electricity", "Building"))]
                _check(abs(sum(ind) - v("Processing Industries, Handcraft")) < 1.5, f"7-3 {y}: industry")
            else:
                _check(abs(v("Government") + v("Private") - v("Consumption")) < 0.5, f"7-4 {y}: consumption")
                _check(abs(v("Capital") + v("Change") - v("Investment")) < 0.5, f"7-4 {y}: investment")
                _check(abs(v("Exports") - v("Imports") - v("The net")) < 0.5, f"7-4 {y}: net exports")
                _check(abs(v("Consumption") + v("Investment") + v("The net") - gdp_cur[y]) < 0.5,
                       f"7-4 {y}: GDP")
    real_growth = {}
    if t71:
        for lab, n in _rows(t71, 6, short_rows=True):
            if lab.startswith("GDP at Current"):
                _check(all(abs(gdp_cur[y] - n[j]) < 0.05 for j, y in enumerate(years)),
                       "7-1 current GDP differs from 7-3")
                continue
            if lab.startswith("GDP Deflator"):
                for j, y in enumerate(years):
                    out.append(_row("aggregate", lab, "7-1", y, "not_applicable", "deflator", n[j], "index"))
                continue
            a = "aggregate" if lab.startswith("GDP at constant") else "production"
            for j, y in enumerate(years):
                out.append(_row(a, lab, "7-1", y, "constant", "level", n[3 * j], _UNIT))
                out.append(_row(a, lab, "7-1", y, "constant", "growth_yoy", n[3 * j + 1], "percent"))
                out.append(_row(a, lab, "7-1", y, "constant", "share", n[3 * j + 2], "percent"))
                if a == "aggregate":
                    real_growth[y] = n[3 * j + 1]
    if t72:
        yrs = _years(t72)
        nums = [_num(t) for t in t72 if _NUM.match(t) and not re.fullmatch(r"(19|20)\d\d\*{0,2}", t)]
        _check(len(nums) == len(yrs), f"7-2: {len(yrs)} years, {len(nums)} rates")
        for y, g in zip(yrs, nums):
            if y in real_growth:
                _check(abs(real_growth[y] - g) < 0.05, f"7-2 {y} differs from 7-1")
                continue
            out.append(_row("aggregate", "GDP at constant prices", "7-1", y, "constant",
                            "growth_yoy", g, "percent"))
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    # Newest edition first: it is the primary, and later rows lose to earlier.
    frames = []
    for p in [path, *(extras or [])]:
        try:
            frames.append(pd.DataFrame(_report(p)))
        except (ValueError, StopIteration) as e:
            if p == path:
                raise
            print(f"[sudan] extra {p.rsplit('/', 1)[-1]} skipped: {e}")
    df = pd.concat(frames, ignore_index=True)
    key = ["approach", "category", "series_code", "period", "price_basis", "measure"]
    df = df.drop_duplicates(subset=key, keep="first")
    df["geography"] = "National"
    df["seasonal_adjustment"] = "nsa"
    return df
