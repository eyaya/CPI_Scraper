"""Tunisia — INS theme pages, employment by branch of economic activity.

Read by `html_wide_labour.make_parser`. The source is the SAME set of
server-rendered theme pages `unemployment` collects, and this indicator takes
the one table there that is composition rather than headline status:

    /statistiques/152   "Répartition de la population active occupée
                         selon le secteur d'activité"   (dataset 1786304631)

The `unemployment` descriptor lists that table under "ALSO PUBLISHED, not yet
captured". This is the entry that captures it, and no figure is written twice:
`unemployment` takes the population active / occupée / chômage totals by SEX,
this takes the employed broken down by ACTIVITY.

"SECTEUR D'ACTIVITÉ" IS A BRANCH OF ACTIVITY, SO THE TOPIC IS `industry`, NOT
`sector`. The distinction matters because both words are "sector" in English
and the schema uses `sector` for the INSTITUTIONAL sector -- public
administration, public enterprises, private -- which is what HCP Morocco's
"secteurs d'emploi" table publishes. INS's five groups (Agriculture et pêche,
Industries manufacturières, Industries non manufacturières, Services, Non
déclarés) are branches of the economy, which is `industry`. Filing them as
`sector` would put them under the same topic as Morocco's public/private split
while measuring something else entirely.

NO NOMENCLATURE IS NAMED. Neither the page nor the table cites NAT, CITI or
ISIC, and the five groups are INS's own broad aggregation rather than any
international standard's sections, so `National` -- the same call as Botswana,
Tanzania and Morocco. Recording ISIC here because "Industries manufacturières"
resembles a section would be inference published as fact.

THE VALUES ARE IN THOUSANDS, though the page's own unit line says "Unité :
Nombre". That is not a guess: INS's quarterly note gives 3 568,1 mille employed
for Q2 2026, and this table's 2026-Q2 total is 3568.1. Emitted as
`thousand_persons` rather than multiplied out, because multiplying would be
recomputation.

THE TOTAL ROW IS LABELLED WITH THE TABLE'S OWN TITLE -- INS repeats
"Répartition de la population active occupée selon le secteur d'activité" as
the label of the row carrying the overall figure, rather than writing "Total".
It is a real published figure, so it is kept and relabelled, not dropped.

ROLLING WINDOW, and the reason merge-on-write matters here: only about nine
quarters are rendered at a time, and the window is NOT the same across INS's
three pages -- 2024-Q4 is absent from THIS table while present on /151. Each
run writes every quarter it can see and history accumulates; a run that
replaced the file would throw away the older quarters permanently, since INS
does not republish them.

CROSS-CHECK (2026-Q2, en milliers): total 3568,1; Agriculture et pêche 581,6;
Industries manufacturières 730,3; Industries non manufacturières 477,4;
Services 1778,8. And 2024-Q1: total 3476,0; Agriculture et pêche 533,0;
Services 1828,4. "Non déclarés" prints "--" in 2025-Q1, 2025-Q2, 2025-Q3 and
2026-Q2 -- a missing cell, never a zero.
"""
from __future__ import annotations

from .html_wide_labour import make_parser

LAYOUT = {
    "survey": "Enquête nationale sur l'emploi — Indicateurs de l'emploi et "
              "du chômage",
    "frequency": "quarterly",
    # INS surveys the population aged 15 and over, as `unemployment` records.
    "working_age_base": "15+",
    # The HTML tables print a POINT decimal ("3568.1"), unlike INS's PDFs.
    "decimal": ".",
    "tables": [
        {
            # Anchored on the full printed title: the page also carries
            # "Evolution de la population active occupée selon le sexe" and
            # "Evolution des créations d'emploi selon le sexe", both of which
            # belong to `unemployment`, and its navigation mentions
            # "groupement sectoriel d'activité" in an unrelated trade series.
            "caption": r"R[ée]partition de la population active occup[ée]e"
                       r"\s+selon le secteur d.activit",
            "topic": "industry",
            "classification": "National",
            "measure": "count",
            "unit": "thousand_persons",
            "relabel": [[r"^R[ée]partition de la population active occup",
                         "Total"]],
            # Total + Agriculture et pêche + Industries manufacturières +
            # Industries non manufacturières + Services + Non déclarés.
            "expect_rows": 6,
            "series_code": "INS secteur d'activité",
        },
    ],
}

parse = make_parser(LAYOUT)
