"""Lesotho — BOS Lesotho Labour Force Survey (LFS) 2024 and 2019: headline
labour-force and labour-underutilisation indicators.

The same three ZIPped documents `labour/` reads (the 2024 report, the 2019
report and the 2019 statistical-tables volume), from the JavaScript publication
array in bos.gov.ls/publications.htm. Base 15+ throughout.

LFS 2024 (report):
* Table 3.9  main indicators by sex -- population 15+, labour force, outside
             LF, employed, unemployed, potential LF; participation, employment
             ratio, informal employment rate, LU1-LU4; and two youth rows.
* Table 3.7  population 15+, labour force and participation by district x sex.
* Table 3.8  the same by age group x settlement type (urban / peri-urban /
             rural).
* Table 3.6  participation by age group x sex (its 2019 half is checked
             against the 2019 report's Table 3.5 and not re-emitted).
* Table 4.22 employment-to-population ratio by district x sex.

LFS 2019 (report, and the tables volume for one table):
* Table 3.9  main indicators by sex and by settlement type -- counts,
             participation, employment ratio, LU1-LU4.
* Table 3.5  population, labour force and participation by age x sex.
* Table 3.6  the same by age x settlement type.
* Table 3.7  participation by district x sex.
* Table 7.1  unemployed by age x sex;  7.2 by settlement x sex;
  tables volume Table 7.4 unemployed by district x sex.

ONE FIGURE PER MERGE KEY. Each main-indicators table (3.9) is the home of the
national, sex and settlement totals; the Total rows and columns of the
supporting tables repeat them and are CHECKED against 3.9, not emitted twice.
Every count/rate pair is also held to its own arithmetic (participation =
labour force / population, LU1 = unemployed / labour force, LF = E + U ...).

PUBLISHED DEFECTS, HANDLED:

* 2024 TABLE 3.9'S YOUTH BLOCK IS INTERNALLY INCONSISTENT. "Youth unemployment
  rate (15-35)" prints 37,1 / 40,8 / 48,9 -- the total lies outside both sexes;
  "Youth labour force participation rate (15-35)" prints 31,5, which is
  exactly the 15-24 rate from Table 3.8's own counts (129 400 / 411 094); and
  a "youth absorption rate" of 62,3 cannot exceed a participation of 31,5.
  Only the two rows that agree with each other and with Table 3.8 are taken:
  "Youth Unemployment Rate (15-24)" and "Youth Employment-to-population ratio
  (15-24)" (31,5 x (1 - 0,488) = 16,1). The NEET row names no age band; the
  rest are refused. Nothing is relabelled.
* 2019 Table 3.6 prints the rural labour force as 313 910 against Table 3.9's
  313 866 and the total as 672 755 against 672 711; its Total row is not
  emitted (3.9 is the home of those cells), and its total-by-age LFPR misrounds
  20-24 (44,9 vs 45,0 from the same counts) -- the 3.5 figure is the one taken.
* 2024 Table 3.8 prints a fractional count (rural 85+ population 13,883.7);
  kept as printed.

NOT COLLECTED: chapter 7 / 10 / 11 percentage distributions of the unemployed,
youth and outside-LF populations (shares of a group, not rates); Table 3.8 of
2019 (literacy -- no column); trade-union rows; time-related underemployment
counts (no topic).

DEFINITIONS: LU1 is strict; LU2-LU4 are broad. Periods 2024 and 2019.

CROSS-CHECK: 2024 population 15+ 1 510 701; labour force 786 298; LU1 30,1
(male 29,5); LFPR 52,0; LU3 46,1; Maseru LFPR 62,0; urban LFPR 64,1; youth
15-24 unemployment 48,8. 2019: labour force 672 711; LU1 22,5 (rural 27,9);
LU4 42,3; unemployed 151 266; Maseru unemployed 45 067.
"""
from __future__ import annotations

import os
import re
import zipfile

import fitz  # PyMuPDF
import pandas as pd
import pdfplumber

from . import _common as C

_DISTRICTS = ["Botha Bothe", "Leribe", "Berea", "Maseru", "Mafeteng",
              "Mohale's Hoek", "Quthing", "Qacha's Nek", "Mokhotlong",
              "Thaba-Tseka"]
_SETTLE = [{"locality": "urban", "locality_label": "Urban"},
           {"locality": "other", "locality_label": "Peri-Urban"},
           {"locality": "rural", "locality_label": "Rural"}]
