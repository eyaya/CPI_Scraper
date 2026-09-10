"""Per-country workbook layouts for the wide-Excel parser.

Only two NSOs in Africa publish their labour headline series as a structured
workbook rather than a report PDF, and both are wide time series (rows =
indicators, columns = periods):

* **South Africa (Stats SA)** -- "QLFS Trends 2008-<YYYY>Q<n>.xlsx", the whole
  back-series from 2008 in one file. The highest-value single source in the
  collector: quarterly, current, and already tidy.
* **Mauritius (Statistics Mauritius)** -- "LF_Emp_Unemp_<n>Qtr<YY>_<DDMMYY>.xlsx",
  the Excel mirror of the quarterly CMPHS tables, plus a 1990-onwards
  historical workbook.

Neither layout hardcodes a cell address: the parser finds the period header row
and the label column itself, so an inserted row at a rebase does not break it.
"""
from __future__ import annotations

EXCEL_LAYOUTS: dict[str, dict] = {}


# =========================================================================
# SOUTH AFRICA -- Stats SA Quarterly Labour Force Survey (P0211).
# Workbook: "QLFS Trends 2008-<YYYY>Q<n>.xlsx" from the P0211 downloads page.
#
# Two wording traps, both real and both fatal if unhandled:
#  * Stats SA RENAMED "Not economically active" to "Outside the labour force".
#    Both spellings are matched so the series survives the rename in either
#    direction.
#  * The official rate is the STRICT one; the "expanded" rate additionally
#    counts discouraged work-seekers. They differ by ~10 points (Q2 2026:
#    33.6% vs 43.8%), so `definition` is mandatory on both.
#
# Levels are published in THOUSANDS, and `unit: thousand_persons` carries that
# so a downstream join cannot mistake them for persons.
#
# CROSS-CHECK (Q2 2026): official unemployment 33.6; expanded 43.8; LFPR 59.6;
# absorption (EPR) 39.6; employed 16,739 thousand; unemployed 8,481 thousand;
# outside the labour force 17,090 thousand; discouraged 3,665 thousand.
#
# NOTE the workbook's internal sheet names could not be read before delivery
# (the file is a binary the recon tools could not open), so `sheet_contains` is
# left unset -- every sheet is scanned and the header/label discovery does the
# work. If the first run is noisy, narrow it to the trends sheet.
# =========================================================================
EXCEL_LAYOUTS["south_africa"] = {
    "survey": "Quarterly Labour Force Survey (QLFS)",
    "frequency": "quarterly",
    "working_age_base": "15-64",
    "decimal": ".",
    # ONE SHEET, NOT ALL OF THEM. This layout used to scan every sheet in the
    # workbook, excluding only the contents page, and take the first block of
    # each. Every sheet's first block is the national total, so the same
    # national series came back SIX TIMES over -- 2,618 rows carrying 444
    # distinct figures -- and, worse, Table 8's first block is "Subsistence
    # farming", whose row labelled "Unemployed" was emitted as the national
    # unemployed count (1,324 thousand against the real 8,481).
    #
    # Table 2 is the headline series. The other sheets are real breakdowns --
    # 2.1 by population group, 2.2 by age, 2.3 by province, 4/6/8 by other
    # characteristics -- and each needs its own block vocabulary before it can
    # be read safely. They are deferred rather than swept up; see PENDING.md.
    "sheet_contains": ["table 2"],
    "sheet_excludes": ["2.1", "2.2", "2.3"],
    # Table 2 repeats its whole indicator list three times, once per sex.
    "blocks": [
        {"match": r"^\s*Both sexes\s*$", "sex": "total"},
        {"match": r"^\s*Women\s*$", "sex": "female"},
        {"match": r"^\s*Men\s*$", "sex": "male"},
    ],
    "rows": [
        {"match": r"^\s*Population 15-64", "topic": "working_age_population",
         "measure": "count", "unit": "thousand_persons",
         "label": "Population 15-64 years"},
        {"match": r"^\s*Labour Force\s*$", "topic": "labour_force",
         "measure": "count", "unit": "thousand_persons", "label": "Labour force"},
        {"match": r"^\s*Employed\s*$", "topic": "employed", "measure": "count",
         "unit": "thousand_persons", "label": "Employed"},
        {"match": r"^\s*Unemployed\s*$", "topic": "unemployed",
         "measure": "count", "unit": "thousand_persons", "label": "Unemployed"},
        {"match": r"^\s*Outside the Labour Force", "topic": "outside_labour_force",
         "measure": "count", "unit": "thousand_persons",
         "label": "Outside the labour force"},
        {"match": r"^\s*Potential Labour Force", "topic": "potential_labour_force",
         "measure": "count", "unit": "thousand_persons",
         "label": "Potential labour force"},
        {"match": r"^\s*Discouraged job", "topic": "potential_labour_force",
         "measure": "count", "unit": "thousand_persons",
         "label": "Discouraged job-seekers"},
        {"match": r"^\s*Labour force partic", "measure": "rate",
         "topic": "labour_force_participation_rate", "definition": "strict",
         "label": "Labour force participation rate"},
        {"match": r"^\s*Employed\s*/\s*population", "measure": "rate",
         "topic": "employment_to_population_ratio",
         "label": "Absorption rate (employed / population ratio)"},
        # THE BROAD MEASURES ARE PRINTED AS LU1-LU4, NOT AS "EXPANDED".
        # The old layout looked for "Expanded unemployment rate", which appears
        # nowhere in this workbook, so South Africa's broad series -- the whole
        # reason the country is worth collecting twice over -- was never read.
        {"match": r"^\s*LU1", "topic": "unemployment_rate", "measure": "rate",
         "definition": "strict", "label": "LU1 - Unemployment rate (official)"},
        {"match": r"^\s*LU2", "topic": "underemployment_rate", "measure": "rate",
         "definition": "broad",
         "label": "LU2 - Combined rate of unemployment and time-related underemployment"},
        {"match": r"^\s*LU3", "topic": "labour_underutilisation_rate",
         "measure": "rate", "definition": "broad",
         "label": "LU3 - Combined rate of unemployment and potential labour force"},
        {"match": r"^\s*LU4", "topic": "labour_underutilisation_rate",
         "measure": "rate", "definition": "broad",
         "label": "LU4 - Composite measure of labour underutilisation"},
    ],
}


