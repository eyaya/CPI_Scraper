"""Back series for Sierra Leone: Stats SL, 'Rebased GDP Report, 2018 base year
and revised series' (2023/24), annex Tableaux 1-6, years 2018-2023. Not a
registry parser: `sierraleone_stats_gdp.parse` hands it the PDF as an extra
(Wayback `id_` copy of statistics.sl's own file -- the live host now answers
every client with a challenge page, which is not bypassed).

UNIT: this report prints EVERY year in OLD leones -- its text states GDP as
"Le 50,687,211 million" (2018) ... "Le 136,604,079 million" (2023), and its
2023 agriculture value added (39,711,719) is the 2024 report's 39,711.7 SLE
million times 1000. So levels here are 'SLL million' (pre-redenomination
leone), never converted; the 2024 report's rows stay 'SLE million'. The two
never share a merge key.

Tables: 1 GDP by activity at current prices, 2 at constant 2018 prices, 3
shares (%), 4 real growth (%, 2019-2023), 5 / 6 GDP by expenditure at current
/ constant 2018 prices. Table 7 (memorandum items) is not read, nor the comparison rows ending
Table 1 (the old series' GDP and the rebased/old gap). Labels keep
the report's own text with the activity code moved to `series_code`, as the
caller does; `category_group` names this report and table (its own vintage).
Values in parentheses are negative. A row must carry one value per year
column or the parse raises. Everything as published.
"""
from __future__ import annotations
import re
import fitz

UNIT = "SLL million (pre-2022 leone)"
_YEARS = ["2018", "2019", "2020", "2021", "2022", "2023"]
_NUM = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?%?$")
_CODE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.*)$")
_SKIP = ("current price estimates", "estimates at constant", "gdp shares",
         "gdp growth rates")
# Table 1 ends with a comparison against the pre-rebasing series: the old
# series' GDP ("Current GDP estimates") and the rebased/old gap ("% Change").
# Neither belongs to the rebased account; both are refused.
_REFUSE = ("Current GDP estimates", "% Change")


def _f(t: str) -> float:
    neg = t.startswith("(")
    v = float(t.strip("()%").replace(",", ""))
    return -v if neg else v


def _spec(tno: str):
    return {
        "1": ("production", "current", "level", UNIT, ""),
        "2": ("production", "constant", "level", UNIT, "2018"),
        "3": ("production", "current", "share", "percent", ""),
        "4": ("production", "constant", "growth_yoy", "percent", "2018"),
        "5": ("expenditure", "current", "level", UNIT, ""),
        "6": ("expenditure", "constant", "level", UNIT, "2018"),
    }.get(tno)


def parse_rebased(path: str) -> list[dict]:
    doc = fitz.open(path)
    out, cap = [], {}
    for page in doc:
        lines = [l.strip() for l in page.get_text().splitlines() if l.strip()]
        caps = [(i, re.match(r"Table\s*(\d+)\s*[:.]\s*(.*)", l)) for i, l in enumerate(lines)]
        caps = [(i, m) for i, m in caps if m]
        if not caps:
            continue
        # only annex pages: a caption followed by the year header
        for k, (i, m) in enumerate(caps):
            tno = m.group(1)
            spec = _spec(tno)
            end = caps[k + 1][0] if k + 1 < len(caps) else len(lines)
            block = lines[i + 1:end]
            try:
                y0 = next(j for j in range(len(block))
                          if block[j:j + 6] == _YEARS)
            except StopIteration:
                continue
            if not spec:
                continue
            # the narrative's untitled 'Table 1:' (old series vs rebased
            # summary) is not an annex table
            if not m.group(2).strip() and tno not in cap:
                continue
            if "contd" not in m.group(0).lower():
                cap[tno] = m.group(2).strip()
            group = (f"Rebased GDP report (2018 base) 2018-2023, Table {tno}: "
                     f"{cap.get(tno, '')}")
            approach, basis, measure, unit, base = spec
            years = _YEARS[1:] if tno == "4" else _YEARS
            label, nums = [], []
            for l in block[y0 + 6:]:
                toks = l.split()
                if all(_NUM.match(t) for t in toks):
                    nums.extend(toks)
                    if len(nums) > len(years):
                        raise ValueError(f"SL rebased T{tno}: {label} {nums}")
                    if len(nums) == len(years):
                        lab = re.sub(r"\s+", " ", " ".join(label)).strip()
                        label, vals = [], nums
                        nums = []
                        mc = _CODE.match(lab)
                        code, cat = (mc.group(1), mc.group(2)) if mc else ("", lab)
                        cat = cat.strip()
                        if cat in _REFUSE:
                            continue
                        appr = "aggregate" if re.match(
                            r"(Gross Domestic Product|GDP|Total Gross Value Added)",
                            cat) else approach
                        for y, t in zip(years, vals):
                            out.append({
                                "approach": appr, "category": cat,
                                "category_group": group, "series_code": code,
                                "geography": "National", "period": y,
                                "frequency": "annual", "price_basis": basis,
                                "seasonal_adjustment": "nsa", "measure": measure,
                                "value": _f(t), "unit": unit,
                                "base_period": base})
                else:
                    if nums:
                        raise ValueError(f"SL rebased T{tno}: row {label} cut short {nums}")
                    if l.lower().startswith(_SKIP) or re.fullmatch(r"\d{1,2}", l):
                        continue
                    label.append(l)
    if not out:
        raise ValueError(f"no rows read from {path}")
    return out
