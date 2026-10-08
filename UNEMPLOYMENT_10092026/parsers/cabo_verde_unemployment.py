"""Cabo Verde — INE, IMC (Inquérito Multiobjetivo Contínuo) "Estatísticas do
Mercado de Trabalho, Principais Quadros" workbook.

THE SAME WORKBOOK `labour/` READS. labour takes its composition sheets
(branch, occupation, sector, status, informal employment); this module takes
the headline series. No sheet is read by both.

ONE WORKBOOK, FIFTEEN YEARS. The "Evolução" sheets reprint every round since
2011, so a single download carries 2011-2020, 2022-2023 and 2024-2025 (by
semester and annual -- the IMC went to two semesters in 2024). There is no
2021 round. Taken:

    TAB_1   População com 15 anos ou mais          -> working_age_population
    TAB_2   população ECONOMICAMENTE ATIVA         -> labour_force
    TAB_3   população EMPREGADA                     -> employed
    TAB_5   população DESEMPREGADA                  -> unemployed
    TAB_6/7 DESEMPREGADA 15-24 / 15-35              -> unemployed, age_group
    TAB_8   população ECONOMICAMENTE INATIVA        -> outside_labour_force
    TAB_21  TAXA DE ATIVIDADE                       -> labour_force_participation_rate
    TAB_22  TAXA DE EMPREGO                         -> employment_to_population_ratio
    TAB_23  TAXA DE SUBEMPREGO                      -> underemployment_rate
    TAB_24  TAXA DE DESEMPREGO                      -> unemployment_rate
    TAB_25/26 TAXA DE DESEMPREGO 15-24 / 15-35      -> youth_unemployment_rate
    TAB_45/46 NEET 15-24 / 15-35 (%)                -> neet_rate

each by residence, the 22 concelhos, sex, age group and education level
(where the sheet prints them), plus the 2025-only cross-tables by sex AND age
within residence/concelho (TAB_47/48/49/50/85/86/94/103/105) and the labour
underutilisation rate (TAB_103 for 2025, the "Quadro resumo" for 2022-2025 H2).

THE 13th / 19th ICLS BREAK. Every series sheet heads its columns "Resolução da
13ª CIET" (2011-2022) and "Resolução I da 19ª CIET" (2022 on), and prints 2022
TWICE, once on each basis -- employed 211 580 vs 190 579 for the same year,
by definition alone. The basis is read from the column's position under those
two headings (never from the year), carried in `survey`, and also in
`series_label`, which is in the merge key: without it the two 2022 readings
would collide and one would silently replace the other. Never chain across it.

ONE FIGURE, ONE ROW. The 2025 cross-tables repeat cells the series sheets
already carry (e.g. TAB_86's Ambos-os-sexos column is TAB_24's 2025 annual
column). Every row is keyed on the merge key with a CANONICAL series_label per
topic and basis, so a repeat lands on the same key; it is then compared with
the first reading and dropped only if equal (to 1e-6). A repeat that differs
is kept under a table-qualified series_label -- a published contradiction, not
a duplicate. In the 2025 cross-tables every COUNT agrees with the series
sheets exactly, but 78 RATES differ by up to 0,26 points (TAB_86 national
6,197 vs TAB_24's 6,192; TAB_105 NEET by up to 0,26) -- the series' 2025
annual figure and the cross-table's are evidently computed differently (the
same pattern labour/ met in TAB_38 vs TAB_65). Both are kept, the cross-table
one tagged "[TAB_nn]". The Quadro resumo prints rounded values (8.028 for TAB_24's
8.032 in 2024): its underutilisation rates are compared to 0.05 and only the
periods no table carries are new.

WHAT IS NOT TAKEN, AND WHY:
* informal employment (TAB_14/38) -- labour/ already holds it as `formality`;
  a figure has one home;
* inactivity rate (TAB_27/95), underemployed / NEET / underutilised COUNTS
  (TAB_4, 19, 20, 82, 101, 102, 104) -- no topic in this schema holds them;
* every other Quadro resumo row -- rounded repeats of the series sheets.

CONCELHO SPELLINGS: the 2025 sheets write "Tarrafal de São Nicolau", "Ribeira
Grande de Santiago" and "Santa Catarina do Fogo" for the series sheets'
"Tarrafal São Nicolau", "Ribeira Grande Santiago" and "Santa Catarina Fogo".
They are mapped to the series form (as labour's module does), so one concelho
is one geography; the value check above proves each mapping (every overlap is
equal).

VALUES are stored by INE as unrounded floats (12.249071...); rounded to 9
decimals to drop float residue only, as labour's module does. "-" (not
available) and "---" (not applicable) are skipped, never read as 0.

Definitions follow the corpus convention: unemployment, youth unemployment and
participation are the ILO measures (`strict`); underutilisation is `broad`;
underemployment and NEET `not_applicable`. Base 15+.

CROSS-CHECK: unemployment rate 12.25 (2011), 10.95 (2022, 19ª) vs 8.75 (2022,
13ª), 6.19 (2025); youth 15-24 15.43 (2025); employed 213 166 (2025);
LFPR 60.6 (2025, summary); underutilisation 23.58 (2025), 34.8 (2022).
"""
from __future__ import annotations

