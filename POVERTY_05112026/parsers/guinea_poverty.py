"""Guinea -- monetary-poverty layout (INS, Rapport final EHCVM 2018/2019, ch. 5).

EHCVM 2018/2019 (two waves, 2018-19; the report dates its results "2019").
National line 5 006 533 GNF per person per year; food (extreme) line
3 068 265 GNF; welfare = consumption per capita. International line as printed:
"$3,2 PPA 2011" (5 947 113 GNF), moderate poverty.

THE NUMBER TRAP -- WHY THIS MODULE BUILDS ITS OWN PAGE TEXT. INS prints
thousands with a SPACE and drops ",0" from whole percentages, so a row reads

    Kankan 30,5 6,6 2 685 665 13      (P0, P1, P2=2, poor 685 665, share 13)
    Guinée 43,7 12,5 5 5 264 038 100  (P2=5, poor 5 264 038, share 100)

and no text rule can tell "2 685 665" (one number) from "2 | 685 665" (two).
The page geometry can: the gap inside a number is 2.4-2.8pt, between columns
it is >= 7pt. `_page_text` rebuilds each line from word boxes, glues a
three-digit group onto the number before it only across a gap < 4pt, and puts
" | " between columns, so the shared reader can never re-glue them. It also
turns a decimal POINT into a comma: Tableaux 5.24/5.25/5.30-5.32 print "49.8"
in an otherwise comma-decimal report, and read with decimal "," that is 498.

Collected (all EHCVM 2018/2019 unless dated otherwise):
  5.8   international ($3,2 PPA 2011) P0/P1/P2 (its national row repeats 5.10)
  5.9   international poor count (6 751 096)
  5.10  8 administrative regions: P0 P1 P2, poor count, share of the poor
  5.11  4 natural regions (Conakry repeats 5.10)
  5.12  Urbain / Autres urbains / Rural
  5.13  household size; 5.14 rural x regions; 5.15 rural x household size;
  5.16  urban x regions
  5.17-5.21  sex, age, education, marital status, occupation of the head
  5.22-5.24  sex, age, education of individuals
  5.28  P0 1994 (EIBC 1993/1994), 2003 (EIBEP 2002/2003), 2007 (ELEP 2007):
        Ensemble, Conakry, Urbain, Rural -- each survey under its OWN line;
        the report says the EHCVM is NOT comparable with these rounds
  5.29  ELEP 2012 P0 P1 P2 by region; 5.30 ELEP 2012 P0 urban/rural by region
  5.31/5.32  P0 by age group (Enfants/Jeunes/Adultes/Personnes âgées) x sex x
        milieu / region, and sex x milieu / region
  5.33/5.34  EXTREME poverty (food line) by region, natural region, milieu, zone

Not collected: 5.3-5.5 (line values by region: no metric for a line itself;
the national lines are in line_value), 5.6/5.7 (mean consumption), 5.9's
national row (prints 5 264 877 poor against 5 264 038 everywhere else),
5.25 (individuals' marital status), 5.26 (individuals' occupation; its
"Ensemble" pairs the national P0 with the employed-only count), 5.27 (branch
of activity) -- no topic for these; 5.35/5.36 (inequality: separate
indicator), 5.37 (MPI). Repeated national / Conakry / rural rows are taken once.
The 2019 columns of 5.28-5.30 repeat 5.10/5.12 and are skipped; 5.30's 2019
"Guinée" column repeats its Urbain column (a published error).

PUBLISHED QUIRKS KEPT: 5.18's caption says "en milieu urbain" but its rows are
national (its Guinée row is 43,7 and its shares sum to 100). Region "N'Nzérékoré"
(5.32/5.33 typo) is filed as Nzérékoré, the name every other table prints.

CROSS-CHECK (verbatim): P0 43,7 / P1 12,5 / P2 5 (5,0); poor 5 264 038;
international P0 56 / P1 18,5 / P2 8,2; Labé 66, Conakry 15,7; rural 55,4;
extreme 13,4 (1 615 664); ELEP 2012 55,2 / 18,4 / 8,4; 1994 62,6.
"""
from __future__ import annotations

import re

import pandas as pd

from . import poverty_tables as T
from ._vocab import label_rows

_NUM = re.compile(r"^-?\d+(?:[.,]\d+)?$")


