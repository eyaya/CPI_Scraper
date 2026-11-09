"""Comoros -- EESIC 2013/14 phase 3 (EDMC consumption survey, INSEED), from
"Dimensions de la pauvreté et du genre aux Comores", on INSEED's NADA
catalogue (study 7, DDI-COM-EESIC-PHASE3-2013, download 62). The report was
prepared by the African Development Bank with UN Women (Remerciements, p. 2)
from INSEED's survey; it is collected because INSEED hosts it (NSO-hosted
rule, 2026-11-05). Fieldwork Nov 2013 - Jan 2014 (NADA study description):
dated 2013; the report calls the year "2014".

THREE LINES, per stratum (Tableau 7, KMF per head per year, so line_value is
blank): food ("insécurité alimentaire"), low = extreme ("seuil bas"), high =
overall ("seuil haut").

    Tableau 8   P0 by milieu, three lines.
    Tableau 9   P1 ("Déficit") by milieu, three lines. Its "Sévérité" column
                is NOT read: it exceeds the gap in every cell (food 17,4 vs
                6,9), so it is not the FGT P2 the schema means.
    Tableau 11  P0 for 2004 and 2014, food and extreme lines, by milieu and
                island. The 2004 columns (EIM 2004 on the 2004 lines of the
                PNUD 2005 report) are kept as their own survey label; of the
                2014 columns only Ngazidja (whole island) is new -- the rest
                repeat Tableaux 8 and 14. Standard errors and variations are
                not read.
    Tableaux 14, 15, 18, 20, 21  P0, population share, absolute and relative
                contribution, by stratum / sex of head / household type /
                socio-professional category / education of head. The
                "Ratio de priorité" (P0 / national P0) is not read; the
                Comores rows repeat Tableau 8. Population shares are taken
                once (under the overall line): they do not depend on the line.
    Tableau 16  P0 by age of head and by household size.
Not collected: Tableau 19 (tenure x dwelling type -- no topic), Tableaux 22+
(probit models), consumption tables 3-5.

CROSS-CHECK (verbatim): Comores P0 21,9 / 35,6 / 44,1; urbain 31,9, rural
52,2 (overall); P1 6,9 / 12,6 / 16,8; Ndzouani overall 47,9 (pop. 41,9,
contribution 20,1 / 45,5); female heads overall 45,4; 2004 extreme Comores
44,9, Ngazidja 2014 extreme 28,4; Néant food 31,3.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_NUM = r"-?\d+,\d+"
_BASE = dict(welfare_aggregate="consumption", line_type="national", frequency="ad_hoc",
             unit_of_analysis="person")
_R14 = dict(survey="EESIC 2013/14 phase 3 (rapport Dimensions de la pauvreté et du genre)",
            period="2013", reference_period="2013/14")
_R04 = dict(survey="EIM 2004 (republié, rapport Dimensions de la pauvreté et du genre)",
            period="2004", reference_period="2004")
_LINES = {
    "Insécurité alimentaire": dict(line_level="other",
                                   line_name="Seuil de pauvreté alimentaire (insécurité alimentaire, EESIC 2013/14)"),
    "Pauvreté extrême": dict(line_level="extreme", line_name="Seuil de pauvreté global bas (extrême, EESIC 2013/14)"),
    "Pauvreté globale": dict(line_level="overall", line_name="Seuil de pauvreté global haut (EESIC 2013/14)"),
}
_LINES04 = {
    "food": dict(line_level="other", line_name="Seuil de pauvreté alimentaire 2004 (rapport PNUD 2005)"),
    "ext": dict(line_level="extreme", line_name="Seuil de pauvreté extrême 2004 (rapport PNUD 2005)"),
}
LAYOUT = {**_BASE, **_R14, **_LINES["Pauvreté globale"], "tables": []}

_MILIEU = {"Urbain": dict(topic="locality", characteristic="Urbain", locality="urban", locality_label="Urbain"),
           "Rural": dict(topic="locality", characteristic="Rural", locality="rural", locality_label="Rural"),
           "Comores": {}}
_STRATA = {"Moroni": dict(geography="Ngazidja - Moroni"),
           "Reste de Ngazidja": dict(geography="Ngazidja - Reste de Ngazidja"),
           "Ndzouani": dict(geography="Ndzuwani"), "Mwali": dict(geography="Mwali")}
_ISLANDS = {"Ngazidja": dict(geography="Ngazidja"), "Ndzouani": dict(geography="Ndzuwani"),
            "Mwali": dict(geography="Mwali")}


def _lines_after(pages: list[str], caption: str, n: int = 45) -> list[str]:
    for t in pages:
        i = t.find(caption)
        if i >= 0:
            return t[i:].split("\n")[1:n + 1]
    raise ValueError(f"{caption!r} not found")


def _row(metric, value, line, rnd=_R14, **attrs):
    unit = "percentage_points" if metric == "absolute_contribution" else "percent"
    return C.row(metric=metric, value=C.to_number(value, ","), unit=unit, **_BASE, **rnd, **line, **attrs)


def _by_line(pages, caption, labels: dict, out, ncols=5):
    """Tableaux 14/15/18/20/21: blocks per line, rows 'Label P0 pop abs rel ratio'."""
    block, seen = None, 0
    for s in _lines_after(pages, caption):
        s = s.strip()
        if s in _LINES:
            block = s
            continue
        m = re.fullmatch(r"(.+?) ((?:%s ?){%d})" % (_NUM, ncols), s)
        if not block or not m or m.group(1) not in labels:
            continue
        p0, pop, ab, rel, _ratio = re.findall(_NUM, m.group(2))
        a = labels[m.group(1)]
        out.append(_row("headcount", p0, _LINES[block], **a))
        out.append(_row("absolute_contribution", ab, _LINES[block], **a))
        out.append(_row("poor_share", rel, _LINES[block], **a))
        if block == "Pauvreté globale":
            out.append(_row("population_share", pop, _LINES[block], **a))
        seen += 1
    if seen != 3 * len(labels):
        raise ValueError(f"{caption}: {seen} rows, expected {3 * len(labels)}")


def parse(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        pages = [p.crop((0, 0, p.width, p.height)).extract_text() or "" for p in pdf.pages]
    out: list[dict] = []
    lines = list(_LINES.values())

    # Tableau 8 (P0) and 9 (P1 = the "Déficit" columns).
    for cap, metric, pick in (("Tableau 8. Incidence de pauvreté selon le milieu", "headcount", (0, 1, 2)),
                              ("Tableau 9. Intensité et sévérité", "gap", (0, 2, 4))):
        got = 0
        for s in _lines_after(pages, cap, 8):
            m = re.fullmatch(r"(Urbain|Rural|Comores) (.+)", s.strip())
            if not m:
                continue
            v = re.findall(_NUM, m.group(2))
            for line, j in zip(lines, pick):
                out.append(_row(metric, v[j], line, **_MILIEU[m.group(1)]))
            got += 1
        if got != 3:
            raise ValueError(f"{cap}: {got} rows")

    # Tableau 11: 'Label food04 food14 ext04 ext14' (variation lines skipped).
    got = 0
    for s in _lines_after(pages, "Tableau 11. Variation de l", 30):
        m = re.fullmatch(r"(Urbain|Rural|Ngazidja|Ndzouani|Mwali|Comores) ((?:%s ?){4})" % _NUM, s.strip())
        if not m:
            continue
        f04, f14, e04, e14 = re.findall(_NUM, m.group(2))
        a = _MILIEU.get(m.group(1)) if m.group(1) in _MILIEU else _ISLANDS[m.group(1)]
        out.append(_row("headcount", f04, _LINES04["food"], _R04, **a))
        out.append(_row("headcount", e04, _LINES04["ext"], _R04, **a))
        if m.group(1) == "Ngazidja":
            out.append(_row("headcount", f14, _LINES["Insécurité alimentaire"], **a))
            out.append(_row("headcount", e14, _LINES["Pauvreté extrême"], **a))
        got += 1
    if got != 6:
        raise ValueError(f"Tableau 11: {got} rows")

    _by_line(pages, "Tableau 14. Décomposition", _STRATA, out)
    _by_line(pages, "Tableau 15. Décomposition", {
        "Homme": dict(topic="sex_of_head", characteristic="Homme", sex="male"),
        "Femme": dict(topic="sex_of_head", characteristic="Femme", sex="female")}, out)
    _by_line(pages, "Tableau 18. Décomposition", {
        k: dict(topic="household_type", characteristic=k)
        for k in ("Couple sans enfants", "Couple avec enfants", "Monoparentale", "Famille élargie")}, out)
    _by_line(pages, "Tableau 20. Décomposition", {
        k: dict(topic="employment_of_head", characteristic=k)
        for k in ("Cadre sup./ moyen", "Employé/ouvrier", "Manœuvre/Stagiaire", "Autonome/Employeur",
                  "Autre travail", "Chômage BIT", "Chômage découragé", "Inactif ou retraite")}, out)
    _by_line(pages, "Tableau 21. Décomposition", {
        k: dict(topic="education_of_head", characteristic=k)
        for k in ("Néant", "Primaire", "Secondaire cycle 1", "Secondaire cycle 2", "Supérieur")}, out)

    # Tableau 16: 'Age P0 ratio P0 ratio Size' -- age of head left, size right.
    block, got = None, 0
    for s in _lines_after(pages, "Tableau 16. Décomposition", 25):
        s = s.strip()
        if s in _LINES:
            block = s
            continue
        m = re.fullmatch(r"(.+? ans(?: ou (?:moins|plus))?) (%s) %s (%s) %s (.+)" % (_NUM, _NUM, _NUM, _NUM), s)
        if not block or not m:
            continue
        out.append(_row("headcount", m.group(2), _LINES[block], topic="age_of_head",
                        characteristic=m.group(1)))
        out.append(_row("headcount", m.group(3), _LINES[block], topic="household_size",
                        characteristic=m.group(4)))
        got += 1
    if got != 15:
        raise ValueError(f"Tableau 16: {got} rows")
    return pd.DataFrame(out)
