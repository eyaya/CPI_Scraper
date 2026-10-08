"""Cabo Verde — INE Inquérito Multiobjetivo Contínuo (IMC), "Estatísticas do
Mercado de Trabalho", Principais Quadros workbook (one per annual round).

A HOUSEHOLD survey (the IMC is INE's continuous multi-purpose household
survey, run in two semesters), base 15+. The workbook is ~115 sheets; the
SERIES sheets reprint every round since 2011, so one current file carries the
whole history and each run accumulates by merge.

WHAT IS READ

Series sheets, 2011-2025 (columns = rounds; 2024 and 2025 also split into
1º/2º Semestre, dated 2024-H1 / 2024-H2 beside the annual 2024):

* TAB_9   counts by RAMO DE ATIVIDADE (21 branches + ND), Cabo Verde / Urbano / Rural
* TAB_10  counts by PROFISSÃO (10 groups incl. Militar, + ND)
* TAB_11  counts by SETOR DE ATIVIDADE (Primário / Secundário / Terciário)
* TAB_12  counts by SITUAÇÃO NA PROFISSÃO (8 + ND)
* TAB_28/29/31/33  the same distributions as column percentages by residence;
  TAB_30/32 the branch and occupation percentages by SEX
* TAB_14  counts in EMPREGO INFORMAL by residence, concelho, sex, age (2015-)
* TAB_38  the informal share of employment (%) for the same groups

2025-only sheets, for cuts the series do not carry:

* TAB_54 / TAB_57  sector and status (%) by CONCELHO, sex and age group
* TAB_55 / TAB_56  branch and occupation counts by SEX (their Cabo Verde /
  Urbano / Rural columns repeat TAB_9/10 and are not read -- see below)
* TAB_63 / TAB_65  informal employment (count, %) by sex and age WITHIN each
  residence and concelho

THE ICLS BREAK TRAVELS IN `survey`. Row 2 of every series sheet heads the
2011-2020 columns "Resolução da 13ª CIET" and 2022 onward "Resolução I da 19ª
CIET". Employment is a different concept either side (19th ICLS excludes
own-use production), so the two are separate surveys here and a series never
chains across them -- as Angola's two IEA workbooks. There is no 2021 round.

TOPICS. Branch -> industry; profissão -> occupation; setor de atividade
(primary/secondary/tertiary) -> industry, a coarser grouping of the same
thing. SITUAÇÃO NA PROFISSÃO -> employment_status, deliberately, although its
first three categories subdivide EMPLOYEES by employer (administração pública
/ setor empresarial privado / setor empresarial do Estado): the nine
categories partition the employed and INE files them as one status variable,
so they stay together, classified National. Informal employment -> formality.

CLASSIFICATION: National throughout. The branch labels are recognisably ISIC
Rev.4 sections and the occupation groups ISCO-08 major groups, but no scheme
is named against these tables -- CITP-08 appears only in the headers of TAB_36
and TAB_73 (managers, groups 11-13), which are not read.

DUPLICATES ARE CHECKED, NOT ASSUMED AWAY. Several sheets reprint the same cell
(TAB_30's national block = TAB_29's; TAB_54's residence rows = TAB_28's 2025
column; TAB_63's residence rows = TAB_14's 2025 column). Every duplicate merge
key must carry the same value (to the sheets' rounding) or the parse raises;
the first reading is kept.

THE CHECK HAS FOUND TWO REAL DISAGREEMENTS, each settled by the counts:

* TAB_30 and TAB_32 reprint TAB_29/31's national block and differ in three
  cells: 2019 transporte e armazenagem 5,782 vs 5,732, 2019 atividades
  administrativas 3,708 vs 3,748, 2018 especialistas 9,245 vs 9,203. TAB_29/31
  are what the TAB_9/10 counts give (11 828,10 / 206 344,42 = 5,732), so the
  national block comes from them and TAB_30/32 are read for their SEX blocks.
* TAB_38's 2025 ANNUAL informal share is the MEAN OF THE TWO SEMESTER SHARES
  (men: 50,26 and 49,45 -> 49,85), while TAB_65's is informal / employed for
  the year (58 731,24 / 117 823,55 = 49,847) -- two published estimators, up
  to 0,46 points apart by concelho. The series sheet is kept for its own
  cells, so the 2011-2025 series is one method; TAB_65 contributes only the
  sex and age groups WITHIN a residence or concelho, which TAB_38 lacks.

TWO COLLISIONS ARE RESOLVED BY DROPPING, and why:

* The broad-sector sheets (11, 28, 54) print their own "Total" and "ND" rows,
  which land on the same key as the branch sheets' (9, 29): the same
  employed total, the same undeclared group. They are taken from the branch
  sheets only. They do NOT always agree -- 2019 ND reads 392,11 in TAB_9
  against 391,87 in TAB_11 -- which is why a silent overwrite would matter.
* TAB_55/56 (2025) and TAB_57 respell categories the series use ("Outras
  Actividades" vs "Outras Atividades", "intelectuais" vs "inteletuais", status
  "Administração pública" vs "Trabalhador de administração pública"). Reading
  their national/residence cells would enter 2025 twice under two labels, so
  only the cuts the series lack are read from them (sex; concelho/sex/age).
  Labels are otherwise kept VERBATIM, spelling included.

PLACE NAMES are the one thing normalised: TAB_63/65 write "Tarrafal de São
Nicolau", "Ribeira Grande de Santiago" and "Santa Catarina do Fogo" where
every other sheet omits the "de"/"do". A concelho is a geography key, not a
published category, and two spellings of one municipality would split its
rows -- and hide from the duplicate check the cells TAB_63 reprints from
TAB_14. ("Ribeira Grande", unqualified, is the Santo Antão concelho, a
different place, and is left alone.)

FLOAT NOISE: cells are formula results carried to full binary precision
(a Total of 100.00000000000907), so every value is rounded to 9 decimal
places -- far below the published precision, and not a recomputation.

TRAPS: counts are unrounded weighted estimates (178571.37...) and are kept as
published; "…" (and once "...") marks CONFIDENTIAL cells -- never 0; "ND"
carries published zeros in the 19th-ICLS columns, which are kept; row labels
sometimes carry a stray leading apostrophe; year headers are merged cells.

NOT READ: TAB_13/37 (non-agricultural employment -- agriculture vs the rest,
already in TAB_9), TAB_15/39 (informal NON-AGRICULTURAL employment: TAB_39's
denominator is non-agricultural employment, a different universe from
TAB_38's), TAB_16/40 (manufacturing, in TAB_9), TAB_17-18/35/41-44 (job
quality), TAB_36/73 (managers by sex -- row percentages), hours, earnings and
every rate.

CROSS-CHECK (2025 annual): employed 213 166,07 (urbano 172 143,82, rural
41 022,25); construção 27 122,91; profissões elementares 51 315,70; setor
empresarial privado 97 810,89; emprego informal 97 288,64 (45,64%); 2011
employed 178 571,37 (13th ICLS).
"""
from __future__ import annotations

