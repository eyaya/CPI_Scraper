"""Burkina Faso -- INSD, "Profil de pauvreté et d'inégalités en 2014 au
Burkina Faso" (Enquête Multisectorielle Continue, EMC 2014), Wayback `id_`
copy of insd.bf/contenu/enquetes_recensements/Enq_EMC/.

Line 153 530 FCFA per person per year; consumption per person. Three
measures, as INSD defines them: "pauvreté monétaire" (overall), "extrême
pauvreté" (total consumption below the food line) and "pauvreté alimentaire"
(food consumption below the food line, line_level other).

Every table prints P0 | CTR | P1 | CTR | P2 | CTR. Collected: 2-1 (national,
the three measures), 2-2 / 2-3 / 2-4 (milieu), 2-5 / 2-6 / 2-7 (13 regions),
3-1 sex, 3-2 age, 3-3 household size, 3-4 marital status, 4-1 literacy, 4-2
education, 6-1 socio-professional category, 6-2 branch, 6-3 activity status,
6-4 type of employment (all of the head). Tables run over page breaks without
repeating their caption (2-2, 2-4, 3-4), so each table is read from its
caption to its "Source" line across the joined document. Labels wrap
("Boucle du / 59,7 ... / Mouhoun") and are re-joined.
Not collected: Ensemble rows of the characteristic tables (repeat 2-1); 6-3's
Ensemble prints P0 40,2 against 40,1 everywhere else.

CROSS-CHECK (verbatim): 40,1 / 9,7 / 3,3; food 57,7; extreme 11,1; rural
47,5, urban 13,7; Nord 70,4; Sahel 20,6; female head 30,4; 12+ persons 60,0;
Aucun niveau 45,3.
"""
from __future__ import annotations
import re

import pandas as pd

from . import poverty_tables as T

_SIX = [{"metric": "headcount"}, {"metric": "poor_share"}, {"metric": "gap"},
        {"metric": "gap_contribution"}, {"metric": "severity"},
        {"metric": "severity_contribution"}]
_EXT = {"line_level": "extreme", "line_name": "Seuil alimentaire (extrême pauvreté, EMC)"}
_FOOD = {"line_level": "other",
         "line_name": "Seuil alimentaire, consommation alimentaire (pauvreté alimentaire, EMC)"}

LAYOUT = {
    "survey": "EMC 2014", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ",",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil de pauvreté (EMC)", "line_value": 153530,
    "line_unit": "XOF per person per year", "period": "2014", "reference_period": "2014",
    "tables": [],
}

_MILIEU = [{"match": r"^Urbain(?=\s)", "topic": "locality", "locality": "urban", "locality_label": "Urbain"},
           {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural"},
           {"match": r"^National(?=\s)"}]


def _scan(topic, attr="characteristic", n=8, **kw):
    # The label is everything before the first decimal number, so labels that
    # begin with digits ("15 à 24 ans", "12 personnes et +") are kept whole.
    return {"row_scan": {"attr": attr, "expect_rows": n, "label": r"^(.{2,70}?)\s+(?=\d+,\d)",
                         "label_ok": r"^\S.*$",
                         "exclude_labels": ["Ensemble", "Burkina Faso"],
                         # one spelling per region across INSD's rounds
                         "label_map": {"Plateau Central": "Plateau-Central"},
                         "defaults": {"topic": topic} if topic else {}}, **kw}


def _specs():
    S = [
        (r"Tableau 2-1:", {"columns": [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"}],
                           "rows": [{"match": r"^Pauvreté monétaire(?=\s)"},
                                    {"match": r"^Pauvreté alimentaire(?=\s)", **_FOOD},
                                    {"match": r"^Extrême pauvreté(?=\s)", **_EXT}]}),
        (r"Tableau 2-2:", {"rows": _MILIEU[:2]}),
        (r"Tableau 2-3:", {"rows": _MILIEU[:2], "defaults": _FOOD}),
        (r"Tableau 2-4:", {"rows": _MILIEU[:2], "defaults": _EXT}),
        (r"Tableau 2-5:", _scan(None, "geography", 13)),
        (r"Tableau 2-6:", dict(_scan(None, "geography", 13), defaults=_FOOD)),
        (r"Tableau 2-7:", dict(_scan(None, "geography", 13), defaults=_EXT)),
        (r"Tableau 3-1:", {"rows": [
            {"match": r"^Homme(?=\s)", "topic": "sex_of_head", "characteristic": "Homme", "sex": "male"},
            {"match": r"^Femme(?=\s)", "topic": "sex_of_head", "characteristic": "Femme", "sex": "female"}]}),
        (r"Tableau 3-2:", _scan("age_of_head", n=6)),
        (r"Tableau 3-3:", _scan("household_size", n=6)),
        (r"Tableau 3-4:", _scan("marital_status_of_head", n=3)),
        (r"Tableau 4-1:", _scan("literacy_of_head", n=2)),
        (r"Tableau 4-2:", _scan("education_of_head", n=5)),
        (r"Tableau 6-1:", _scan("employment_of_head", n=10, _prefix="Catégorie socioprofessionnelle")),
        (r"Tableau 6-2:", _scan("employment_of_head", n=15, _prefix="Branche d'activité")),
        (r"Tableau 6-3:", _scan("employment_of_head", n=3, _prefix="Statut d'activité")),
        (r"Tableau 6-4:", _scan("employment_of_head", n=4, _prefix="Type d'emploi")),
    ]
    return S


_NOISE = re.compile(r"^(?:Profil de pauvreté et d.inégalités ?en ?2014 ?au Burkina Faso|"
                    r"Résultats de l.Enquête ?multisectorielle ?continue ?\(EMC\) ?en 2014|\d{1,3})\s*$")


def _doc(pages: list[str]) -> str:
    keep = []
    for t in pages:
        if "...." in t:          # table of contents / list of tables
            continue
        keep += [l for l in t.splitlines() if not _NOISE.match(l.strip())]
    return "\n".join(keep)


def _table(doc: str, caption: str) -> list[str]:
    m = None
    for m in re.finditer(r"^" + re.escape(caption).replace(r"\ ", r"\s?"), doc, re.M):
        pass                     # the LAST occurrence: the text sometimes cites a caption earlier
    if not m:
        return []
    body = doc[m.end():]
    body = body[body.index("\n") + 1:] if "\n" in body else body
    k = re.search(r"^(?:Source|Tableau\s?\d|Graphique\s?\d)", body, re.M)
    return [body[:k.start()] if k else body]


def parse(path: str) -> pd.DataFrame:
    doc = _doc(T._pages(path, halves=False)["full"])
    rows: list[dict] = []
    for cap, spec in _specs():
        tbl = {"columns": _SIX, "join_wrapped_labels": True, "exact_numbers": True, **spec}
        prefix = tbl.pop("_prefix", None)
        got, matched = T._parse_table({"full": _table(doc, cap)}, LAYOUT, tbl, "2014", "2014")
        if "rows" in tbl and len(matched) != len(tbl["rows"]):
            raise ValueError(f"EMC 2014 {cap}: matched {sorted(matched)} of {len(tbl['rows'])} rows")
        if prefix:
            for r in got:
                r["characteristic"] = f"{prefix}: {r['characteristic']}"
        rows.extend(got)
    return pd.DataFrame.from_records(rows)
