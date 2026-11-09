"""Cameroon -- monetary poverty (INS, ECAM).

THREE INS FILES, all from ins-cameroun.cm (WordPress media API):

1. PRIMARY: "Fifth Cameroon Household Survey (ECAM5) -- Situation of household
   living conditions in 2021-2022, policy guidance note" (Jan 2024, English).
   Figure 4 prints P0 for the 12 SURVEY REGIONS (10 regions, with Douala and
   Yaoundé split from Littoral and Centre) as TEXT DATA LABELS, each name on
   the same line as its value ("Littoral (Excluding Douala) 23.8") -- published
   figures, the Burkina Faso rule (labour README). Line: 296 691 FCFA per
   person per year (813 FCFA a day), NEW methodology aligned with EHCVM --
   INS states ECAM5 is NOT comparable with ECAM1-4 or the 2021 test survey.
2. EXTRA "Page-ODD-ECAM5-Fr.pdf": the SDG 1.2.1 row, P0 2022 by milieu and SEX
   OF THE PERSON (Urbain 21,6 Rural 56,3 M 37,3 F 38,0 Total 37,7). Persons,
   not heads: the brochure gives male-/female-HEADED 39,0 / 33,5.
3. EXTRA "Evolution de la pauvreté au Cameroun entre 1996 et 2001" (ECAM I /
   ECAM II harmonised): Tableaux 2.3-2.6, P0/P1/P2 1996 and 2001 by milieu,
   six strata, sex and activity status of the head. Values are the
   HARMONISED re-estimates (P0 1996 53,3 -- the report's scenario 1; the
   independently computed figure is 50,5%), so `survey` says so.

Tables 2.3-2.6 stack the three measures as blocks, each ending on its
"Cameroun" row, with the metric name printed on the MIDDLE row of a block
("Incidence (P0) Rural 59,6 ...") -- read by `_metric_blocks` below rather
than by the engine, which matches each row label only once per table.

Not collected: 2021 test survey (old method; its figures are only in a garbled
two-language chart and in prose), the brochure's sex-of-head and literacy
charts (values are not ordered with their labels in the text layer), Gini and
quintile ratios (inequality), ECAM4 thematic notes (no P0 tables).
"""
from __future__ import annotations
import os
import re

import pandas as pd

from . import _common as C
from . import poverty_tables as T

_REG = [("Far-North", r"(?<![\w-])Far-North"), ("Nort-West", r"(?<![\w-])Nort-West"),
        ("North", r"(?<![\w-])North"), ("Adamawa", r"(?<![\w-])Adamawa"),
        ("East", r"(?<![\w-])East"), ("West", r"(?<![\w-])West"),
        ("Littoral (Excluding Douala)", r"Littoral \(Excluding Douala\)"),
        ("South-West", r"(?<![\w-])South-West"),
        ("Centre (Excluding Yaounde)", r"Centre \(Excluding Yaounde\)"),
        ("South", r"(?<![\w-])South"), ("Yaounde", r"(?<![\w-])Yaounde"),
        ("Douala", r"(?<![\w-])Douala")]

_E5 = {"survey": "ECAM5 2022", "period": "2022", "reference_period": "2022",
       "line_name": "Seuil de pauvreté ECAM5 2022", "line_value": 296691,
       "line_unit": "XAF per person per year"}

LAYOUT = {
    "survey": "ECAM5 2022", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "ad_hoc", "decimal": ".",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil de pauvreté ECAM5 2022", "line_value": 296691,
    "line_unit": "XAF per person per year",
    "period": "2022", "reference_period": "2022",
    "tables": [
        {   # Figure 4 -- P0 by survey region, text data labels
            "page_contains": ["figure 4", "income poverty rate (%) by area"],
            "exact_numbers": True,
            "columns": [{"metric": "headcount"}],
            "rows": [{"match": pat + r"(?=\s+\d+\.\d$)", "geography": name}
                     for name, pat in _REG],
        },
    ],
}

# ODD page: Urbain | Rural | M | F | Total (comma decimals).
_ODD = {**{k: v for k, v in LAYOUT.items() if k != "tables"}, "decimal": ",",
        "tables": [{
            "page_contains": ["incidence de pauvreté monétaire"],
            "exact_numbers": True,
            "columns": [
                {"metric": "headcount", "topic": "locality", "locality": "urban", "locality_label": "Urbain"},
                {"metric": "headcount", "topic": "locality", "locality": "rural", "locality_label": "Rural"},
                {"metric": "headcount", "topic": "sex", "characteristic": "M", "sex": "male"},
                {"metric": "headcount", "topic": "sex", "characteristic": "F", "sex": "female"},
                {"metric": "headcount"}],
            "rows": [{"match": r"^1\.2\.1 Incidence de pauvreté monétaire"}],
        }]}

