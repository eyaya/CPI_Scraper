"""Tanzania NBS 2022 Population & Housing Census — Tier-3 report-PDF parser.

Two clean text tables of the "URT Demographic and Socio-Economic Profile" report:

* Table 3.1 — national population by five-year age group and sex (2022);
* Table 2.2 — population by region for the 2002, 2012 and 2022 censuses.

Table 3.1 gives the age structure (national); Table 2.2 gives the sub-national
head counts across the three census years. Everything is emitted as published;
the rural/urban split (Tables 3.2/3.3) and the aggregate rows of Table 2.2 are
left out (locality / national aggregates). Hand-typed dashes are normalised.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_HEADER = "Number and Percentage Distribution of Population by Sex and Five-Year Age"
_AGE_RE = re.compile(r"^(Total|\d{1,2}[–—�-]\d{1,2}|\d{1,2}\+)$")
_NUM_RE = re.compile(r"^\d[\d,]*(?:\.\d+)?$")

# rows of Table 2.2 that are national / locality / mainland-zanzibar aggregates,
# not a region.
_AGG = {"Tanzania", "Rural", "Urban", "Tanzania Mainland", "Tanzania Zanzibar", "Zanzibar"}
_CENSUS_YEARS = ("2002", "2012", "2022")
_REGION_RE = re.compile(r"^([A-Za-z][A-Za-z .'-]+?)\s+([\d,]{4,})\s+([\d,]{4,})\s+([\d,]{4,})\b")


def _row(sex, age, geo, period, value):
    return {"series_type": "census", "sex": sex, "age_group": age, "geography": geo,
            "period": period, "frequency": "annual", "measure": "count",
            "value": value, "unit": "persons", "series_code": "PHC2022"}


def _find_page(pdf, needle, extra, lo, hi):
    n = len(pdf.pages)
    order = list(range(lo, min(hi, n))) + [i for i in range(n) if i < lo or i >= hi]
    for idx in order:
        t = pdf.pages[idx].extract_text() or ""
        if needle in t and extra in t:
            return t
    return None


def _parse_national(text: str) -> list[dict]:
    start = text.find("Table 3. 1")
    end = text.find("Median Age", start)
    block = text[start:end if end > 0 else len(text)]
    rows = []
    for line in block.splitlines():
        toks = line.split()
        if not toks or not _AGE_RE.match(toks[0]):
            continue
        nums = [t.replace(",", "") for t in toks[1:] if _NUM_RE.match(t)]
        if len(nums) < 6:
            continue
        age = "Total" if toks[0] == "Total" else re.sub(r"[–—�]", "-", toks[0])
        for sex, i in (("total", 0), ("male", 2), ("female", 4)):
            rows.append(_row(sex, age, "Total country", "2022", float(nums[i])))
    return rows


def _parse_regions(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        m = _REGION_RE.match(line)
        if not m:
            continue
        name = m.group(1).strip()
        if name in _AGG:
            continue
        for yr, g in zip(_CENSUS_YEARS, (m.group(2), m.group(3), m.group(4))):
            rows.append(_row("total", "Total", name, yr, float(g.replace(",", ""))))
    return rows


def parse(local_path: str) -> pd.DataFrame:
    with pdfplumber.open(local_path) as pdf:
        nat = _find_page(pdf, "Table 3. 1", "; Tanzania,", 55, 75)
        reg = _find_page(pdf, "Table 2. 2", "by Place of Residence and Region", 45, 60)
    if nat is None:
        raise ValueError("nbs_tanzania_population: Table 3.1 (national) not found")

    rows = _parse_national(nat)
    if reg is not None:
        rows += _parse_regions(reg)

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError("nbs_tanzania_population: no rows parsed")
    return df.drop_duplicates(["geography", "sex", "age_group", "period"])