import re
from collections import defaultdict

import openpyxl
import pandas as pd

from . import _common as C

S13 = "Inquérito Multiobjetivo Contínuo (IMC), Resolução da 13ª CIET"
S19 = "Inquérito Multiobjetivo Contínuo (IMC), Resolução I da 19ª CIET"
_BASE = "15+"
_MISSING = {"…", "...", ""}
# TAB_63/65 spell three concelhos differently from every other sheet.
_PLACE = {"Tarrafal de São Nicolau": "Tarrafal São Nicolau",
          "Ribeira Grande de Santiago": "Ribeira Grande Santiago",
          "Santa Catarina do Fogo": "Santa Catarina Fogo"}

# Section headings inside group tables, and the dimension each opens.
_SECTIONS = {"meio de residencia": "locality", "concelho": "geography",
             "sexo": "sex", "grupo etario": "age_group",
             "grupo etario (em anos)": "age_group"}
_GROUP_TOKENS = {"cabo verde": {}, "urbano": {"locality": "urban"},
                 "rural": {"locality": "rural"},
                 "masculino": {"sex": "male"}, "feminino": {"sex": "female"}}


def _clean(v) -> str:
    return re.sub(r"\s+", " ", str(v or "")).strip().lstrip("'‘’").strip()


def _key(s: str) -> str:
    return C.deaccent(_clean(s)).lower()


def _num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 9)
    s = _clean(v)
    return None if s in _MISSING else round(float(s.replace(",", ".")), 9)


def _group(label: str, section: str | None) -> dict:
    """The row's own group: national, a residence, a concelho, a sex, an age."""
    k = _key(label)
    if k == "cabo verde":
        return {}
    if section == "locality" or (section is None and k in ("urbano", "rural")):
        return {"locality": "urban" if k == "urbano" else "rural",
                "locality_label": label}
    if section == "geography":
        return {"geography": _PLACE.get(label, label)}
    if section == "sex":
        return {"sex": C.normalise_sex(label)}
    if section == "age_group":
        return {"age_group": label}
    raise ValueError(f"row {label!r} under no known section")


