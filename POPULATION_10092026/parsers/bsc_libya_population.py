"""BSC Libya — the Statistical Book (الكتاب الإحصائي), population chapter.

Bureau of Statistics and Census. The book is bilingual: every population table
carries English captions and (for regions) English names beside the Arabic,
so the broken Arabic font mapping that forced labour's Libya layout to state
its labels from rendered pages does not bite here. Tables are found by their
ENGLISH captions:

* "...Libyan Population Residing in Libya and Sex Ratio by Census Years" --
  CENSUS 1984 / 1995 / 2006 by sex (persons) and the sex ratio;
* "Number of The Libyan Population Estimated During 2014 - 2024 per (1000)" --
  ESTIMATES, total, thousands;
* "Libyan Population Estimated by Region for The Year <Y>" -- ESTIMATES by the
  22 regions (mantiqa) and sex, persons;
* "Estimated Distribution of the Libyan Population by Age Group, <Y>" --
  ESTIMATES by 5-year age group and sex, persons.

LIBYAN NATIONALS ONLY. Every table counts "the Libyan population"; resident
foreigners are not in it. The 2006 census total here (5 298 152) is Libyans
residing in Libya.

COLUMN ORDER is right-to-left in print: the text layer gives Total, Female,
Male for the region and age tables, and Male, Female, Total for the census
table (read the other way round). Bound by position and checked: M + F = T on
every row, to +-1 -- three regions and the 85+ row miss by exactly one person
(Ghat 14 830 + 14 936 = 29 766, printed 29 765). Regions sum to the national
Total row to within one person per region (2024: off by 1 / 1 / 2).

AGE LABELS print right-to-left ("4-0", "9-5"); they are written here in
reading order ("0-4", "5-9") -- the same band, not a remapping. The open band
"85فأكثر" is "85+".

THE 2014-2024 TOTAL SERIES IS IN THOUSANDS and its last year duplicates the
region/age tables' Total (7384.2 vs 7 384 208): that year is taken from the
detailed tables only (checked to agree to the rounding), so one key never
carries two figures in two units.

CROSS-CHECK: census 2006 5 298 152 (M 2 687 513 / F 2 610 639), sex ratio
102.9; estimate 2024 7 384 208 (M 3 745 587 / F 3 638 621); Tripoli 1 389 416;
estimate 2014 6 103.1 thousand.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_CAPS = {
    "census": re.compile(r"Libyan Population Residing in Libya and"),
    "series": re.compile(r"Number of The Libyan Population Estimated During "
                         r"(\d{4}) - (\d{4}) per \(1000\)"),
    "region": re.compile(r"Libyan Population Estimated by Region for The Year (\d{4})"),
    "age": re.compile(r"Estimated Distribution of the Libyan Population by Age "
                      r"Group, (\d{4})"),
}


def _row(series, sex, age, geo, period, measure, value, unit, code):
    return {"series_type": series, "sex": sex, "age_group": age,
            "geography": geo, "period": str(period), "frequency": "annual",
            "measure": measure, "value": value, "unit": unit,
            "series_code": code}


def _tfm(t, f, m, where):
    if abs(m + f - t) > 1:
        raise ValueError(f"BSC Libya {where}: {m} + {f} != {t}")
    return [("total", t), ("female", f), ("male", m)]


def parse(path: str) -> pd.DataFrame:
    pages = {}
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[10:40]:
            text = page.extract_text() or ""
            for k, rx in _CAPS.items():
                m = rx.search(text)
                if m and k not in pages:
                    pages[k] = (m, text)
    missing = [k for k in _CAPS if k not in pages]
    if missing:
        raise ValueError(f"BSC Libya: population tables not found: {missing}")
    rows = []

    # Census: "<ratio> 100.00 <%F> <%M> <T> <F> <M> <year>" (right-to-left).
    _, text = pages["census"]
    years = []
    for ln in text.splitlines():
        m = re.fullmatch(r"([\d.]+) 100\.00 [\d.]+ [\d.]+ (\d+) (\d+) (\d+) (19\d\d|20\d\d)",
                         ln.strip())
        if m:
            ratio, t, f, mm, y = m.groups()
            years.append(y)
            for sex, v in _tfm(int(t), int(f), int(mm), f"census {y}"):
                rows.append(_row("census", sex, "Total", "Total country", y,
                                 "count", v, "persons", "BSC SB census"))
            rows.append(_row("census", "total", "Total", "Total country", y,
                             "sex_ratio", float(ratio), "ratio", "BSC SB census"))
    if years != ["1984", "1995", "2006"]:
        raise ValueError(f"BSC Libya census years {years}")

    # Region table: "<English name> <T> <F> <M> <Arabic name>".
    m_reg, text = pages["region"]
    year = m_reg.group(1)
    regions = {}
    for ln in text.splitlines():
        m = re.match(r"^([A-Z][A-Za-z` ]+?) (\d+) (\d+) (\d+)\b", ln.strip())
        if m:
            regions[m.group(1).strip()] = tuple(int(x) for x in m.groups()[1:])
    if "Total" not in regions or len(regions) != 23:
        raise ValueError(f"BSC Libya regions: {len(regions)} rows {list(regions)[:4]}")
    nat = regions.pop("Total")
    for i in range(3):
        # rounded per region: the 2024 book misses by 1 / 1 / 2 persons
        if abs(sum(v[i] for v in regions.values()) - nat[i]) > len(regions):
            raise ValueError("BSC Libya: regions do not sum to the Total row")
    for name, (t, f, m) in regions.items():
        for sex, v in _tfm(t, f, m, name):
            rows.append(_row("estimate", sex, "Total", name, year, "count", v,
                             "persons", f"BSC SB regions {year}"))
    for sex, v in _tfm(*nat, "regions Total"):
        rows.append(_row("estimate", sex, "Total", "Total country", year,
                         "count", v, "persons", f"BSC SB regions {year}"))

    # Age table: "<T> <F> <M> <band printed right-to-left>", Total row last.
    m_age, text = pages["age"]
    if m_age.group(1) != year:
        raise ValueError("BSC Libya: age and region tables are different years")
    ages = []
    for ln in text.splitlines():
        m = re.fullmatch(r"(\d+) (\d+) (\d+)(?: (.+))?", ln.strip())
        if not m:
            continue
        t, f, mm, lab = int(m.group(1)), int(m.group(2)), int(m.group(3)), m.group(4)
        if lab is None:                               # the Total row
            if (t, f, mm) != nat:
                raise ValueError("BSC Libya: age Total != regions Total")
            continue
        r = re.fullmatch(r"(\d+)-(\d+)", lab)
        if r:
            band = f"{r.group(2)}-{r.group(1)}"        # "4-0" -> "0-4"
        elif re.search(r"85", lab):
            band = "85+"
        else:
            raise ValueError(f"BSC Libya: unreadable age label {lab!r}")
        ages.append(band)
        for sex, v in _tfm(t, f, mm, band):
            rows.append(_row("estimate", sex, band, "Total country", year,
                             "count", v, "persons", f"BSC SB age {year}"))
    if len(ages) != 18 or ages[0] != "0-4" or ages[-1] != "85+":
        raise ValueError(f"BSC Libya: age bands {ages}")

    # The 2014-<Y> total series (thousands); its last year is the detailed
    # tables' Total and is taken from those instead.
    m_ser, text = pages["series"]
    lines = [ln.strip() for ln in text.splitlines()]
    yi = next(i for i, ln in enumerate(lines) if re.fullmatch(r"(20\d\d ?)+", ln))
    # bilingual row labels ("Year", "Total") sit between the year row and the
    # value row, so take the first all-decimal line after the years
    vi = next(i for i in range(yi + 1, len(lines))
              if re.fullmatch(r"(\d+\.\d ?)+", lines[i]))
    yrs, vals = lines[yi].split(), lines[vi].split()
    if len(yrs) != len(vals):
        raise ValueError("BSC Libya: series years and values differ in count")
    for y, v in zip(yrs, vals):
        v = float(v)
        if y == year:
            if abs(v * 1000 - nat[0]) > 100:
                raise ValueError(f"BSC Libya: {y} series {v} vs table {nat[0]}")
            continue
        rows.append(_row("estimate", "total", "Total", "Total country", y,
                         "count", v, "thousand_persons", "BSC SB series"))
    return pd.DataFrame(rows)
