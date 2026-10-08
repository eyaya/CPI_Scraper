"""Angola — INE IEA time-series workbooks (both methodologies).

INE replaced the quarterly IEA bulletin PDF (still laid out in
`angola_unemployment.py`, should it return) with five workbooks behind a POST.
This reader takes four of them, plus one more for provinces:

* "1.SERIES CRONOLÓGICAS ... (ANTIGA METODOLOGIA_13ª CIET)" -- PRIMARY,
  2019 Q2 to 2025 Q3 with annual columns; and
* "3.SERIES CRONOLÓGICAS ... (NOVA METODOLOGIA_19ª, 20ª e 21ª CIET)",
  2025 Q4 onwards. Sheet "PRINCIPAIS INDICADORES IEA": three stacked blocks --
  15+, 15-24 and 18+ -- each opening with the population row and carrying the
  labour force, employed, unemployed, outside, and the rates. The 15-24 block
  is the youth cut of the 15+ base; the 18+ block is a second BASE.
* "2./4.QUADROS COMPLEMETARES": the rates by área de residência, sexo and
  grupo etário, one sheet per indicator. Their "Angola" row repeats the
  headline and is CHECKED against the series file, not emitted twice; their
  "15-24 anos" row likewise against the series file's 15-24 block.
* "5.INDICADORES POR PROVÍNCIA" (13ª CIET): annual, by the 18 provinces, for
  2019-2022, 2024 and 2025 (INE prints no 2023). Counts + rates for
  actividade, emprego, desemprego, inactividade and informal. The provinces'
  labour forces are checked to sum to the national annual figure.

THE TWO METHODOLOGIES MUST NEVER BE CHAINED. Participation is 87-89% on the
13th-ICLS basis and 50-56% on the 19th: the old basis counts own-use
production work as employment. `survey` names the basis on every row; the
periods do not overlap.

WHAT IS LEFT, AND WHY:
* "Taxa de inactividade" / "...fora da força de trabalho" -- no topic here; it
  is 100 minus participation, a derivation.
* "População empregada com emprego formal/informal" (counts) and "Taxa de
  Emprego Formal" -- the schema carries the informal SHARE, which is taken;
  the formal share is its complement.
* Informality by activity (a rate WITHIN each branch) and employment by
  sector/situation -- composition, which lives in `labour/angola.yaml`.
* The provinces' "Informal em actividades não agrícolas" -- a different
  denominator (non-agricultural employment) that `informal_employment_share`
  does not name.

Rates are INE's unrounded cell values, kept as stored.

CROSS-CHECK: new 2026 Q2 (15+) -- população 23 006 410; força de trabalho
12 962 065; empregada 10 171 244; desempregada 2 790 821; taxa da força de
trabalho 56,34; taxa de emprego 44,21; taxa de emprego informal 80,08; taxa de
desemprego 21,53 (matching the last bulletin PDF). Old 2019 Q2 -- taxa de
desemprego 28,71, taxa de actividade 87,46; 15-24 desemprego 52,62. Province
2019 Luanda desemprego 43,88%.
"""
from __future__ import annotations

import os
import re
import unicodedata

import openpyxl
import pandas as pd

from ._common import row

SURVEY_OLD = "IEA (antiga metodologia, 13ª CIET)"
SURVEY_NEW = "IEA (nova metodologia, 19ª, 20ª e 21ª CIET)"
_Q = {"i": 1, "ii": 2, "iii": 3, "iv": 4}


def _key(s) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", str(s))
                if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().lower()


def _period(year, label) -> tuple[str, str, str]:
    lab = str(label).strip()
    m = re.fullmatch(r"(I{1,3}|IV)\s*trim", lab, re.I)
    if m:
        return (f"{int(year)}-Q{_Q[m.group(1).lower()]}", "quarterly",
                f"{lab} {int(year)}")
    if lab.lower().startswith("anual"):
        return str(int(year)), "annual", f"Anual {int(year)}"
    raise ValueError(f"unreadable period header {year!r} {label!r}")


def _sheet(path, name):
    wb = openpyxl.load_workbook(path, data_only=True)
    hit = [ws for ws in wb.worksheets if _key(ws.title) == _key(name)]
    if len(hit) != 1:
        raise ValueError(f"{os.path.basename(path)}: no sheet {name!r} "
                         f"({wb.sheetnames})")
    rows = [list(r) for r in hit[0].iter_rows(values_only=True)]
    cols = [(i, rows[1][i], rows[2][i]) for i in range(1, len(rows[1]))
            if rows[1][i] is not None and rows[2][i] is not None]
    return rows, cols


