"""Comoros -- EIM 2004 and EBC 1995 (Ministère du Plan / Direction de la
Statistique, now INSEED), from "Enquête intégrale auprès des ménages 2004 --
Eléments d'analyse" (J.-P. Lachaud, janvier 2005), the "Principaux résultats"
volume of the EIM study on INSEED's NADA catalogue (study 3, download 24).
The cover of the companion "Rapport principal" (download 23) carries the
Ministère du Plan et de l'Aménagement du Territoire and UNDP.

EVERY MEASURE IS PRINTED AS A FRACTION -- its own footnote: "Toutes les
mesures de la pauvreté n'ont pas été multipliées par 100" -- so every value
here carries unit "index" and is kept as printed (value_std puts it on the
percent scale). Line: 285 144 FC per person per year (2004); 170 337 (1995).

    Tableau 3   households: P0, contribution, P1, contribution, P2,
                contribution; persons: P0 -- by island and island x milieu.
    Tableau 4   the same by labour-market status of the head (heads 14+;
                its Ensemble, 0,373, covers only the heads with a status).
    Tableau 5   P0 and contribution for households and persons, 1995 (EBC
                1995) and 2004. Only the 1995 columns and the 2004 PERSON
                contributions are read: the other 2004 columns repeat T3.
    Tableau 44  T3 + T4 again, separately for male- and female-headed
                households ("Hommes" / "Femmes"). Its "Pour mémoire" row
                repeats T3's national row and is skipped; "Pêcheur & divers"
                (women) prints dashes.
Not collected: standard errors (in brackets under each row), consumption per
head and weighted N (not poverty measures), Tableaux 6-8 (vulnerability,
chronic / transient poverty) and 35-37 (elasticities, decompositions).

CROSS-CHECK (verbatim): Ensemble households 0,369 / 0,128 / 0,062, persons
0,448; Ndzouani rural 0,435; 1995 Ensemble households 0,473, persons 0,546;
Ndzouani 1995 0,608; male heads 0,386, female heads 0,304.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_FR = re.compile(r"\d,\d{3}")
_HH_COLS = ["headcount", "poor_share", "gap", "gap_contribution", "severity", "severity_contribution"]
_BASE = dict(welfare_aggregate="consumption", line_type="national", line_level="overall",
             frequency="ad_hoc", unit="index")
_R04 = dict(survey="EIM 2004", period="2004", reference_period="2004",
            line_name="Seuil national de pauvreté (EIM 2004)", line_value=285144,
            line_unit="KMF per person per year")
_R95 = dict(survey="EBC 1995", period="1995", reference_period="1995",
            line_name="Seuil national de pauvreté (EBC 1995)", line_value=170337,
            line_unit="KMF per person per year")

# Printed place -> (geography, locality, locality_label). Island names follow
# comoros_poverty (EHCVM 2024): Ndzouani -> Ndzuwani.
_PLACES = {
    "Ngazidja": ("Ngazidja", "all", "Total"),
    "Moroni": ("Ngazidja - Moroni", "all", "Total"),
    "Ngazidja urbain secondaire": ("Ngazidja", "urban", "Urbain secondaire"),
    "Ngazidja rural": ("Ngazidja", "rural", "Rural"),
    "Ndzouani": ("Ndzuwani", "all", "Total"),
    "Ndzouani urbain": ("Ndzuwani", "urban", "Urbain"),
    "Ndzouani rural": ("Ndzuwani", "rural", "Rural"),
    "Mwali": ("Mwali", "all", "Total"),
    "Mwali urbain": ("Mwali", "urban", "Urbain"),
    "Mwali rural": ("Mwali", "rural", "Rural"),
}
_STATUS = ["Salarié protégé", "Salarié non protégé", "Micro-entrepreneur", "Indépendant informel",
           "Agriculteur céréales & autres", "Agriculteur fruits, légumes & divers",
           "Eleveur & divers", "Pêcheur & divers", "Apprenti & aide familial", "Chômeur", "Inactif"]


def _page(pdf, caption: str) -> list[str]:
    for pg in pdf.pages:
        t = pg.extract_text() or ""
        if caption in t:
            return t.split("\n")
    raise ValueError(f"{caption!r} not found")


def _split(line: str):
    """(label, fractions) for a data line 'Label 0,353 0,460 ... 661,3 1433'."""
    m = _FR.search(line)
    if not m or line[max(0, m.start() - 1):m.start()] == "(":  # a standard-error line
        return line.strip(), []
    return line[:m.start()].strip(), _FR.findall(line)


def _attrs(label: str, sex: str | None):
    """Row attributes for a printed label, crossed with sex of head if given."""
    if label in _PLACES:
        geo, loc, lab = _PLACES[label]
        if sex:
            a = dict(topic="sex_of_head", characteristic={"male": "Hommes", "female": "Femmes"}[sex], sex=sex)
        elif loc != "all":
            a = dict(topic="locality", characteristic=lab)
        else:
            a = {}
        return dict(a, geography=geo, locality=loc, locality_label=lab)
    if label in _STATUS:
        a = dict(topic="employment_of_head", characteristic=label)
        return dict(a, sex=sex) if sex else a
    if label == "Ensemble":
        if sex:
            return dict(topic="sex_of_head", characteristic={"male": "Hommes", "female": "Femmes"}[sex], sex=sex)
        return {}
    return None


def _fgt_rows(lines, out, sex_blocks=False, ensemble_attrs=None):
    sex = None
    for line in lines:
        s = line.strip()
        if sex_blocks and s in ("Hommes", "Femmes"):
            sex = {"Hommes": "male", "Femmes": "female"}[s]
            continue
        label, fr = _split(s)
        if len(fr) < 7 or label.startswith(("Pour m", "(")):  # "(" = standard errors
            continue
        if label == "Ensemble" and ensemble_attrs is not None and not sex_blocks:
            attrs = ensemble_attrs
        else:
            attrs = _attrs(label, sex)
        if attrs is None:
            raise ValueError(f"unknown row label {label!r}")
        for metric, v in zip(_HH_COLS, fr[:6]):
            out.append(C.row(metric=metric, value=C.to_number(v, ","), unit_of_analysis="household",
                             **_BASE, **_R04, **attrs))
        out.append(C.row(metric="headcount", value=C.to_number(fr[6], ","), unit_of_analysis="person",
                         **_BASE, **_R04, **attrs))


def parse(path: str) -> pd.DataFrame:
    out: list[dict] = []
    with pdfplumber.open(path) as pdf:
        _fgt_rows(_page(pdf, "Tableau 3 : Mesures de la pauvret"), out)
        _fgt_rows(_page(pdf, "Tableau 4 : Mesures de la pauvret"), out,
                  ensemble_attrs=dict(topic="employment_of_head",
                                      characteristic="Ensemble (chefs au statut renseigné)"))
        _fgt_rows(_page(pdf, "Tableau 44 : Mesures de la pauvret"), out, sex_blocks=True)
        # Tableau 5: the label sits before the numbers or on the line below
        # (before the bracketed standard errors), or is split across both.
        lines = _page(pdf, "Tableau 5 : Evolution de l")
        n5 = 0
        for i, line in enumerate(lines):
            pre, fr = _split(line)
            if len(fr) < 8 or pre.startswith(("Statistique", "(")):
                continue
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            label = re.sub(r"\s+", " ", (pre + " " + nxt.split("(")[0]).strip())
            attrs = _attrs(label, None)
            if attrs is None:
                raise ValueError(f"Tableau 5: unknown row label {label!r}")
            hh0, hhc, p0, pc, _, _, _, pc04 = (C.to_number(x, ",") for x in fr[:8])
            for metric, v, unit in (("headcount", hh0, "household"), ("poor_share", hhc, "household"),
                                    ("headcount", p0, "person"), ("poor_share", pc, "person")):
                out.append(C.row(metric=metric, value=v, unit_of_analysis=unit, **_BASE, **_R95, **attrs))
            out.append(C.row(metric="poor_share", value=pc04, unit_of_analysis="person",
                             **_BASE, **_R04, **attrs))
            n5 += 1
        if n5 != 11:
            raise ValueError(f"Tableau 5: expected 11 rows, got {n5}")
    return pd.DataFrame(out)


LAYOUT = {**_BASE, **_R04, "unit_of_analysis": "household", "tables": []}
