"""Annual back series for Congo: INS Congo, 'Comptes nationaux définitifs 2022'
(PDF, French), annex Tableaux 3-10, years 2018-2022. Not a registry parser:
`congo_ins_gdp.parse` hands it the report as an extra.

  T3 PIB courant par branche            current levels, XAF billion
  T4 PIB réel par branche               chained volume (reference 2005)
  T5 croissance par branche             real growth, percent
  T6 contributions par branche          percentage points
  T7 PIB courant et ses emplois         current levels (expenditure)
  T8 PIB réel et ses emplois            chained volume (reference 2005)
  T9 croissance du PIB et ses emplois   real growth, percent
  T10 contributions des emplois         percentage points

Not read: T1 (resource-use balance in a different layout), T2 (a mixed
summary that repeats T3-T9 alongside ratios). In T9/T10 the public/private
split of investment is printed as a row of zeros for every year -- a
placeholder, not a measured zero growth -- and such all-zero rows are not
emitted. Labels are INS's own; `category_group` names the report and table,
so these definitive figures never overwrite the quarterly notes' rows.
Everything as published; nothing derived.
"""
from __future__ import annotations
import re
import fitz

_YEARS = 5
_NUM = re.compile(r"^-?\d{1,3}(?:\s\d{3})*(?:,\d+)?$|^-?\d+(?:,\d+)?$")
_CAP = re.compile(r"Tableau n°\s*(\d+)\s*:\s*([^\n]+)")
_SPEC = {
    "3": ("production", "current", "level", "XAF billion", ""),
    "4": ("production", "constant", "level", "XAF billion",
          "chained volume, reference 2005"),
    "5": ("production", "constant", "growth_yoy", "percent", ""),
    "6": ("production", "constant", "contribution", "percentage points", ""),
    "7": ("expenditure", "current", "level", "XAF billion", ""),
    "8": ("expenditure", "constant", "level", "XAF billion",
          "chained volume, reference 2005"),
    "9": ("expenditure", "constant", "growth_yoy", "percent", ""),
    "10": ("expenditure", "constant", "contribution", "percentage points", ""),
}
_HEADS = ("Dépense de consommation finale", "Formation brute de capitale fixe")


def _f(t: str) -> float:
    return float(t.replace(" ", "").replace(",", "."))


def _is_agg(label: str) -> bool:
    return label.startswith("PIB")


def parse_report(path: str) -> list[dict]:
    with fitz.open(path) as doc:
        text = "\n".join(p.get_text() for p in doc)
    title = "Comptes nationaux définitifs 2022"
    caps = list(_CAP.finditer(text))
    rows = []
    # The list of tables at the front repeats every caption; the annex table
    # is the LAST occurrence of each number.
    last = {m.group(1): k for k, m in enumerate(caps)}
    for k, m in enumerate(caps):
        tno = m.group(1)
        if tno not in _SPEC or last[tno] != k:
            continue
        approach, basis, measure, unit, base = _SPEC[tno]
        group = f"{title}, Tableau n° {tno} : {m.group(2).strip()}"
        body = text[m.end(): caps[k + 1].start() if k + 1 < len(caps) else len(text)]
        # a dash rule ('-----Exportations') is stripped; a minus sign is kept
        lines = [re.sub(r"^-{2,}", "", l.strip()).strip() for l in body.split("\n")]
        lines = [l for l in lines if l]
        yi = next(i for i, l in enumerate(lines) if re.fullmatch(r"20\d\d", l))
        years = lines[yi: yi + _YEARS]
        assert all(re.fullmatch(r"20\d\d", y) for y in years), years
        label, nums, head = [], [], ""
        for l in lines[yi + _YEARS:]:
            if _NUM.match(l):
                nums.append(l)
                if len(nums) == _YEARS:
                    lab = re.sub(r"\s+", " ", " ".join(label)).strip()
                    label, vals = [], [_f(x) for x in nums]
                    nums = []
                    if not lab:
                        continue
                    if lab in _HEADS:
                        head = lab
                        cat = lab
                    elif approach == "expenditure" and lab in ("Publique", "Privée") \
                            and head:
                        cat = f"{head}: {lab}"
                    else:
                        cat = lab
                    if measure != "level" and all(v == 0 for v in vals):
                        continue                    # placeholder row
                    for y, v in zip(years, vals):
                        rows.append({
                            "approach": "aggregate" if _is_agg(cat) else approach,
                            "category": cat, "category_group": group,
                            "series_code": f"INS CND2022 T{tno}",
                            "geography": "National", "period": y,
                            "frequency": "annual", "price_basis": basis,
                            "seasonal_adjustment": "not_applicable",
                            "measure": measure, "value": v, "unit": unit,
                            "base_period": base})
            else:
                if nums:            # a label interrupting numbers: misaligned
                    raise ValueError(f"T{tno}: label '{l}' after {nums}")
                if l.startswith(("Comptes nationaux définitifs", "Source")) \
                        or re.fullmatch(r"\d{1,2}", l) or l.startswith(
                        ("En milliards", "Évolution annuelle", "Libellé", "Année",
                         "Secteurs /")):
                    continue
                label.append(l)
    if not rows:
        raise ValueError(f"no rows read from {path}")
    return rows
