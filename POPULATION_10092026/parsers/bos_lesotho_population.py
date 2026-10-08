"""Lesotho — BOS "Lesotho Population Projections Report 2016-2036" (medium
variant), a PDF inside a ZIP.

FOUND THROUGH THE BROWSER-BUILT CATALOGUE. bos.gov.ls lists its publications in
a JavaScript array inside publications.htm, so a crawler sees no link -- which
is why Lesotho was recorded as rejected ("census.htm has only policy PDFs").
The array lists the projections report and the 2016 census analytical volumes
under /Bos_Reports/Copy%20of%20Demography/.

Two tables, both medium variant, series_type `projection`, 2016-2036:

* Table 5.2  national population by five-year age group x sex, 21 years;
* Table 5.6  the ten districts by five-year age group x sex, 21 years.

Table 5.7 (district totals by year) repeats Table 5.6's Total rows; it is used
as a check, not emitted.

READ BY LINE, ACROSS PAGES. Table 5.6's continuation pages carry only the
district name, not the caption, so a table is read from its first caption page
until another Table 5.x opens; Berea's year header is letter-spaced ("20 24 20
25 ...") and is rejoined. Each page holds year blocks of 3 (5.2) or 4 (5.6) years; the
year header line dates the columns, and every data row must carry exactly
3 x (number of years) values -- Male, Female, Both Sexes per year, the order
the header prints. Every row is held to Male + Female = Both Sexes (within 2:
the projections are rounded independently, e.g. 2017 50-54 prints 32,123 +
39,055 = 71,177), and every year's age bands to the printed Total (within 10).

A PUBLISHED DEFECT, PINNED: in Table 5.2 the 2016 "70+" row prints
12,007 / 18,785 / 30,792 -- the 70-74 band, not 70+ -- against 29,087 / 57,296
for 2017; the 2016 bands then sum to 1,951,616 against the printed Total
2,007,201 (55,585 short). That one row is not collected (`_KNOWN_BAD`), and
the check that finds it raises if anything else fails to add up, so a
corrected reissue is noticed.

Age bands are kept as printed ("00-04", "70+"); district names as Table 5.6
prints them (upper case).

CROSS-CHECK: Total 2016 2,007,201 (982,133 M / 1,025,068 F); 2036 Maseru
716,773 (Table 5.7); Botha-Bothe 2016 118,242.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_T52 = "Table 5.2: Projected National Population by Five"
_T56 = "Table 5.6: District Population Projections by five-year"
_T57 = "Table 5.7: Summary District Projections"
_YEARS = re.compile(r"^(?:20\d\d\s*)+$")
_ROW = re.compile(r"^(\d\d\s*-\s*\d\d|70\+|Total)\s+((?:[\d,]+\s*)+)$")
_DISTRICT = re.compile(r"^[A-Z][A-Z' ’-]+$")
# (table, year, age band): rows printed wrongly and left out, re-checked
_KNOWN_BAD = {("5.2", "2016", "70+")}


def _num(s: str) -> float:
    return float(s.replace(",", ""))


_NEXT_TABLE = re.compile(r"^Table 5\.(\d)", re.M)


def _read(pdf, caption: str, table: str, district_blocks: bool) -> list[dict]:
    """From the first page carrying `caption` (not the contents page) until a
    page opens a DIFFERENT Table 5.x -- continuation pages of 5.6 carry only
    the district name, not the caption."""
    rows, years, geo, on = [], [], "Total country", False
    for page in pdf.pages:
        text = page.extract_text() or ""
        if "TABLE OF CONTENTS" in text or "...." in text:
            continue
        if caption in text:
            on = True
        elif on and any(m.group(1) != table[-1] for m in _NEXT_TABLE.finditer(text)):
            break
        if not on:
            continue
        for ln in text.splitlines():
            s = ln.strip()
            # Year headers are letter-spaced irregularly: "20 24 20 25 ..."
            # (Berea), "20 20 20 21 20 22 2 023" (Qacha's Nek). A line of only
            # digits and spaces that collapses into 4-digit chunks, each a
            # 20xx year, is a year header however it was spaced.
            packed = s.replace(" ", "")
            if (re.fullmatch(r"[\d ]+", s) and len(packed) % 4 == 0
                    and all(packed[i:i + 2] == "20"
                            for i in range(0, len(packed), 4))):
                years = [packed[i:i + 4] for i in range(0, len(packed), 4)]
                continue
            if district_blocks and _DISTRICT.match(s) and not s.startswith("TABLE"):
                geo = s
                continue
            m = _ROW.match(s)
            if not m or not years:
                continue
            vals = [_num(v) for v in m.group(2).split()]
            if len(vals) != 3 * len(years):
                raise ValueError(f"BOS Lesotho T{table} {geo}: {len(vals)} values "
                                 f"for years {years}: {s!r}")
            band = re.sub(r"\s+", "", m.group(1))
            for i, y in enumerate(years):
                male, female, both = vals[3 * i:3 * i + 3]
                if abs(male + female - both) > 2:     # independent rounding
                    raise ValueError(f"BOS Lesotho T{table} {geo} {y} {band}: "
                                     f"{male}+{female} != {both}")
                rows.append({"table": table, "geography": geo, "year": y,
                             "age_group": band, "male": male, "female": female,
                             "total": both})
    return rows


def _check_and_drop(rows: list[dict], table: str) -> list[dict]:
    df = pd.DataFrame(rows)
    keep = []
    for (geo, y), g in df.groupby(["geography", "year"]):
        tot = g[g.age_group == "Total"]
        bands = g[g.age_group != "Total"]
        if len(tot) != 1:
            raise ValueError(f"BOS Lesotho T{table} {geo} {y}: {len(tot)} Total rows")
        bad = {(table, y, a) for a in bands.age_group} & _KNOWN_BAD
        if bad:
            ok = bands[~bands.age_group.isin({a for _, _, a in bad})]
            # the defect must still be there, or it has been corrected
            if abs(bands.total.sum() - tot.total.iloc[0]) <= 10:
                raise ValueError(f"BOS Lesotho T{table} {y}: bands now add up -- "
                                 f"remove {bad} from _KNOWN_BAD")
            keep.append(tot)
            keep.append(ok)
            continue
        for sex in ("male", "female", "total"):
            if abs(bands[sex].sum() - tot[sex].iloc[0]) > 10:   # rounding across 15 bands
                raise ValueError(f"BOS Lesotho T{table} {geo} {y} {sex}: bands sum "
                                 f"{bands[sex].sum()} != Total {tot[sex].iloc[0]}")
        keep.append(g)
    return pd.concat(keep).to_dict("records")


def _summary_totals(pdf) -> dict[tuple[str, str], float]:
    """Table 5.7, district totals by year -- a check on Table 5.6."""
    out = {}
    for page in pdf.pages:
        text = page.extract_text() or ""
        if _T57 not in text:
            continue
        for ln in text.splitlines():
            m = re.match(r"^(20\d\d)\s+((?:[\d,]+\s+){9}[\d,]+)$", ln.strip())
            if m:
                for i, v in enumerate(m.group(2).split()):
                    out[(m.group(1), i)] = _num(v)
    return out


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    with pdfplumber.open(local_path) as pdf:
        nat = _check_and_drop(_read(pdf, _T52, "5.2", False), "5.2")
        dist_raw = _read(pdf, _T56, "5.6", True)
        dist = _check_and_drop(dist_raw, "5.6")
        summ = _summary_totals(pdf)
    # PRINTED order (Table 5.7's columns follow it), not the checked rows'
    # order, which groupby has sorted alphabetically.
    geos = list(dict.fromkeys(r["geography"] for r in dist_raw))
    if len(geos) != 10:
        raise ValueError(f"BOS Lesotho T5.6: {len(geos)} districts {geos}")
    years = sorted({r["year"] for r in nat})
    if years != [str(y) for y in range(2016, 2037)]:
        raise ValueError(f"BOS Lesotho T5.2: years {years}")
    # Table 5.7 lists the districts in Table 5.6's order.
    for r in dist:
        if r["age_group"] == "Total":
            want = summ.get((r["year"], geos.index(r["geography"])))
            if want is not None and want != r["total"]:
                raise ValueError(f"BOS Lesotho: T5.6 {r['geography']} {r['year']} "
                                 f"{r['total']} != T5.7 {want}")
    out = []
    for r in nat + dist:
        for sex in ("male", "female", "total"):
            out.append({"series_type": "projection", "sex": sex,
                        "age_group": r["age_group"], "geography": r["geography"],
                        "period": r["year"], "frequency": "annual",
                        "measure": "count", "value": r[sex], "unit": "persons",
                        "series_code": f"BOS-PROJ-2016-2036 T{r['table']}"})
    return pd.DataFrame(out)