import re
import unicodedata

import openpyxl
import pandas as pd

from . import _common as C

_SURVEY = "Inquérito Multiobjetivo Contínuo (IMC)"
_BASES = {"13": "Resolução da 13ª CIET", "19": "Resolução I da 19ª CIET"}

# sheet -> (topic, canonical label, fixed age_group or None)
_SERIES = {
    "TAB_1": ("working_age_population", "População com 15 anos ou mais", None),
    "TAB_2": ("labour_force", "População economicamente ativa", None),
    "TAB_3": ("employed", "População empregada", None),
    "TAB_5": ("unemployed", "População desempregada", None),
    "TAB_6": ("unemployed", "População desempregada", "15-24"),
    "TAB_7": ("unemployed", "População desempregada", "15-35"),
    "TAB_8": ("outside_labour_force", "População economicamente inativa", None),
    "TAB_21": ("labour_force_participation_rate", "Taxa de atividade", None),
    "TAB_22": ("employment_to_population_ratio", "Taxa de emprego", None),
    "TAB_23": ("underemployment_rate", "Taxa de subemprego", None),
    "TAB_24": ("unemployment_rate", "Taxa de desemprego", None),
    "TAB_25": ("youth_unemployment_rate", "Taxa de desemprego (jovens)", "15-24"),
    "TAB_26": ("youth_unemployment_rate", "Taxa de desemprego (jovens)", "15-35"),
    "TAB_45": ("neet_rate", "Jovens sem emprego, educação ou formação (%)", "15-24"),
    "TAB_46": ("neet_rate", "Jovens sem emprego, educação ou formação (%)", "15-35"),
}
# 2025 cross-tables (sex x age within residence / concelho), 19th basis only.
_CROSS = {
    "TAB_47": "TAB_2", "TAB_48": "TAB_21", "TAB_49": "TAB_3", "TAB_50": "TAB_22",
    "TAB_85": "TAB_5", "TAB_86": "TAB_24", "TAB_94": "TAB_8",
    "TAB_103": None, "TAB_105": "TAB_45",
}
_UNDERUTIL = ("labour_underutilisation_rate", "Taxa de subutilização do trabalho")

_DEFINITION = {
    "unemployment_rate": "strict", "youth_unemployment_rate": "strict",
    "labour_force_participation_rate": "strict",
    "labour_underutilisation_rate": "broad",
}
_SECTIONS = {"meio de residencia": "locality", "concelho": "geography",
             "sexo": "sex", "grupo etario": "age",
             "nivel de instrucao frequentado": "education"}
_NATIONAL = {"cabo verde"}
# Employment and underemployment BY SECTOR (TAB_3, TAB_23): composition, which
# labour/ holds, and a breakdown no column here can carry.
_SKIP_SECTIONS = {"setor de atividade", "setor atividade"}
_CONCELHO = {"Tarrafal de São Nicolau": "Tarrafal São Nicolau",
             "Ribeira Grande de Santiago": "Ribeira Grande Santiago",
             "Santa Catarina do Fogo": "Santa Catarina Fogo"}


