"""Republic of Congo — CNSEE / INS household surveys, read from Wayback `id_`
copies of CNSEE's own files (cnsee.org is dead; INS's rebuilt site hosts no
household labour report -- see the descriptor). Three documents, three
surveys, never chained:

1. ECOM 2005 (Enquête Congolaise auprès des Ménages, June-August 2005) --
   "Profil de pauvreté au Congo en 2005", Annexe 3 "Tableau des indicateurs
   prioritaires": taux de chômage and taux d'activité (15+) by stratum and
   national. THE ONLY NATIONAL SOURCE. Tagged STRICT although the row label is
   bare "Taux de chômage": the report's own glossary (annex 1.4) defines the
   unemployed by the three ILO criteria -- no work in the reference week,
   searched in the past month, available immediately -- and publishes no
   relaxed variant.
2. EESIC 2009 (Enquête sur l'Emploi et le Secteur Informel au Congo, November
   2009), phase-1 indicator sheet: Brazzaville, Pointe-Noire and "Urbain
   Congo" only -- the survey covered the two cities, so nothing is national.
3. "Tableaux Emploi et Chômage en milieu Urbain" (INS, November-December 2011,
   published 2012): Congo urbain and six towns; BIT and élargi rates by sex,
   age and education, and BIT activity rates.

PUBLISHED DEFECTS, NOT SMOOTHED:

* EESIC 2009's "Urbain Congo" column pools the two cities, so each of its
  values must lie between them. Two do not: male BIT unemployment 13,9
  (Brazzaville 13,5, Pointe-Noire 11,5) and chômage élargi 26,6 (28,6 and
  32,1). Those two urban cells are refused; the city values are kept. Every
  other row passes the same test, which runs on every parse.
* The 2011 tables disagree with each other in the last digit (Tab. 5 gives
  Pointe-Noire 9,0 / urban 10,0; Tab. 6 gives 8,9 / 10,0; Tab. 9 gives urban
  10,1). Both kept, told apart by `series_label` -- not reconciled.
* "-" cells (Tab. 9, Tab. 10) are missing, never 0, and keep their column.

NOT COLLECTED: the RAPPORT_QUIBB_2012 (QUIBB 2011, national) -- every capture
of CNSEE's file is byte-identical and truncated at source (no trailer, no
root object; 53 page objects survive), so nothing can be read reliably;
EESIC 2009's "sous-emploi invisible" (income-based) and "sous-emploi global"
(which folds it in), salarisation, vulnerable employment (no topic); ECOM's
composition rows (labour/'s); the 2011 tables on inactivity, job search and
household relationship / migration.

CROSS-CHECK: ECOM 2005 chômage 19,4 (Brazzaville 32,6, rural 5,8), activité
69,5. EESIC 2009 urban BIT 16,1, élargi (Brazzaville) 28,6, activité 15-64
59,0. 2011 urban BIT 10,0, élargi 19,7, activité 53,1.
"""
from __future__ import annotations

import os
import re

import pandas as pd
import pdfplumber

from ._common import row

_UR, _LFPR = "unemployment_rate", "labour_force_participation_rate"


def _num(tok: str):
    """'12,4' / '9' -> float; '-' -> None (a missing cell keeps its place)."""
    if tok in ("-", "–"):
        return None
    return float(tok.replace(",", "."))


def _cells(s: str) -> list:
    return [_num(t) for t in s.split()]