# ------------------------------------------------ the two series files
# label (deaccented, lower) -> topic. Old and new wording both listed.
_SERIES_ROWS = {
    "populacao economicamente activa": "labour_force",
    "forca de trabalho": "labour_force",
    "populacao empregada": "employed",
    "populacao desempregada": "unemployed",
    "populacao inactiva": "outside_labour_force",
    "populacao fora da forca de trabalho": "outside_labour_force",
    "taxa de actividade": "labour_force_participation_rate",
    "taxa da forca de trabalho": "labour_force_participation_rate",
    "taxa de emprego": "employment_to_population_ratio",
    "taxa de emprego informal": "informal_employment_share",
    "taxa de desemprego": "unemployment_rate",
}
_SERIES_SKIP = {
    "populacao empregada com emprego formal",
    "populacao empregada com emprego informal",
    "taxa de inactividade", "taxa da populacao fora da forca de trabalho",
    "taxa de emprego formal",
}
_BLOCKS = {  # block header -> (working_age_base, age_group)
    "populacao com 15 ou mais anos": ("15+", "Total"),
    "populacao com 15-24 anos": ("15+", "15-24"),
    "populacao com 18 ou mais anos": ("18+", "Total"),
}


def _definition(topic: str) -> str:
    return "strict" if topic in {"unemployment_rate", "youth_unemployment_rate",
                                 "labour_force_participation_rate"} \
        else "not_applicable"


def _series(path, survey) -> list[dict]:
    rows, cols = _sheet(path, "PRINCIPAIS INDICADORES IEA")
    out, block = [], None
    for r in rows[3:]:
        if r[0] is None or str(r[0]).startswith("Fonte"):
            continue
        lab = str(r[0]).strip()
        k = _key(lab)
        if k in _BLOCKS:
            block = _BLOCKS[k]
            topic = "working_age_population"
        elif k in _SERIES_SKIP:
            continue
        elif k in _SERIES_ROWS:
            topic = _SERIES_ROWS[k]
        else:
            raise ValueError(f"{survey}: unknown series row {lab!r}")
        if block is None:
            raise ValueError(f"{survey}: row {lab!r} before any block")
        base, age = block
        if topic == "unemployment_rate" and age == "15-24":
            topic = "youth_unemployment_rate"
        for i, year, label in cols:
            v = r[i]
            if v is None:
                continue
            period, freq, ref = _period(year, label)
            out.append(row(topic=topic, value=v, series_label=lab,
                           survey=survey, period=period, reference_period=ref,
                           frequency=freq, working_age_base=base,
                           age_group=age, definition=_definition(topic),
                           series_code="IEA series"))
    return out


# ----------------------------------------- the complementary rate sheets
_RATE_SHEETS = {
    SURVEY_OLD: {"Taxa de actividade": "labour_force_participation_rate",
                 "Taxa de emprego": "employment_to_population_ratio",
                 "Taxa de emprego informal": "informal_employment_share",
                 "Taxa de desemprego": "unemployment_rate"},
    SURVEY_NEW: {"Taxa da força de trabalho": "labour_force_participation_rate",
                 "Taxa de emprego": "employment_to_population_ratio",
                 "Taxa de emprego informal": "informal_employment_share",
                 "Taxa de desemprego": "unemployment_rate"},
}
# THE TWO WORKBOOKS DISAGREE SLIGHTLY where they repeat a cell. Five cells
# differ, all by 0,05 points or less -- old 2022 Anual 15-24 taxa de emprego
# (37,360 vs 37,342) and desemprego (55,230 vs 55,251); new 2025 IV trim taxa
# da força de trabalho (49,554 vs 49,599), desemprego (20,192 vs 20,211) and
# 15-24 desemprego (43,399 vs 43,446) -- the signature of a reweighting applied
# to one workbook and not the other. The SERIES file is the headline of record
# and its value is the one emitted; the repeat is a check, and anything beyond
# this tolerance is treated as a misread and raises.
_REPEAT_TOL = 0.1

# Blocks read from the rate sheets; anything else ("Sector de actividade",
# "Situação perante o emprego", "... por actividade económica") is composition
# and ends the read.
_RATE_BLOCKS = {"area de residencia", "sexo", "grupos etarios",
                "outros grupos etarios"}


