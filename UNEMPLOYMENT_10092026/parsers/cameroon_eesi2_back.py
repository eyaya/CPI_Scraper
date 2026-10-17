"""Cameroon -- EESI3 leaflet (primary) PLUS the EESI2 2010 main report.

The primary (EESI3 phase 1 leaflet, 2021) is read by `cameroon_pdf`. The
earlier round is INS's "Deuxième Enquête sur l'Emploi et le Secteur
Informel au Cameroun (EESI 2) -- Phase 1 : Enquête sur l'emploi, Rapport
principal" (20 March 2012, fieldwork 2010), a Wayback `id_` copy of the INS
file at statistics-cameroon.org/downloads/EESI2/ (INS's former site; the
current ins-cameroun.cm does not host it). Read here:

    Tableau 4.1  Taux d'activité au sens du BIT, personnes de 10 ans ou plus,
                 by survey region and age group        labour_force_participation_rate
    Tableau 5.1  Taux de chômage au sens du BIT, by survey region
                                                       unemployment_rate

each with nine columns [Urbain | Rural | Ensemble] x [Masculin | Féminin |
Ensemble]. "///" marks a stratum that does not exist (Douala and Yaoundé
have no rural part) and is skipped.

DEFINITIONS DIFFER BETWEEN ROUNDS. EESI2 is 13th-ICLS (activity "au sens du
BIT"), working age 10 and over; EESI3 is 19th-ICLS, 14 and over. They are
kept apart by `working_age_base` and `survey`, and are not comparable.

PUBLISHED, KEPT: Tableau 5.1 Sud-Ouest, Ensemble/Masculin 9,5 lies outside
its own urban (8,5) and rural (4,3) male rates, which an overall rate cannot
do -- probably a misprint, kept as printed and pinned in `KNOWN_ODD`.
"""
from __future__ import annotations

import re

import pandas as pd

from . import cameroon_unemployment

_SURVEY = "EESI2 -- Deuxième Enquête sur l'Emploi et le Secteur Informel (2010)"
_REGIONS = ["Douala", "Yaoundé", "Adamaoua", "Centre", "Est", "Extrême-Nord",
            "Littoral", "Nord", "Nord-Ouest", "Ouest", "Sud", "Sud-Ouest", "Ensemble"]
_AGES = {"10-14 ans": "10-14", "15-34 ans": "15-34", "35-64 ans": "35-64",
         "65 ans ou plus": "65+"}
_COLS = [(loc, lab, sex) for loc, lab in (("urban", "Urbain"), ("rural", "Rural"), ("all", "Total"))
         for sex in ("male", "female", "total")]
_TABLES = {
    "Tableau 4.1": ("labour_force_participation_rate", "strict",
                    "Taux d'activité au sens du BIT (10 ans ou plus)", True),
    "Tableau 5.1": ("unemployment_rate", "strict",
                    "Taux de chômage au sens du BIT", False),
}
KNOWN_ODD = {("Tableau 5.1", "Sud-Ouest", "male")}
_NUM = r"(?:\d+(?:,\d+)?|///)"
_LINE = re.compile(rf"^(.+?)\s+((?:{_NUM}\s+){{8}}{_NUM})\s*$")


def _page(pdf, caption: str) -> str:
    for p in pdf.pages:
        t = p.extract_text() or ""
        if re.search(re.escape(caption) + r"\s*:", t) and "Source : EESI" in t.replace("Source:", "Source :"):
            # the caption page, not the list of tables
            if "...." not in t[t.find(caption):t.find(caption) + 300]:
                return t[t.find(caption):]
    raise ValueError(f"EESI2 report: {caption} not found")


def _report(path: str) -> pd.DataFrame:
    import pdfplumber
    rows = []
    with pdfplumber.open(path) as pdf:
        for caption, (topic, definition, label, has_ages) in _TABLES.items():
            text = _page(pdf, caption)
            text = text[:text.find("Source")]
            seen = set()
            for line in text.splitlines():
                m = _LINE.match(line.strip())
                if not m:
                    continue
                name = m.group(1).strip()
                if name in _REGIONS:
                    geo, age = ("Total country" if name == "Ensemble" else name), "Total"
                elif has_ages and name in _AGES:
                    geo, age = "Total country", _AGES[name]
                else:
                    continue
                key = (geo, age)
                if key in seen:
                    continue
                seen.add(key)
                for (loc, loc_lab, sex), v in zip(_COLS, m.group(2).split()):
                    if v == "///":
                        continue
                    rows.append({
                        "survey": _SURVEY, "topic": topic, "definition": definition,
                        "series_label": label, "sex": sex, "age_group": age,
                        "education": "Total", "geography": geo, "locality": loc,
                        "locality_label": loc_lab, "working_age_base": "10+",
                        "period": "2010", "reference_period": "2010",
                        "frequency": "ad_hoc", "measure": "rate",
                        "value": float(v.replace(",", ".")), "unit": "percent",
                        "series_code": f"EESI2 {caption}",
                    })
            want = len(_REGIONS) + (len(_AGES) if has_ages else 0)
            if len(seen) != want:
                raise ValueError(f"EESI2 {caption}: read {len(seen)} rows, expected {want}")
    df = pd.DataFrame(rows)
    # Overall must lie between urban and rural, except where pinned.
    p = df.pivot_table(index=["series_code", "geography", "age_group", "sex"],
                       columns="locality", values="value")
    p = p.dropna(subset=["urban", "rural", "all"])
    bad = p[(p["all"] < p[["urban", "rural"]].min(axis=1) - 0.1) |
            (p["all"] > p[["urban", "rural"]].max(axis=1) + 0.1)]
    odd = {(c.replace("EESI2 ", ""), g, s) for c, g, a, s in bad.index}
    if odd != KNOWN_ODD:
        raise ValueError(f"EESI2: overall-outside-strata cells changed: {sorted(odd)}")
    return df


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    frames = [cameroon_unemployment.parse(path)]
    frames += [_report(p) for p in extras or []]
    return pd.concat(frames, ignore_index=True)
