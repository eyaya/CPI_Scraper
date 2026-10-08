"""Equatorial Guinea — INEGE, II Encuesta Nacional de Hogares (ENH2), informe
definitivo (November 2024), Capítulo V "Empleo", Tabla 46 "Principales
Indicadores del mercado laboral".

THE SAME REPORT `labour/` READS (Tablas 46-49 for composition, of which it
takes only Tabla 46's formal/informal columns). This module takes the four
headline rates from the same Tabla 46, by nation, región, zona, sexo and the
seven provinces:

* PA  "Población Activa" -- the report itself calls it "la tasa de
      participación en la fuerza laboral" -> labour_force_participation_rate;
* TO  "Tasa de Ocupación" -> employment_to_population_ratio (TO = PA x (1-TD)
      to the rounding in every row -- 72,0 x 0,863 = 62,1 -- so it is the
      employed over the working-age population, not over the actives);
* TD  "Tasa de Desocupación" ("tasa de paro") -> unemployment_rate;
* TS  "Tasa de Subocupación" -> underemployment_rate.

WORKING-AGE BASE 18-64, the legal working age (Ley 10/2012): "población en
edad legal de trabajar ... de 18 a 64 años". No other country here uses it.

A HOUSEHOLD survey (consumption, poverty and employment), fieldwork 16 August
2022 to 14 August 2023 -> period 2023 (end-year convention), reference
"agosto 2022 - agosto 2023".

DEFINITION `not_applicable`: INEGE publishes one unemployment rate with no
strict / broad qualifier, and the report's prose describes TD loosely ("la
población en edad de trabajar sin empleo") -- the arithmetic above shows it is
unemployed over the actives.

NOT COLLECTED: the first count column (it is the TOTAL population of each
group -- 1.594.432 nationally -- with PET the share of it aged 18-64, neither a
topic here); PHST (mean weekly hours); OF / OI (formal / informal shares of the
employed -- `labour/` holds them, and a figure has one home); CSS / SSS
(social-security cover). Tabla 52 is a distribution of the unemployed across
education levels, not a rate per level, and has no topic here.

SPANISH NUMBERS: "1.594.432" thousands dot, "50,2" decimal comma.

A SECOND, EARLIER ROUND comes from INEGE's Anuario Estadístico 2023
(an `extra_urls` file): its Tabla 88 "Tasa de Actividad, Empleo y Paro, por
características sociodemográficas (%). G.E. 2015" reprints the EPAFE 2015
(Encuesta de Población Activa, Formación y Empleo -- INEGE's labour force
survey) by sex, nationality and zone. The yearbook defines the employment rate
over "el total de población de 16 y más años", so that round's base is 16+;
the ENH2's is 18-64. They are different surveys on different bases and must
not be chained. Its nationality rows (nacionales / extranjeros) are not
collected: no column of this schema holds nationality.

CROSS-CHECK: PA 72,0 (rural 79,9); TO 62,1; TD 13,7 (urbana 16,7, femenino
15,0, Litoral 21,5, Kie Ntem 4,6); TS 5,6. EPAFE 2015: actividad 60,2, empleo
50,6, paro 15,9 (hombres 17,4, mujeres 14,2, urbana 19,1).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_SURVEY = "II Encuesta Nacional de Hogares (ENH2)"
_BASE, _PERIOD, _REF = "18-64", "2023", "agosto 2022 - agosto 2023"
_NUM = r"\d{1,3}(?:\.\d{3})+|\d+(?:,\d)?|-"

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
# Tabla 46's eleven columns: population, PET%, PA, TO, TD, TS, PHST, OF, OI,
# CSS, SSS. Only these four are collected.
_TAKE = {2: ("labour_force_participation_rate", "Población Activa (PA)"),
         3: ("employment_to_population_ratio", "Tasa de Ocupación (TO)"),
         4: ("unemployment_rate", "Tasa de Desocupación (TD)"),
         5: ("underemployment_rate", "Tasa de Subocupación (TS)")}
_CAPTION = re.compile(r"^Tabla 46\. Principales Indicadores del mercado laboral"
                      r"(?![^\n]*\.{4})", re.M)


def _num(tok: str) -> float | None:
    return None if tok == "-" else float(tok.replace(".", "").replace(",", "."))


_T88 = re.compile(r"^Tabla 88: Tasa de Actividad, Empleo y Paro, por "
                  r"características sociodemográficas(?![^\n]*\.{4})", re.M)
_T88_GROUPS = {"Hombres": {"sex": "male"}, "Mujeres": {"sex": "female"},
               "Urbana": {"locality": "urban", "locality_label": "Urbana"},
               "Rural": {"locality": "rural", "locality_label": "Rural"},
               "Total": {}}


def _epafe_2015(path: str) -> list[dict]:
    """Anuario Estadístico 2023, Tabla 88 (EPAFE 2015)."""
    # The list of tables repeats the caption (wrapped before its dot leaders),
    # so the table's page is the one that also carries its EPAFE source line.
    with pdfplumber.open(path) as pdf:
        text = next((t for t in (p.extract_text() or "" for p in pdf.pages)
                     if _T88.search(t)
                     and "Fuente: EPAFE de Guinea Ecuatorial, 2015" in t), None)
    if text is None:
        raise ValueError("Anuario: Tabla 88 with an EPAFE 2015 source not found")
    body = text[_T88.search(text).end():]
    read = {}
    for ln in body.splitlines():
        m = re.fullmatch(r"(Hombres|Mujeres|Urbana|Rural|Total|Nacionales|"
                         r"Extranjeros)\s+(\d{1,3},\d)\s+(\d{1,3},\d)\s+(\d{1,3},\d)",
                         ln.strip())
        if m:
            read[m.group(1)] = [_num(v) for v in m.groups()[1:]]
        if ln.startswith("Fuente"):
            break
    if not set(_T88_GROUPS) <= set(read):
        raise ValueError(f"Anuario T88: rows read {sorted(read)}")
    rows = []
    for lab, ctx in _T88_GROUPS.items():
        act, emp, paro = read[lab]
        if abs(act * (1 - paro / 100) - emp) > 0.15:
            raise ValueError(f"Anuario T88 {lab}: {act}, {paro} do not give {emp}")
        for topic, label, v in (
                ("labour_force_participation_rate", "Tasa de actividad", act),
                ("employment_to_population_ratio", "Tasa de Empleo", emp),
                ("unemployment_rate", "Tasa de Paro", paro)):
            rows.append(C.row(topic=topic, definition="not_applicable", value=v,
                              series_label=label,
                              survey="Encuesta de Población Activa, Formación y "
                                     "Empleo (EPAFE) 2015",
                              period="2015", reference_period="EPAFE 2015",
                              frequency="ad_hoc", working_age_base="16+",
                              series_code="Anuario 2023 T88", **ctx))
    return rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for ex in extras or []:
        rows += _epafe_2015(ex)
    with pdfplumber.open(path) as pdf:
        text = next(t for t in (p.extract_text() or "" for p in pdf.pages[100:])
                    if _CAPTION.search(t))
    text = text[_CAPTION.search(text).start():]
    read = {}
    for ln in text.splitlines()[1:]:
        m = re.fullmatch(rf"(\D+?)\s+((?:(?:{_NUM})\s*)+)", ln.strip())
        if not m or m.group(1) not in _GROUPS:
            continue
        vals = [_num(t) for t in re.findall(_NUM, m.group(2))]
        if len(vals) != 11:
            raise ValueError(f"ENH2 T46: {m.group(1)!r} has {len(vals)} cells: {ln!r}")
        read[m.group(1)] = vals
    if set(read) != set(_GROUPS):
        raise ValueError(f"ENH2 T46: groups read {sorted(read)}")
    for lab, vals in read.items():
        pa, to, td = vals[2], vals[3], vals[4]
        # TO is the employed over the working-age population: PA x (1 - TD).
        if abs(pa * (1 - td / 100) - to) > 0.15:
            raise ValueError(f"ENH2 T46 {lab}: PA {pa}, TD {td} do not give TO {to}")
        for idx, (topic, label) in _TAKE.items():
            if vals[idx] is None:
                continue
            rows.append(C.row(topic=topic, definition="not_applicable",
                              value=vals[idx], series_label=label,
                              survey=_SURVEY, period=_PERIOD,
                              reference_period=_REF, frequency="ad_hoc",
                              working_age_base=_BASE, series_code="ENH2 T46",
                              **_GROUPS[lab]))
    return pd.DataFrame(rows)
