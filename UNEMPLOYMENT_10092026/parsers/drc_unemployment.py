"""DR Congo — INS, Enquête 1-2-3 2012, Rapport global (2014), Part I (phase 1,
the HOUSEHOLD employment survey), read from the Wayback `id_` copy of INS's own
PDF -- ins-rdc.org answers a Cloudflare 403 to every client (see drc.yaml).

TAKEN:

* Tableau I.6.1 -- taux de chômage by age band x stratum, in THREE
  definitions, each told apart by `series_label`: "au sens du BIT" (strict),
  "au sens large" (broad: adds discouraged job-seekers) and "doublement
  élargi" (broad: also drops the availability test -- INS's own term). The
  third block prints no "Autre urbain" row. Base 10+ (the survey's working
  age; the age bands start at 10-14).
* Tableau I.2 bis -- taux d'activité 2012 by sex, on the 10+ and 15+ bases,
  by stratum.
* Tableau I.5.18 -- the SAME table printed again sixteen pages later, with
  last-digit differences (Kinshasa men 10+: 49,6 vs 49,9; Autre urbain women
  15+: 49,0 vs 49,1). Both kept, told apart by `series_label` -- not
  reconciled.
* Tableau I.5.2 -- taux d'activité from the 2004-2005 Enquête 1-2-3 round as
  this report republishes it (Kinshasa / urbain / rural / RDC), period 2005.
* Tableau I.6.8 -- time-related underemployment of the employed (working
  under 45 h and under 35 h a week) by sex x stratum -> underemployment_rate.

NOT TAKEN: I.6.8's "sous-emploi invisible" (earning under the hourly minimum
wage -- income-based, no topic) and "sous-emploi global" (which folds it in);
I.5.19/I.5.20 (activity by household position / ICT access -- no column);
the Phase 2/3 informal-unit and consumption parts.

STRATA: Kinshasa (a province, and wholly urban), "Autre urbain" (other urban
areas -> locality other), Urbain, Rural, RDC (national). The 2004-05 table
has no "Autre urbain" column.

CROSS-CHECK: BIT 4,5 (Kinshasa 18,8; 15-24 ans 8,8); au sens large 8,0;
doublement élargi 17,7; activité 15+ 67,5 (2012), 71,6 (2004-05);
<35 h 4,0 rural.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from ._common import numbers_in, row

_SURVEY = "Enquête 1-2-3 2012 (phase 1, emploi)"
_BASE = dict(survey=_SURVEY, period="2012", reference_period="Enquête 1-2-3 2012",
             frequency="ad_hoc")
_KIN = {"geography": "Kinshasa", "locality": "urban", "locality_label": "Kinshasa"}
_AUT = {"locality": "other", "locality_label": "Autre urbain"}
_URB = {"locality": "urban", "locality_label": "Urbain"}
_RUR = {"locality": "rural", "locality_label": "Rural"}
_STRATA5 = [_KIN, _AUT, _URB, _RUR, {}]
# locality_label keeps each table's own spelling ("Urban" in I.6.1's third
# block, "Autres urbains" / "Ensemble urbains" / "Ruraux" in I.6.8).
_STRATUM = {"Kinshasa": _KIN, "Autre urbain": _AUT,
            "Autres urbains": {**_AUT, "locality_label": "Autres urbains"},
            "Urbain": _URB, "Urban": {**_URB, "locality_label": "Urban"},
            "Ensemble urbains": {**_URB, "locality_label": "Ensemble urbains"},
            "Rural": _RUR, "Ruraux": {**_RUR, "locality_label": "Ruraux"},
            "RDC": {}}


def _lines(path: str) -> list[str]:
    with pdfplumber.open(path) as pdf:
        return [ln.strip() for p in pdf.pages[60:96]
                for ln in (p.extract_text() or "").splitlines()]


def _after(L, cap):
    i = next((k for k, ln in enumerate(L) if re.match(cap, ln)), None)
    if i is None:
        raise ValueError(f"1-2-3: {cap!r} not found")
    return L[i + 1:]


def _activity(L, cap, label, cols, extra, n_cols):
    out = []
    n = 0
    for ln in _after(L, cap):
        m = re.match(r"^(Hommes|Femmes|Ensemble) (10|15) ans et plus\s+(.*)$", ln)
        if not m:
            if n:
                break
            continue
        vals = numbers_in(m.group(3), decimal=",")
        if len(vals) != n_cols:
            raise ValueError(f"1-2-3 {cap}: {ln!r}")
        sex = {"Hommes": {"sex": "male"}, "Femmes": {"sex": "female"},
               "Ensemble": {}}[m.group(1)]
        for col, v in zip(cols, vals):
            out.append(row(topic="labour_force_participation_rate",
                           series_label=label, value=v,
                           working_age_base=f"{m.group(2)}+",
                           **{**_BASE, **extra, **sex, **col}))
        n += 1
    if n != 6:
        raise ValueError(f"1-2-3 {cap}: {n} rows")
    return out


def parse(path: str, extras=None) -> pd.DataFrame:
    L = _lines(path)
    out = []
    out += _activity(L, r"^Tableaux n° I\.2 bis", "Taux d'activité (Tableau I.2 bis)",
                     _STRATA5, {"series_code": "1-2-3 2012 T.I.2bis"}, 5)
    out += _activity(L, r"^Tableau I\.5\.18", "Taux d'activité (Tableau I.5.18)",
                     _STRATA5, {"series_code": "1-2-3 2012 T.I.5.18"}, 5)
    out += _activity(L, r"^Tableaux I\.5\.2 :", "Taux d'activité (Enquête 1-2-3 "
                     "2004-2005, Tableau I.5.2)", [_KIN, _URB, _RUR, {}],
                     {"series_code": "1-2-3 2012 T.I.5.2",
                      "survey": "Enquête 1-2-3 2004-2005, as republished in "
                                "the 2012 Rapport global",
                      "period": "2005", "reference_period": "2004-2005"}, 4)

    # --- I.6.1: three blocks of stratum x age
    ages = ["10-14", "15-24", "25-34", "35-54", "55-64", "65+", None]
    blocks = {"Taux de chômage au sens du BIT": "strict",
              "Taux de chômage au sens large": "broad",
              "Taux de chômage doublement élargi": "broad"}
    block, got = None, {}
    for ln in _after(L, r"^Tableau I\.6\.1"):
        if ln in blocks:
            block = ln
            continue
        m = re.match(r"^(Kinshasa|Autre urbain|Urbain|Urban|Rural|RDC)\s+(.*)$", ln)
        if block and m:
            vals = numbers_in(m.group(2), decimal=",")
            if len(vals) != 7:
                raise ValueError(f"1-2-3 I.6.1: {ln!r}")
            got.setdefault(block, []).append(m.group(1))
            for age, v in zip(ages, vals):
                out.append(row(topic="unemployment_rate", definition=blocks[block],
                               series_label=block, value=v,
                               working_age_base="10+",
                               series_code="1-2-3 2012 T.I.6.1",
                               **{**_BASE, **_STRATUM[m.group(1)],
                                  **({"age_group": age} if age else {})}))
            if block == "Taux de chômage doublement élargi" and m.group(1) == "RDC":
                break
    want = {"Taux de chômage au sens du BIT": 5, "Taux de chômage au sens large": 5,
            "Taux de chômage doublement élargi": 4}
    if {k: len(v) for k, v in got.items()} != want:
        raise ValueError(f"1-2-3 I.6.1: blocks read {got}")

    # --- I.6.8: sex blocks x stratum; first two columns are time-related
    sex, n = None, 0
    for ln in _after(L, r"^Tableau I\.6\.8"):
        if ln in ("Hommes", "Femmes", "Ensemble"):
            sex = {"Hommes": {"sex": "male"}, "Femmes": {"sex": "female"},
                   "Ensemble": {}}[ln]
            continue
        m = re.match(r"^(Kinshasa|Autres urbains|Ensemble urbains|Ruraux)\s+(.*)$", ln)
        if sex is not None and m:
            vals = numbers_in(m.group(2), decimal=",")
            if len(vals) != 4:
                raise ValueError(f"1-2-3 I.6.8: {ln!r}")
            for hours, v in zip((45, 35), vals[:2]):
                out.append(row(topic="underemployment_rate",
                               series_label="Sous-emploi lié à la durée du "
                                            f"travail : travailler moins de {hours} h "
                                            "par semaine",
                               value=v, working_age_base="10+",
                               series_code="1-2-3 2012 T.I.6.8",
                               **{**_BASE, **_STRATUM[m.group(1)], **sex}))
            n += 1
            if n == 12:
                break
    if n != 12:
        raise ValueError(f"1-2-3 I.6.8: {n} rows")

    df = pd.DataFrame(out)
    nat = (df.geography == "Total country") & (df.locality == "all") & \
          (df.sex == "total") & (df.age_group == "Total")
    for code, label, want in (("1-2-3 2012 T.I.6.1", "Taux de chômage au sens du BIT", 4.5),
                              ("1-2-3 2012 T.I.6.1", "Taux de chômage doublement élargi", 17.7)):
        got = df[nat & (df.series_code == code) & (df.series_label == label)].value.tolist()
        if got != [want]:
            raise ValueError(f"{code} {label}: national {got}, want {want}")
    return df
