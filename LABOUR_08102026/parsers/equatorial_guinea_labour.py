"""Equatorial Guinea — INEGE II Encuesta Nacional de Hogares (ENH2), informe
definitivo (November 2024), Capítulo V "Empleo".

A HOUSEHOLD survey (consumption, poverty and employment), collected over twelve
months, 16 August 2022 to 14 August 2023. Its employment chapter reports ONLY
the legal working-age population, **18 to 64** ("población en edad legal de
trabajar ... de 18 a 64 años", Ley 10/2012) -- a base no other country in the
corpus uses, and one that travels on every row.

Four tables, read from the text layer by `_table`, which knows each one's shape:

* Tabla 46  OF / OI -- formal and informal shares of the employed, by group
            -> formality. The table's other columns (PET, activity/employment/
            unemployment/underemployment rates, mean hours, social-security
            cover) are rates or have no topic here.
* Tabla 47  "tipo de ocupación" -- eight kinds of job, by group -> employment_status.
* Tabla 48  sector de actividad (21 branches) -- the Ocupados COUNT column only
            -> industry.
* Tabla 49  "tipo ocupación" -- nine occupation groups + Otro, by group -> occupation.

47, 46 AND 49 ARE COMPOSITION, NOT ROW PERCENTAGES. Each ROW is a population
group -- the nation, a region, a zone, a sex, a province -- and its values are
that group's distribution across the categories (they sum to 100). The group
goes in geography / locality / sex, exactly as Mali's EMOP tables are read.
Tabla 48 is the other way round: its rows are branches and its % columns split
EACH BRANCH by region, zone and sex (Construcción 97,1% masculino) -- genuine
row percentages, not collected. Its Ocupados column is a count per branch and
is collected; the 21 counts must sum to the printed national 496.965.

TABLA 47 IS A HYBRID OF STATUS AND SECTOR: "Empleado privado" / "Empleado
público" split employees by employer, beside independiente, destajista,
trabajador familiar auxiliar, servicio doméstico, empresario and cooperativa.
Together they partition the employed, so -> employment_status, National. The
column order comes from PAGE GEOMETRY (each value's x-position under its
wrapped header word) and is confirmed by the prose: independientes 46,8,
privado 32,7, público 12,5, empresarios 0,7.

TABLA 49's groups are printed as ROMAN NUMERALS whose names are in footnote
33 ("I: Directores y Gerentes" ... "IX: Trabajadores no cualificados/
Ocupaciones elementales", "Otro: No clasificados en otra parte"). Those are
ISCO-08's nine major groups in their Spanish (CIUO-08) wording, but neither
ISCO nor CIUO is named anywhere in the report -- so National, and the label is
the numeral with its footnote name. Armed forces (ISCO group 0) is absent.

"-" IS AN EMPTY CELL (no observation), never a zero; the report prints "0,0"
where it means zero.

GEOGRAPHY: regions are labelled "Región Continental" / "Región Insular" (how
the report names them; the row prints only "Continental") so they cannot be
mistaken for provinces; provinces as printed.

NOT COLLECTED: the Ocupados column of 46/47/49 (employment LEVELS by group --
`unemployment`'s territory), Tabla 50 (education x row %), Tabla 51 (contract
type, employees only -- "excluye al Destajista, al Independiente ..."), 52-53
(unemployment). NO NOMENCLATURE is named for any table (CIIU/CIUO/ISIC/ISCO
absent) -> National; the 21 branches are recognisably ISIC Rev.4 sections.

PERIOD 2023, reference "agosto 2022 - agosto 2023" (end-year convention, as
Liberia 2016-17 and Chad 2018-19).

CROSS-CHECK: employed 18-64 496.965; independiente o autónomo 46,8; empleado
público 12,5; agricultura 155.913; comercio 66.026; administración pública
39.084; group VI (agricultores) 28,3; informal 83,0 (rural 91,7).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_SURVEY = "II Encuesta Nacional de Hogares (ENH2)"
_BASE = "18-64"
_PERIOD, _REF = "2023", "agosto 2022 - agosto 2023"

_NUM = r"\d{1,3}(?:\.\d{3})+|\d+(?:,\d)?|-"

# row label -> column settings, and the section heading each follows
_GROUPS = {
    "Guinea Ecuatorial": {},
    "Continental": {"geography": "Región Continental"},
    "Insular": {"geography": "Región Insular"},
    "Urbana": {"locality": "urban", "locality_label": "Urbana"},
    "Rural": {"locality": "rural", "locality_label": "Rural"},
    "Masculino": {"sex": "male"},
    "Femenino": {"sex": "female"},
    **{p: {"geography": p} for p in (
        "Annobón", "Bioko Norte", "Bioko Sur", "Centro Sur", "Kie Ntem",
        "Litoral", "Wele Nzas")},
}
_SECTIONS = {"Región", "Zona", "Sexo", "Provincia"}

_T47_CATS = ["Independiente o Autónomo", "Empleado privado", "Empleado público",
             "Destajista", "Trabajador familiar auxiliar", "Servicio doméstico",
             "Empresario (Propietario)", "Miembro de cooperativas"]
_T49_CATS = [
    "I: Directores y Gerentes",
    "II: Profesionales universitarios, científicos e intelectuales",
    "III: Técnicos y profesionales no universitarios",
    "IV: Empleados de oficina/personal de apoyo administrativo",
    "V: Trabajadores de los servicios y vendedores de comercios y mercados",
    "VI: Agricultores y trabajadores independientes agropecuarios, forestales y pesqueros",
    "VII: Oficiales, operarios y artesanos de la construcción, la metalurgia, "
    "las artes gráficas y la industria manufacturera",
    "VIII: Operadores de instalaciones, de máquinas y ensambladores",
    "IX: Trabajadores no cualificados/Ocupaciones elementales",
    "Otro: No clasificados en otra parte",
]
# The footnote is the table's own legend: check it still says what the labels
# above say, numeral by numeral, rather than trusting them blind.
_FOOTNOTE_RE = re.compile(r"^(?:33 )?(I|II|III|IV|V|VI|VII|VIII|IX|Otro):\s*(.+)$", re.M)


def _num(tok: str) -> float | None:
    if tok == "-":
        return None
    return float(tok.replace(".", "").replace(",", "."))


def _page(pdf, caption: str) -> str:
    # The caption also opens a line of the list of tables (dot leaders).
    rx = re.compile(rf"^{caption}(?![^\n]*\.{{4}})", re.M)
    for p in pdf.pages[100:]:
        t = p.extract_text() or ""
        if rx.search(t):
            return t[rx.search(t).start():]
    raise ValueError(f"ENH2: {caption!r} not found")


def _group_rows(text: str, ncols: int, where: str) -> list[tuple[dict, list]]:
    """Rows 'label n1 n2 ...' for the fourteen published groups."""
    out = []
    for ln in text.splitlines()[1:]:
        s = ln.strip()
        if s in _SECTIONS:
            continue
        m = re.fullmatch(rf"(\D+?)\s+((?:(?:{_NUM})\s*)+)", s)
        if not m or m.group(1) not in _GROUPS:
            continue
        toks = re.findall(_NUM, m.group(2))
        if len(toks) != ncols:
            raise ValueError(f"{where}: {m.group(1)!r} has {len(toks)} cells, "
                             f"want {ncols}: {s!r}")
        out.append((_GROUPS[m.group(1)], [_num(t) for t in toks]))
    if len(out) != len(_GROUPS):
        raise ValueError(f"{where}: read {len(out)} groups, want {len(_GROUPS)}")
    return out


def _row(topic, cat, value, series, measure="share", unit="percent", **ctx):
    return C.row(topic=topic, characteristic=cat, classification=(
                     "Not applicable" if topic == "formality" else "National"),
                 value=value, survey=_SURVEY, period=_PERIOD,
                 reference_period=_REF, frequency="ad_hoc", measure=measure,
                 unit=unit, working_age_base=_BASE, series_code=series, **ctx)


def _distribution(text, cats, topic, series, lead: int, pick=None) -> list[dict]:
    """A group-by-category table. `lead` columns precede the categories
    (Ocupados, or PET..PHST); `pick` restricts to some category columns."""
    idx = pick or range(len(cats))
    out = []
    for ctx, vals in _group_rows(text, lead + len(cats), series):
        shares = vals[lead:]
        got = [shares[i] for i in idx]
        total = sum(v for v in got if v is not None)
        if abs(total - 100) > 0.4:
            raise ValueError(f"{series}: {ctx or 'national'} sums to {total:.1f}")
        for i in idx:
            if shares[i] is not None:
                out.append(_row(topic, cats[i], shares[i], series, **ctx))
    return out


def _t48(text: str) -> list[dict]:
    """The Ocupados count per branch. Two labels wrap AROUND their numbers
    ("Suministro de agua, saneamiento, gestión de desechos y" / "1.522 81,4
    ..." / "descontaminación"): a line of numbers with no label takes the line
    above and the line below."""
    lines = [ln.strip() for ln in text.splitlines()[1:]]
    row_re = re.compile(rf"(\D*?)\s*((?:(?:{_NUM})\s*){{7}})")
    out_rows, i = [], 0
    while i < len(lines) and len(out_rows) < 22:
        m = row_re.fullmatch(lines[i])
        if m:
            label = m.group(1).strip()
            if not label:
                label = f"{lines[i - 1]} {lines[i + 1]}"
                i += 1
            out_rows.append((label, _num(re.findall(_NUM, m.group(2))[0])))
        i += 1
    labels = [l for l, _ in out_rows]
    if len(out_rows) != 22 or labels[0] != "Guinea Ecuatorial":
        raise ValueError(f"ENH2 T48: read {len(out_rows)} rows: {labels}")
    total, *branches = out_rows
    if sum(v for _, v in branches) != total[1]:
        raise ValueError(f"ENH2 T48: branches sum to "
                         f"{sum(v for _, v in branches):,.0f}, not {total[1]:,.0f}")
    return [_row("industry", "Total" if lab == "Guinea Ecuatorial" else lab, v,
                 "ENH2 T48", measure="count", unit="persons")
            for lab, v in out_rows]


def parse(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        t46 = _page(pdf, r"Tabla 46\. Principales Indicadores del mercado laboral")
        t47 = _page(pdf, r"Tabla 47\. Distribución de la población ocupada según "
                         r"tipo de ocupación")
        t48 = _page(pdf, r"Tabla 48\. Distribución de la población ocupada según "
                         r"su área de residencia y por sector de actividad")
        t49 = _page(pdf, r"Tabla 49\. Distribución de la población según tipo "
                         r"ocupación")

    legend = dict(_FOOTNOTE_RE.findall(t49))
    for cat in _T49_CATS:
        num, name = cat.split(": ", 1)
        if re.sub(r"\s+", " ", legend.get(num, "")).rstrip(".") != name:
            raise ValueError(f"ENH2 T49: footnote {num!r} reads "
                             f"{legend.get(num)!r}, layout says {name!r}")

    rows = []
    # Tabla 46: PET(count) PET% PA TO TD TS PHST | OF OI | CSS SSS
    rows += _distribution(t46, ["Ocupación formal", "Ocupación informal",
                                "Con seguridad social", "Sin seguridad social"],
                          "formality", "ENH2 T46", lead=7, pick=[0, 1])
    rows += _distribution(t47, _T47_CATS, "employment_status", "ENH2 T47", lead=1)
    rows += _t48(t48)
    rows += _distribution(t49, _T49_CATS, "occupation", "ENH2 T49", lead=1)
    return pd.DataFrame(rows)
