"""Column vocabularies shared by the per-country unemployment layouts.

Split out of the old single `layouts.py`, so that each country lives in its
own module beside its own descriptor -- the shape every other indicator in
this repo uses. What stays here is only what more than one country needs;
anything used once sits in that country's module, next to the layout that
explains it.

Two habits keep the layouts honest, and they belong with this vocabulary:

* **Never normalise a caption before matching it.** "Employment to
  Population Ration" (Botswana), "Economically Activity Persons"
  (Ethiopia), "Treads of unemployment rate" (Eswatini) and "Labour force"
  with a lower-case f (Somalia) are all real. Anchored, loose regexes beat
  tidy ones.
* **Never assume a column order.** Zambia prints `... Rural | Urban`;
  Namibia prints `... Urban | Rural`; Egypt's PDF runs Total, Females,
  Males where its workbook runs Males, Females, Total. Getting this
  backwards swaps two real series and nothing downstream can notice.
"""
from __future__ import annotations
# --- reusable column vocabularies -----------------------------------------

_TOTAL = {"sex": "total", "locality": "all", "locality_label": "Total"}
_MALE = {"sex": "male", "locality": "all", "locality_label": "Total"}
_FEMALE = {"sex": "female", "locality": "all", "locality_label": "Total"}
_URBAN = {"sex": "total", "locality": "urban", "locality_label": "Urban"}
_RURAL = {"sex": "total", "locality": "rural", "locality_label": "Rural"}

# Total | Male | Female | Urban | Rural -- the single commonest LFS header.
COLS_TMF_UR = [_TOTAL, _MALE, _FEMALE, _URBAN, _RURAL]
# Total | Male | Female | Rural | Urban -- Zambia prints residence the other way.
COLS_TMF_RU = [_TOTAL, _MALE, _FEMALE, _RURAL, _URBAN]
# Male | Female | Both sexes -- Eswatini, Seychelles.
#
# SEX ONLY. A COLUMN SPEC IS MERGED AFTER THE ROW'S, so anything a column
# states wins. `_MALE`/`_FEMALE`/`_TOTAL` also carry `locality: all`, which is
# right for a header whose columns ARE the localities and wrong for one whose
# ROWS are: Eswatini's absorption-rate table lists Hhohho, Manzini, ..., then
# Urban and Rural, and the row's `locality: urban` was being overwritten back
# to `all`. Its urban and rural figures went out as four extra national rows
# (17.1, 20.0 and two copies of 18.7), indistinguishable from each other and
# from the real national value -- and merge-on-write then collapsed them.
#
# `_common.row` defaults locality to "all"/"Total", so a sex-only column leaves
# an ordinary table exactly as it was.
_M = {"sex": "male"}
_F = {"sex": "female"}
_T = {"sex": "total"}
COLS_MFT = [_M, _F, _T]


def _sex_x_locality(locality: str, label: str) -> list[dict]:
    return [
        {"sex": s, "locality": locality, "locality_label": label}
        for s in ("total", "male", "female")
    ]

# Most of this vocabulary is underscore-prefixed, and `from ._vocab import *`
# skips those by default -- so every country module raised NameError on its
# first column spec. `__all__` is what makes the star import mean what it
# looks like it means.
__all__ = [
    "COLS_MFT",
    "_F",
    "_M",
    "_T",
    "COLS_TMF_RU",
    "COLS_TMF_UR",
    "_FEMALE",
    "_MALE",
    "_RURAL",
    "_TOTAL",
    "_URBAN",
    "_sex_x_locality",
]