_SEXES = [{"sex": "male"}, {"sex": "female"}]
_NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"


def _pdf(path: str) -> str:
    """BOS ships every report as a ZIP holding one PDF (as labour/ reads it)."""
    if not path.lower().endswith(".zip"):
        return path
    with zipfile.ZipFile(path) as z:
        pdfs = [m for m in z.namelist() if m.lower().endswith(".pdf")]
        if len(pdfs) != 1:
            raise ValueError(f"{path}: expected one PDF, found {pdfs}")
        z.extract(pdfs[0], os.path.dirname(path))
        return os.path.join(os.path.dirname(path), pdfs[0])


def _f(tok: str) -> float:
    return float(tok.replace(",", ""))


def _table_lines(pages: list[str], caption: str, stop: str) -> list[str]:
    rx = re.compile(caption + r"(?![^\n]*\.{4})", re.M)
    # The list of tables repeats each caption, and its dot leaders can wrap
    # onto the next line; the table itself is always the LAST occurrence.
    for i in reversed(range(len(pages))):
        t = pages[i]
        m = rx.search(t)
        if not m:
            continue
        text = t[m.end():]
        if i + 1 < len(pages) and not re.search(stop, text, re.M):
            text += "\n" + pages[i + 1]
        s = re.search(stop, text, re.M)
        return [ln.strip() for ln in (text[:s.start()] if s else text).splitlines()]
    raise ValueError(f"LFS: caption {caption!r} not found")


def _rows(lines: list[str], labels: list[str], n: int) -> dict[str, list[float]]:
    """label -> its n numbers, for lines '<label> <n numbers>'."""
    out = {}
    for ln in lines:
        for lab in labels:
            m = re.fullmatch(re.escape(lab) + rf"((?:\s+(?:{_NUM})){{{n}}})", ln)
            if m and lab not in out:
                out[lab] = [_f(x) for x in m.group(1).split()]
    missing = [lab for lab in labels if lab not in out]
    if missing:
        raise ValueError(f"LFS: rows not read {missing}")
    return out


def _numeric_runs(lines: list[str], n: int) -> list[list[float]]:
    rows = []
    for ln in lines:
        toks = ln.split()
        run = []
        for tok in reversed(toks):
            if re.fullmatch(_NUM, tok):
                run.append(tok)
            else:
                break
        if len(run) == n:
            rows.append([_f(x) for x in reversed(run)])
    return rows


def _close(a, b, tol, what):
    if abs(a - b) > tol:
        raise ValueError(f"LFS: {what}: {a} vs {b}")


class _Out:
    def __init__(self, survey: str, period: str):
        self.kw = dict(survey=survey, period=period,
                       reference_period=f"LFS {period}", frequency="ad_hoc",
                       working_age_base="15+")
        self.rows: list[dict] = []

    def add(self, topic, value, label, code, definition="not_applicable", **ctx):
        self.rows.append(C.row(topic=topic, value=value, series_label=label,
                               definition=definition, series_code=code,
                               **self.kw, **ctx))


# ---------------------------------------------------------------------------
# LFS 2024
# ---------------------------------------------------------------------------

_T39_24 = {  # printed label -> (key, topic, definition)
    "Working Age Population (15+ years)": ("wap", "working_age_population", "not_applicable"),
    "Labour Force (Employed + Unemployed)": ("lf", "labour_force", "not_applicable"),
    "Outside Labour Force": ("olf", "outside_labour_force", "not_applicable"),
    "Employed Population": ("emp", "employed", "not_applicable"),
    "Unemployed Population": ("unemp", "unemployed", "not_applicable"),
    "Potential labour force": ("plf", "potential_labour_force", "not_applicable"),
    "Labour Force Participation Rate": ("lfpr", "labour_force_participation_rate", "not_applicable"),
    "Employment-to-Population Ratio": ("epr", "employment_to_population_ratio", "not_applicable"),
    "Informal employment rate": ("inf", "informal_employment_share", "not_applicable"),
    "Unemployment Rate (LU1)": ("lu1", "unemployment_rate", "strict"),
    "Combined rate of time-related underemployment and unemployment (LU2)":
        ("lu2", "labour_underutilisation_rate", "broad"),
    "Combined rate of unemployment and potential labour force (LU3)":
        ("lu3", "labour_underutilisation_rate", "broad"),
    "Aggregated measure of labour underutilization (LU4)":
        ("lu4", "labour_underutilisation_rate", "broad"),
    "Youth Unemployment Rate (15-24)": ("y_ur", "youth_unemployment_rate", "strict"),
    "Youth Employment-to-population ratio (15-24)":
        ("y_epr", "employment_to_population_ratio", "not_applicable"),
}
_SEX3 = [{"sex": "male"}, {"sex": "female"}, {}]