_E12 = dict(welfare_aggregate="consumption", unit_of_analysis="person",
            line_type="national", line_level="overall",
            line_name="Seuil de pauvreté ECAM I/II (harmonisé)",
            frequency="ad_hoc")
_YEARS = (("1996", "ECAM I 1996 (harmonisé avec ECAM II)"),
          ("2001", "ECAM II 2001 (harmonisé avec ECAM I)"))
_METRICS = ("headcount", "gap", "severity")
_MARK = re.compile(r"^(?:Incidence \(P0\)|Intensité \(P1\)|Sévérité \(P2\))\s*")

# (caption, topic, {printed label: row attrs}); "Cameroun" ends each block.
_T12 = [
    ("Tableau 2.3", "locality", {
        "Urbain": {"locality": "urban", "locality_label": "Urbain"},
        "Rural": {"locality": "rural", "locality_label": "Rural"}}),
    ("Tableau 2.4", "locality", {
        "Yaoundé": {"locality": "other", "locality_label": "Yaoundé"},
        "Douala": {"locality": "other", "locality_label": "Douala"},
        "Autres villes": {"locality": "other", "locality_label": "Autres villes"},
        "Rurale Forêt": {"locality": "other", "locality_label": "Rurale Forêt"},
        "Rurale Hauts plateaux": {"locality": "other", "locality_label": "Rurale Hauts plateaux"},
        "Rurale Savane": {"locality": "other", "locality_label": "Rurale Savane"}}),
    ("Tableau 2.5", "sex_of_head", {
        "Masculin": {"sex": "male"}, "Féminin": {"sex": "female"}}),
    ("Tableau 2.6", "employment_of_head", {
        "Actifs Occupés": {}, "Chômeurs": {}, "Inactifs": {}}),
]


def _metric_blocks(text: str, caption: str, topic: str, labels: dict) -> list[dict]:
    """Read one stacked P0/P1/P2 table: three blocks, each closed by its
    'Cameroun' row. Every label must be found in every block, or nothing is
    returned for that table and the caller raises."""
    if caption not in text:
        return []
    body = text[text.index(caption):]
    body = body[:body.index("Sources")] if "Sources" in body else body
    rows, block, seen = [], 0, set()
    for raw in body.splitlines()[1:]:
        line = _MARK.sub("", raw.strip())
        if block >= 3:
            break
        hit = None
        for lab in list(labels) + ["Cameroun"]:
            if re.match(re.escape(lab) + r"\s+\d", line):
                hit = lab
                break
        if not hit:
            continue
        nums = C.numbers_in(line[len(hit):], decimal=",")
        if len(nums) < 2:
            continue
        if hit != "Cameroun":
            for (period, survey), v in zip(_YEARS, nums[:2]):
                rows.append(C.row(metric=_METRICS[block], value=v, survey=survey,
                                  period=period, reference_period=period,
                                  topic=topic, characteristic=hit,
                                  **{**_E12, **labels[hit]}))
            seen.add((block, hit))
        elif caption == "Tableau 2.3":   # the national rows, once
            for (period, survey), v in zip(_YEARS, nums[:2]):
                rows.append(C.row(metric=_METRICS[block], value=v, survey=survey,
                                  period=period, reference_period=period, **_E12))
        if hit == "Cameroun":
            block += 1
    want = {(b, lab) for b in range(3) for lab in labels}
    if seen != want:
        raise ValueError(f"{caption}: read {len(seen)} of {len(want)} cells "
                         f"(missing {sorted(want - seen)[:4]}) -- re-read the report")
    return rows


def _pdf_text(path: str) -> str:
    return "\n".join(T._pages(path, halves=False)["full"])


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    frames = [T.make_parser(LAYOUT)(path)]
    for ex in extras or []:
        name = os.path.basename(ex)
        if name.startswith("Page-ODD-ECAM5"):
            frames.append(T.make_parser(_ODD)(ex))
        elif name.startswith("ECAM-I-and-ECAM-II"):
            text = _pdf_text(ex)
            rows = []
            for caption, topic, labels in _T12:
                got = _metric_blocks(text, caption, topic, labels)
                if not got:
                    raise ValueError(f"{name}: {caption} not found")
                rows += got
            frames.append(pd.DataFrame(rows))
    return pd.concat(frames, ignore_index=True)