def _dims(d: dict) -> dict:
    out = dict(d)
    if "locality" in out:
        out.setdefault("locality_label",
                       "Urbano" if out["locality"] == "urban" else "Rural")
    return out


# --------------------------------------------------------------------------
# Series sheets: rounds across the columns
# --------------------------------------------------------------------------

def _series_columns(ws) -> list[tuple[int, str, str, str, str]]:
    """(col, period, reference, frequency, survey) for each value column."""
    r2 = [c.value for c in ws[2]]
    r3 = [c.value for c in ws[3]]
    r4 = [c.value for c in ws[4]]
    start19 = next((i for i, v in enumerate(r2) if v and "19" in str(v)), None)
    if start19 is None or not any(v and "13" in str(v) for v in r2):
        raise ValueError(f"{ws.title}: no 13ª/19ª CIET header in row 2")
    cols, year = [], None
    for i in range(1, len(r3)):
        if isinstance(r3[i], (int, float)):
            year = int(r3[i])
        sem = _key(r4[i]) if i < len(r4) else ""
        if year is None or (r3[i] is None and not sem):
            continue
        if sem.startswith("1"):
            per, ref, freq = f"{year}-H1", f"1º Semestre {year}", "semiannual"
        elif sem.startswith("2"):
            per, ref, freq = f"{year}-H2", f"2º Semestre {year}", "semiannual"
        else:
            per, ref, freq = str(year), str(year), "annual"
        cols.append((i, per, ref, freq, S19 if i >= start19 else S13))
    return cols


def _series(ws, *, topic: str, measure: str, code: str, mode: str,
            expect: int, blocks: set[str] | None = None,
            drop: set[str] = frozenset(),
            characteristic: str | None = None) -> list[dict]:
    """`mode` "category": blocks of category rows (Cabo Verde/Urbano/...).
    `mode` "group": each row is a group, `characteristic` names the value."""
    cols = _series_columns(ws)
    unit = "persons" if measure == "count" else "percent"
    grid, per_block = [], defaultdict(int)   # (block, char, dims, cells)
    block, section = None, None
    for row in ws.iter_rows(min_row=5, values_only=True):
        label = _clean(row[0])
        if not label:
            continue
        if _key(label).startswith(("fonte", "nd -", "... dados", "… dados")):
            break
        cells = [row[i] if i < len(row) else None for i, *_ in cols]
        has_cell = any(_clean(v) != "" for v in cells if v is not None)
        k = _key(label)
        if mode == "category":
            if k in _GROUP_TOKENS and (not has_cell or k == "cabo verde"):
                block = k
                if not has_cell:
                    continue
                label = "Total"          # the CABO VERDE row carries the total
            elif not has_cell:
                continue                  # "MEIO DE RESIDÊNCIA"
            dims, char = _dims(_GROUP_TOKENS[block]), label
            if char != "Total":
                per_block[block] += 1
        else:
            if not has_cell:
                section = _SECTIONS.get(k, section)
                continue
            dims, char = _group(label, section), characteristic
            per_block["rows"] += 1
        grid.append((block if mode == "category" else None, char, dims, cells))
    short = {b: n for b, n in per_block.items() if n != expect}
    if not per_block or short:
        raise ValueError(f"IMC {code}: expected {expect} rows per block, "
                         f"read {dict(per_block) or 'none'}")

    bad = _defective_columns(grid, cols, code) if (
        mode == "category" and measure == "share") else set()
    out = []
    for blk, char, dims, cells in grid:
        if char in drop or (blocks is not None and blk not in blocks):
            continue
        for j, ((i, per, ref, freq, survey), v) in enumerate(zip(cols, cells)):
            val = _num(v)
            if val is None or (blk, j) in bad:
                continue
            out.append(C.row(topic=topic, characteristic=char,
                             classification="National" if topic != "formality"
                             else "Not applicable",
                             value=val, survey=survey, period=per,
                             reference_period=ref, frequency=freq,
                             measure="count" if measure == "count" else "share",
                             unit=unit, working_age_base=_BASE,
                             series_code=f"IMC {code}", **dims))
    return out


