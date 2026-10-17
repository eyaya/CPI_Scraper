"""Nigeria -- Debt Management Office (DMO), "Nigeria's Total Public Debt
(Portfolio/Stock) as at <date>", one single-page PDF per quarter, December 2012
to the latest quarter (dmo.gov.ng/debt-profile/total-public-debt).

PUBLISHER: the DMO, Nigeria's statutory debt compiler (an accepted official
national compiler under this indicator's source policy).

COVERAGE: public debt of the Federal Government (FGN), the 36 States and the
FCT, external and domestic -- but WHAT EACH ROW COVERS CHANGES ACROSS THE
SERIES, and the labels are therefore kept exactly as printed:

* 2013 - 2017 (two columns, US$ and N): "External Debt Stock (FGN + States)",
  "Domestic Debt Stock (FGN Only)", "Sub-Total", "Domestic Debt of States*",
  "Grand-Total (A+B)". The early "Total" (June 2013) is FGN external + FGN
  domestic only -- states' domestic debt is NOT in it. Never chain it to the
  later "Total Public Debt (A+B)".
* Q1-Q3 2018: "External Debt (FGN + State & FCT Only)", "Domestic Debt (FGN
  Only)", "Domestic Debt (States + FCT)", "Sub-Total - Domestic Debt",
  "Total (A+D)".
* December 2018 onward (three columns, adding "% of Total"): "Total External
  Debt", "Total Domestic Debt", each sometimes split into "FGN Only" /
  "States & FCT", and "Total Public Debt (A+B)". Sub-rows are emitted with
  their section ("Total Domestic Debt: FGN Only") because "FGN Only" alone is
  ambiguous.

States' domestic debt is often reported AS AT AN EARLIER DATE than the
quarter (each report's own footnote, e.g. December 2022: Katsina and Taraba as
at September 30, 2022, Rivers as at September 30, 2021). The figures are the
DMO's; the footnotes are not encoded as data.

MEASURES: stock in "USD million" and in "NGN million" (both as printed --
the DMO converts at the CBN official rate it names), and `share` = the
"% of Total" column (percent of total public debt), from late 2018.

READING. Rows are rebuilt from the text layer: a row label can sit on the line
above its numbers ("Total External Debt" / "A. 26,941.50 ..." / "(FGN +
States & FCT)"), and a number can wrap onto its own line above the rest of
its row ("47,690.77" / "FGN Only 65,774,356.36 39.44%"). Two structural guards
run on every row: the number count must match the report's columns, and the
naira figure must exceed the dollar figure (a column swap cannot pass).

PERIOD: the quarter of the report's own "as at" date (YYYY-Qn), read from its
title; a document whose title carries no date falls back to its file name.

UNITS AS PRINTED: September 2023 is published in US$ billion and N
trillion; those rows carry those units (read from the report's header). The two
December 2014 uploads are both read; the later upload wins where they differ
(the DMO's revision). "PROVISIONAL" stamps on some issues are not encoded --
the next merge-on-write run keeps the latest published value.

CROSS-CHECK (printed): June 2026 total public debt US$120,932.71m /
N166,788,480.19m; external 45.09%. June 2013 "Total" US$50,905.65m.
December 2022 domestic FGN only N22,210,364.60m.
"""
from __future__ import annotations

import os
import re

import pandas as pd
import pdfplumber

_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july",
     "august", "september", "october", "november", "december"], 1)}
_NUM = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+%?|\d+%")
_STOP = re.compile(r"^(?:\*|note|notes|source|cbn |i+\.|i+\s|central bank|"
                   r"domestic debt stock for|d e b t)", re.I)
_SECTION = re.compile(r"total (external|domestic) debt", re.I)
_SUBLABEL = re.compile(r"^(fgn only|states & fct|fgn \+ states & fct( only)?|"
                       r"external debt)$", re.I)
# Sub-labels differ only in letter case across issues ("FGN only" / "FGN
# Only"); the case is normalised so the series is continuous. Wording is not.
_SUBCASE = {"fgn only": "FGN Only", "states & fct": "States & FCT",
            "fgn + states & fct": "FGN + States & FCT",
            "fgn + states & fct only": "FGN + States & FCT only",
            "external debt": "External Debt"}
# Units are read from each report's own header: September 2023 is printed in
# US$ BILLION and N TRILLION, every other issue in millions.
_USD = {"m": ("USD million", 1.0), "mn": ("USD million", 1.0),
        "bn": ("USD billion", 1e3)}
_NGN = {"m": ("NGN million", 1.0), "mn": ("NGN million", 1.0),
        "bn": ("NGN billion", 1e3), "trn": ("NGN trillion", 1e6)}


def _date(text: str, path: str) -> tuple[int, int]:
    head = " ".join(text.splitlines()[:6])
    pats = [
        r"as at\s+(?:end\s+)?(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})",
        r"as at\s+(?:end\s+)?([A-Za-z]+)\s+(\d{1,2}),?\s+(\d{4})",
        r"as at\s+(?:end\s+)?([A-Za-z]+),?\s+(\d{4})",
    ]
    for p in pats:
        m = re.search(p, head, re.I)
        if m:
            g = m.groups()
            month = next((x for x in g if x and x.lower() in _MONTHS), None)
            if month:
                return int(g[-1]), _MONTHS[month.lower()]
    # Fall back to the slug the DMO gives the file.
    slug = os.path.basename(path).lower()
    m = re.search(r"(january|february|march|april|may|june|july|august|"
                  r"september|october|november|december)-(?:\d{1,2}-)?(\d{4})", slug)
    if not m:
        m2 = re.search(r"(\d{2})-(\d{2})-(\d{4})", slug)
        if m2:
            return int(m2.group(3)), int(m2.group(2))
        raise ValueError(f"DMO: cannot date {os.path.basename(path)}")
    return int(m.group(2)), _MONTHS[m.group(1)]