def _lfs_2024(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    o = _Out("Lesotho Labour Force Survey 2024", "2024")

    lines = _table_lines(pages, r"^Table 3\.9: Labour Force Main Indicators by Sex",
                         r"^CHAPTER 4")
    t = _rows(lines, list(_T39_24), 3)
    v = {k: t[lab] for lab, (k, _, _) in _T39_24.items()}
    for c in range(3):
        _close(v["lf"][c], v["emp"][c] + v["unemp"][c], 2, "T3.9 LF = E + U")
        _close(v["wap"][c], v["lf"][c] + v["olf"][c], 2, "T3.9 pop = LF + OLF")
        _close(100 * v["unemp"][c] / v["lf"][c], v["lu1"][c], 0.15, "T3.9 LU1")
        _close(100 * v["lf"][c] / v["wap"][c], v["lfpr"][c], 0.15, "T3.9 LFPR")
        _close(100 * v["emp"][c] / v["wap"][c], v["epr"][c], 0.15, "T3.9 EPR")
    for lab, (k, topic, definition) in _T39_24.items():
        for ctx, val in zip(_SEX3, v[k]):
            ctx = dict(ctx)
            if k.startswith("y_"):
                ctx["age_group"] = "15-24"
            o.add(topic, val, lab, "LFS2024 T3.9", definition, **ctx)

    # Table 3.8: age x settlement -- (pop, LF, LFPR) x Lesotho/U/PU/R.
    lines = _table_lines(pages, r"^Table 3\.8: Labour Force Participation Rate by "
                                r"Age-group and Settlement", r"^\d+$")
    ages = ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49",
            "50-54", "55-59", "60-64", "65-69", "70-74", "75-79", "80-84", "85+"]
    t = _rows(lines, ages + ["Total"], 12)
    lfpr_by_age = {}
    for lab, vals in t.items():
        groups = [{}] + _SETTLE
        for g, ctx in enumerate(groups):
            pop, lf, rate = vals[3 * g:3 * g + 3]
            _close(100 * lf / pop, rate, 0.15, f"T3.8 {lab} LFPR")
            if lab == "Total":
                if g == 0:              # national: Table 3.9's
                    _close(pop, v["wap"][2], 2, "T3.8 total vs T3.9")
                    continue
            else:
                ctx = {**ctx, "age_group": lab}
            if g == 0:
                lfpr_by_age[lab] = rate
            o.add("working_age_population", pop, "Working Age Population", "LFS2024 T3.8", **ctx)
            o.add("labour_force", lf, "Labour Force", "LFS2024 T3.8", **ctx)
            o.add("labour_force_participation_rate", rate, "LFPR (%)", "LFS2024 T3.8", **ctx)

    # Table 3.6: LFPR by age x sex, 2024 beside 2019 (and point change).
    lines = _table_lines(pages, r"^Table 3\.6: Comparison of Labour Force "
                                r"Participation Rate", r"^Figure 3\.5")
    rows36 = {}
    for ln in lines:
        m = re.fullmatch(r"(\d{2}-\d{2}|85\+|Total)((?:\s+-?\d+\.\d){9})", ln)
        if m:
            rows36[m.group(1)] = [float(x) for x in m.group(2).split()]
    if len(rows36) < 14:
        raise ValueError(f"LFS 2024 T3.6: {len(rows36)} rows")
    t36_2019 = {}
    for lab, vals in rows36.items():
        if lab in lfpr_by_age:
            _close(vals[0], lfpr_by_age[lab], 0.05, f"T3.6 {lab} vs T3.8")
        t36_2019[lab] = (vals[1], vals[4], vals[7])      # 2019 total, male, female
        if lab == "Total":
            _close(vals[3], v["lfpr"][0], 0.05, "T3.6 male total vs T3.9")
            _close(vals[6], v["lfpr"][1], 0.05, "T3.6 female total vs T3.9")
            continue
        for ctx, val in ((_SEXES[0], vals[3]), (_SEXES[1], vals[6])):
            o.add("labour_force_participation_rate", val, "2024 LFPR",
                  "LFS2024 T3.6", age_group=lab, **ctx)

    # Table 3.7: district x sex -- (pop, LF, LFPR) x total/male/female.
    lines = _table_lines(pages, r"^Table 3\.7: Labour Force Participation Rate by "
                                r"District and Sex", r"^Table 3\.8 shows")
    t = _rows(lines, _DISTRICTS + ["Total"], 9)
    for lab, vals in t.items():
        for g, ctx in enumerate([{}] + _SEXES):
            pop, lf, rate = vals[3 * g:3 * g + 3]
            _close(100 * lf / pop, rate, 0.15, f"T3.7 {lab} LFPR")
            if lab == "Total":
                _close(lf, v["lf"][[2, 0, 1][g]], 2, "T3.7 total vs T3.9")
                continue
            ctx = {**ctx, "geography": lab}
            o.add("working_age_population", pop, "Working Age Population", "LFS2024 T3.7", **ctx)
            o.add("labour_force", lf, "Labour Force", "LFS2024 T3.7", **ctx)
            o.add("labour_force_participation_rate", rate, "LFPR (%)", "LFS2024 T3.7", **ctx)

    # Table 4.22: EPR by district x sex.
    lines = _table_lines(pages, r"^Table 4\.22: Employment-to-Population Ratio by "
                                r"District", r"^Figure 4\.3")
    t = _rows(lines, _DISTRICTS + ["Total"], 3)
    for lab, vals in t.items():
        if lab == "Total":
            for c in range(3):
                _close(vals[c], v["epr"][c], 0.05, "T4.22 total vs T3.9")
            continue
        for ctx, val in zip(_SEXES + [{}], vals):
            o.add("employment_to_population_ratio", val,
                  "Employment-to-Population Ratio", "LFS2024 T4.22",
                  geography=lab, **ctx)
    return o.rows, t36_2019