def _defective_columns(grid, cols, code: str) -> set[tuple[str, int]]:
    """(block, column) cells of a percentage sheet that are not a distribution
    of that block, found structurally so an INE correction is picked up:

    * a residence or sex column IDENTICAL, category by category, to the
      national one -- a copied block (TAB_31, Urbano/Rural 2011-2018);
    * a column whose categories sum more than 3 points from 100 while none of
      them is confidential (TAB_28, Rural 2024-H2: 46,39).

    Each is announced; the counts sheets carry the true figures."""
    by = defaultdict(dict)                 # block -> {char: cells}
    for blk, char, _, cells in grid:
        if char != "Total":
            by[blk][char] = cells
    nat = by.get("cabo verde", {})
    bad = set()
    for blk, rows in by.items():
        for j, (_, per, *_rest) in enumerate(cols):
            vals = [_num(c[j]) for c in rows.values()]
            nums = [v for v in vals if v is not None]
            if blk != "cabo verde" and nat and len(nums) >= 3:
                natv = [_num(nat[ch][j]) if ch in nat else None for ch in rows]
                if vals == natv:
                    bad.add((blk, j))
                    print(f"[Cabo_Verde] IMC {code}: {blk} {per} is a copy of the "
                          f"national column -- not collected")
                    continue
            if nums and None not in vals and abs(sum(nums) - 100) > 3:
                bad.add((blk, j))
                print(f"[Cabo_Verde] IMC {code}: {blk} {per} sums to "
                      f"{sum(nums):.2f}, not 100 -- not collected")
    return bad


# --------------------------------------------------------------------------
# 2025 cross-tables: one round, the dimensions across the columns
# --------------------------------------------------------------------------

def _header(ws, row: int) -> list[str]:
    return [_clean(c.value) for c in ws[row]]


def _groups_by_categories(ws, *, topic: str, code: str, expect: int,
                          skip_rows: set[str]) -> list[dict]:
    """TAB_54 / TAB_57: rows = groups, columns = categories (%)."""
    head = _header(ws, 2)
    out, section, n = [], None, 0
    for row in ws.iter_rows(min_row=3, values_only=True):
        label = _clean(row[0])
        k = _key(label)
        if not label:
            continue
        if k.startswith("fonte"):
            break
        if all(_num(v) is None for v in row[1:]):
            section = _SECTIONS.get(k, section)
            continue
        n += 1
        if k in skip_rows:
            continue
        dims = _group(label, section)
        for cat, v in zip(head[1:], row[1:]):
            val = _num(v)
            if cat and val is not None:
                out.append(_row25(topic, cat, val, "share", code, dims))
    if n != expect:
        raise ValueError(f"IMC {code}: expected {expect} group rows, read {n}")
    return out


def _categories_by_sex(ws, *, topic: str, code: str, expect: int) -> list[dict]:
    """TAB_55 / TAB_56: rows = categories; only the two SEX columns are read."""
    sub = [_key(v) for v in _header(ws, 3)]
    sexcols = {i: C.normalise_sex(_header(ws, 3)[i]) for i, v in enumerate(sub)
               if v in ("masculino", "feminino")}
    if len(sexcols) != 2:
        raise ValueError(f"IMC {code}: sex columns not found in {sub}")
    out, n = [], 0
    for row in ws.iter_rows(min_row=4, values_only=True):
        label = _clean(row[0])
        if not label:
            continue
        if _key(label).startswith(("fonte", "… dados", "... dados")):
            break
        if label != "Total":
            n += 1
        for i, sex in sexcols.items():
            val = _num(row[i])
            if val is not None:
                out.append(_row25(topic, label, val, "count", code, {"sex": sex}))
    if n != expect:
        raise ValueError(f"IMC {code}: expected {expect} categories, read {n}")
    return out


def _informal_cross(ws, *, measure: str, code: str, expect: int,
                    only_crosses: bool = False) -> list[dict]:
    """TAB_63 / TAB_65: rows = residence / concelho, columns = sex or age.

    `only_crosses` reads just the cells the series sheet lacks -- a sex or age
    group WITHIN a residence or concelho -- and leaves the national row and the
    both-sexes column to the series (see TAB_65 in the module docstring)."""
    top, sub = _header(ws, 2), _header(ws, 3)
    colspec, dim = {}, None
    for i in range(1, len(sub)):
        if top[i]:
            dim = _SECTIONS[_key(top[i])]
        if not sub[i]:
            continue
        if dim == "sex":
            s = C.normalise_sex(sub[i]) if _key(sub[i]) != "ambos os sexos" else "total"
            colspec[i] = {"sex": s}
        else:
            colspec[i] = {"age_group": sub[i]}
    out, section, n = [], None, 0
    for row in ws.iter_rows(min_row=4, values_only=True):
        label = _clean(row[0])
        k = _key(label)
        if not label:
            continue
        if k.startswith("fonte"):
            break
        if all(_num(v) is None for v in row[1:]):
            section = _SECTIONS.get(k, section)
            continue
        n += 1
        base = _group(label, section)
        for i, extra in colspec.items():
            if only_crosses and (not base or extra.get("sex") == "total"):
                continue
            val = _num(row[i])
            if val is not None:
                out.append(_row25("formality", "Emprego informal", val, measure,
                                  code, {**base, **extra}))
    if n != expect:
        raise ValueError(f"IMC {code}: expected {expect} rows, read {n}")
    return out


