"""Rwanda -- NISR "The Second Rwanda Multidimensional Poverty Report" (EICV5
thematic report), Annex Tables B 5 and B 6.

A DIFFERENT MEASURE from the EICV7 edition `rwanda_mpi` collects, never to be
chained to it. This report's national MPI (designed with OPHI, November 2016):

    4 dimensions, each 25% -- Education; Housing; Public Services; Social
      Services & Economic Activity
    14 indicators -- school attendance, years of schooling | electricity,
      floor, overcrowding, cooking fuel | sanitation, drinking water, garbage
      disposal | bank account, health insurance, assets for communication,
      distance to health care, subsistence farming (Table 1.2)
    k = 40% ("deprived in k >= 40% of the weighted indicators"), person-level

EICV7 changed the cutoff to 33.3% and the indicator set, and its report flags
the break. Hence a separate `measure_name`.

THE REPORT RESTATES THREE ROUNDS ON THIS ONE METHODOLOGY -- EICV3 (2010/11),
EICV4 (2013/14), EICV5 (2016/17) -- so the three ARE comparable with each
other. Each row is dated to its round's end year and names its round in
`survey`.

Table B 5 (area and province) prints, per round, Pop. share | H | A | M0;
the share is not an MPI measure and is skipped. Table B 6 does the same by
consumption quintile; its national row's label is scrambled in the text layer
("Rwanda(1N0a0ti.o0n%al)") and repeats B 5's national row, so it is not read.
EICV5's quintile shares print without a % sign -- skipped either way.

Province names are as printed here ("Kigali City", not EICV7's "City of
Kigali").

CROSS-CHECK: national H 44.4 / 32.9 / 28.7 (EICV3 / 4 / 5), A 53.8 / 51.7 /
51.5, M0 0.239 / 0.170 / 0.148; Kigali City EICV5 13.3 / 50.8 / 0.068;
Q1 EICV5 55.3 / 54.0 / 0.299; Q5 EICV5 5.9 / 48.5 / 0.029.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_METHOD = dict(mpi_type="national",
               measure_name="Rwanda MPI (Second Report, k = 40%)",
               k_cutoff=40, n_dimensions=4, n_indicators=14,
               unit_of_analysis="person", frequency="ad_hoc")
_ROUNDS = [("EICV3", "2011", "2010/11"), ("EICV4", "2014", "2013/14"),
           ("EICV5", "2017", "2016/17")]
_NUM = r"\d+(?:\.\d+)?%?"
_ROW = re.compile(rf"^(?P<label>[A-Za-z][A-Za-z ()]*?|Q[1-5])\s+(?P<nums>(?:{_NUM}\s+){{11}}{_NUM})$")

_B5 = {"Kigali City": {"geography": "Kigali City"},
       "Southern Province": {"geography": "Southern Province"},
       "Western Province": {"geography": "Western Province"},
       "Northern Province": {"geography": "Northern Province"},
       "Eastern Province": {"geography": "Eastern Province"},
       "Urban": {"locality": "urban", "locality_label": "Urban",
                 "topic": "locality", "characteristic": "Urban"},
       "Rural": {"locality": "rural", "locality_label": "Rural",
                 "topic": "locality", "characteristic": "Rural"},
       "Rwanda(National)": {}}


def _table(lines: list[str], caption: str, end: str) -> list[str]:
    i = next(i for i, ln in enumerate(lines) if ln.startswith(caption))
    out = []
    for ln in lines[i + 1:]:
        if ln.startswith(end):
            break
        out.append(ln.strip())
    return out


def _read(lines, labels) -> dict[str, list[float]]:
    got = {}
    for ln in lines:
        m = _ROW.match(ln)
        if not m or m.group("label").strip() not in labels:
            continue
        got[m.group("label").strip()] = [float(x.rstrip("%"))
                                         for x in m.group("nums").split()]
    missing = [l for l in labels if l not in got]
    if missing:
        raise ValueError(f"Rwanda EICV5 MPI: rows not read {missing}")
    return got


def parse(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        page = next(p for p in pdf.pages
                    if "Table B 5: Incidence, Intensity and MPI" in (p.extract_text() or "")
                    and "...." not in (p.extract_text() or ""))
        lines = page.extract_text().split("\n")
    b5 = _read(_table(lines, "Table B 5:", "Source:"), list(_B5))
    quint = [f"Q{i}" for i in range(1, 6)]
    b6 = _read(_table(lines, "Table B 6:", "Source:"), quint)

    out = []
    for table, labels, ctxf in ((b5, _B5, lambda l: _B5[l]),
                                (b6, quint, lambda l: {"topic": "quintile",
                                                       "characteristic": l})):
        for label in labels:
            v = table[label]
            for r, (survey, period, ref) in enumerate(_ROUNDS):
                share, h, a, m0 = v[4 * r:4 * r + 4]
                # M0 is read, never computed; H x A only CHECKS the reading.
                if abs(m0 - h * a / 1e4) > 0.006:
                    raise ValueError(f"Rwanda EICV5 MPI {label} {survey}: M0 "
                                     f"{m0} != H x A ({h} x {a})")
                for metric, val in (("incidence_H", h), ("intensity_A", a),
                                    ("index_M0", m0)):
                    out.append(C.row(
                        metric=metric, value=val, period=period,
                        reference_period=ref, series_code=f"NISR MPI2 {'B5' if table is b5 else 'B6'}",
                        survey=f"{survey} ({ref}) -- Integrated Household Living Conditions Survey",
                        **_METHOD, **ctxf(label)))
    return pd.DataFrame(out)