# ---------------------------------------------------------------------------
# LFS 2019
# ---------------------------------------------------------------------------

_SEQ_39_19 = ["wap", "lf", "emp", "unemp", "olf", "lu_n", "lu_unemp", "tru_n",
              "plf", "lfpr", "epr", "lu1", "lu2", "lu3", "lu4"]
_EMIT_39_19 = {
    "wap": ("working_age_population", "not_applicable", "Working age population"),
    "lf": ("labour_force", "not_applicable", "Labour force"),
    "emp": ("employed", "not_applicable", "Employed"),
    "unemp": ("unemployed", "not_applicable", "Unemployed"),
    "olf": ("outside_labour_force", "not_applicable", "Outside labour force"),
    "plf": ("potential_labour_force", "not_applicable", "Potential labour force"),
    "lfpr": ("labour_force_participation_rate", "not_applicable",
             "Labour force participation rate (%)"),
    "epr": ("employment_to_population_ratio", "not_applicable",
            "Employment to population ratio (%)"),
    "lu1": ("unemployment_rate", "strict", "LU1-Unemployment rate (%)"),
    "lu2": ("labour_underutilisation_rate", "broad",
            "LU2-Combine rate of unemployment and Time-related underemployment (%)"),
    "lu3": ("labour_underutilisation_rate", "broad",
            "LU3-Combine rate of unemployment and potential labour force (%)"),
    "lu4": ("labour_underutilisation_rate", "broad",
            "LU4-Composite measure of labour underutilization (%)"),
}
_COLS_39_19 = [{"sex": "male"}, {"sex": "female"}, {}] + _SETTLE + [None]