def _text(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [ln.strip() for p in pdf.pages
                for ln in (p.extract_text() or "").splitlines()]


def _place(name: str) -> dict:
    n = name.replace("Pointe Noire", "Pointe-Noire")
    if n.lower().startswith(("urbain congo", "congo (urbain)")):
        return {"locality": "urban", "locality_label": n}
    return {"geography": n, "locality": "urban", "locality_label": n}


# --------------------------------------------------------------------------
# 1. ECOM 2005, Annexe 3
# --------------------------------------------------------------------------
_ECOM_STRATA = [
    {"geography": "Brazzaville", "locality": "urban", "locality_label": "Brazzaville"},
    {"geography": "Pointe-Noire", "locality": "urban", "locality_label": "Pointe-Noire"},
    {"locality": "other", "locality_label": "Autres communes"},
    {"locality": "other", "locality_label": "Milieu semi urbain"},
    {"locality": "rural", "locality_label": "Milieu rural"},
    {},
]


def _ecom(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        lines = [ln.strip() for p in pdf.pages[120:132]
                 for ln in (p.extract_text() or "").splitlines()]
    base = dict(survey="ECOM 2005 -- Enquête Congolaise auprès des Ménages",
                period="2005", reference_period="juin-août 2005",
                frequency="ad_hoc", working_age_base="15+",
                series_code="ECOM 2005 Annexe 3")
    out, seen = [], set()
    for ln in lines:
        for pat, topic, label, kw in (
                (r"^Taux de chômage \(%\)\s+(.*)$", _UR, "Taux de chômage",
                 {"definition": "strict"}),
                (r"^4\.2\.4 Taux d.activité \(%\)\s+(.*)$", _LFPR,
                 "Taux d'activité", {})):
            m = re.match(pat, ln)
            if m and topic not in seen:
                vals = _cells(m.group(1))
                if len(vals) != 6:
                    raise ValueError(f"ECOM annex {label}: {vals}")
                seen.add(topic)
                for ctx, v in zip(_ECOM_STRATA, vals):
                    out.append(row(topic=topic, series_label=label, value=v,
                                   **base, **kw, **ctx))
    if seen != {_UR, _LFPR}:
        raise ValueError(f"ECOM annex: found {seen}")
    return out


# --------------------------------------------------------------------------
# 2. EESIC 2009 indicator sheet: Brazzaville | Pointe Noire | Urbain Congo
# --------------------------------------------------------------------------
_EESIC_COLS = ["Brazzaville", "Pointe Noire", "Urbain Congo"]


def _eesic(path: str) -> list[dict]:
    lines = _text(path)
    base = dict(survey="EESIC 2009 -- Enquête sur l'Emploi et le Secteur "
                       "Informel au Congo (Brazzaville et Pointe-Noire)",
                period="2009-Q4", reference_period="novembre 2009",
                frequency="ad_hoc", series_code="EESIC 2009 phase 1")
    headings = [(r"^Taux d.activité au sens du BIT", "act"),
                (r"^Chômage au sens du BIT", "bit"),
                (r"^Caractéristiques des chômeurs", "chom"),
                (r"^Sous-emploi", "se"),
                (r"^Autres indicateurs", "autres"),
                (r"^Répartition des emplois", None)]
    section, out, refused = None, [], []
    for ln in lines:
        hit = next((sec for pat, sec in headings if re.match(pat, ln)), "")
        if hit != "":
            section = hit
            continue
        m = re.match(r"^(.*?)\s+(\d+,\d) (\d+,\d) (\d+,\d)$", ln)
        if not m:
            continue
        label, vals = m.group(1).strip(), [_num(m.group(i)) for i in (2, 3, 4)]
        spec = None
        if section == "act":
            a = re.match(r"^(\d+)\s*[–-]\s*(\d+) ans$", label)
            if a:
                spec = (_LFPR, "Taux d'activité au sens du BIT", "15-64",
                        {"age_group": f"{a.group(1)}-{a.group(2)}"}, {})
            elif label.startswith("Ensemble (15"):
                spec = (_LFPR, "Taux d'activité au sens du BIT", "15-64", {}, {})
            elif label in ("Hommes", "Femmes"):
                spec = (_LFPR, "Taux d'activité au sens du BIT", "15-64",
                        {"sex": "male" if label == "Hommes" else "female"}, {})
        elif section == "bit":
            a = re.match(r"^(\d+)\s*[–-]\s*(\d+) ans$", label)
            if a:
                spec = (_UR, "Chômage au sens du BIT", "15-64",
                        {"age_group": f"{a.group(1)}-{a.group(2)}"},
                        {"definition": "strict"})
            elif label.startswith("Ensemble (15"):
                spec = (_UR, "Chômage au sens du BIT", "15-64", {},
                        {"definition": "strict"})
            elif label in ("Hommes", "Femmes"):
                spec = (_UR, "Chômage au sens du BIT", "15-64",
                        {"sex": "male" if label == "Hommes" else "female"},
                        {"definition": "strict"})
            elif label.startswith("Chômage élargi"):
                spec = (_UR, "Chômage élargi (15 - 64 ans)", "15-64", {},
                        {"definition": "broad"})
        elif section == "chom" and label.startswith("% des chômeurs de plus"):
            spec = ("long_term_unemployment_share",
                    "% des chômeurs de plus d'1 an", "15-64", {}, {})
        elif section == "se" and label == "Taux de sous-emploi visible":
            spec = ("underemployment_rate", label, "15-64", {}, {})
        elif section == "autres" and label == "Taux d'informalité":
            spec = ("informal_employment_share", label, "not stated", {}, {})
        elif section == "autres" and label.startswith("Ratio emploi/population"):
            spec = ("employment_to_population_ratio", label, "not stated", {}, {})
        if not spec:
            continue
        topic, slabel, wab, ctx, kw = spec
        b, p, u = vals
        # The pooled column must lie between its two cities.
        if not (min(b, p) - 0.05 <= u <= max(b, p) + 0.05):
            refused.append((slabel, ctx, u))
            cols = list(zip(_EESIC_COLS[:2], vals[:2]))
        else:
            cols = list(zip(_EESIC_COLS, vals))
        for place, v in cols:
            out.append(row(topic=topic, series_label=slabel, value=v,
                           working_age_base=wab, **base, **kw, **ctx,
                           **_place(place)))
    known = {("Chômage au sens du BIT", (("sex", "male"),)),
             ("Chômage élargi (15 - 64 ans)", ())}
    got = {(s, tuple(sorted(c.items()))) for s, c, _ in refused}
    if got != known:
        raise ValueError(f"EESIC 2009: pooled-column failures changed: {refused}")
    if len(out) < 40:
        raise ValueError(f"EESIC 2009: only {len(out)} values read")
    return out


# --------------------------------------------------------------------------
# 3. Tableaux Emploi et Chômage en milieu Urbain, Nov-Dec 2011
# --------------------------------------------------------------------------
_T11 = dict(survey="Enquête Emploi et Chômage en milieu urbain 2011 (INS, "
                   "Tableaux Emploi 2012)",
            period="2011-Q4", reference_period="novembre-décembre 2011",
            frequency="ad_hoc", working_age_base="15+")
_SEX = {"Masculin": {"sex": "male"}, "Féminin": {"sex": "female"},
        "Ensemble": {}}
_AGE3 = [{"age_group": "15-29"}, {"age_group": "30-49"},
         {"age_group": "50+"}, {}]
_EDU = ["Primaire", "Secondaire général cycle I", "Secondaire général cycle II",
        "Secondaire technique cycle I", "Secondaire technique cycle II",
        "Supérieur", None]
_TOWNS6 = ["Congo (Urbain)", "Dolisie", "Nkayi", "Ouesso", "Brazzaville",
           "Pointe-Noire"]
_TOWNS7 = ["Congo (Urbain)", "Dolisie", "Mossendjo", "Nkayi", "Ouesso",
           "Brazzaville", "Pointe-Noire"]


def _between(lines, start_re, stop_re):
    i = next(k for k, ln in enumerate(lines) if re.match(start_re, ln))
    out = []
    for ln in lines[i + 1:]:
        if re.match(stop_re, ln):
            break
        out.append(ln)
    return out


def _town_by_sex(block, n):
    """'Town v v v' rows (Masculin Féminin Ensemble)."""
    got = []
    for ln in block:
        m = re.match(r"^(.+?)\s+((?:[\d,]+|-)(?: (?:[\d,]+|-)){%d})$" % (n - 1), ln)
        if m and not m.group(1)[0].isdigit():
            got.append((m.group(1), _cells(m.group(2))))
    return got


def _sex_groups(block, ncells, towns):
    """Masculin / Féminin / Ensemble triples, one per town in `towns` order;
    the town's name may sit on any line of its triple (or wrap round it)."""
    rows, text = [], []
    for ln in block:
        m = re.match(r"^(.*?)\b(Masculin|Féminin|Ensemble)\s+((?:[\d,]+|-)"
                     r"(?: (?:[\d,]+|-)){%d})$" % (ncells - 1), ln)
        if m:
            rows.append((m.group(2), _cells(m.group(3))))
            text.append(m.group(1))
        elif rows or not text:
            text.append(ln)
    if len(rows) != 3 * len(towns):
        raise ValueError(f"2011 tables: {len(rows)} sex rows for {len(towns)} towns")
    flat = " ".join(block)
    pos = 0
    for t in towns:            # each town name must appear, in order
        first = t.split()[0].split("-")[0]
        k = flat.find(first, pos)
        if k < 0:
            raise ValueError(f"2011 tables: town {t!r} not found in order")
        pos = k + len(first)
    out = []
    for i, t in enumerate(towns):
        for sexlab, cells in rows[3 * i:3 * i + 3]:
            out.append((t, sexlab, cells))
    if [r[1] for r in out[:3]] != ["Masculin", "Féminin", "Ensemble"]:
        raise ValueError("2011 tables: sex rows out of order")
    return out


def _tables_2011(path: str) -> list[dict]:
    L = _text(path)
    out = []

    def emit(topic, label, code, v, ctx, definition="not_applicable"):
        if v is None:
            return
        out.append(row(topic=topic, series_label=label, value=v,
                       definition=definition, series_code=f"INS 2011 {code}",
                       **_T11, **ctx))

    # Tab 5 / Tab 7 / Tab 21: town x (Masculin Féminin Ensemble)
    for start, stop, topic, label, code, dfn, towns in (
            (r"^Tableau 5 :", r"^Tableau 6 :", _UR,
             "Taux de chômage au sens BIT", "Tab. 5", "strict", 6),
            (r"^Tableau 7:", r"^Tableau 8 :", _UR,
             "Taux de chômage élargi", "Tab. 7", "broad", 7),
            (r"^Tableau 21 :", r"^Tableau 22 :", _LFPR,
             "Taux d'activité BIT", "Tab. 21", "not_applicable", 7)):
        got = _town_by_sex(_between(L, start, stop), 3)
        if len(got) != towns:
            raise ValueError(f"2011 {code}: {len(got)} towns")
        for town, cells in got:
            for sexctx, v in zip(_SEX.values(), cells):
                emit(topic, label, code, v, {**_place(town), **sexctx}, dfn)

    # Tab 6 / Tab 8: town x sex x 3 age classes + total
    for start, stop, label, code, dfn, towns in (
            (r"^Tableau 6 :", r"^Tableau 7:", "Taux de chômage BIT",
             "Tab. 6", "strict", _TOWNS6),
            (r"^Tableau 8 :", r"^Tableau 9 :", "Taux de chômage élargi",
             "Tab. 8", "broad", _TOWNS7)):
        for town, sexlab, cells in _sex_groups(_between(L, start, stop), 4, towns):
            for agectx, v in zip(_AGE3, cells):
                emit(_UR, f"{label} par grand groupe d'âge", code, v,
                     {**_place(town), **_SEX[sexlab], **agectx}, dfn)

    # Tab 9: five-year age x sex, Congo urbain
    n = 0
    for ln in _between(L, r"^Tableau 9 :", r"^Tableau 10 :"):
        m = re.match(r"^(\d+ à \d+ ans|60 ans et plus|Ensemble)\s+"
                     r"((?:[\d,]+|-) (?:[\d,]+|-) (?:[\d,]+|-))$", ln)
        if not m:
            continue
        lab = m.group(1)
        age = ({} if lab == "Ensemble" else
               {"age_group": "60+" if lab.startswith("60") else
                re.sub(r"(\d+) à (\d+) ans", r"\1-\2", lab)})
        for sexctx, v in zip(_SEX.values(), _cells(m.group(2))):
            emit(_UR, "Taux de chômage (BIT) par groupe d'âges quinquennal",
                 "Tab. 9", v, {**_place("Congo (Urbain)"), **sexctx, **age},
                 "strict")
        n += 1
    if n != 11:
        raise ValueError(f"2011 Tab. 9: {n} rows")

    # Tab 10: town x sex x education (7 cells)
    block = _between(L, r"^Tableau 10 :", r"^\d+$")
    for town, sexlab, cells in _sex_groups(block, 7, _TOWNS6):
        for edu, v in zip(_EDU, cells):
            emit(_UR, "Taux de chômage BIT par niveau d'instruction", "Tab. 10",
                 v, {**_place(town), **_SEX[sexlab],
                     **({"education": edu} if edu else {})}, "strict")

    # Tab 22: activity by age x sex, Congo urbain
    n = 0
    for ln in _between(L, r"^Tableau 22 :", r"^Tableau 23 :"):
        m = re.match(r"^(\d+ ?-\s?\d+|70 ans et \+|Ensemble)\s+"
                     r"([\d,]+ [\d,]+ [\d,]+)$", ln)
        if not m:
            continue
        lab = m.group(1)
        age = ({} if lab == "Ensemble" else
               {"age_group": "70+" if lab.startswith("70") else
                re.sub(r"\s", "", lab)})
        for sexctx, v in zip(_SEX.values(), _cells(m.group(2))):
            emit(_LFPR, "Taux d'activité BIT par groupe d'âges", "Tab. 22", v,
                 {**_place("Congo (Urbain)"), **sexctx, **age})
        n += 1
    if n != 13:
        raise ValueError(f"2011 Tab. 22: {n} rows")
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    out = _ecom(path)
    for ex in extras or []:
        name = os.path.basename(ex).lower()
        if "eesic" in name:
            out += _eesic(ex)
        elif "tableauxemploi" in name.replace("_", ""):
            out += _tables_2011(ex)
        else:
            raise ValueError(f"Congo: unexpected extra file {ex}")
    return pd.DataFrame(out)
