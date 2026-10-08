"""Burkina Faso — INSD ENB-ESI 2023, employment by branch of activity.

Read by `pdf_tables_labour.make_parser`. The source is the SAME note the
`unemployment` indicator collects (Tableau 2 there, Figure 4 here).

THE ONE COLLECTABLE COMPOSITION CUT IN THIS NOTE IS "FIGURE 4", and it is worth
being explicit about why reading it is legitimate when Zimbabwe's charts are
refused. ZIMSTAT's figures carry NO category values anywhere in the PDF -- the
text layer under them holds a caption and the sex totals, and the only way to
get a number would be to measure the rendered bars, which invents precision the
NSO never published. INSD's Figure 4 is the opposite case: every category and
its value are PRINTED AS TEXT in the document, as data labels --

    Agriculture, sylviculture, pêche 31,4
    Commerce 24,4
    Activités de fabrication 16,4
    ...
    Activités spécialisées, scientifiques et techniques 0,6

-- so this is reading published figures that exist in the file, not recovering
them from a picture. The corroboration is the report's own arithmetic: the
sixteen shares sum to 99,9, a complete distribution, and the three largest
match the narrative on the preceding page ("cette branche représente 31,4% de
l'emploi total des 16 ans ou plus, suivie par le commerce ... 24,4% ... La part
des activités de fabrication représente 16,4%").

THE AXIS IS NOT A CATEGORY. The block ends with the chart's x-axis ticks,
"0 5 10 15 20 25 30 35", which is a perfectly plausible-looking line of
numbers. It is skipped because it carries EIGHT values where the layout expects
one, not because it is named -- the same reason prose lines quoting two figures
are skipped. `expect_rows` is what makes that safe.

WHAT IS DELIBERATELY LEFT HERE:

* TABLEAU 5, "Répartition de la main d'œuvre des UPI par secteur d'activité et
  branche d'activité". This is the INFORMAL-SECTOR module (phase 2), sampled
  through unités de production informelles, and its shares are of INFORMAL
  employment only: it puts Commerce at 39,4% against Figure 4's total-economy
  24,4% for the same country and year. Emitting it under `industry` would file
  a share of one universe under the same merge key as shares of another, with
  nothing in the row to say so -- the Kenya trap, and the reason Benin, Niger
  and Guinea-Bissau are not collected either. Industry crossed with formality
  is not something one category column can hold.
* TABLEAU 4 (répartition des UPI) counts production UNITS, not people.
* TABLEAUX 1/2/3 and Figures 3, 8, 9, 10 -- participation, employment,
  unemployment and underutilisation RATES, which belong to `unemployment` and
  are already collected there from this same file.
* FIGURE 1, "Répartition des 16 ans ou plus sur le domaine de l'emploi", which
  WOULD be an activity_status distribution: its text layer carries no values at
  all, so there is nothing to read.

NO CLASSIFICATION IS NAMED ANYWHERE IN THE NOTE -- NAEMA, NOPEMA, CITI, ISIC,
CITP and the word "nomenclature" appear ZERO times in all 36 pages. The sixteen
branches are recognisably ISIC Rev.4's sections in French ("Activités
extractives", "Activités de fabrication", "Hébergement et restauration",
"Activités spécialisées, scientifiques et techniques"), and saying so would be
inference published as fact. `National`, as for Botswana, Tanzania and Morocco.

WORKING-AGE BASE IS 16+, not 15+ -- unusual for West Africa and shared with
INSD's ENSE bulletins. The note states it repeatedly: "5 239 416 personnes
âgées de 16 ans ou plus sont en emploi".

PERIOD IS 2023, the collection window (January-April 2023), NOT the 2024
publication date on the cover. Frequency ad_hoc: this is a benchmark survey,
not a recurring series -- and per the descriptor, INSD's fresher ENSE bulletin
must NOT be substituted for it, because that one's numbers exist only as chart
data labels with no category names.

CROSS-CHECK (2023, % of employment of those aged 16+): agriculture,
sylviculture, pêche 31,4; commerce 24,4; activités de fabrication 16,4;
activités extractives 4,1; construction 4; enseignement 3,5; hébergement et
restauration 2,9; transports et entreposage 2,5; activités d'administration
publique 1,1; activités artistiques, sportives et récréatives 0,6. Sixteen
branches summing to 99,9. Total employed on this base: 5 239 416.
"""
from __future__ import annotations

from .pdf_tables_labour import make_parser

LAYOUT = {
    "survey": "Enquête nationale de base sur l'emploi et le secteur informel "
              "(ENB-ESI)",
    "frequency": "ad_hoc",
    "working_age_base": "16+",
    "period": "2023",
    # "31,4" -- comma decimals. Space thousands are irrelevant here (every
    # value is a percentage under 100) but the default is harmless.
    "decimal": ",",
    "tables": [
        {
            "caption": r"Figure\s*4\s*:\s*R[ée]partition des emplois selon la "
                       r"branche d.activit",
            "topic": "industry",
            "classification": "National",
            # PIN TO THE FIGURE'S OWN PAGE. The caption also appears in the
            # list of figures on page 5; that line carries dot leaders and is
            # dropped by the scan's `exclude_lines`, but pinning makes the
            # selection explicit rather than relying on it.
            "page_contains": ["branche d’activité", "pluriactivité"],
            "columns": [{"measure": "share", "unit": "percent"}],
            "series_code": "ENB-ESI F4",
            # Sixteen branches. The x-axis tick line that follows carries eight
            # numbers where one is expected and is skipped on that basis.
            "row_scan": {"expect_rows": 16},
        },
    ],
}

parse = make_parser(LAYOUT)