def _lfs_2019_report(path: str, t36_2019: dict | None) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    o = _Out("Lesotho Labour Force Survey 2019", "2019")

    lines = _table_lines(pages, r"^Table 3\.9: Main Labour Force Indicators - LFS 2019",
                         r"^3\.3 Summary")
    runs = _numeric_runs(lines, 7)
    if len(runs) != len(_SEQ_39_19):
        raise ValueError(f"LFS 2019 T3.9: {len(runs)} rows, expected {len(_SEQ_39_19)}")
    v = dict(zip(_SEQ_39_19, runs))
    for c in range(7):
        _close(v["lf"][c], v["emp"][c] + v["unemp"][c], 2, "2019 T3.9 LF = E + U")
        _close(v["wap"][c], v["lf"][c] + v["olf"][c], 2, "2019 T3.9 pop = LF + OLF")
        _close(v["lu_n"][c], v["unemp"][c] + v["tru_n"][c] + v["plf"][c], 3,
               "2019 T3.9 LU = U + TRU + PLF")
        _close(100 * v["unemp"][c] / v["lf"][c], v["lu1"][c], 0.15, "2019 T3.9 LU1")
        _close(100 * v["lf"][c] / v["wap"][c], v["lfpr"][c], 0.15, "2019 T3.9 LFPR")
        _close(100 * v["emp"][c] / v["wap"][c], v["epr"][c], 0.15, "2019 T3.9 EPR")
    for k in v:
        if v[k][2] != v[k][6]:
            raise ValueError(f"2019 T3.9: the two Total columns differ for {k}")
    for k, (topic, definition, label) in _EMIT_39_19.items():
        for ctx, val in zip(_COLS_39_19, v[k]):
            if ctx is not None:
                o.add(topic, val, label, "LFS2019 T3.9", definition, **ctx)

    ages = ["15-19", "20-24", "25-29", "30-34", "35-39", "40-44", "45-49",
            "50-54", "55-59", "60-64", "65-69", "70-74", "75-79", "80-84", "85+"]
    # Table 3.5: age x sex -- (pop, LF, LFPR) x male / female / total.
    lines = _table_lines(pages, r"^Table 3\.5: Labour Force Participation Rate by "
                                r"Age-Group and Sex", r"^Table 3\.6 reports")
    t35 = _rows(lines, ages + ["Total"], 9)
    for lab, vals in t35.items():
        for g, ctx in enumerate(_SEXES + [{}]):
            pop, lf, rate = vals[3 * g:3 * g + 3]
            _close(100 * lf / pop, rate, 0.15, f"2019 T3.5 {lab} LFPR")
            if lab == "Total":
                _close(lf, v["lf"][[0, 1, 2][g]], 2, "2019 T3.5 total vs T3.9")
                continue
            ctx = {**ctx, "age_group": lab}
            o.add("working_age_population", pop, "Working Age", "LFS2019 T3.5", **ctx)
            o.add("labour_force", lf, "Labour Force", "LFS2019 T3.5", **ctx)
            o.add("labour_force_participation_rate", rate, "LFPR (%)", "LFS2019 T3.5", **ctx)
        # the 2024 report's comparison table reprints these LFPRs
        if t36_2019 and lab in t36_2019:
            for got, want in zip(t36_2019[lab], (vals[8], vals[2], vals[5])):
                _close(got, want, 0.05, f"2024 T3.6 2019 {lab} vs 2019 T3.5")

    # Table 3.6: age x settlement -- (pop, LF, LFPR) x U / PU / R / Total.
    lines = _table_lines(pages, r"^Table 3\.6: Labour Force Participation Rate by "
                                r"Age-group and Settlement", r"^\d+$")
    t36 = _rows(lines, ages, 12)
    for lab, vals in t36.items():
        _close(vals[9], t35[lab][6], 0, f"2019 T3.6 {lab} total pop vs T3.5")
        _close(vals[10], t35[lab][7], 0, f"2019 T3.6 {lab} total LF vs T3.5")
        for g, ctx in enumerate(_SETTLE):
            pop, lf, rate = vals[3 * g:3 * g + 3]
            _close(100 * lf / pop, rate, 0.15, f"2019 T3.6 {lab} LFPR")
            ctx = {**ctx, "age_group": lab}
            o.add("working_age_population", pop, "Working Age Popn.", "LFS2019 T3.6", **ctx)
            o.add("labour_force", lf, "Labour Force", "LFS2019 T3.6", **ctx)
            o.add("labour_force_participation_rate", rate, "LFPR (%)", "LFS2019 T3.6", **ctx)

    # Table 3.7: LFPR by district x sex.
    lines = _table_lines(pages, r"^Table 3\.7: Labour Force Participation Rate by "
                                r"District and Sex", r"^Table 3\.8 presents")
    dist19 = ["Botha-Bothe"] + _DISTRICTS[1:]
    t = _rows(lines, dist19 + ["Total"], 3)
    for lab, vals in t.items():
        if lab == "Total":
            for c, k in enumerate((0, 1, 2)):
                _close(vals[c], v["lfpr"][k], 0.05, "2019 T3.7 total vs T3.9")
            continue
        for ctx, val in zip(_SEXES + [{}], vals):
            o.add("labour_force_participation_rate", val, "LFPR (%)",
                  "LFS2019 T3.7", geography=lab, **ctx)

    # Table 7.1: unemployed by age x sex -- (Number, Percent) x M / F / T.
    lines = _table_lines(pages, r"^Table 7\.1: Unemployed Population by Age-Group "
                                r"and Sex", r"^7\.1\.2")
    ages71 = ages[:-2] + ["80+"]
    ages71 = [a for a in ages71 if a != "80-84"]
    t = _rows(lines, ages71 + ["Total"], 6)
    for lab, vals in t.items():
        n_m, n_f, n_t = vals[0], vals[2], vals[4]
        if abs(n_m + n_f - n_t) > 2:
            raise ValueError(f"2019 T7.1 {lab}: M + F != T")
        if lab == "Total":
            _close(n_t, v["unemp"][2], 0, "2019 T7.1 total vs T3.9")
            continue
        for ctx, val in zip(_SEXES + [{}], (n_m, n_f, n_t)):
            o.add("unemployed", val, "Number", "LFS2019 T7.1", age_group=lab, **ctx)

    # Table 7.2: unemployed by settlement x sex (male / female new; settlement
    # totals and the Total row are Table 3.9's).
    lines = _table_lines(pages, r"^Table 7\.2: Unemployed Population by Settlement "
                                r"and Sex", r"^7\.1\.5")
    t = _rows(lines, ["Urban", "Peri-Urban", "Rural", "Total"], 6)
    for g, lab in enumerate(["Urban", "Peri-Urban", "Rural"]):
        vals = t[lab]
        _close(vals[4], v["unemp"][3 + g], 0, f"2019 T7.2 {lab} vs T3.9")
        for ctx, val in zip(_SEXES, (vals[0], vals[2])):
            o.add("unemployed", val, "Number", "LFS2019 T7.2", **_SETTLE[g], **ctx)
    return o.rows


