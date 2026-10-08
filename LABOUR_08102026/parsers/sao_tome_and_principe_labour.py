"""São Tomé and Príncipe — INE STP, RGPH 2012 (Recenseamento Geral da
População e Habitação), thematic report 5 "Actividade Económica", chapter IV
"População Empregada".

A CENSUS: the employed population aged 15 and over (56 295 persons), May 2012.
There is no labour force survey; the 2024 census results carry no employment
tables and the IOF 2017 has only a sector summary.

COLLECTED (all shares of the employed 15+ unless stated):

* Tabela 4.5.1  sector (Primário / Secundário / Terciário / NS/NR) by sex x age
                group -- three stacked blocks (all, Masculino, Feminino)
                -> industry
* Tabela 4.5.4  branch of activity, CAE-STP SECTIONS, by district -- each
                district row is that district's distribution -> industry
* Tabela 4.6.1  occupation groups 0-9 (CNP-STP 2012), counts and % by sex
* Tabela 4.6.2  occupation groups by age group
* Tabela 4.6.3  occupation groups, urban and rural COUNTS only
* Tabela 4.6.7  situação na profissão by district -> employment_status
* Tabela 4.7.1  hours usually worked per week, bands by sex -> hours

LABELS AS PRINTED. The CAE-STP sections are printed as bare letters ("A",
"G", "NA") and are kept as letters -- adding ISIC names would be publishing
text INE did not print. The occupation groups are "Grupo 0" ... "Grupo 9".
CAE-STP and CNP-STP 2012 are INE's national classifications (ISIC- and
ISCO-based, named in the prose); the schema has no member for them, so both
are recorded as National and named here. Situação na profissão mixes status
with public/private employer (nomeado da administração pública, militar) --
filed as employment_status, National, a hybrid like Chad's and Cameroon's CSP.

NOT COLLECTED, AND WHY:

* TABELA 4.5.2 (branch by sex): ITS SEX COLUMNS ARE SCRAMBLED. The Total
  column is sound (it matches 4.5.4's Total row letter for letter), but the
  Masculino/Feminino columns cannot belong to their rows: men's Commerce (G)
  prints 0,2 and women's 0,0 against 14,9 overall, while D (electricity)
  prints 15,0 for men against 0,7 overall and F prints 23,1 for women. The
  values look moved between rows, but nothing in the table says where, so
  restoring them would be guesswork. Its Total column is not taken either:
  4.5.4's Total row carries the same national distribution.
* Tabela 4.5.3 distributes each BRANCH across districts, 4.6.4 each
  occupation group across districts, 4.6.5 each status across the sexes, 4.6.6
  each status across age groups, and 4.6.3's % columns each group across
  urban/rural -- all row percentages.
* Gráfico 4.6.3 (status, national): its data labels print as text, but the
  same national distribution is 4.6.7's "Total STP" column, read from a table.
* 4.5.4's own "Total" column (a row sum), and 4.6.3's Total counts (4.6.1's).
* 4.4.1 (education of the employed) and 4.7.2 (payment frequency): no topic.

PUBLISHED DEFECT KEPT: Tabela 4.5.4's CAUÉ ROW SUMS TO 106,1 and INE prints
its Total as 106,0 -- an excess spread across the row, not one misplaced
value. It is collected as printed, with the sum pinned (`_PINNED_SUMS`) so a
correction by INE is noticed; every other district sums to 100.

CROSS-CHECK: employed 56 295 (34 813 men / 21 482 women); terciário 52,7;
section A (agriculture) 23,2 nationally, 53,2 in Lembá, 8,6 in Agua Grande;
Grupo 5 (services and sales) 14 509 = 25,8%; conta de outrem sem contrato
37,5; 45 horas ou mais 32,6.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_SURVEY = "Recenseamento Geral da População e Habitação 2012 (RGPH 2012)"
_BASE = dict(survey=_SURVEY, period="2012", reference_period="RGPH 2012 (maio 2012)",
             frequency="ad_hoc", working_age_base="15+")
_AGES = ["15-24", "25-34", "35-44", "45-54", "55-64", "65+"]
_DISTRICTS = ["Lobata", "Lembá", "Mé-Zochi", "Agua Grande", "Cantagalo",
              "Caué", "Príncipe"]
_GROUPS = [f"Grupo {i}" for i in range(10)]
_STATUS = [
    "Trabalhador por conta de outrem com contrato",
    "Trabalhador por conta de outrem sem contrato",
    "Trabalhador nomeado da administração pública",
    "Trabalhador da administração pública com contrato",
    "Militar do exército ou da marinha",
    "Trabalhador por conta própria",
    "Empregador",
    "Trabalhador familiar não remunerado",
    "Trabalhador na produção para o próprio consumo no alojamento",
]
_HOURS = ["De 1 hora a menos de 15 horas", "De 15 horas a menos de 35 horas",
          "De 35 horas a menos de 45 horas", "De 45 horas ou mais"]
# Rows printed with a sum other than 100, kept as published (see docstring).
_PINNED_SUMS = {("T4.5.4", "Caué"): 106.1}

# A cell is a whole token: a count ("14509", no thousands separator in this
# report) or a one-decimal share ("25,8", "100,0", "100").
_CELL = re.compile(r"\d{1,6}|\d{1,3},\d")


def _split(line: str, n: int):
    """(label, values) when `line` ends in exactly n numeric tokens and the
    token before them is not numeric, else None."""
    toks = line.split()
    if len(toks) < n or not all(_CELL.fullmatch(t) for t in toks[-n:]):
        return None
    # A numeric token before the values means the row has more cells than
    # expected -- unless it is the group number of a "Grupo 5" label.
    if (len(toks) > n and _CELL.fullmatch(toks[-n - 1])
            and not (len(toks) > n + 1 and toks[-n - 2] == "Grupo")):
        return None
    return (" ".join(toks[:-n]),
            [float(t.replace(",", ".")) for t in toks[-n:]])


def _lines(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        out = []
        for page in pdf.pages[58:74]:
            out += (page.extract_text() or "").splitlines()
    return [ln.strip() for ln in out if ln.strip()]


def _after(lines: list[str], caption: str) -> list[str]:
    for i, ln in enumerate(lines):
        if re.match(caption, ln):
            return lines[i + 1:]
    raise ValueError(f"RGPH 2012: {caption!r} not found")


def _row(**kw) -> dict:
    return C.row(**_BASE, **kw)


def _check_sum(code: str, key: str, vals: list[float], tol: float = 0.3):
    want = _PINNED_SUMS.get((code, key), 100.0)
    s = round(sum(vals), 1)
    if abs(s - want) > tol:
        raise ValueError(f"RGPH 2012 {code} {key}: sums to {s}, expected {want}")


def _t451(lines) -> list[dict]:
    body = _after(lines, r"Tabela 4\.5\.1\.")
    blocks, cur = [], None
    for ln in body:
        if ln.startswith(("NS/NR =", "Gráfico")):
            break
        m = re.match(r"^(Sector de Atividade|Masculino|Feminino) Total 15-24", ln)
        if m:
            cur = {"Sector de Atividade": "total", "Masculino": "male",
                   "Feminino": "female"}[m.group(1)]
            blocks.append((cur, {}))
            continue
        got = _split(ln, 7)
        if got and blocks:
            lab = "Total" if got[0].startswith("Total") else got[0]
            blocks[-1][1][lab] = got[1]
    if [b[0] for b in blocks] != ["total", "male", "female"]:
        raise ValueError(f"RGPH 2012 T4.5.1: blocks {[b[0] for b in blocks]}")
    out = []
    for sex, rows in blocks:
        if list(rows) != ["Total", "Primário", "Secundário", "Terciário", "NS/NR"]:
            raise ValueError(f"RGPH 2012 T4.5.1 {sex}: rows {list(rows)}")
        for j, age in enumerate(["Total"] + _AGES):
            _check_sum("T4.5.1", f"{sex} {age}",
                       [v[j] for k, v in rows.items() if k != "Total"])
        for lab, vals in rows.items():
            for age, v in zip(["Total"] + _AGES, vals):
                out.append(_row(topic="industry", characteristic=lab,
                                classification="National", value=v, sex=sex,
                                age_group=age, measure="share", unit="percent",
                                series_code="RGPH2012 T4.5.1"))
    return out


def _t454(lines) -> list[dict]:
    body = _after(lines, r"Tabela 4\.5\.4\.")
    header = body[1] if not body[0].startswith("Total A") else body[0]
    for ln in body[:4]:
        if re.fullmatch(r"Total(?: [A-Z]{1,2})+", ln):
            header = ln
            break
    letters = header.split()[1:]
    if len(letters) != 21 or sorted(letters) != sorted(
            list("ABCDEFGHIJKLMNOPQRST") + ["NA"]):
        raise ValueError(f"RGPH 2012 T4.5.4: header {header!r}")
    rows = {}
    for ln in body:
        if ln.startswith("4.6."):
            break
        got = _split(ln, 22)
        if got:
            rows[got[0]] = got[1][1:]          # drop the row-sum column
    if list(rows) != ["Total"] + _DISTRICTS:
        raise ValueError(f"RGPH 2012 T4.5.4: rows {list(rows)}")
    out = []
    for dist, vals in rows.items():
        _check_sum("T4.5.4", dist, vals)
        geo = "Total country" if dist == "Total" else dist
        for letter, v in zip(letters, vals):
            out.append(_row(topic="industry", characteristic=letter,
                            classification="National", value=v, geography=geo,
                            measure="share", unit="percent",
                            series_code="RGPH2012 T4.5.4"))
    return out


def _t461(lines) -> list[dict]:
    body = _after(lines, r"Tabela 4\.6\.1 ")
    rows = {}
    for ln in body:
        got = _split(ln, 6)
        if got and (got[0] in _GROUPS or got[0] == "Total"):
            rows[got[0]] = got[1]
            if got[0] == "Total":
                break
    if list(rows) != _GROUPS + ["Total"]:
        raise ValueError(f"RGPH 2012 T4.6.1: rows {list(rows)}")
    for lab, v in rows.items():
        if v[2] + v[4] != v[0]:
            raise ValueError(f"RGPH 2012 T4.6.1 {lab}: men + women != total")
    for j in (1, 3, 5):
        _check_sum("T4.6.1", f"col {j}", [rows[g][j] for g in _GROUPS])
    out = []
    for lab, v in rows.items():
        for sex, n, pct in (("total", v[0], v[1]), ("male", v[2], v[3]),
                            ("female", v[4], v[5])):
            out.append(_row(topic="occupation", characteristic=lab,
                            classification="National", value=n, sex=sex,
                            measure="count", unit="persons",
                            series_code="RGPH2012 T4.6.1"))
            out.append(_row(topic="occupation", characteristic=lab,
                            classification="National", value=pct, sex=sex,
                            measure="share", unit="percent",
                            series_code="RGPH2012 T4.6.1"))
    return out, rows["Total"][0]


def _t462(lines) -> list[dict]:
    body = _after(lines, r"Tabela 4\.6\.2 ")
    rows = {}
    for ln in body:
        got = _split(ln, 6)
        if got and (got[0] in _GROUPS or got[0] == "Total"):
            rows[got[0]] = got[1]
            if got[0] == "Grupo 9":
                break
    if list(rows) != ["Total"] + _GROUPS:
        raise ValueError(f"RGPH 2012 T4.6.2: rows {list(rows)}")
    for j, age in enumerate(_AGES):
        _check_sum("T4.6.2", age, [rows[g][j] for g in _GROUPS])
    return [_row(topic="occupation", characteristic=lab,
                 classification="National", value=v, age_group=age,
                 measure="share", unit="percent", series_code="RGPH2012 T4.6.2")
            for lab, vals in rows.items() for age, v in zip(_AGES, vals)]


def _t463(lines, total_employed: float) -> list[dict]:
    body = _after(lines, r"Tabela 4\.6\.3\.")
    rows = {}
    for ln in body:
        got = _split(ln, 6)
        if got and (got[0] in _GROUPS or got[0] == "Total"):
            rows[got[0]] = got[1]
            if got[0] == "Grupo 9":
                break
    if list(rows) != ["Total"] + _GROUPS:
        raise ValueError(f"RGPH 2012 T4.6.3: rows {list(rows)}")
    for lab, v in rows.items():
        if v[2] + v[4] != v[0]:
            raise ValueError(f"RGPH 2012 T4.6.3 {lab}: urban + rural != total")
    if rows["Total"][0] != total_employed:
        raise ValueError("RGPH 2012 T4.6.3: total differs from T4.6.1")
    out = []
    for lab, v in rows.items():
        for loc, label, n in (("urban", "Urbano", v[2]), ("rural", "Rural", v[4])):
            out.append(_row(topic="occupation", characteristic=lab,
                            classification="National", value=n, locality=loc,
                            locality_label=label, measure="count",
                            unit="persons", series_code="RGPH2012 T4.6.3"))
    return out


def _t467(lines) -> list[dict]:
    body = _after(lines, r"Tabela 4\.6\.7\.")
    rows, pending = {}, ""
    for ln in body:
        if re.fullmatch(r"\d{1,3}", ln) or ln.startswith("Capítulo"):
            continue
        got = _split(ln, 8)
        if got:
            lab = re.sub(r"\s+", " ", f"{pending} {got[0]}").strip()
            rows["Total" if lab == "Total STP" else lab] = got[1]
            pending = ""
            if len(rows) == len(_STATUS) + 1:
                break
        elif rows:                       # a label's first line (header lines precede Total STP)
            pending = f"{pending} {ln}".strip()
    if list(rows) != ["Total"] + _STATUS:
        raise ValueError(f"RGPH 2012 T4.6.7: rows {list(rows)}")
    geos = ["Total country"] + _DISTRICTS
    for j, g in enumerate(geos):
        _check_sum("T4.6.7", g, [rows[s][j] for s in _STATUS])
    return [_row(topic="employment_status", characteristic=lab,
                 classification="National", value=v, geography=g,
                 measure="share", unit="percent", series_code="RGPH2012 T4.6.7")
            for lab, vals in rows.items() for g, v in zip(geos, vals)]


def _t471(lines) -> list[dict]:
    body = _after(lines, r"Tabela 4\.7\.1\.")
    rows = {}
    for ln in body:
        got = _split(ln, 3)
        if got and (got[0] in _HOURS or got[0] == "Total"):
            rows[got[0]] = got[1]
            if got[0] == _HOURS[-1]:
                break
    if list(rows) != ["Total"] + _HOURS:
        raise ValueError(f"RGPH 2012 T4.7.1: rows {list(rows)}")
    for j in range(3):
        _check_sum("T4.7.1", f"col {j}", [rows[h][j] for h in _HOURS])
    return [_row(topic="hours", characteristic=lab, classification="Not applicable",
                 value=v, sex=sex, measure="share", unit="percent",
                 series_code="RGPH2012 T4.7.1")
            for lab, vals in rows.items()
            for sex, v in zip(("total", "male", "female"), vals)]


def parse(path: str) -> pd.DataFrame:
    lines = _lines(path)
    t461, employed = _t461(lines)
    rows = (_t451(lines) + _t454(lines) + t461 + _t462(lines)
            + _t463(lines, employed) + _t467(lines) + _t471(lines))
    return pd.DataFrame(rows)