def _key(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def _num(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return round(float(v), 9)
    return None                      # "-", "---", "…": not available / n.a.


class _Rows:
    """Rows keyed on the merge key; a repeat must agree or is kept apart."""
    KEY = ("topic", "definition", "series_label", "sex", "age_group",
           "education", "geography", "locality", "locality_label",
           "working_age_base", "period", "measure")

    def __init__(self):
        self.rows: dict[tuple, dict] = {}
        self.repeats = 0
        self.contradictions: list[str] = []

    def add(self, r: dict, sheet: str, tol: float = 1e-6):
        k = tuple(r[c] for c in self.KEY)
        if k in self.rows:
            if abs(self.rows[k]["value"] - r["value"]) <= tol:
                self.repeats += 1
                return
            self.contradictions.append(f"{sheet} {k[0]} {k[10]} {k[6]}/{k[3]}/{k[4]}: "
                                       f"{self.rows[k]['value']} vs {r['value']}")
            r = {**r, "series_label": f"{r['series_label']} [{sheet}]"}
            k = tuple(r[c] for c in self.KEY)
        self.rows[k] = r


def _row(topic, label, basis, value, period, ref, freq, sheet, **dims):
    return C.row(topic=topic, value=value,
                 series_label=f"{label} — {_BASES[basis]}" if basis else label,
                 survey=f"{_SURVEY}, {_BASES[basis]}" if basis else _SURVEY,
                 period=period, reference_period=ref, frequency=freq,
                 working_age_base="15+",
                 definition=_DEFINITION.get(topic, "not_applicable"),
                 series_code=f"IMC {sheet}", **dims)


def _dims(section: str | None, label: str) -> dict:
    if section is None:
        return {}
    if section == "locality":
        return {"locality": C.normalise_locality(label), "locality_label": label}
    if section == "geography":
        return {"geography": _CONCELHO.get(label, label)}
    if section == "sex":
        sex = C.normalise_sex(label)
        if sex == "total":
            raise ValueError(f"IMC: unreadable sex row {label!r}")
        return {"sex": sex}
    if section == "age":
        return {"age_group": label}
    return {"education": label}


def _body(ws, first: int):
    """(section, label, row) for every data row from `first` on."""
    section = None
    for r in ws.iter_rows(min_row=first, values_only=True):
        lab = r[0]
        if not isinstance(lab, str):
            continue
        lab = lab.strip()
        k = _key(lab)
        if k.startswith(("fonte", "nd -", "- dado", "--- nao", "*")):
            break
        if k in _NATIONAL:
            yield None, lab, r
            continue
        if all(v is None for v in r[1:]):
            if k in _SECTIONS:
                section = _SECTIONS[k]
            elif k in _SKIP_SECTIONS:
                section = "skip"
            else:
                raise ValueError(f"IMC {ws.title}: unknown section {lab!r}")
            continue
        if section == "skip":
            continue
        yield section, lab, r


def _series_columns(ws):
    """[(col, period, basis, reference, frequency)] from the header rows."""
    head = [list(r) for r in ws.iter_rows(min_row=1, max_row=6, values_only=True)]
    yr_row = next(i for i, r in enumerate(head)
                  if sum(isinstance(v, int) and 2000 < v < 2100 for v in r) >= 3)
    basis_row = next((i for i, r in enumerate(head[:yr_row])
                      if any(isinstance(v, str) and "CIET" in v for v in r)), None)
    cut = None
    if basis_row is not None:
        cut = next(c for c, v in enumerate(head[basis_row])
                   if isinstance(v, str) and "19" in v and "CIET" in v)
    sem = head[yr_row + 1] if yr_row + 1 < len(head) else []
    cols, year = [], None
    for c, v in enumerate(head[yr_row]):
        if c == 0:
            continue
        if isinstance(v, int):
            year = v
        s = sem[c] if c < len(sem) else None
        if year is None or (v is None and not isinstance(s, str)):
            continue
        basis = None if cut is None else ("19" if c >= cut else "13")
        if isinstance(s, str) and "1" in s and "Semestre" in s:
            period, freq, ref = f"{year}-H1", "semiannual", f"IMC {year}, 1º Semestre"
        elif isinstance(s, str) and "2" in s and "Semestre" in s:
            period, freq, ref = f"{year}-H2", "semiannual", f"IMC {year}, 2º Semestre"
        else:
            period, freq, ref = str(year), "annual", f"IMC {year}"
        cols.append((c, period, basis, ref, freq))
    return cols, yr_row + (2 if any(isinstance(v, str) for v in sem) else 1) + 1


def _read_series(wb, sheet, out: _Rows):
    topic, label, fixed_age = _SERIES[sheet]
    ws = wb[sheet]
    cols, first = _series_columns(ws)
    seen_bases = {b for _, _, b, _, _ in cols}
    if sheet != "TAB_1" and seen_bases != {"13", "19"}:
        raise ValueError(f"IMC {sheet}: bases {seen_bases}, expected 13ª and 19ª")
    n = 0
    for section, lab, r in _body(ws, first):
        dims = _dims(section, lab)
        if fixed_age:
            if "age_group" in dims:
                raise ValueError(f"IMC {sheet}: an age section inside a youth table")
            dims["age_group"] = fixed_age
        for c, period, basis, ref, freq in cols:
            v = _num(r[c]) if c < len(r) else None
            if v is None:
                continue
            out.add(_row(topic, label, basis, v, period, ref, freq, sheet, **dims), sheet)
            n += 1
    if n < 30:
        raise ValueError(f"IMC {sheet}: only {n} values read")


def _read_cross(wb, sheet, out: _Rows):
    ws = wb[sheet]
    head = [list(r) for r in ws.iter_rows(min_row=2, max_row=3, values_only=True)]
    if sheet == "TAB_103":
        topic, label = _UNDERUTIL
    else:
        topic, label, _ = _SERIES[_CROSS[sheet]]
    cols, block = [], None
    for c in range(1, max(len(head[0]), len(head[1]))):
        top = head[0][c] if c < len(head[0]) else None
        sub = head[1][c] if c < len(head[1]) else None
        if isinstance(top, str) and re.match(r"\d{2}-\d{2} anos", top.strip()):
            block = top.strip().replace(" anos", "")
        sub = sub.strip() if isinstance(sub, str) else sub
        if sub is None and isinstance(top, str) and top.strip() == "Total":
            dims = {}
        elif sub is None:
            continue
        elif _key(sub) == "ambos os sexos":
            dims = {}
        elif _key(sub) in ("masculino", "feminino"):
            dims = {"sex": C.normalise_sex(sub)}
        elif re.match(r"^\d{2}(-\d{2}| ou \+)", sub):
            dims = {"age_group": sub}
        else:
            raise ValueError(f"IMC {sheet}: unknown column {sub!r}")
        if block:
            if "age_group" in dims:
                raise ValueError(f"IMC {sheet}: age inside an age block")
            dims = {**dims, "age_group": block}
        cols.append((c, dims))
    if topic == "neet_rate" and not all("age_group" in d for _, d in cols):
        raise ValueError(f"IMC {sheet}: NEET column without its age block")
    n = 0
    for section, lab, r in _body(ws, 4):
        if section not in (None, "locality", "geography"):
            raise ValueError(f"IMC {sheet}: unexpected section {section!r}")
        base = _dims(section, lab)
        for c, dims in cols:
            v = _num(r[c]) if c < len(r) else None
            if v is None:
                continue
            if set(base) & set(dims):
                raise ValueError(f"IMC {sheet}: dimension clash at {lab!r}")
            out.add(_row(topic, label, "19", v, "2025", "IMC 2025", "annual",
                         sheet, **base, **dims), sheet)
            n += 1
    if n < 100:
        raise ValueError(f"IMC {sheet}: only {n} values read")


def _read_summary_underutilisation(wb, out: _Rows):
    ws = wb["QUADRO RESUMO_1"]
    rows = list(ws.iter_rows(values_only=True))
    hdr = next(r for r in rows if sum(isinstance(v, int) and v > 2000 for v in r) >= 3)
    basis_row = next(r for r in rows if any(isinstance(v, str) and "CIET" in v for v in r))
    cut = next(c for c, v in enumerate(basis_row)
               if isinstance(v, str) and "19" in v and "CIET" in v)
    line = next(r for r in rows if isinstance(r[0], str)
                and _key(r[0]).startswith("taxa de subutilizacao"))
    topic, label = _UNDERUTIL
    for c in range(cut, len(hdr)):
        h, v = hdr[c], _num(line[c]) if c < len(line) else None
        if h is None or v is None:
            continue
        m = re.match(r"^(\d{4})(?:\s*\((\d)º?S\)|\s*\(ANUAL\))?$", str(h).strip())
        if not m:
            raise ValueError(f"IMC resumo: header {h!r}")
        y, s = m.group(1), m.group(2)
        period, freq = (f"{y}-H{s}", "semiannual") if s else (y, "annual")
        ref = f"IMC {y}" + (f", {s}º Semestre" if s else "")
        out.add(_row(topic, label, "19", v, period, ref, freq, "QUADRO RESUMO_1"),
                "QUADRO RESUMO_1", tol=0.05)


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    wb = openpyxl.load_workbook(path, data_only=True)
    out = _Rows()
    for sheet in _SERIES:
        _read_series(wb, sheet, out)
    for sheet in _CROSS:
        _read_cross(wb, sheet, out)
    _read_summary_underutilisation(wb, out)
    if out.contradictions:
        print(f"[cabo_verde] {len(out.contradictions)} published contradiction(s) "
              f"kept under table-qualified labels, e.g. {out.contradictions[:3]}")
    return pd.DataFrame(list(out.rows.values()))