def _lfs_2019_tables(path: str) -> list[dict]:
    """Tables volume, Table 7.4: unemployed by district x sex. PyMuPDF renders
    one cell per line here."""
    with fitz.open(path) as doc:
        text = next(p.get_text() for p in doc
                    if re.search(r"Table 7\.4: Distribution of Unemployed Population "
                                 r"by District and Sex(?![^\n]*\.\.)", p.get_text()))
    body = text[re.search(r"Table 7\.4: Distribution of Unemployed", text).end():]
    toks = [t.strip() for t in body.splitlines() if t.strip()]
    o = _Out("Lesotho Labour Force Survey 2019", "2019")
    rows = {}
    for i, tok in enumerate(toks):
        if tok in _DISTRICTS + ["Total"] and tok not in rows:
            vals = toks[i + 1:i + 4]
            if all(re.fullmatch(_NUM, x) for x in vals):
                rows[tok] = [_f(x) for x in vals]
    if set(rows) != set(_DISTRICTS + ["Total"]):
        raise ValueError(f"LFS 2019 tables T7.4: read {sorted(rows)}")
    for c in range(3):
        if abs(sum(rows[d][c] for d in _DISTRICTS) - rows["Total"][c]) > 5:
            raise ValueError("LFS 2019 tables T7.4: districts do not sum to Total")
    for d in _DISTRICTS:
        m, f, t = rows[d]
        if abs(m + f - t) > 2:
            raise ValueError(f"LFS 2019 tables T7.4 {d}: M + F != T")
        for ctx, val in zip(_SEXES + [{}], (m, f, t)):
            o.add("unemployed", val, "Unemployed population",
                  "LFS2019 Tables T7.4", geography=d, **ctx)
    return o.rows


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    paths = {os.path.splitext(os.path.basename(_pdf(p)))[0].lower(): _pdf(p)
             for p in [local_path, *(extras or [])]}
    rows, t36_2019 = _lfs_2024(paths["2024_labour_force_survey_report"])
    rows += _lfs_2019_report(paths["2019_lesotho_lfs_report"], t36_2019)
    rows += _lfs_2019_tables(paths["2019_lesotho_lfs_tables"])
    return pd.DataFrame(rows)
