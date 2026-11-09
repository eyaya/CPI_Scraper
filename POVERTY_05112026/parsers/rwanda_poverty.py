"""Rwanda -- monetary poverty from NISR's EICV7 poverty-profile WORKBOOK.

EICV7 (2023/24), "Excel Tables-Poverty Analysis" (the tables of the EICV7
Poverty Profile report). Consumption per adult equivalent, January 2024 prices.
Lines: total poverty RWF 560,127 per adult equivalent per year; extreme
poverty = the food line, RWF 356,432 (Table 5.1 note).

Collected (sheet -> rows):
  5.1  P0 total and extreme, national + 5 provinces + urban/rural, 2024, with
       95% CI bounds; and the 2017 values for national + provinces, which are
       MODELLED (EICV5 consumption predicted on the EICV7 basis, multiple
       imputation) -- filed under their own survey name so they cannot pass
       for the published EICV5 estimates.
  5.2  P1 (poverty gap), national 2024 and 2017-modelled; urban/rural under
       the 2012 census definition.
  5.4  P0, population share, absolute and relative contribution by urban/
       rural under BOTH definitions (2022 census, used by EICV7; 2012 census).
  6.1  P0 and population share by sex and age of the household head.
  6.2  P0 by demographic group (adult men / women, boys / girls aged <=16).
  6.3  P0 and population share by education completed by the head.

THE URBAN DEFINITION CHANGED between EICV5 and EICV7. Each urban/rural row
carries the definition in `locality_label`, and the 2017 urban/rural
predictions of Table 5.1 are NOT collected: their printed change column
(-6.2 for urban) matches the 2012-definition rate (12.7), not the 2024 rate
printed beside it (16.7) -- the table mixes definitions within a row.

Not collected: 0.1 (repeats 5.1), 5.3 (consumption), 5.5 (repeats 5.2/5.4
with differently rounded 2017 values), 6.4-6.11 (distributions of non-poverty
characteristics by poverty status), 7.1 (inequality).

CROSS-CHECK (verbatim): P0 27.4 (CI 26.4-28.4), extreme 5.4; 2017 modelled
39.8 / 11.3; Kigali 9.1, West 37.4; P1 6.06; urban 16.7 (2022 def) / 12.7 (2012
def); absolute contributions 4.7 + 22.6 = 27.3 vs 27.4 printed.
"""
from __future__ import annotations

import re

import openpyxl
import pandas as pd

from . import _common as C

LAYOUT = {
    "survey": "EICV7 2023/24", "welfare_aggregate": "consumption",
    "line_type": "national", "line_level": "overall",
    "line_name": "Total poverty line (NISR, EICV7)", "period": "2024",
    "tables": [],
}
_TOTAL = {"line_level": "overall", "line_name": "Total poverty line (NISR, EICV7)",
          "line_value": 560127, "line_unit": "RWF per adult equivalent per year"}
_EXTREME = {"line_level": "extreme", "line_name": "Extreme (food) poverty line (NISR, EICV7)",
            "line_value": 356432, "line_unit": "RWF per adult equivalent per year"}
_S24 = {"survey": "EICV7 2023/24", "period": "2024", "reference_period": "2023/24"}
_S17 = {"survey": "EICV5 2016/17 (predicted on the EICV7 basis, multiple imputation)",
        "period": "2017", "reference_period": "2016/17"}
_URB22 = "Urban (2022 census definition)"
_RUR22 = "Rural (2022 census definition)"
_URB12 = "Urban (2012 census definition)"
_RUR12 = "Rural (2012 census definition)"


def _loc(label: str) -> dict:
    loc = "urban" if label.startswith("Urban") else "rural"
    return {"topic": "locality", "locality": loc, "locality_label": label}


