"""Shared column vocabularies for the per-country MPI layouts.

Every entry was written against the report's ACTUAL rendered text: column orders,
row labels and their spellings are as printed. Two habits keep this honest:

* **Never assume the column order.** Egypt prints `MPI | H | A | population
  share`; Mali prints `population share | IPM | H | A`; Botswana puts the
  METRICS in the rows and the strata in the columns. Getting this wrong swaps an
  index for a rate and nothing downstream would notice, because both are
  plausible numbers.
* **Never assume k = 33.3%.** Observed across these seventeen: Nigeria 25,
  Seychelles 25, Egypt 29, Namibia 30, Angola 30, Mauritius 30, Ghana 33,
  Morocco 33, Guinea 33.33, Madagascar 33.3, Rwanda 33.3, South Africa 33.3,
  Somalia 35, Burkina 38, Malawi 38, Uganda 40, Sierra Leone 40, Botswana 40,
  **Mali 60**.

CROSS-CHECK values sit beside each layout. Running the parser and comparing
against them is the fastest way to prove a layout still holds.
"""
from __future__ import annotations


# --- reusable column vocabularies -----------------------------------------

# The commonest MPI table: H | A | M0, in that order.
COLS_H_A_M0 = [
    {"metric": "incidence_H"},
    {"metric": "intensity_A"},
    {"metric": "index_M0"},
]
# Angola, Mali and Egypt lead with the index or a population share instead.
COLS_M0_H_A = [
    {"metric": "index_M0"},
    {"metric": "incidence_H"},
    {"metric": "intensity_A"},
]

_URBAN = {"locality": "urban", "locality_label": "Urban", "topic": "locality"}
_RURAL = {"locality": "rural", "locality_label": "Rural", "topic": "locality"}
_NATIONAL = {"locality": "all", "locality_label": "Total"}
