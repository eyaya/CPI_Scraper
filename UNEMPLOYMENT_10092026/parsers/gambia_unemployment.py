"""Gambia — GBoS Gambia Labour Force Survey (GLFS): headline labour-force and
labour-underutilisation indicators from three findings reports, four rounds.

The same three reports `labour/` reads (2026, 2022-23, 2018), fetched by the
same descriptor. What is taken here:

* GLFS 2026 (Q1), Annex Table 0.3 -- "Main labour force and labour
  underutilisation (LU) indicators, Population 15 years and above": counts
  (population 15+, labour force, employed, unemployed, outside LF, potential
  LF) and rates (participation, employment-to-population, time-related
  underemployment, LU1-LU4, informal employment) by sex, residence, the eight
  LGAs, adults 36+, and total.
* A PUBLISHED CONTRADICTION, kept: 0.3's youth (15-35) column and 0.4's
  Total are the same population but print 925,607 vs 919,078 persons (labour
  force 451,083 vs 444,159; LU1 8.6 vs 8.7). Both are collected; 0.3's carry
  "[Table 0.3 age column]" in series_label.
* GLFS 2026 (Q1), Annex Table 0.4 -- the same for youth 15-35 by sex,
  residence and LGA, plus NEET rates (15-35 and 15-24).
* GLFS 2025 (Q1), from Tables 2.2 and 2.3 of the 2026 report, which reprint
  2025 beside 2026 (participation, employment ratio, LU1, time-related
  underemployment, LU3, youth and adult unemployment, by sex, residence, LGA).
  The 2025 findings report itself is not fetched.
* GLFS 2022-23 ("2023 (Q1)" in GBoS's own dating), Table 3.1 -- the same
  nineteen-column table as 0.3, including youth 15-35 and adults 36+.
* GLFS 2018 (base 15-64): Table 4.3 participation rates and Table 7.1
  unemployed counts by sex, area, LGA and age group. NOTHING ELSE from 2018 --
  see the trap below.

READ BY POSITION, PROVED BY ARITHMETIC (the Liberia method). The annex tables
wrap every label around its numbers, so the reader takes each line's trailing
run of exactly N numbers (19 or 15) in printed order and maps it to the row
sequence the table prints. The mapping is then proved IN EVERY COLUMN:
labour force = employed + unemployed; population = labour force + outside;
LU1 = unemployed / labour force; participation = labour force / population;
employment ratio = employed / population; and (0.3, 0.4) underutilisation =
unemployed + time-related underemployed + potential labour force. A slipped row
breaks those identities at once and the read raises. Tables 2.2/2.3 are proved
the other way round: the 2026 half of every row must equal the annex values,
which pins the row order before the 2025 half is taken.

PUBLISHED DEFECTS, HANDLED EXPLICITLY:

* GLFS 2022-23 Table 3.1 prints urban and rural PARTICIPATION as 62,6 and 37,4,
  while its own counts give 44,3 and 42,5 (and the urban and rural EMPLOYMENT
  RATIOS, 40,2 and 40,6, reproduce exactly). Those two cells are not
  collected; `_KNOWN_BAD` re-checks that they still fail, so a corrected
  reprint is noticed. In two columns of the same table (female; with a
  functional difficulty) the labour-underutilisation COUNT leaves out the
  time-related underemployed -- the gap is exactly that column's TRU count
  (53,820; 2,745). Check-only counts, never emitted, listed likewise.
* Table 2.2 prints the 2025 youth and adult unemployment rates as 11,5 / 11,5
  / 11,5 and 4,4 / 4,4 / 4,4 for male / female / total -- the sex cells repeat
  the total. They are not collected (urban, rural and total are); the reader
  raises if they ever differ, so a correction is taken deliberately.
* THE 2018 REPORT'S "RATE" TABLES ARE DISTRIBUTIONS. Tables 7.3, 7.4, 7.5,
  9.2, 9.7 and 9.8 are captioned "Unemployment Rate" / "Employment to
  Population Ratio" but every column sums to 100 down the LGAs or areas: they
  are SHARES of the unemployed (or employed), e.g. Basse 26,5 = Basse's share
  of the unemployed, not its unemployment rate. The executive summary repeats
  them as rates ("youth employment-to-population ratio in the urban areas is
  54,7 per cent"). Filing them as rates would publish real values under the
  wrong series, so they are refused; so is the prose-only national 35,2%.
  Table 7.3 even contradicts Table 7.4 on the same shares (rural 76,6 vs 69,4,
  the latter matching Table 7.1's counts).

NOT COLLECTED: the disability and own-use-foodstuff columns (no schema column
holds them); counts of informal employment, discouraged job-seekers and
agricultural employment and their percentages (no topic); NEET counts.
The 2026 report says 2025 informal-employment figures are not comparable
(full 21st ICLS adoption in 2026), and Tables 2.2/2.3 print none.

DEFINITIONS: LU1 is the ILO strict unemployment rate; LU2, LU3 and LU4 are the
broad underutilisation measures. Periods: 2026-Q1, 2025-Q1, 2023-Q1, 2018.

CROSS-CHECK: 2026 population 15+ 1,434,115; labour force 781,868; LU1 6.2;
LFPR 54.5; LU4 32.1; youth LU1 8.7; Banjul LU1 12.5. 2025: LFPR 47.1, LU1 8.3,
Kuntaur LU1 19.6. 2022-23: labour force 609,410; LU1 7.6; LFPR 43.6.
2018: LFPR 53.0 (Basse 77.6); unemployed 15-64 234,725.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_GLFS = "Gambia Labour Force Survey (GLFS)"
_LGAS = ["Banjul", "Kanifing", "Brikama", "Mansakonko", "Kerewan", "Kuntaur",
         "Janjanbureh", "Basse"]
_SEX_RES = [{"sex": "male"}, {"sex": "female"},
            {"locality": "urban", "locality_label": "Urban"},
            {"locality": "rural", "locality_label": "Rural"}]
_GEO = [{"geography": g} for g in _LGAS]
_SKIP = None

_NUM = re.compile(r"^(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?|n\.a\.)$")

# key -> (topic, definition, series label as GBoS prints it)
_EMIT = {
    "wap": ("working_age_population", "not_applicable", "Population"),
    "lf": ("labour_force", "not_applicable", "Labour force"),
    "emp": ("employed", "not_applicable", "Employed"),
    "unemp": ("unemployed", "not_applicable", "Unemployed"),
    "olf": ("outside_labour_force", "not_applicable", "Outside the labour force"),
    "plf_n": ("potential_labour_force", "not_applicable", "Potential labour force"),
    "lfpr": ("labour_force_participation_rate", "not_applicable",
             "Labour force participation rate (%)"),
    "epr": ("employment_to_population_ratio", "not_applicable",
            "Employment-to-population ratio (%)"),
    "tru": ("underemployment_rate", "not_applicable",
            "Time related underemployment rate (%)"),
    "inf_pct": ("informal_employment_share", "not_applicable",
                "Informal employment (%)"),
    "lu1": ("unemployment_rate", "strict", "LU1: Unemployment rate (%)"),
    "lu2": ("labour_underutilisation_rate", "broad",
            "LU2: Combined rate of time-related underemployment and unemployment (%)"),
    "lu3": ("labour_underutilisation_rate", "broad",
            "LU3: Combined rate of unemployment and potential labour force (%)"),
    "lu4": ("labour_underutilisation_rate", "broad",
            "LU4: Composite measure of labour underutilisation (%)"),
    "neet35": ("neet_rate", "not_applicable", "NEET % (15-35)"),
    "neet24": ("neet_rate", "not_applicable", "NEET % (15-24)"),
}

# Printed row orders (each line of exactly N numbers, in order).
_SEQ_03 = ["wap", "lf", "emp", "unemp", "olf", "lu_n", "lu_unemp", "tru_n",
           "plf_n", "inf_n", "disc_n", "agri_n", "nonagri_n", "inf_na_n",
           "lfpr", "olf_pct", "plf_pct", "epr", "disc_olf", "disc_pop",
           "inf_pct", "agri_pct", "inf_na_pct", "tru", "lu1", "lu2", "lu3", "lu4"]
_SEQ_04 = ["wap", "lf", "emp", "unemp", "olf", "lu_n", "lu_unemp", "tru_n",
           "plf_n", "neet35_n", "neet24_n", "inf_n", "disc_n", "agri_n",
           "nonagri_n", "inf_na_n", "lfpr", "olf_pct", "plf_pct", "epr",
           "neet35", "neet24", "disc_olf", "disc_pop", "inf_pct", "agri_pct",
           "inf_na_pct", "tru", "lu1", "lu2", "lu3", "lu4"]
_SEQ_31 = ["wap", "lf", "emp", "unemp", "olf", "lu_n", "lu_unemp", "tru_n",
           "plf_n", "inf_n", "inf_pct", "lfpr", "epr", "tru", "lu1", "lu2",
           "lu3", "lu4"]

# Column contexts, printed order. _SKIP = no schema column holds it.
_COLS_03 = (_SEX_RES + _GEO + [_SKIP, _SKIP]            # without / with disability
            + [{"age_group": "15-35", "_suffix": " [Table 0.3 age column]"},
               {"age_group": "36+"}]                     # youth / adult
            + [_SKIP, _SKIP, {}])                       # foodstuff / not / Total
_COLS_04 = _SEX_RES + _GEO + [_SKIP, _SKIP, {}]          # foodstuff / not / Total
_COLS_31 = (_SEX_RES + _GEO + [_SKIP, _SKIP]            # with / without difficulty
            + [{"age_group": "15-35"}, {"age_group": "36+"}]
            + [_SKIP, _SKIP, {}])

# (table, key, column index) printed cells that fail their own arithmetic.
_KNOWN_BAD = {("T3.1", "lfpr", 2), ("T3.1", "lfpr", 3),
              # labour underutilisation counts that OMIT the time-related
              # underemployed (gap = exactly that column's TRU count): female
              # 162,004 vs 215,824, "with functional difficulty" 6,609 vs
              # 9,354. Check-only counts; never emitted.
              ("T3.1", "lu_n", 1), ("T3.1", "lu_n", 12)}


def _pages(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [p.extract_text() or "" for p in pdf.pages]


def _numeric_runs(texts: list[str], n: int) -> list[list[float | None]]:
    rows = []
    for t in texts:
        for ln in t.splitlines():
            # A wrapped label can be glued to its first value
            # ("underemploymen9.2 20.3 ..."): split a letter from a number.
            toks = re.sub(r"(?<=[A-Za-z])(?=\d+(?:\.\d+)?(?:\s|$))", " ", ln).split()
            run = []
            for tok in reversed(toks):
                if _NUM.match(tok):
                    run.append(tok)
                else:
                    break
            if len(run) == n:
                rows.append([None if x == "n.a." else float(x.replace(",", ""))
                             for x in reversed(run)])
    return rows


def _caption_page(pages: list[str], caption: str) -> int:
    rx = re.compile(caption + r"(?![^\n]*\.{4})", re.M)
    hits = [i for i, t in enumerate(pages) if rx.search(t)]
    if not hits:
        raise ValueError(f"GLFS: caption {caption!r} not found")
    return hits[-1]       # the annex copy, after any list-of-tables mention


def _region(pages: list[str], start: int, end_caption: str | None,
            span: int) -> list[str]:
    out = []
    for i in range(start, min(start + span, len(pages))):
        t = pages[i]
        if i == start:
            t = t[t.index("Table"):] if "Table" in t else t
        if end_caption and i > start and re.search(end_caption, t):
            out.append(t[:re.search(end_caption, t).start()])
            break
        out.append(t)
    return out


def _check(v: dict, code: str, ncols: int, lu_identity: bool) -> set:
    """Prove the row mapping column by column. Returns the (key, col) cells
    that fail and are listed in _KNOWN_BAD; raises on any other failure."""
    bad = set()

    def fail(key, c, msg):
        if (code, key, c) in _KNOWN_BAD:
            bad.add((key, c))
        else:
            raise ValueError(f"GLFS {code} col {c}: {msg}")

    for c in range(ncols):
        if abs(v["lf"][c] - v["emp"][c] - v["unemp"][c]) > 2:
            fail("lf", c, "labour force != employed + unemployed")
        if abs(v["wap"][c] - v["lf"][c] - v["olf"][c]) > 2:
            fail("wap", c, "population != labour force + outside")
        if lu_identity and abs(v["lu_n"][c] - v["unemp"][c] - v["tru_n"][c]
                               - v["plf_n"][c]) > 3:
            fail("lu_n", c, "underutilisation != U + TRU + PLF")
        if v["lu1"][c] is not None and abs(100 * v["unemp"][c] / v["lf"][c]
                                           - v["lu1"][c]) > 0.15:
            fail("lu1", c, "LU1 != unemployed / labour force")
        if abs(100 * v["lf"][c] / v["wap"][c] - v["lfpr"][c]) > 0.15:
            fail("lfpr", c, "participation != labour force / population")
        if abs(100 * v["emp"][c] / v["wap"][c] - v["epr"][c]) > 0.15:
            fail("epr", c, "employment ratio != employed / population")
    missing = {(k, c) for (t, k, c) in _KNOWN_BAD if t == code} - bad
    if missing:
        raise ValueError(f"GLFS {code}: cells {sorted(missing)} now reproduce -- "
                         f"GBoS corrected them; remove them from _KNOWN_BAD")
    return bad


def _emit(v: dict, cols: list, bad: set, *, survey: str, period: str,
          reference: str, frequency: str, base: str, code: str,
          age: str | None = None, youth: bool = False) -> list[dict]:
    out = []
    for key, (topic, definition, label) in _EMIT.items():
        if key not in v:
            continue
        for c, ctx in enumerate(cols):
            if ctx is None or (key, c) in bad or v[key][c] is None:
                continue
            ctx = dict(ctx)
            suffix = ctx.pop("_suffix", "")
            t = topic
            if age and "age_group" not in ctx:
                ctx["age_group"] = age
            if key == "neet24":
                ctx["age_group"] = "15-24"
            if key == "lu1" and (youth or ctx.get("age_group") == "15-35"):
                t = "youth_unemployment_rate"
            lab = label
            if key == "wap":
                lab = f"Population {ctx.get('age_group', '15+')}" \
                    if ctx.get("age_group") not in (None, "36+") else "Population 15+"
            out.append(C.row(topic=t, value=v[key][c], series_label=lab + suffix,
                             survey=survey, period=period,
                             reference_period=reference, frequency=frequency,
                             working_age_base=base, definition=definition,
                             series_code=code, **ctx))
    return out


def _annex_2026(pages: list[str]) -> tuple[list[dict], dict, dict]:
    p03 = _caption_page(pages, r"^Table 0\.3: Main labour force and labour underutilisation")
    p04 = _caption_page(pages, r"^Table 0\.4: Main labour force and labour underutilisation")
    r03 = _numeric_runs(_region(pages, p03, r"^Table 0\.4", 4), 19)
    r04 = _numeric_runs(_region(pages, p04, None, 3), 15)
    if len(r03) != len(_SEQ_03) or len(r04) != len(_SEQ_04):
        raise ValueError(f"GLFS 2026 annex: {len(r03)}/{len(r04)} rows, expected "
                         f"{len(_SEQ_03)}/{len(_SEQ_04)}")
    v03, v04 = dict(zip(_SEQ_03, r03)), dict(zip(_SEQ_04, r04))
    b03 = _check(v03, "T0.3", 19, True)
    b04 = _check(v04, "T0.4", 15, True)
    # 0.3's youth column and 0.4's Total column should be one population and
    # are not (925,607 vs 919,078 aged 15-35; LU1 8.6 vs 8.7). A published
    # contradiction: both are kept, 0.3's labelled as its age column. Raise if
    # they ever agree, so the duplicate is then dropped deliberately.
    if v03["wap"][14] == v04["wap"][14]:
        raise ValueError("GLFS 2026: 0.3 youth column now equals 0.4 -- drop it")
    kw = dict(survey=f"{_GLFS} 2026 (Q1)", period="2026-Q1",
              reference="GLFS 2026 (Q1)", frequency="annual", base="15+")
    out = _emit(v03, _COLS_03, b03, code="GLFS 2026 T0.3", **kw)
    out += _emit(v04, _COLS_04, b04, code="GLFS 2026 T0.4", age="15-35",
                 youth=True, **kw)
    return out, v03, v04


_ROWS_22 = ["lfpr", "epr", "lu1", "tru", "lu3", "youth", "adult", "ownuse"]
_LBL_22 = {
    "lfpr": ("labour_force_participation_rate", "not_applicable", "Labour force participation rate"),
    "epr": ("employment_to_population_ratio", "not_applicable", "Employment-to-population ratio"),
    "lu1": ("unemployment_rate", "strict", "Unemployment rate (LU1)"),
    "tru": ("underemployment_rate", "not_applicable", "Time-related underemployment rate"),
    "lu3": ("labour_underutilisation_rate", "broad", "Labour underutilisation (LU3)"),
    "youth": ("youth_unemployment_rate", "strict", "Youth (15-35) unemployment rate"),
    "adult": ("unemployment_rate", "strict", "Adult (36+) unemployment rate"),
}


def _tables_2_2_and_2_3(pages: list[str], v03: dict, v04: dict) -> list[dict]:
    """2025 (Q1) from the comparison tables; the 2026 halves must equal the
    annex, which proves the row order."""
    p22 = _caption_page(pages, r"^Table 2\.2: Labour market changes by sex and residence")
    p23 = _caption_page(pages, r"^Table 2\.3: Labour Market Indicators by LGA")
    r22 = _numeric_runs(_region(pages, p22, r"^Figure 2\.2", 1), 10)
    t23 = _region(pages, p23, r"^Figure 2\.4", 1)
    r23 = _numeric_runs(t23, 9)
    if len(r22) != 8 or len(r23) != 16:
        raise ValueError(f"GLFS T2.2/T2.3: {len(r22)}/{len(r23)} rows, expected 8/16")
    v22 = dict(zip(_ROWS_22, r22))
    v23_25 = dict(zip(_ROWS_22, r23[:8]))
    v23_26 = dict(zip(_ROWS_22, r23[8:]))
    # 2026 halves vs the annex (sex/residence = annex cols 0-3, total = 18;
    # LGAs = annex cols 4-11; youth from 0.4).
    annex = {"lfpr": v03["lfpr"], "epr": v03["epr"], "lu1": v03["lu1"],
             "tru": v03["tru"], "lu3": v03["lu3"], "youth": v04["lu1"]}
    for k, ref in annex.items():
        tot = ref[14] if k == "youth" else ref[18]
        if v22[k][5:10] != ref[0:4] + [tot]:
            raise ValueError(f"GLFS T2.2 2026 {k} {v22[k][5:10]} != annex")
        if v23_26[k] != ref[4:12] + [tot]:
            raise ValueError(f"GLFS T2.3 2026 {k} {v23_26[k]} != annex")
    if v22["adult"][9] != v03["lu1"][15]:
        raise ValueError("GLFS T2.2 2026 adult unemployment != annex 36+ column")
    # Published copies: 2025 youth/adult male and female repeat the total.
    copies = set()
    for k in ("youth", "adult"):
        m, f, tot = v22[k][0], v22[k][1], v22[k][4]
        if m == f == tot:
            copies |= {(k, 0), (k, 1)}
        else:
            raise ValueError(f"GLFS T2.2 2025 {k}: sex cells no longer copy the "
                             f"total -- GBoS corrected them; collect them")

    out = []
    for period, survey, rows, cols, code in (
            ("2025-Q1", f"{_GLFS} 2025 (Q1)", v22, _SEX_RES + [{}], "GLFS 2026 T2.2"),
            ("2025-Q1", f"{_GLFS} 2025 (Q1)", v23_25, _GEO + [{}], "GLFS 2026 T2.3"),
            ("2026-Q1", f"{_GLFS} 2026 (Q1)", v23_26, _GEO + [{}], "GLFS 2026 T2.3")):
        for k, (topic, definition, label) in _LBL_22.items():
            # 2026: only the adult-by-LGA rows are new (the rest is the annex).
            if period == "2026-Q1" and k != "adult":
                continue
            vals = rows[k][:5] if code.endswith("T2.2") else rows[k]
            for c, (ctx, val) in enumerate(zip(cols, vals)):
                if code.endswith("T2.2") and (k, c) in copies:
                    continue
                if period == "2026-Q1" and ctx == {}:
                    continue            # national adult rate: annex T0.3
                if code.endswith("T2.3") and ctx == {}:
                    # 2025's national column is printed by T2.2 as well:
                    # taken once, from T2.2, and required to agree.
                    if val != v22[k][4]:
                        raise ValueError(f"GLFS T2.3 2025 {k} total {val} != "
                                         f"T2.2 {v22[k][4]}")
                    continue
                ctx = dict(ctx)
                if k == "youth":
                    ctx["age_group"] = "15-35"
                if k == "adult":
                    ctx["age_group"] = "36+"
                out.append(C.row(topic=topic, value=val, series_label=label,
                                 survey=survey, period=period,
                                 reference_period=f"GLFS {period[:4]} (Q1)",
                                 frequency="annual", working_age_base="15+",
                                 definition=definition, series_code=code, **ctx))
    return out


def _glfs_2022_23(pages: list[str]) -> list[dict]:
    p = _caption_page(pages, r"^Table 3\. ?1: Main labour force and labour "
                             r"underutilization \(LU\) indicators")
    rows = _numeric_runs(_region(pages, p, r"^(?:A similar pattern|Figure 3)", 2), 19)
    if len(rows) != len(_SEQ_31):
        raise ValueError(f"GLFS 2022-23 T3.1: {len(rows)} rows, expected {len(_SEQ_31)}")
    v = dict(zip(_SEQ_31, rows))
    bad = _check(v, "T3.1", 19, True)
    return _emit(v, _COLS_31, bad, survey=f"{_GLFS} 2022-23", period="2023-Q1",
                 reference="GLFS 2022-23", frequency="annual", base="15+",
                 code="GLFS 2022-23 T3.1")


def _glfs_2018(pages: list[str]) -> list[dict]:
    kw = dict(survey=f"{_GLFS} 2018", period="2018", reference_period="GLFS 2018",
              frequency="ad_hoc", working_age_base="15-64")
    out = []
    # Table 4.3: participation rate by sex, area, LGA.
    p = _caption_page(pages, r"^Table 4\.3: Labour Force Participation Rate by Area")
    t = pages[p][pages[p].index("Table 4.3:"):]
    ctx = {"Male": {"sex": "male"}, "Female": {"sex": "female"},
           "Urban": {"locality": "urban", "locality_label": "Urban"},
           "Rural": {"locality": "rural", "locality_label": "Rural"},
           "The Gambia": {}, **{g: {"geography": g} for g in _LGAS}}
    got = {}
    for ln in t.splitlines():
        m = re.fullmatch(r"(Male|Female|Urban|Rural|The Gambia|"
                         + "|".join(_LGAS) + r") (\d+\.\d)", ln.strip())
        if m:
            got[m.group(1)] = float(m.group(2))
    if set(got) != set(ctx):
        raise ValueError(f"GLFS 2018 T4.3: read {sorted(got)}")
    for lab, val in got.items():
        out.append(C.row(topic="labour_force_participation_rate", value=val,
                         series_label="Labour force participation rate",
                         definition="not_applicable", series_code="GLFS 2018 T4.3",
                         **kw, **ctx[lab]))
    # Table 7.1: unemployed persons 15-64 by sex / area / LGA x age group.
    p = _caption_page(pages, r"^Table 7\.1: Number of Unemployed Persons")
    t = pages[p][pages[p].index("Table 7.1:"):]
    ages = ["15-24", "25-35", "36-64", "Total"]
    rows = {}
    for ln in t.splitlines():
        m = re.fullmatch(r"(Male|Female|Urban|Rural|The Gambia|" + "|".join(_LGAS)
                         + r")((?: \d{1,3}(?:,\d{3})*){4})", ln.strip())
        if m:
            rows[m.group(1)] = [float(x.replace(",", "")) for x in m.group(2).split()]
    if set(rows) != set(ctx):
        raise ValueError(f"GLFS 2018 T7.1: read {sorted(rows)}")
    tot = rows["The Gambia"]
    for r in rows.values():
        if sum(r[:3]) != r[3]:
            raise ValueError(f"GLFS 2018 T7.1: age groups do not sum: {r}")
    for group in (("Male", "Female"), ("Urban", "Rural"), tuple(_LGAS)):
        if [sum(rows[g][j] for g in group) for j in range(4)] != tot:
            raise ValueError(f"GLFS 2018 T7.1: {group} do not sum to the total")
    for lab, vals in rows.items():
        for age, val in zip(ages, vals):
            out.append(C.row(topic="unemployed", value=val,
                             series_label="Number of unemployed persons",
                             definition="not_applicable",
                             series_code="GLFS 2018 T7.1",
                             age_group=age if age != "Total" else "Total",
                             **kw, **ctx[lab]))
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    out = []
    for p in [path, *(extras or [])]:
        pages = _pages(p)
        name = p.replace("\\", "/").rsplit("/", 1)[-1]
        if "2026" in name:
            rows, v03, v04 = _annex_2026(pages)
            out += rows + _tables_2_2_and_2_3(pages, v03, v04)
        elif "2022" in name:
            out += _glfs_2022_23(pages)
        elif "2018" in name:
            out += _glfs_2018(pages)
        else:
            raise ValueError(f"GLFS: unrecognised report {name!r}")
    return pd.DataFrame(out)