# =========================================================================
# MAURITIUS -- Statistics Mauritius, Continuous Multi-Purpose Household Survey
# (CMPHS). Workbook "LF_Emp_Unemp_<n>Qtr<YY>_<DDMMYY>.xlsx"; the Excel mirrors
# the PDF's nine tables one sheet per table.
#
# WORKING-AGE BASE IS 16+, not 15+. Comparing a Mauritius rate with a 15+ rate
# without saying so is a real error, so it travels on every row.
#
# No urban/rural and no regional breakdown is published in this release.
#
# CROSS-CHECK (Q1 2026): unemployment rate 5.7 (M 4.3 / F 7.5);
# labour force 587,000; employment 553,700; unemployment 33,300;
# activity rate 59.2.
# =========================================================================
EXCEL_LAYOUTS["mauritius"] = {
    "survey": "Continuous Multi-Purpose Household Survey (CMPHS)",
    "frequency": "quarterly",
    "working_age_base": "16+",
    "decimal": ".",
    "sheet_excludes": ["contents", "notes", "cover"],
    "rows": [
        {"match": r"^\s*Labour force\b", "exclude": r"rate|participation",
         "topic": "labour_force", "measure": "count", "unit": "persons",
         "label": "Labour force"},
        {"match": r"^\s*Employment\b|^\s*Employed\b", "exclude": r"rate|ratio",
         "topic": "employed", "measure": "count", "unit": "persons",
         "label": "Employment"},
        {"match": r"^\s*Unemployment\b", "exclude": r"rate",
         "topic": "unemployed", "measure": "count", "unit": "persons",
         "label": "Unemployment"},
        {"match": r"Unemployment rate", "exclude": r"youth",
         "topic": "unemployment_rate", "definition": "strict",
         "label": "Unemployment rate"},
        {"match": r"Activity rate|Labour force participation rate",
         "topic": "labour_force_participation_rate", "definition": "strict",
         "label": "Activity rate"},
    ],
}


# =========================================================================
# EGYPT -- CAPMAS, quarterly Labour Force Survey bulletin
# (بحث القوى العاملة - الربع سنوي), publication id 11.
#
# Reached through the same JSON API the CPI collector already uses
# successfully: GET https://www.capmas.gov.eg:8080/api/Publication/<id> returns
# the newest issue with `pdfUrl` and `excelUrl`. Verified live during this
# build, along with ids 12 (annual), 157 and 149 (analytical, PDF-only).
#
# THE WORKBOOK IS ARABIC. Row labels are Arabic, and both the Arabic and any
# English gloss are matched so the layout survives either. The terms:
#   قوة العمل        labour force
#   المشتغلون        the employed
#   المتعطلون        the unemployed
#   معدل البطالة     unemployment rate
#   معدل المساهمة    participation rate
#
# UNVERIFIED: the workbook's internal sheet and cell structure could not be
# opened during this build (no environment here could reach the file), so the
# layout scans every sheet and finds the period header row and label column by
# structure. Treat the first run as the verification step -- the cross-check
# below is the fastest way to tell whether it worked.
#
# CROSS-CHECK (Q1 2026, from the CAPMAS release): unemployment rate 6.0%.
# Breakdowns published: sex, urban/rural (حضر/ريف), 27 governorates, age group,
# educational status, occupation, economic activity. Levels in thousands.
# =========================================================================
EXCEL_LAYOUTS["egypt"] = {
    "survey": "Labour Force Survey (quarterly bulletin)",
    "frequency": "quarterly",
    "working_age_base": "15+",
    "decimal": ".",
    "sheet_excludes": ["cover", "index", "notes", "فهرس"],
    "rows": [
        {"match": r"قوة العمل|labou?r force", "exclude": r"معدل|rate|ratio",
         "topic": "labour_force", "measure": "count", "unit": "thousand_persons",
         "label": "قوة العمل (labour force)"},
        {"match": r"المشتغلون|المشتغلين|^\s*employed",
         "exclude": r"معدل|rate|ratio|غير",
         "topic": "employed", "measure": "count", "unit": "thousand_persons",
         "label": "المشتغلون (employed)"},
        {"match": r"المتعطلون|المتعطلين|^\s*unemployed", "exclude": r"معدل|rate",
         "topic": "unemployed", "measure": "count", "unit": "thousand_persons",
         "label": "المتعطلون (unemployed)"},
        {"match": r"معدل البطالة|unemployment rate", "exclude": r"شباب|youth",
         "topic": "unemployment_rate", "definition": "strict",
         "label": "معدل البطالة (unemployment rate)"},
        {"match": r"معدل المساهمة|participation rate",
         "topic": "labour_force_participation_rate", "definition": "strict",
         "label": "معدل المساهمة في قوة العمل (participation rate)"},
    ],
}
