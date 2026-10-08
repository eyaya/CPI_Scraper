"""Central African Republic — ICASEES (formerly DGSEED), RGPH03 (census of
December 2003), thematic report "Caractéristiques économiques" (June 2005).

A CENSUS. Two activity rates and one unemployment rate, as the report defines
them:

* "Taux brut d'activité" -- the active population over the population, read
  by the report itself as persons aged 6 and over ("trois personnes de six ans
  et plus sur cinq sont actifs en zone rurale"), the census's own activity
  threshold -> working_age_base 6+;
* "Taux spécifique d'activité" -- the same on the 15+ population (footnote 4
  of chapter II) -> 15+;
* "Taux de chômage" -- population 15+ (Tableaux Eco 25-27 say so).

THE UNEMPLOYMENT RATE IS TAGGED `not_applicable`, NOT strict. The report
defines the unemployed as persons 15+ "qui ne sont pas occupées mais ayant
déjà travaillé ou à la recherche éventuelle d'un premier emploi rémunéré" --
a census concept with no availability test and no BIT label, and no élargi
variant beside it. Calling it strict would claim an ILO definition ICASEES
never states; calling it broad would invent a contrast it never draws.

TAKEN: Eco 3 (both rates by milieu x sex), Eco 4 (both rates by région and
préfecture x sex), Eco 5 (taux brut by education x sex), Eco 8's RGPH 1988
half (the 1988 census as this report republishes it, period 1988), Eco 25
(chômage by milieu x sex), Eco 26 (by five-year age x sex), Eco 27 (by région
and préfecture x sex -- its columns are Ensemble | Homme | Femme, the reverse
of Eco 25's order, read from its own header).

NOT TAKEN: Eco 8's 2003 half (it repeats Eco 3, checked equal on every run);
Eco 1 (shares of the active 6+ by occupied / CDT / CJT -- an unemployment
share would have to be summed from two printed shares); Eco 6 (by marital
status -- no column for it); the composition tables (labour/'s).

PRINTED DOT DECIMAL: Eco 4 prints Bangui's taux spécifique as "46.1" among
comma decimals; a French reader takes the dot as a thousands mark (461). It is
read as 46,1, the figure the prose gives ("la ville de Bangui ... 46 %").

Régions are printed "Région 1".."Région 6" (Eco 4) and "Region 1" (Eco 27);
préfectures in capitals. Both kept as printed. Bangui is a commune with the
status of a préfecture, outside the six régions.

CROSS-CHECK: taux brut 51,9 (H 56,8 / F 47,1); taux spécifique 66,4; chômage
7,6 (urbain 15,2, rural 4,2; Bangui 21,1; 15-19 ans 14,2); 1988 taux brut
48,2.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from ._common import numbers_in, row

_SURVEY = "Recensement Général de la Population et de l'Habitation (RGPH03)"
_BASE = dict(period="2003", reference_period="RGPH décembre 2003",
             frequency="ad_hoc")
_LFPR = "labour_force_participation_rate"
_UR = "unemployment_rate"
_BRUT = "Taux brut d'activité"
_SPEC = "Taux spécifique d'activité"
_CHOM = "Taux de chômage"
_SEX3 = [{"sex": "male"}, {"sex": "female"}, {}]


def _nums(text: str) -> list[float]:
    # "46.1" among comma decimals: a dot before ONE trailing digit is a decimal
    # mark misprinted, not a thousands separator.
    text = re.sub(r"(?<=\d)\.(?=\d\b)", ",", text)
    return numbers_in(text, decimal=",")


def _lines(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        out = []
        for p in pdf.pages[20:50]:
            out += [ln.strip() for ln in (p.extract_text() or "").splitlines()]
    return out


def _after(lines: list[str], caption: str) -> list[str]:
    i = next((k for k, ln in enumerate(lines) if re.match(caption, ln)), None)
    if i is None:
        raise ValueError(f"RGPH03: {caption!r} not found")
    return lines[i + 1:]


def _geo(label: str) -> dict:
    if label.lower().startswith("ensemble"):
        return {}
    return {"geography": label}


def _milieu(label: str) -> dict:
    if label.startswith("Ensemble"):
        return {}
    return {"locality": "urban" if label == "Urbain" else "rural",
            "locality_label": label}


def parse(path: str, extras=None) -> pd.DataFrame:
    L = _lines(path)
    out = []

    def emit(topic, label, base, vals, cols, ctx, code, survey=_SURVEY, **kw):
        for col, v in zip(cols, vals):
            out.append(row(topic=topic, series_label=label, value=v,
                           working_age_base=base, survey=survey,
                           series_code=f"RGPH03 {code}",
                           **{**_BASE, **kw, **ctx, **col}))

    # --- Eco 3: milieu x (brut H F E | spécifique H F E)
    got = {}
    for ln in _after(L, r"^Tableau Eco 3:"):
        m = re.match(r"^(Urbain|Rural|Ensemble RCA)\s+(.*)$", ln)
        if m:
            got[m.group(1)] = _nums(m.group(2))
        if "Ensemble RCA" in got:
            break
    if len(got) != 3 or any(len(v) != 6 for v in got.values()):
        raise ValueError(f"RGPH03 Eco 3: {got}")
    for lab, v in got.items():
        emit(_LFPR, _BRUT, "6+", v[:3], _SEX3, _milieu(lab), "Eco 3")
        emit(_LFPR, _SPEC, "15+", v[3:], _SEX3, _milieu(lab), "Eco 3")
    eco3 = got

    # --- Eco 4: label on one line, its six values on the next
    seq, pending = [], None
    for ln in _after(L, r"^Tableau Eco 4:"):
        if pending is not None:
            v = _nums(ln)
            if len(v) == 6:
                seq.append((pending, v))
                if pending.startswith("Ensemble"):
                    break
                pending = None
                continue
        if re.match(r"^(Région \d|[A-Z][A-Z \-]+[A-Z]|Ensemble RCA)$", ln):
            pending = ln
    if len(seq) != 24:
        raise ValueError(f"RGPH03 Eco 4: {len(seq)} rows, 24 expected")
    if seq[-1][1] != eco3["Ensemble RCA"]:
        raise ValueError("RGPH03 Eco 4: national row differs from Eco 3")
    for lab, v in seq[:-1]:
        emit(_LFPR, _BRUT, "6+", v[:3], _SEX3, _geo(lab), "Eco 4")
        emit(_LFPR, _SPEC, "15+", v[3:], _SEX3, _geo(lab), "Eco 4")

    # --- Eco 5: taux brut by education x sex (H F E)
    n = 0
    for ln in _after(L, r"^Tableau Eco 5:"):
        m = re.match(r"^(Sans Niveau|Primaire|Secondaire [12]|Technique|"
                     r"Supérieur|Autres)\s+(.*)$", ln)
        if m:
            emit(_LFPR, _BRUT, "6+", _nums(m.group(2)), _SEX3,
                 {"education": m.group(1)}, "Eco 5")
            n += 1
        if n == 7:
            break
    if n != 7:
        raise ValueError(f"RGPH03 Eco 5: {n} rows")

    # --- Eco 8: 1988 | 2003, each Urbain Rural Ensemble, in two blocks
    block, rows8 = None, {}
    for ln in _after(L, r"^Tableau Eco 8:"):
        if ln.startswith("Taux bruts"):
            block = _BRUT
        elif ln.startswith("Taux spécifiques"):
            block = _SPEC
        m = re.match(r"^(Hommes|Femmes|Ensemble)\s+(.*)$", ln)
        if block and m:
            rows8[(block, m.group(1))] = _nums(m.group(2))
        if len(rows8) == 6:
            break
    sex = {"Hommes": {"sex": "male"}, "Femmes": {"sex": "female"}, "Ensemble": {}}
    mil = [{"locality": "urban", "locality_label": "Urbain"},
           {"locality": "rural", "locality_label": "Rural"}, {}]
    for (blk, s), v in rows8.items():
        if len(v) != 6:
            raise ValueError(f"RGPH03 Eco 8 {blk} {s}: {v}")
        # the 2003 half must be Eco 3 again
        col = {"Hommes": 0, "Femmes": 1, "Ensemble": 2}[s] + (3 if blk == _SPEC else 0)
        if v[3:] != [eco3["Urbain"][col], eco3["Rural"][col], eco3["Ensemble RCA"][col]]:
            raise ValueError(f"RGPH03 Eco 8 {blk} {s}: 2003 half differs from Eco 3")
        emit(_LFPR, f"{blk} (RGPH 1988)", "6+" if blk == _BRUT else "15+",
             v[:3], mil, sex[s], "Eco 8", survey="RGP 1988, as republished in "
             "the RGPH03 economic-characteristics report",
             period="1988", reference_period="RGP 1988")

    # --- Eco 25: milieu x (H F E)
    got = {}
    for ln in _after(L, r"^Tableau Eco 25:"):
        m = re.match(r"^(Urbain|Rural|Ensemble RCA)\s+(.*)$", ln)
        if m:
            got[m.group(1)] = _nums(m.group(2))
        if "Ensemble RCA" in got:
            break
    for lab, v in got.items():
        if len(v) != 3:
            raise ValueError(f"RGPH03 Eco 25 {lab}: {v}")
        emit(_UR, _CHOM, "15+", v, _SEX3, _milieu(lab), "Eco 25")
    eco25 = got

    # --- Eco 26: five-year age x (H F E); no total row is printed
    n = 0
    for ln in _after(L, r"^Tableau Eco 26:"):
        m = re.match(r"^(\d\d) - (\d\d)\s+(.*)$", ln)
        if m:
            emit(_UR, _CHOM, "15+", _nums(m.group(3)), _SEX3,
                 {"age_group": f"{m.group(1)}-{m.group(2)}"}, "Eco 26")
            n += 1
        elif n:
            break
    if n != 9:
        raise ValueError(f"RGPH03 Eco 26: {n} age rows, 9 expected")

    # --- Eco 27: région / préfecture x (Ensemble H F) -- note the order
    seq = []
    for ln in _after(L, r"^Tableau Eco 27:"):
        m = re.match(r"^(Region \d|[A-Z][A-Z \-]+[A-Z]|Ensemble RCA)\s+"
                     r"(\d+,\d \d+,\d \d+,\d)$", ln)
        if m:
            seq.append((m.group(1), _nums(m.group(2))))
            if m.group(1) == "Ensemble RCA":
                break
    if len(seq) != 24:
        raise ValueError(f"RGPH03 Eco 27: {len(seq)} rows, 24 expected")
    nat = seq[-1][1]
    if [nat[1], nat[2], nat[0]] != eco25["Ensemble RCA"]:
        raise ValueError("RGPH03 Eco 27: national row differs from Eco 25 -- "
                         "column order changed?")
    for lab, v in seq[:-1]:
        emit(_UR, _CHOM, "15+", v, [{}, {"sex": "male"}, {"sex": "female"}],
             _geo(lab), "Eco 27")

    return pd.DataFrame(out)
