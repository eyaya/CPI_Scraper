"""Per-country layouts for the HTML-table parser.

Only one NSO in Africa publishes its labour series as server-rendered HTML
tables: INS Tunisie. See `html_wide_series` for why that route is used in
preference to the PDF.
"""
from __future__ import annotations

HTML_LAYOUTS: dict[str, dict] = {}


# =========================================================================
# TUNISIA -- INS, "Indicateurs de l'emploi et du chômage", quarterly.
#
# Three theme pages carry the whole series as real HTML tables:
#   /statistiques/151  population active        (dataset 1611321389)
#   /statistiques/152  population active occupée (dataset 1611321992)
#   /statistiques/153  chômage                  (datasets 1611322781, 1611322839)
#
# WHY NOT THE PDF: the quarterly note is a bilingual Arabic/French document
# whose numeric runs come out of the text layer bidi-scrambled -- reversed on
# Tableau 1, rotated by four positions on Tableau 4, and digits run together
# without recoverable boundaries on Tableau 5. Verified by anchoring on the
# note's own narrative figures. There is no correct way to parse it; these
# HTML tables carry the same series in reading order.
#
# Row labels are `Total` / `Masculin` / `Féminin`; column headers are French
# ordinal quarter labels ("première-trimestre 2024"), which `parse_period`
# handles including the hyphen INS uses instead of a space.
#
# ROLLING WINDOW: only about eight or nine quarters are rendered at a time, and
# the window is not identical across the three pages (Q4 2024 is present on
# /151 but absent from /153). History therefore accumulates across runs rather
# than arriving complete in one scrape -- which is fine, since each run writes
# every quarter it can see.
#
# Levels are published in thousands ("en millier"); rates are percent.
#
# CROSS-CHECK (Q2 2026): population active 4 190,5 mille (M 2 887,7 /
# F 1 302,8); occupés 3 568,1 mille; chômeurs 622,4 mille (M 341,6 / F 280,7);
# taux de chômage 14,9 (M 11,8 / F 21,6). Q1 2026: chômeurs 641,7; taux 15,0.
# =========================================================================
_TN_ROWS = [
    {"match": r"^Total\b|^Ensemble\b", "sex": "total"},
    {"match": r"^Masculin\b|^Hommes?\b", "sex": "male"},
    {"match": r"^F[ée]minin\b|^Femmes?\b", "sex": "female"},
]

HTML_LAYOUTS["tunisia"] = {
    "survey": "Enquête nationale sur l'emploi -- Indicateurs de l'emploi et "
              "du chômage",
    "frequency": "quarterly",
    "working_age_base": "15+",
    "decimal": ".",
    "tables": [
        {"caption": r"population active.*selon le sexe",
         "defaults": {"topic": "labour_force", "measure": "count",
                      "unit": "thousand_persons",
                      "label": "Population active (en millier)"},
         "rows": list(_TN_ROWS)},
        {"caption": r"population active occup[ée]e.*selon le sexe",
         "defaults": {"topic": "employed", "measure": "count",
                      "unit": "thousand_persons",
                      "label": "Population active occupée (en millier)"},
         "rows": list(_TN_ROWS)},
        {"caption": r"population active en ch[ôo]mage.*selon le sexe",
         "defaults": {"topic": "unemployed", "measure": "count",
                      "unit": "thousand_persons",
                      "label": "Population active en chômage (en millier)"},
         "rows": list(_TN_ROWS)},
        {"caption": r"taux de ch[ôo]mage selon le sexe",
         "defaults": {"topic": "unemployment_rate", "definition": "strict",
                      "label": "Taux de chômage (%)"},
         "rows": list(_TN_ROWS)},
    ],
}