def _num(tok: str) -> float:
    return float(tok.rstrip("%").replace(",", ""))


def _clean(label: str) -> str:
    # "A. External ..." and, in June 2017, "A External ..." (no dot)
    s = re.sub(r"^[A-Ea-e](?:\.\s*|\s+(?=[A-Z(]))", "", label.strip())
    s = s.replace("*", "").replace("–", "-")
    s = re.sub(r"\s*\(?\s*A\s*\+\s*([BD])\s*\)?\s*$", r" (A+\1)", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    s = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", s))   # "( FCT )" -> "(FCT)"
    return s


def _rows(text: str, where: str):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    start = next((i for i, ln in enumerate(lines)
                  if re.search(r"debt category|^description(?![a-z])", ln, re.I)), None)
    if start is None:
        raise ValueError(f"{where}: no 'Debt Category' / 'Description' header")
    header = " ".join(lines[max(0, start - 3):start + 4])
    ncol = 3 if re.search(r"%\s*of\s*total", header, re.I) else 2
    mu = re.search(r"US\$\s*['’]?\s*(Mn|Bn|M)(?![a-z])", header, re.I)
    mn = re.search(r"\(\s*N\s*['’]?\s*(Trn|Mn|Bn|M)(?![a-z])", header, re.I)
    units = (_USD[(mu.group(1) if mu else "m").lower()],
             _NGN[(mn.group(1) if mn else "m").lower()])

    out, pend_label, pend_nums = [], "", []
    for ln in lines[start + 1:]:
        if _STOP.match(ln):
            break
        nums = _NUM.findall(ln)
        label = ln
        for t in nums:
            label = label.replace(t, " ")
        label = re.sub(r"^[A-Ea-e]\.\s*", "", label.strip()).strip()
        if not nums:
            if re.match(r"^\(?(US\$|N'|N’|\(N|in usd|in ngn|usd|ngn|amount|"
                        r"outstanding|in millions)", label, re.I):
                continue                      # header residue
            if label.startswith("(") and out and not pend_label:
                out[-1][0] = f"{out[-1][0]} {label}"   # "(FGN + States & FCT)"
            else:
                pend_label = f"{pend_label} {label}".strip()
            continue
        if not label and not pend_label and len(nums) < ncol:
            pend_nums += nums                 # a number wrapped above its row
            continue
        label = f"{pend_label} {label}".strip() if not label or pend_label else label
        nums = pend_nums + nums
        pend_label, pend_nums = "", []
        if len(nums) != ncol:
            raise ValueError(f"{where}: row {label!r} has {len(nums)} values "
                             f"for {ncol} columns")
        out.append([label, nums])
    if not out:
        raise ValueError(f"{where}: no rows")
    return out, ncol, units


def _parse_one(path: str) -> list[dict]:
    where = os.path.basename(path)
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    if len(text.strip()) < 40:
        print(f"[nigeria_dmo] {where}: no text layer -- skipped (no OCR)")
        return []
    year, month = _date(text, path)
    period = f"{year}-Q{(month - 1) // 3 + 1}"
    rows, ncol, ((usd_unit, usd_k), (ngn_unit, ngn_k)) = _rows(text, where)

    recs, section = [], ""
    for label, nums in rows:
        lab = _clean(label)
        sec = _SECTION.search(lab)
        if sec:
            section = f"Total {sec.group(1).title()} Debt"
        if _SUBLABEL.match(lab) and section:
            comp = f"{section}: {_SUBCASE[re.sub(r'\s+', ' ', lab.lower())]}"
        else:
            comp = lab
        usd, ngn = _num(nums[0]), _num(nums[1])
        if not ngn * ngn_k > usd * usd_k:
            raise ValueError(f"{where}: {lab!r} naira {ngn} not above dollars "
                             f"{usd} -- columns swapped?")
        for val, unit, meas in ((usd, usd_unit, "stock"),
                                (ngn, ngn_unit, "stock")):
            recs.append(dict(component=comp, period=period, frequency="quarterly",
                             measure=meas, value=val, unit=unit,
                             series_code="DMO total public debt"))
        if ncol == 3:
            recs.append(dict(component=comp, period=period, frequency="quarterly",
                             measure="share", value=_num(nums[2]), unit="percent",
                             series_code="DMO total public debt"))
    return recs


def _doc_id(path: str) -> int:
    m = re.match(r"(\d+)-", os.path.basename(path))
    return int(m.group(1)) if m else 10**9      # the latest-issue primary sorts last


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in sorted([path, *(extras or [])], key=_doc_id):
        rows += _parse_one(p)
    df = pd.DataFrame(rows)
    key = ["component", "period", "frequency", "measure", "unit", "series_code"]
    # A quarter uploaded twice (December 2014): the later upload wins.
    return df.drop_duplicates(key, keep="last").reset_index(drop=True)
