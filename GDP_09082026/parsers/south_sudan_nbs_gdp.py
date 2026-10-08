"""South Sudan — NBS (National Bureau of Statistics) GDP press release,
"Press Release for South Sudan Gross Domestic Product (GDP) Estimates for
2021" (November 2022), listed on nbs.gov.ss/statistics/GDP_Growth.php.

EXPENDITURE APPROACH, ANNUAL, 2008-2021, the whole series re-estimated in this
release. NBS compiles GDP only by expenditure (no production or income
approach is published). Read:

* Table 2  expenditure on GDP at current prices and at CONSTANT 2009 PRICES
           (million SSP): final consumption (government, households, NPISH),
           gross capital formation, gross domestic expenditure, exports (of
           which oil), imports, GDP; oil-sector value added, non-oil GDP and its
           "of which" general government / NPISH (filed `production`, as value
           added); the oil sector's contribution to and share of GDP (%); real
           annual changes (%) and contributions to growth (percentage points);
* Table 3  national accounts aggregates: GDP, non-oil GDP, net property income
           to the rest of the world, GNI -- in million SSP and million USD --
           and per-capita GDP, non-oil GDP and GNI in SSP and USD;
* Table 1  2021 only: each expenditure component's share of GDP (%) and its
           volume change (%).

THE GROWTH ROWS HAVE 13 VALUES FOR 14 YEAR COLUMNS: the 2008 column is empty
and the first value is 2009's (26,677.0 / 24,478.8 = +9.0%). The parser asserts
that alignment from the release's own levels every run. Negative numbers print
with a space ("- 0.5", "- 0"), which is closed up.

WHY ONLY THE NEWEST RELEASE. The 2015 and 2016 releases on the same page are
earlier vintages of the same series; this one revises every year from 2008
(2015 GDP: 53,843.8 in the 2015 release, 54,830.0 in 2016's, 25,479.6 here).
GDP outputs are replaced each run, not merged, so mixing vintages would put
superseded figures beside current ones. The older releases also contradict
themselves: each prints a "Table 1: GDP Growth Rates" that does not match its
own annual-change table.

PUBLISHED DEFECTS NOT CARRIED: the release's prose gives real GDP as "22,871.1
(0.02) trillion" and, on another page, "````````` trillion"; the tables (million
SSP) are what is read. Population and exchange rates in Table 3 are not GDP
measures and are not collected.

IDENTITIES CHECKED every run (current and constant): government + households +
NPISH = final consumption; final consumption + capital formation = gross
domestic expenditure; GDE + exports - imports = GDP; oil value added + non-oil
GDP = GDP. Table 1's 2021 levels must equal Table 2's.

QUALITY CAVEAT, NBS's OWN: "South Sudan's GDP may not be accurate as the last
estimate compiled with sufficient contemporary source data was for calendar
year 2009."

CROSS-CHECK: GDP 2021 4,245,060.8 current / 22,871.1 constant (million SSP);
real growth 2021 -2.3%; GNI 2021 4,104,180; GDP per capita 2021 USD 733;
household consumption share 2021 80.7%.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_YEARS = [str(y) for y in range(2008, 2022)]
_NUM = r"-?\s?\d{1,3}(?:,\d{3})*(?:\.\d+)?"
_TOKEN = re.compile(r"^-?\d{1,3}(?:,\d{3})*(?:\.\d+)?$")
_TOL = 0.25


def _nums(run: str) -> list[float]:
    # "- 0.5" / "- 1,159" are single negative numbers: close the gap first.
    run = re.sub(r"-\s+(?=\d)", "-", run)
    return [float(v.replace(",", "")) for v in run.split()]


def _split(line: str):
    """(label part, values) when the line ENDS in 13 or 14 numbers, else None.
    A token scan from the right: a backtracking regex over long lines of
    numbers hangs."""
    toks = re.sub(r"(?<!\S)-\s+(?=\d)", "-", line).split()
    n = 0
    while n < len(toks) and _TOKEN.match(toks[len(toks) - 1 - n]):
        n += 1
    if n < 13:
        return None
    n = min(n, 14)                  # a label ending in a number keeps its digits
    vals = toks[len(toks) - n:]
    return " ".join(toks[:len(toks) - n]), [float(v.replace(",", "")) for v in vals]


def _lines(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    return [ln.strip() for ln in text.splitlines()]


# Section headings (matched on the joined label text) -> (measure, basis, unit)
# The 4th element is the series_code: the schema's key has no `unit`, so GDP
# in SSP and in USD (Table 3) are told apart by their block's code.
_SECTIONS = [
    (r"Expenditure on GDP Current Prices", ("level", "current", "SSP million", "T2-current")),
    (r"Oil sector: Contribution to and share of GDP", ("share", "current", "percent", "T2-oil-share")),
    (r"Expenditure on GDP Constant 2009 Prices", ("level", "constant", "SSP million", "T2-constant")),
    (r"Constant 2009 Prices, Annual Changes", ("growth_yoy", "constant", "percent", "T2-growth")),
    (r"Contribution to growth", ("contribution", "constant", "percentage points", "T2-contribution")),
    (r"Table 3\. National Accounts Aggregates", ("level", "current", "SSP million", "T3-SSP")),
]
# Table 3 sub-blocks change unit / measure.
_T3_BLOCKS = [
    (r"Per capita, SSP", ("per_capita", "current", "SSP", "T3-SSP-per-capita")),
    (r"Million USD", ("level", "current", "USD million", "T3-USD")),
    (r"Per capita, USD", ("per_capita", "current", "USD", "T3-USD-per-capita")),
]
_SKIP = re.compile(r"^(Population|Exchange Rate)", re.I)


def _rows(lines: list[str]):
    """Yield (section_spec, label, values) from Tables 2 and 3."""
    start = next(i for i, ln in enumerate(lines) if ln.startswith("Table 2. Gross Domestic Product"))
    spec, pending = None, []
    for ln in lines[start:]:
        # A year header ("category 2008 2009 ... 2021", "Million SSP 2008 ...")
        # ends whatever label text came before it; it is never a data row.
        if len(re.findall(r"\b20\d\d\b", ln)) >= 10:
            pending = []
            continue
        m = _split(ln)
        if not m:
            pending.append(ln)
            joined = " ".join(pending)
            for pat, sp in _SECTIONS + _T3_BLOCKS:
                if re.search(pat, joined):
                    spec, pending = sp, []
                    break
            continue
        label = re.sub(r"\s+", " ", " ".join(pending + [m[0]])).strip()
        pending = []
        if spec is None or not label or _SKIP.match(label):
            continue
        yield spec, label, m[1]


def _approach(label: str) -> str:
    low = label.lower()
    if low in ("gross domestic product", "gross national income",
               "property income, net, to the rest of the world"):
        return "aggregate"
    if low.startswith(("oil sector", "non-oil", "of which: general", "of which: npish")):
        return "production"
    return "expenditure"


def _table1(lines: list[str]) -> list[dict]:
    i = next(i for i, ln in enumerate(lines) if ln.startswith("Table 1: Proportion of GDP"))
    out = []
    for ln in lines[i:i + 20]:
        m = re.match(rf"(.+?)\s+({_NUM})\s+({_NUM})\s+({_NUM})$", ln)
        if not m or not re.search(r"[A-Za-z]", m.group(1)):
            continue
        lab, lvl, sh, vol = m.group(1), *(_nums(g)[0] for g in m.groups()[1:])
        out.append((lab.strip(), lvl, sh, vol))
        if lab.strip() == "GDP":
            break
    if [o[0] for o in out][-1:] != ["GDP"] or len(out) != 7:
        raise ValueError(f"NBS T1: read {[o[0] for o in out]}")
    return out


def parse(path: str) -> pd.DataFrame:
    lines = _lines(path)
    data, out = {}, []
    for (measure, basis, unit, code), label, vals in _rows(lines):
        years = _YEARS if len(vals) == 14 else _YEARS[1:]
        if len(vals) == 13 and measure not in ("growth_yoy", "contribution"):
            raise ValueError(f"NBS: {label!r} ({measure}) has 13 values")
        key = (measure, basis, unit, label.lower())
        if key in data:
            # Table 3 repeats GDP and non-oil GDP (million SSP) from Table 2,
            # rounded to whole numbers: proved equal, then not emitted twice.
            old = data[key]
            if any(abs(old[y] - v) > 0.51 for y, v in zip(_YEARS, vals)):
                raise ValueError(f"NBS: {label!r} printed twice with different values")
            continue
        data[key] = dict(zip(years, vals))
        for y, v in zip(years, vals):
            out.append(dict(approach=_approach(label), category=label,
                            category_group=f"{measure}, {basis}, {unit}",
                            series_code=code, period=y, frequency="annual",
                            price_basis=basis if measure != "per_capita" else "current",
                            measure=measure, value=v, unit=unit,
                            base_period="Constant 2009 prices" if basis == "constant"
                            and measure == "level" else ""))

    # --- identities, current and constant --------------------------------
    for basis in ("current", "constant"):
        g = lambda lab: data[("level", basis, "SSP million", lab.lower())]
        fce, gov = g("Final consumption expenditure"), g("Final consum exp, government")
        hh, npi = g("Final consum exp, households"), g("Final consum exp, NPISH")
        gcf, gde = g("Gross capital formation"), g("Gross Domestic Expenditure")
        x, m = g("Exports of goods and services"), g("Imports of goods and services")
        gdp, oil, non = g("Gross Domestic Product"), g("Oil sector value added"), g("Non-oil GDP")
        for y in _YEARS:
            for what, a, b in (("consumption", gov[y] + hh[y] + npi[y], fce[y]),
                               ("GDE", fce[y] + gcf[y], gde[y]),
                               ("GDP", gde[y] + x[y] - m[y], gdp[y]),
                               ("oil + non-oil", oil[y] + non[y], gdp[y])):
                if abs(a - b) > 0.5:
                    raise ValueError(f"NBS {basis} {y}: {what} {a:.1f} != {b:.1f}")
    # --- growth rows start in 2009: prove it from the levels --------------
    real = data[("level", "constant", "SSP million", "gross domestic product")]
    gr = data[("growth_yoy", "constant", "percent", "gross domestic product")]
    for y0, y1 in zip(_YEARS[:-1], _YEARS[1:]):
        implied = 100 * (real[y1] / real[y0] - 1)
        if abs(implied - gr[y1]) > _TOL:
            raise ValueError(f"NBS: growth {y1} {gr[y1]} does not match levels "
                             f"({implied:.2f}) -- column alignment is off")

    # --- Table 1: 2021 shares and volume changes --------------------------
    t2 = {"Household Final Consumption Expenditure": "Final consum exp, households",
          "Government Final Consumption Expenditure": "Final consum exp, government",
          "NPISH Final Consumption Expenditure": "Final consum exp, NPISH",
          "Gross Capital Formation": "Gross capital formation",
          "Exports": "Exports of goods and services",
          "Imports": "Imports of goods and services", "GDP": "Gross Domestic Product"}
    for lab, lvl, sh, vol in _table1(lines):
        ref = data[("level", "current", "SSP million", t2[lab].lower())]["2021"]
        if abs(abs(lvl) - ref) > 1:
            raise ValueError(f"NBS T1 {lab}: {lvl} != Table 2 {ref}")
        for val, measure, basis, unit in ((sh, "share", "current", "percent"),
                                          (vol, "growth_yoy", "constant", "percent")):
            out.append(dict(approach="aggregate" if lab == "GDP" else "expenditure",
                            category=lab, category_group="Table 1 (2021)",
                            series_code="T1", period="2021", frequency="annual",
                            price_basis=basis, measure=measure, value=val,
                            unit=unit, base_period=""))
    df = pd.DataFrame(out)
    df["geography"] = "National"
    df["seasonal_adjustment"] = "nsa"
    return df