def _row25(topic, char, val, measure, code, dims) -> dict:
    return C.row(topic=topic, characteristic=char,
                 classification="Not applicable" if topic == "formality"
                 else "National",
                 value=val, survey=S19, period="2025", reference_period="2025",
                 frequency="annual", measure=measure,
                 unit="persons" if measure == "count" else "percent",
                 working_age_base=_BASE, series_code=f"IMC {code}",
                 **_dims(dims))


# --------------------------------------------------------------------------

_KEYS = ["topic", "characteristic", "classification", "sex", "age_group",
         "education", "geography", "locality", "locality_label",
         "working_age_base", "period", "measure"]


def _dedupe(rows: list[dict]) -> list[dict]:
    """Keep the first reading of each merge key -- after checking every later
    reading of it carries the same value to the sheets' rounding."""
    seen, out, bad = {}, [], []
    for r in rows:
        k = tuple(r[c] for c in _KEYS)
        if k in seen:
            first = seen[k]
            tol = 0.011 if r["measure"] == "share" else 0.02
            if abs(first["value"] - r["value"]) > tol:
                bad.append((k, first["series_code"], first["value"],
                            r["series_code"], r["value"]))
            continue
        seen[k] = r
        out.append(r)
    if bad:
        raise ValueError(f"IMC: {len(bad)} reprinted cell(s) disagree, e.g. {bad[:3]}")
    return out


_BROAD_DROP = {"Total", "ND"}
_SEXES = {"masculino", "feminino"}


def parse(path: str) -> pd.DataFrame:
    wb = openpyxl.load_workbook(path, data_only=True)
    s = lambda name: wb[name]  # noqa: E731
    rows: list[dict] = []
    # counts
    rows += _series(s("TAB_9"), topic="industry", measure="count", code="T9",
                    mode="category", expect=22)
    rows += _series(s("TAB_10"), topic="occupation", measure="count", code="T10",
                    mode="category", expect=11)
    rows += _series(s("TAB_11"), topic="industry", measure="count", code="T11",
                    mode="category", expect=4, drop=_BROAD_DROP)
    rows += _series(s("TAB_12"), topic="employment_status", measure="count",
                    code="T12", mode="category", expect=9)
    # column percentages
    rows += _series(s("TAB_29"), topic="industry", measure="share", code="T29",
                    mode="category", expect=22)
    # TAB_30/32: SEX blocks only -- their national blocks reprint TAB_29/31
    # and disagree with them in three cells (see the docstring).
    rows += _series(s("TAB_30"), topic="industry", measure="share", code="T30",
                    mode="category", expect=22, blocks=_SEXES)
    rows += _series(s("TAB_28"), topic="industry", measure="share", code="T28",
                    mode="category", expect=4, drop=_BROAD_DROP)
    rows += _series(s("TAB_31"), topic="occupation", measure="share", code="T31",
                    mode="category", expect=11)
    rows += _series(s("TAB_32"), topic="occupation", measure="share", code="T32",
                    mode="category", expect=11, blocks=_SEXES)
    rows += _series(s("TAB_33"), topic="employment_status", measure="share",
                    code="T33", mode="category", expect=9)
    # informal employment
    rows += _series(s("TAB_14"), topic="formality", measure="count", code="T14",
                    mode="group", expect=32, characteristic="Emprego informal")
    rows += _series(s("TAB_38"), topic="formality", measure="share", code="T38",
                    mode="group", expect=32, characteristic="Emprego informal")
    # 2025-only cuts
    rows += [r for r in _groups_by_categories(
                 s("TAB_54"), topic="industry", code="T54", expect=33,
                 skip_rows=set())
             if r["characteristic"] not in _BROAD_DROP]
    rows += _groups_by_categories(s("TAB_57"), topic="employment_status",
                                  code="T57", expect=33,
                                  skip_rows={"cabo verde", "urbano", "rural"})
    rows += _categories_by_sex(s("TAB_55"), topic="industry", code="T55",
                               expect=21)
    rows += _categories_by_sex(s("TAB_56"), topic="occupation", code="T56",
                               expect=10)
    rows += _informal_cross(s("TAB_63"), measure="count", code="T63", expect=25)
    rows += _informal_cross(s("TAB_65"), measure="share", code="T65", expect=25,
                            only_crosses=True)
    return pd.DataFrame(_dedupe(rows))