def _page_text(page) -> str:
    """One page's text rebuilt from word boxes (see the module docstring)."""
    w, h = page.width, page.height
    words = sorted(page.crop((0, 0, w, h)).extract_words(), key=lambda x: (x["top"], x["x0"]))
    lines: list[list[dict]] = []
    for wd in words:
        if lines and abs(wd["top"] - lines[-1][0]["top"]) <= 2.5:
            lines[-1].append(wd)
        else:
            lines.append([wd])
    out = []
    for ln in lines:
        ln.sort(key=lambda x: x["x0"])
        toks: list[list] = []  # [text, x1, is_chain]
        for wd in ln:
            t = wd["text"]
            # A decimal point becomes a comma -- but not a caption or section
            # number ("Tableau 5.8", "5.5 Déterminants" at line start).
            if (re.fullmatch(r"-?\d+\.\d+", t) and toks
                    and toks[-1][0] not in ("Tableau", "Carte", "Graphique")):
                t = t.replace(".", ",")
            if toks:
                prev, gap = toks[-1], wd["x0"] - toks[-1][1]
                if (gap < 4 and re.fullmatch(r"\d{3}(?:,\d+)?", t)
                        and re.fullmatch(r"\d+", prev[0])
                        and (len(prev[0]) <= 3 or prev[2])):
                    prev[0], prev[1], prev[2] = prev[0] + t, wd["x1"], True
                    continue
                sep = " | " if (_NUM.match(prev[0]) and _NUM.match(t)) else " "
                toks.append([t, wd["x1"], False, sep])
            else:
                toks.append([t, wd["x1"], False, ""])
        out.append("".join(tk[3] + tk[0] for tk in toks))
    return "\n".join(out)


def _pages(path: str) -> dict[str, list[str]]:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return {"full": [_page_text(p) for p in pdf.pages]}


# --- the lines ------------------------------------------------------------
_NAT = {"line_type": "national", "line_level": "overall",
        "line_name": "Seuil national de pauvreté (EHCVM 2018/2019)",
        "line_value": 5006533, "line_unit": "GNF per person per year"}
_EXT = {"line_type": "national", "line_level": "extreme",
        "line_name": "Seuil d'extrême pauvreté (seuil alimentaire, EHCVM 2018/2019)",
        "line_value": 3068265, "line_unit": "GNF per person per year"}
_INT = {"line_type": "international", "line_level": "other",
        "line_name": "Seuil international en 2018 ($3,2 PPA 2011)",
        "line_value": 5947113, "line_unit": "GNF per person per year"}
_ELEP12 = {"survey": "ELEP 2012", "period": "2012", "reference_period": "2012",
           "line_name": "Seuil national de pauvreté (ELEP 2012)",
           "line_value": 3217305, "line_unit": "GNF per person per year"}


def _old(survey, period, ref):
    return {"metric": "headcount", "survey": survey, "period": period,
            "reference_period": ref, "line_name": f"Seuil national de pauvreté ({survey})",
            "line_value": "", "line_unit": ""}


# --- column vocabularies --------------------------------------------------
_FGT5 = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"},
         {"metric": "poor_count"}, {"metric": "poor_share"}]
_SKIP = {"skip": True}

_REGIONS = ["Boké", "Conakry", "Faranah", "Kankan", "Kindia", "Labé", "Mamou", "Nzérékoré"]
_NATREG = ["Basse Guinée", "Moyenne Guinée", "Haute Guinée", "Guinée Forestière"]


def _geo_rows(names, **attrs):
    out = []
    for n in names:
        pat = r"^(?:N')?" + re.escape(n) if n == "Nzérékoré" else r"^" + re.escape(n)
        out.append({"match": pat + r"(?=\s+-?\d)", "geography": n, **attrs})
    return out


def _cap(*words):
    return {"page_contains": list(words), "page_excludes": ["liste des tableaux"]}


_RURAL = {"locality": "rural", "locality_label": "Rural"}
_URBAN = {"locality": "urban", "locality_label": "Urbain"}
_AGE4 = ["Enfants", "Jeunes", "Adultes", "Personnes âgées"]


def _age_cols(sex, **loc):
    return [{"metric": "headcount", "topic": "age", "characteristic": a, "sex": sex, **loc}
            for a in _AGE4]