def _num(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return C.to_number(str(v).replace("*", ""))


def _row(metric, value, **kw):
    base = dict(welfare_aggregate="consumption", line_type="national",
                frequency="ad_hoc", **_S24, **_TOTAL)
    base.update(kw)
    return C.row(metric=metric, value=value, **base)


def _rows(ws):
    return [r for r in ws.iter_rows(values_only=True) if any(c is not None for c in r)]


def _sheet(wb, prefix):
    for ws in wb.worksheets:
        if ws.title.strip().rstrip(".") == prefix:
            return ws
    raise ValueError(f"Rwanda workbook: no sheet {prefix!r}")


def parse(path: str) -> pd.DataFrame:
    wb = openpyxl.load_workbook(path, data_only=True)
    out: list[dict] = []

    # ---- 5.1 -------------------------------------------------------------
    rows = _rows(_sheet(wb, "Table 5.1"))
    places = {"Rwanda": {}, "Kigali City": {"geography": "Kigali City"},
              "South": {"geography": "South"}, "West": {"geography": "West"},
              "North": {"geography": "North"}, "East": {"geography": "East"},
              "Urban": _loc(_URB22), "Rural": _loc(_RUR22)}
    seen = set()
    for i, r in enumerate(rows):
        name = str(r[0] or "").strip()
        if name not in places or name in seen:
            continue
        seen.add(name)
        where = places[name]
        ci = rows[i + 1] if i + 1 < len(rows) else ()
        is_ci = str(ci[0] or "").strip().rstrip(":") in ("95% confidence interval", "CI")
        for line, col24, col17 in ((_TOTAL, 1, 3), (_EXTREME, 6, 8)):
            out.append(_row("headcount", _num(r[col24]), **line, **where))
            if is_ci and ci[col24]:
                lo, hi = (float(x) for x in re.match(r"\s*([\d.]+)\s*-\s*([\d.]+)", str(ci[col24])).groups())
                out.append(_row("headcount_ci_low", lo, **line, **where))
                out.append(_row("headcount_ci_high", hi, **line, **where))
            if name not in ("Urban", "Rural"):   # see the module docstring
                out.append(_row("headcount", _num(r[col17]), **line, **where, **_S17))
    if len(seen) != len(places):
        raise ValueError(f"Rwanda 5.1: rows found {sorted(seen)}")

    # ---- 5.2: the poverty gap block ----------------------------------------
    rows = _rows(_sheet(wb, "Table 5.2"))
    k = next(i for i, r in enumerate(rows) if str(r[1] or "").strip() == "% poverty gap")
    gap = {str(r[0]).strip(): r for r in rows[k + 1:k + 4]}
    if set(gap) != {"Urban", "Rural", "Rwanda"}:
        raise ValueError(f"Rwanda 5.2: gap rows {sorted(gap)}")
    out.append(_row("gap", _num(gap["Rwanda"][1])))
    out.append(_row("gap", _num(gap["Rwanda"][2]), **_S17))
    out.append(_row("gap", _num(gap["Urban"][1]), **_loc(_URB12)))
    out.append(_row("gap", _num(gap["Rural"][1]), **_loc(_RUR12)))

    # ---- 5.4 -------------------------------------------------------------
    rows = _rows(_sheet(wb, "Table 5.4"))
    defn = None
    for r in rows:
        name = str(r[0] or "").strip()
        if name.startswith("Urban: 2022"):
            defn = (_URB22, _RUR22)
        elif name.startswith("Urban: 2012"):
            defn = (_URB12, _RUR12)
        elif name in ("Urban", "Rural") and defn:
            where = _loc(defn[0] if name == "Urban" else defn[1])
            if defn[0] == _URB12:          # the 2012-definition P0 is not in 5.1
                out.append(_row("headcount", _num(r[1]), **where))
            out.append(_row("population_share", _num(r[2]), **where))
            out.append(C.row(metric="absolute_contribution", value=_num(r[3]),
                             welfare_aggregate="consumption", line_type="national",
                             frequency="ad_hoc", **_S24, **_TOTAL, **where))
            out.append(_row("poor_share", _num(r[4]), **where))

    # ---- 6.1 / 6.3: characteristics of the head ------------------------------
    def head_table(prefix, blocks):
        topic = None
        for r in _rows(_sheet(wb, prefix)):
            name = str(r[0] or "").strip()
            if name in blocks:
                topic = blocks[name]
                continue
            if not topic or not name or name == "Total" or name.startswith("Source"):
                continue
            extra = {}
            if topic == "sex_of_head":
                extra["sex"] = "male" if name == "Male" else "female"
            if _num(r[4]) is not None:
                out.append(_row("headcount", _num(r[4]), topic=topic, characteristic=name, **extra))
            if _num(r[3]) is not None:
                out.append(_row("population_share", _num(r[3]), topic=topic, characteristic=name, **extra))

    head_table("Table 6.1", {"Gender": "sex_of_head", "Age categories (years)": "age_of_head"})
    head_table("Table 6.3", {"Level of education completed": "education_of_head"})

    # ---- 6.2: demographic groups --------------------------------------------
    groups = {"Adult males": ("male", "Adult"), "Adult females": ("female", "Adult"),
              "Boys (age<=16)": ("male", "age<=16"), "Girls (age<=16)": ("female", "age<=16")}
    got = 0
    for r in _rows(_sheet(wb, "Table 6.2")):
        name = str(r[0] or "").strip()
        if name in groups:
            sx, age = groups[name]
            out.append(_row("headcount", _num(r[1]), topic="sex", characteristic=name,
                            sex=sx, age_group=age))
            got += 1
    if got != 4:
        raise ValueError(f"Rwanda 6.2: {got} groups")
    if any(r["value"] is None for r in out):
        raise ValueError("Rwanda: an empty cell was read as a value")
    return pd.DataFrame(out)
