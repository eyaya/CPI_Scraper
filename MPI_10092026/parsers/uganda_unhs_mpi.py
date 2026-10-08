"""Uganda -- UBOS "Multidimensional Poverty Index for Uganda" (2022 report),
from UNHS 2016/17 and UNHS 2019/20.

A DIFFERENT MEASURE from the census edition `uganda_mpi` collects (2024
census, 13 indicators, Basic Services dimension), and never to be chained to
it. This one: 4 dimensions -- education, health, living standards, and
employment and financial inclusion -- 12 indicators, k = 40%, person-level.
Its two rounds ARE comparable with each other; each row is dated to the round's
end year (2017, 2020).

WHAT IS TAKEN, AND WHY ONLY THAT:

* Table 3.3 prints H and A as PROPORTIONS (Total H 0.443, A 0.564), M0 as an
  index (0.25). M0 is taken from it, for residence, region, sub-region and
  Total. H and A are NOT taken from it: the schema's H and A are percentages,
  and multiplying 0.443 by 100 would be this collector computing a figure.
* H AS A PERCENTAGE IS PRINTED ELSEWHERE, and taken from there: Table 3.5
  (national and the 15 sub-regions, "Multidimensional poor", %) and Table 3.4
  (by sex of head, consumption quintile, education and age of head, %). Table
  3.5 agrees with 3.3's proportions where both print (Kampala 2.7 / 0.027,
  Buganda South 17.9 / 0.179) -- checked every run.
* A is printed ONLY as a proportion, so it is not collected.
* Table 3.3's "% change" columns are differences, not measures. Table 3.4's
  marital-status and household-size blocks have no topic here.

ONE LABEL CORRECTED, deliberately: Table 3.5 prints "To0ro" (a zero for an
"o"); Table 3.3 of the same report prints "Toro", which is used.

CROSS-CHECK: Total M0 0.25 (2016/17), 0.23 (2019/20); national H 44.3 / 42.1;
Karamoja M0 0.593 / 0.55, H 86.7 / 84.9; female-headed H 49.8 / 48.9.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_METHOD = dict(mpi_type="national", measure_name="Uganda MPI (UNHS, 2022 report)",
               k_cutoff=40, n_dimensions=4, n_indicators=12,
               unit_of_analysis="person", frequency="ad_hoc")
_ROUNDS = [("2017", "UNHS 2016/17"), ("2020", "UNHS 2019/20")]
_N = r"-?\d+(?:\.\d+)?"
_SUBREGIONS = ["Kampala", "Buganda South", "Buganda North", "Busoga", "Bukedi",
               "Elgon", "Teso", "Karamoja", "Lango", "Acholi", "West Nile",
               "Bunyoro", "Toro", "Ankole", "Kigezi"]
_GEO33 = (["Central", "Eastern", "Northern", "Western"] + _SUBREGIONS)


def _page(pdf, caption):
    for p in pdf.pages:
        t = p.extract_text() or ""
        if caption in t and "...." not in t.split(caption, 1)[1][:80]:
            return t.split(caption, 1)[1].split("Source:", 1)[0].split("\n")
    raise ValueError(f"Uganda UNHS MPI: {caption!r} not found")


def _rows(lines, labels, n):
    got = {}
    for ln in lines:
        ln = ln.strip().replace("To0ro", "Toro")
        for lab in labels:
            m = re.fullmatch(rf"{re.escape(lab)}\s+((?:{_N}\s+){{{n - 1}}}{_N})", ln)
            if m:
                got[lab] = [float(x) for x in m.group(1).split()]
    missing = [l for l in labels if l not in got]
    if missing:
        raise ValueError(f"Uganda UNHS MPI: rows not read {missing}")
    return got


def _row(metric, value, period, ref, **ctx):
    return C.row(metric=metric, value=value, period=period, reference_period=ref,
                 survey=f"{ref} (Uganda National Household Survey)",
                 series_code="UBOS MPI 2022", **_METHOD, **ctx)


def parse(path: str) -> pd.DataFrame:
    out = []
    with pdfplumber.open(path) as pdf:
        t33 = _rows(_page(pdf, "TABLE 3.3: INCIDENCE, INTENSITY AND MULTIDIMENSIONAL"),
                    ["Rural", "Urban", "Total"] + _GEO33, 9)
        t35 = _rows(_page(pdf, "TABLE 3.5: MONETARY AND MULTIDIMENSIONAL POVERTY BY SUB-REGION"),
                    ["National"] + _SUBREGIONS, 4)
        t34 = _page(pdf, "TABLE 3.4: INCIDENCE OF MULTIDIMENSIONAL POVERTY")

    def geo(label):
        if label in ("Rural", "Urban"):
            return {"locality": label.lower(), "locality_label": label,
                    "topic": "locality", "characteristic": label}
        return {} if label in ("Total", "National") else {"geography": label}

    # Table 3.3: M0 (cols 7, 8 = 2016/17, 2019/20); H as a proportion (cols 1, 2)
    # only CHECKS Table 3.5's percentages.
    for label, v in t33.items():
        for (period, ref), m0 in zip(_ROUNDS, v[6:8]):
            out.append(_row("index_M0", m0, period, ref, **geo(label)))
    for label, v in t35.items():
        key = "Total" if label == "National" else label
        for (period, ref), h_pct, h_prop in zip(_ROUNDS, v[2:4], t33[key][0:2]):
            if abs(h_pct - 100 * h_prop) > 0.15 and label != "National":
                raise ValueError(f"Uganda UNHS MPI {label} {ref}: Table 3.5 H "
                                 f"{h_pct} disagrees with Table 3.3's {h_prop}")
            out.append(_row("incidence_H", h_pct, period, ref, **geo(label)))

    # Table 3.4: H (%) by household characteristic; blocks by heading.
    blocks = {"Sex of household head": "sex_of_head",
              "Consumption expenditure quintile": "quintile",
              "Education level": "education", "Age group": "age",
              "Marital status": None, "Household size": None}
    topic = None
    for ln in t34:
        ln = ln.strip()
        if ln in blocks:
            topic = blocks[ln]
            continue
        m = re.fullmatch(rf"(.+?)\s+({_N})\s+({_N})", ln)
        if not m or topic is None or m.group(1) in ("Total", "Characteristic"):
            continue
        lab = m.group(1).replace("–", "-")
        ctx = {"topic": topic, "characteristic": lab}
        if topic == "sex_of_head":
            ctx["sex"] = "female" if lab == "Female" else "male"
        for (period, ref), val in zip(_ROUNDS, (float(m.group(2)), float(m.group(3)))):
            out.append(_row("incidence_H", val, period, ref, **ctx))
    n34 = sum(1 for r in out if r["topic"] in ("sex_of_head", "quintile", "education", "age"))
    if n34 != 2 * (2 + 5 + 6 + 4):
        raise ValueError(f"Uganda UNHS MPI Table 3.4: {n34 // 2} categories read, expected 17")
    return pd.DataFrame(out)