LAYOUT = {
    "survey": "EHCVM 2018/2019", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    **_NAT,
    # Dated 2018 like every other EHCVM 2018/19 round (CIV, SEN, TCD, WAEMU);
    # the report itself labels its results "2019".
    "period": "2018", "reference_period": "2018/2019",
    "tables": [
        {   # 5.8 -- the international row: its label wraps over four lines and
            # its values sit on a line that begins with the line's own amount.
            # Read P0/P1/P2 only: the next value on that line is the WELFARE
            # indicator (the poor count is printed a line lower; taken from 5.9).
            **_cap("tableau 5.8", "seuils internationaux ppa"),
            "defaults": _INT,
            "columns": [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"}],
            "rows": [{"match": r"^5947113(?=\s+\|)"}],
        },
        {   # 5.9 -- international poor count
            **_cap("tableau 5.9", "éradiquer la pauvreté"),
            "defaults": _INT,
            "columns": [_SKIP, _SKIP, _SKIP, _SKIP, {"metric": "poor_count"}],
            "rows": [{"match": r"^pauvreté en(?=\s+\d)"}],
        },
        {   # 5.10 -- administrative regions
            **_cap("tableau 5.10", "par région administrative"),
            "exact_numbers": True, "columns": _FGT5,
            "rows": [{"match": r"^Guinée(?=\s+\d)"}]
                    + _geo_rows(_REGIONS),
        },
        {   # 5.11 -- natural regions
            **_cap("tableau 5.11", "par région naturelle"),
            "exact_numbers": True, "columns": _FGT5, "rows": _geo_rows(_NATREG),
        },
        {   # 5.12 -- milieu
            **_cap("tableau 5.12", "par zone de résidence"),
            "exact_numbers": True, "columns": _FGT5,
            "rows": [
                {"match": r"^Urbain(?=\s+\d)", "topic": "locality", **_URBAN},
                {"match": r"^Autres urbains(?=\s+\d)", "topic": "locality",
                 "locality": "other", "locality_label": "Autres urbains"},
                {"match": r"^Rural(?=\s+\d)", "topic": "locality", **_RURAL},
            ],
        },
        {   # 5.13 -- household size
            **_cap("tableau 5.13", "par taille de ménage"),
            "exact_numbers": True, "columns": _FGT5,
            "rows": label_rows("household_size", ["Une personne", "2-3 personnes",
                                                  "4-5 personnes", "6-7 personnes",
                                                  "8-10 personnes", "11 personnes ou +"]),
        },
        {   # 5.14 -- rural, by administrative and natural region
            **_cap("tableau 5.14", "en milieu rural par région administrative"),
            "exact_numbers": True, "columns": _FGT5, "defaults": _RURAL,
            "rows": _geo_rows([r for r in _REGIONS if r != "Conakry"]) + _geo_rows(_NATREG),
        },
        {   # 5.15 -- rural, by household size
            **_cap("tableau 5.15", "en milieu rural par taille de ménage"),
            "exact_numbers": True, "columns": _FGT5, "defaults": _RURAL,
            "rows": label_rows("household_size", ["Une personne", "2-3 personnes",
                                                  "4-5 personnes", "6-7 personnes",
                                                  "8-10 personnes", "11 personnes ou +"]),
        },
        {   # 5.16 -- urban, by administrative and natural region
            **_cap("tableau 5.16", "en milieu urbain par région naturelle"),
            "exact_numbers": True, "columns": _FGT5, "defaults": _URBAN,
            "rows": _geo_rows(_REGIONS) + _geo_rows(_NATREG),
        },
        {   # 5.17 -- sex of the head
            **_cap("tableau 5.17", "par sexe du chef de ménage"),
            "exact_numbers": True, "columns": _FGT5,
            "rows": [{"match": r"^Masculin(?=\s+\d)", "topic": "sex_of_head",
                      "characteristic": "Masculin", "sex": "male"},
                     {"match": r"^Féminin(?=\s+\d)", "topic": "sex_of_head",
                      "characteristic": "Féminin", "sex": "female"}],
        },
        {   # 5.18 -- age of the head (caption says "en milieu urbain"; rows are national)
            **_cap("tableau 5.18", "groupe d’âge du chef de ménage"),
            "exact_numbers": True, "columns": _FGT5,
            "rows": label_rows("age_of_head", ["Moins de 35 ans", "35-44 ans",
                                               "45-64 ans", "65 ans et +"]),
        },
        {   # 5.19 -- education of the head
            **_cap("tableau 5.19", "niveau d’instruction du chef de ménage"),
            "exact_numbers": True, "columns": _FGT5,
            "rows": label_rows("education_of_head", ["Aucun", "Primaire", "Secondaire général",
                                                     "Secondaire Prof/Techn", "Supérieur"]),
        },
        {   # 5.20 -- marital status of the head
            **_cap("tableau 5.20", "situation matrimoniale du chef de ménage"),
            "exact_numbers": True, "columns": _FGT5,
            "rows": label_rows("marital_status_of_head", ["célibataire", "Marié monogame",
                                                          "Marié polygame", "Veuf",
                                                          "Divorcé/séparé"]),
        },
        {   # 5.21 -- socio-professional category of the (employed) head
            **_cap("tableau 5.21", "catégorie socioprofessionnelle du chef"),
            "exact_numbers": True, "columns": _FGT5,
            "rows": label_rows("employment_of_head", [
                "Cadre supérieur", "Cadre moyen/agent de maitrise",
                "Ouvrier ou employé qualifié", "Ouvrier ou employé non qualifié",
                "Travailleur pour compte propre", "Patron"]) + [
                {"match": r"^apprenti rémunéré(?=\s+\d)", "topic": "employment_of_head",
                 "characteristic": "Manœuvre, aide-ménagère, Stagiaire apprenti rémunéré"},
                {"match": r"^Stagiaire ou Apprenti non rémunéré,(?=\s+\d)",
                 "topic": "employment_of_head",
                 "characteristic": "Stagiaire ou Apprenti non rémunéré"}],
        },
        {   # 5.22 -- sex of individuals
            **_cap("tableau 5.22", "selon le sexe des individus"),
            "exact_numbers": True, "columns": _FGT5,
            "rows": [{"match": r"^Masculin(?=\s+\d)", "topic": "sex",
                      "characteristic": "Masculin", "sex": "male"},
                     {"match": r"^Féminin(?=\s+\d)", "topic": "sex",
                      "characteristic": "Féminin", "sex": "female"}],
        },
        {   # 5.23 -- age of individuals
            **_cap("tableau 5.23", "selon le groupe d’âge des individus"),
            "exact_numbers": True, "columns": _FGT5,
            "rows": label_rows("age", ["Moins de 15 ans", "15-34 ans", "35-44 ans",
                                       "45-64 ans", "65 ans et +"]),
        },
        {   # 5.24 -- education of individuals (printed with decimal POINTS)
            **_cap("tableau 5.24", "selon le niveau d’instruction"),
            "start": r"^Niveau d'instruction$",
            "exact_numbers": True, "columns": _FGT5,
            "rows": label_rows("education", ["Aucun", "Primaire", "Secondaire général",
                                             "Secondaire Prof/Techn", "Superieur"]),
        },
        {   # 5.28 -- trend: the three rounds before ELEP 2012, each its own survey/line
            **_cap("tableau 5.28", "tendance de l’incidence de pauvreté"),
            "exact_numbers": True,
            "columns": [_old("EIBC 1993/1994", "1994", "1993/1994"),
                        _old("EIBEP 2002/2003", "2003", "2002/2003"),
                        _old("ELEP 2007", "2007", "2007"), _SKIP, _SKIP],
            "rows": [{"match": r"^Ensemble(?=\s+\d)"},
                     {"match": r"^Conakry(?=\s+\d)", "geography": "Conakry"},
                     {"match": r"^Urbain(?=\s+\d)", "topic": "locality", **_URBAN},
                     {"match": r"^Rural(?=\s+\d)", "topic": "locality", **_RURAL}],
        },
        {   # 5.29 -- ELEP 2012 P0 P1 P2 by region (2019 columns repeat 5.10)
            **_cap("tableau 5.29", "évolution des indicateurs de pauvreté selon la région"),
            "exact_numbers": True, "defaults": _ELEP12,
            "columns": [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"},
                        _SKIP, _SKIP, _SKIP],
            "rows": _geo_rows(_REGIONS) + [{"match": r"^Ensemble(?=\s+\d)"}],
        },
        {   # 5.30 -- ELEP 2012 urban / rural by region (Conakry prints only two cells)
            **_cap("tableau 5.30", "évolution de l’incidence de pauvreté entre 2012"),
            "exact_numbers": True, "defaults": _ELEP12,
            "columns": [{"metric": "headcount", **_URBAN}, {"metric": "headcount", **_RURAL},
                        _SKIP, _SKIP, _SKIP, _SKIP],
            "rows": _geo_rows([r for r in _REGIONS if r != "Conakry"])
                    + [{"match": r"^Ensemble(?=\s+\d)", "topic": "locality"}],
        },
    ],
}

# Tableaux 5.31 / 5.32: P0 by age group x sex x milieu / region. Each sex block
# repeats the same row labels, so each block is its own table bounded by
# start/end. The Total column is taken only where it is NEW (sex x milieu or
# sex x region); the "Total" block's Total column repeats 5.10/5.12.
_CAP31 = ("tableau 5.31", "groupe d’âge, sexe et milieu de résidence")
_CAP32 = ("tableau 5.32", "groupe d’âge, sexe et région administrative")
for _sex, _word, _start, _end in (("total", "Total", r"^Total National", r"^Masculin National"),
                                  ("male", "Masculin", r"^Masculin National", r"^Féminin National"),
                                  ("female", "Féminin", r"^Féminin National", None)):
    _tot_topic = {"topic": "sex", "characteristic": _word, "sex": _sex}
    _tot = (_SKIP if _sex == "total" else {"metric": "headcount", **_tot_topic})
    _nat_tot = _SKIP  # the national sex totals repeat 5.22
    # 5.31: National / Urbain / Rural
    LAYOUT["tables"].append({
        **_cap(*_CAP31), "start": _start, "end": _end or r"^Tableau 5\.32", "start_inclusive": True,
        "columns": _age_cols(_sex) + [_SKIP],
        "rows": [
            {"match": rf"^{_word} National(?=\s+\d)", "columns": _age_cols(_sex) + [_nat_tot]},
            {"match": r"^Urbain(?=\s+\d)", "columns": _age_cols(_sex, **_URBAN)
             + [_SKIP if _sex == "total" else {"metric": "headcount", **_tot_topic, **_URBAN}]},
            {"match": r"^Rural(?=\s+\d)", "columns": _age_cols(_sex, **_RURAL)
             + [_SKIP if _sex == "total" else {"metric": "headcount", **_tot_topic, **_RURAL}]},
        ],
    })
    # 5.32: the eight regions (the national line of each block repeats 5.31)
    LAYOUT["tables"].append({
        **_cap(*_CAP32), "start": _start, "end": _end or r"^5\.7 ", "start_inclusive": True,
        "exact_numbers": True,
        "columns": _age_cols(_sex) + [_tot],
        "rows": _geo_rows(_REGIONS),
    })

# Tableaux 5.33 / 5.34 -- EXTREME poverty (food line)
LAYOUT["tables"] += [
    {   **_cap("tableau 5.33", "extrême pauvreté selon la région administrative"),
        "defaults": _EXT, "exact_numbers": True, "columns": _FGT5,
        "rows": [{"match": r"^Total(?=\s+\d)", "columns": _FGT5[:4]}]
                + _geo_rows(_REGIONS) + _geo_rows(_NATREG),
    },
    {   **_cap("tableau 5.34", "selon le milieu et la zone de résidence"),
        "defaults": _EXT, "exact_numbers": True, "columns": _FGT5,
        "rows": [{"match": r"^Urbain(?=\s+\d)", "topic": "locality", **_URBAN},
                 {"match": r"^Rural(?=\s+\d)", "topic": "locality", **_RURAL},
                 {"match": r"^Autres urbains(?=\s+\d)", "topic": "locality",
                  "locality": "other", "locality_label": "Autres urbains"}],
    },
]


def parse(path: str) -> pd.DataFrame:
    """The shared engine's table reader over this module's geometry-built text."""
    pages = _pages(path)
    if not any(p.strip() for p in pages["full"]):
        raise ValueError(f"{path}: no extractable text")
    period, reference = LAYOUT["period"], LAYOUT["reference_period"]
    rows, misses = [], []
    for t, tbl in enumerate(LAYOUT["tables"]):
        got, matched = T._parse_table(pages, LAYOUT, tbl, period, reference)
        rows.extend(got)
        misses += [f"table[{t}].{r['match']!r}" for i, r in enumerate(tbl.get("rows", []))
                   if i not in matched]
    if misses:
        raise ValueError(f"guinea: {len(misses)} row spec(s) matched nothing: {misses[:10]}")
    return pd.DataFrame.from_records(rows)