def _rates(path, survey, headline: dict) -> list[dict]:
    out = []
    for sheet, topic in _RATE_SHEETS[survey].items():
        rows, cols = _sheet(path, sheet)
        block = None
        for r in rows[3:]:
            if r[0] is None or str(r[0]).startswith("Fonte"):
                continue
            lab = str(r[0]).strip()
            k = _key(lab)
            if all(r[i] is None for i, _, _ in cols):
                if k not in _RATE_BLOCKS:
                    break                      # composition from here down
                block = k
                continue
            sex, loc, loc_lab, age, base = "total", "all", "Total", "Total", "15+"
            t = topic
            if k == "angola":
                block_kind = "national"
            elif block == "area de residencia":
                loc, loc_lab = ("urban" if k.startswith("urban") else "rural"), lab
                block_kind = "cut"
            elif block == "sexo":
                sex = "male" if k.startswith("homem") else "female"
                block_kind = "cut"
            elif block in ("grupos etarios", "outros grupos etarios"):
                m = re.match(r"(\d+)\s*(?:-\s*(\d+)|ou mais)", k)
                if not m:
                    raise ValueError(f"{survey} {sheet}: age row {lab!r}")
                if block == "outros grupos etarios" and k.startswith("18 ou mais"):
                    base, age = "18+", "Total"
                else:
                    age = (f"{m.group(1)}-{m.group(2)}" if m.group(2)
                           else f"{m.group(1)}+")
                block_kind = "cut"
            else:
                raise ValueError(f"{survey} {sheet}: row {lab!r} outside a block")
            if t == "unemployment_rate" and age == "15-24":
                t = "youth_unemployment_rate"
            for i, year, label in cols:
                v = r[i]
                if v is None:
                    continue
                period, freq, ref = _period(year, label)
                hk = (t, period, age, base)
                repeats = block_kind == "national" or (
                    sex == "total" and loc == "all" and hk in headline)
                if repeats:
                    # Already emitted from the series file: must agree.
                    want = headline.get(hk if block_kind != "national"
                                        else (t, period, "Total", "15+"))
                    if want is not None and abs(want - v) > _REPEAT_TOL:
                        raise ValueError(f"{survey} {sheet} {lab} {ref}: "
                                         f"{v} != series file {want}")
                    continue
                out.append(row(topic=t, value=v, series_label=f"{sheet} — {lab}",
                               survey=survey, period=period,
                               reference_period=ref, frequency=freq,
                               working_age_base=base, sex=sex, age_group=age,
                               locality=loc, locality_label=loc_lab,
                               definition=_definition(t),
                               series_code=f"IEA {sheet}"))
    return out


# ---------------------------------------------------------- provinces
_PROV = {  # (group, 'Nº'|'%') -> topic
    ("actividade", "nº"): "labour_force",
    ("actividade", "%"): "labour_force_participation_rate",
    ("emprego", "nº"): "employed",
    ("emprego", "%"): "employment_to_population_ratio",
    ("desemprego", "nº"): "unemployed",
    ("desemprego", "%"): "unemployment_rate",
    ("inactividade", "nº"): "outside_labour_force",
    ("informal", "%"): "informal_employment_share",
}


def _provinces(path, national_lf: dict) -> list[dict]:
    ws = openpyxl.load_workbook(path, data_only=True).worksheets[0]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    year, group, spec = None, None, {}
    for i in range(1, len(rows[1])):
        if rows[1][i] is not None:
            year = str(int(rows[1][i]))
        if rows[2][i] is not None:
            group = _key(rows[2][i])
        unit = _key(rows[3][i] or "")
        if year and group and (group, unit) in _PROV:
            spec[i] = (year, _PROV[(group, unit)], rows[2][i] if rows[2][i]
                       else None)
    out, lf_sum = [], {}
    for r in rows[5:]:
        if r[0] is None or str(r[0]).startswith("Fonte"):
            continue
        prov = str(r[0]).strip()
        for i, (yr, topic) in ((i, s[:2]) for i, s in spec.items()):
            v = r[i]
            if v is None:
                continue
            if topic == "labour_force":
                lf_sum[yr] = lf_sum.get(yr, 0) + v
            out.append(row(topic=topic, value=v,
                           series_label=f"Quadro 1 — {topic}",
                           survey=SURVEY_OLD, period=yr,
                           reference_period=f"Anual {yr}", frequency="annual",
                           working_age_base="15+", geography=prov,
                           definition=_definition(topic),
                           series_code="IEA Quadro 1 por província"))
    for yr, s in lf_sum.items():
        nat = national_lf.get(yr)
        if nat is not None and abs(s - nat) / nat > 0.001:
            raise ValueError(f"provinces {yr}: labour force sums to {s:,.0f}, "
                             f"national annual is {nat:,.0f}")
    if len({r["geography"] for r in out}) != 18:
        raise ValueError("expected the 18 provinces")
    return out


def _pick(paths, *terms):
    hit = [p for p in paths
           if all(_key(t) in _key(os.path.basename(p)) for t in terms)]
    if len(hit) != 1:
        raise FileNotFoundError(f"need one workbook matching {terms}")
    return hit[0]


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    paths = [local_path] + list(extras or [])
    rows = []
    for survey, tag in ((SURVEY_OLD, "ANTIGA"), (SURVEY_NEW, "NOVA")):
        series = _series(_pick(paths, "SERIES", tag), survey)
        headline = {(r["topic"], r["period"], r["age_group"],
                     r["working_age_base"]): r["value"] for r in series}
        rows += series
        rows += _rates(_pick(paths, "QUADROS", tag), survey, headline)
        if survey == SURVEY_OLD:
            nat_lf = {r["period"]: r["value"] for r in series
                      if r["topic"] == "labour_force" and r["age_group"] == "Total"
                      and r["working_age_base"] == "15+"
                      and r["frequency"] == "annual"}
            rows += _provinces(_pick(paths, "PROV"), nat_lf)
    return pd.DataFrame(rows)
