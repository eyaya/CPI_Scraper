"""São Tomé and Príncipe — INE "Projecções Demográficas 2012-2035" (base IV
RGPH 2012), a PDF in ine.st's "Dados Localidade e Projecções" category.

THE REJECTION WAS STALE LINKS, NOT A MISSING SOURCE. São Tomé was recorded as
rejected because the demography category's preview paths 404. The projections
report sits in category 76 ("dados-localidade-projecoes") at a working
/phocadownload/userupload/ path.

WHAT IS READ:

* Tabela II.04 / II.04a  national population by five-year age group (0-4 ..
  80+) and Total, by sex, 2012-2035 -> `projection` (2012 is the base year,
  equal to the census count);
* Tabela III.38  population by district / region (6 districts + Região
  Autónoma do Príncipe, "RAP"), by sex: the RGPH-2001 and RGPH-2012 columns
  -> `census`, 2013-2035 -> `projection`;
* Tabelas III.39-III.45  each district / RAP by five-year age group (0-4 ..
  70+) x sex, 2001 and 2012 (`census`) and 2013-2035 (`projection`).

The district tables' Total rows repeat III.38 and are checks, not emitted;
III.38's Total row repeats II.04's.

NOT READ: II.05-II.05g (by residence -- no residence column here); II.06-II.37
(special age groups and single years overlapping the five-year bands); the
indicator summaries II.01/II.02.

READING. Numbers use a DOT thousands separator ("27.720" = 27,720). Column
order is NOT constant: II.04 prints Total / Masc. / Fem., III.38-III.45 print
Homens / Mulheres / Total -- each table's header binds the columns. Year
headers can be letter-spaced or mistyped ("2021 2022 203 2024 2025" in
Mé-Zóchi's table): a lone malformed token between two years exactly two apart
is read as the year between them, and that year's figures are then held to
III.38. Chapter IV's prose follows III.45 with no caption between, so a year
header must be a line of years only, and a data row needs three or more
values. District names follow III.38 ("Agua Grande", "Me-Zochi", "RAP").

CHECKS: male + female = total on every row (within 2, independent rounding);
each year's bands = its Total row (within 5); districts = national (within 5);
each district age table's Total = III.38's figure for that district and year.

WITHHELD, NOT SMOOTHED: where a district age table's Total disagrees with
III.38, that district-year's age bands are NOT collected (the III.38 total
still is). Fourteen district-years in two tables:
  * Mé-Zóchi (III.40, which also mistypes a year header) -- 2018 (50.812 vs
    50.821), 2020 (54.786 vs 52.967) and 2021 (30.000 vs 54.076; its 0-4 row
    prints males as 408);
  * Lobata (III.44) 2018-2028 -- the columns are SHIFTED one year (its "2018"
    is III.38's 2019, ... its "2027" is 2028) and its "2028" repeats its 2026
    figures (26.480): the real 2018 column is missing. Relabelling the columns
    would be inference, so the eleven years are withheld.
Each block adds up internally, so nothing but the cross-table check catches it. `_WITHHELD` pins the set: the
parse raises if it grows or shrinks, so a corrected reissue is noticed.

CROSS-CHECK: 2012 178.739 (88.867 M / 89.872 F); 2001 census 137.599; Água
Grande 2012 census 69.454; Me-Zochi 2035 71.644.
"""
from __future__ import annotations

import re
import sys

import pandas as pd
import pdfplumber

_NUMTOK = re.compile(r"^\d{1,3}(?:\.\d{3})*$")
_YEAR = re.compile(r"^(?:19|20)\d\d$")
_CAP_NAT = re.compile(r"^Tabela II\.04a?:")
_CAP_DISTRICTS = re.compile(r"^Tabela III\.38:")
_CAP_DISTRICT = re.compile(r"^Tabela III\.(39|4[0-5]):.*?(?:distrito de|Região "
                           r"Autónoma do)\s+(.+?)\s+no horizonte")
_CAP_ANY = re.compile(r"^Tabela [IVX]+\.\d+")
_HEADER = re.compile(r"(?:(?:Ano|Idade|Distrito)\s+)?(?:(?:RGPH-)?\d{3,4}\s*)+")
_DISTRICT_NAME = {"Água Grande": "Agua Grande", "Mé-Zóchi": "Me-Zochi",
                  "Cantagalo": "Cantagalo", "Caué": "Caue", "Lembá": "Lemba",
                  "Lobata": "Lobata", "Príncipe": "RAP"}
# district-years whose age tables contradict III.38 (see the module docstring)
_WITHHELD = ({("Me-Zochi", "2018"), ("Me-Zochi", "2020"), ("Me-Zochi", "2021")}
             | {("Lobata", str(y)) for y in range(2018, 2029)})


def _num(t: str) -> float:
    return float(t.replace(".", ""))


def _order(line: str):
    s = line.replace(" ", "").lower()
    if s.startswith(("idade", "ano")) and "totalmasc" in s:
        return ("total", "male", "female")
    if "homensmulherestotal" in s:
        return ("male", "female", "total")
    return None


def _years(s: str) -> list[str] | None:
    if not _HEADER.fullmatch(s):
        return None
    toks = re.findall(r"\d{3,4}", s)
    packed = re.sub(r"\D", "", s)
    if re.fullmatch(r"[\d ]+", s) and len(packed) % 4 == 0 and all(
            _YEAR.match(packed[i:i + 4]) for i in range(0, len(packed), 4)):
        return [packed[i:i + 4] for i in range(0, len(packed), 4)]
    bad = [i for i, t in enumerate(toks) if not _YEAR.match(t)]
    if not bad:
        return toks
    if len(bad) == 1 and 0 < bad[0] < len(toks) - 1 \
            and int(toks[bad[0] + 1]) - int(toks[bad[0] - 1]) == 2:
        toks[bad[0]] = str(int(toks[bad[0] - 1]) + 1)       # "203" -> 2023
        return toks
    return None


def _read(pages: list[str]) -> pd.DataFrame:
    rows, table, geo, order, years = [], None, None, None, []
    for text in pages:
        for ln in text.splitlines():
            s = ln.strip()
            if _CAP_ANY.match(s):
                table, years, order = None, [], None
                if _CAP_NAT.match(s):
                    table, geo = "II.04", "Total country"
                elif _CAP_DISTRICTS.match(s):
                    table, geo = "III.38", None
                else:
                    m = _CAP_DISTRICT.match(s)
                    if m:
                        name = m.group(2).strip()
                        table = f"III.{m.group(1)}"
                        geo = _DISTRICT_NAME.get(name, name)
                continue
            if table is None:
                continue
            order = _order(s) or order
            ys = _years(s)
            if ys:
                years = ys
                continue
            toks = s.split()
            nums = []
            while toks and _NUMTOK.match(toks[-1]):
                nums.insert(0, toks.pop())
            label = " ".join(toks)
            if not label or len(nums) < 3 or not years or label.startswith("Ano"):
                continue
            if len(nums) != 3 * len(years):
                raise ValueError(f"INE STP {table}: {len(nums)} values for "
                                 f"{years}: {s!r}")
            cols = order or ("male", "female", "total")    # III.38+ header wraps
            vals = [_num(n) for n in nums]
            for i, y in enumerate(years):
                d = dict(zip(cols, vals[3 * i:3 * i + 3]))
                if abs(d["male"] + d["female"] - d["total"]) > 2:
                    raise ValueError(f"INE STP {table} {label} {y}: M+F != T")
                rows.append({"table": table, "label": label, "geo": geo,
                             "year": y, **d})
    return pd.DataFrame(rows)


def _bands_add_up(frame: pd.DataFrame, what: str) -> None:
    for (g, y), grp in frame.groupby(["geo", "year"]):
        tot = grp[grp.label == "Total"]
        band = grp[grp.label != "Total"]
        if len(tot) != 1:
            raise ValueError(f"INE STP {what} {g} {y}: {len(tot)} Total rows")
        for sex in ("male", "female", "total"):
            if abs(band[sex].sum() - tot[sex].iloc[0]) > 5:
                raise ValueError(f"INE STP {what} {g} {y} {sex}: bands "
                                 f"{band[sex].sum()} != {tot[sex].iloc[0]}")


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    with pdfplumber.open(local_path) as pdf:
        df = _read([p.extract_text() or "" for p in pdf.pages])
    nat = df[df.table == "II.04"]
    dist = df[df.table == "III.38"]
    ages = df[df.table.str.match(r"III\.(39|4[0-5])$")]

    years = sorted(nat.year.unique())
    if years != [str(y) for y in range(2012, 2036)]:
        raise ValueError(f"INE STP II.04: years {years}")
    want = ["Agua Grande", "Caue", "Cantagalo", "Lemba", "Lobata", "Me-Zochi", "RAP"]
    if sorted(set(dist.label) - {"Total"}) != sorted(want):
        raise ValueError(f"INE STP III.38: rows {sorted(dist.label.unique())}")
    if sorted(ages.geo.unique()) != sorted(want):
        raise ValueError(f"INE STP III.39-45: districts {sorted(ages.geo.unique())}")

    _bands_add_up(nat, "II.04")
    _bands_add_up(ages, "III.39-45")

    for y, grp in dist.groupby("year"):
        tot = grp[grp.label == "Total"].iloc[0]
        parts = grp[grp.label != "Total"]
        for sex in ("male", "female", "total"):
            if abs(parts[sex].sum() - tot[sex]) > 5:
                raise ValueError(f"INE STP III.38 {y} {sex}: districts sum "
                                 f"{parts[sex].sum()} != {tot[sex]}")
            if y in years:
                n = nat[(nat.year == y) & (nat.label == "Total")][sex].iloc[0]
                if abs(n - tot[sex]) > 5:
                    raise ValueError(f"INE STP {y} {sex}: III.38 {tot[sex]} != "
                                     f"II.04 {n}")

    # district age tables against III.38: disagreeing district-years withheld
    withheld = set()
    for _, r in ages[ages.label == "Total"].iterrows():
        d = dist[(dist.label == r.geo) & (dist.year == r.year)]
        if len(d) != 1:
            raise ValueError(f"INE STP III.38 has no {r.geo} {r.year}")
        if abs(d.total.iloc[0] - r.total) > 5:
            withheld.add((r.geo, r.year))
    if withheld != _WITHHELD:
        raise ValueError(f"INE STP: district-years contradicting III.38 are now "
                         f"{sorted(withheld)}, pinned {sorted(_WITHHELD)}")
    for g, y in sorted(withheld):
        print(f"[sao_tome] {g} {y}: age table contradicts III.38 -- age bands "
              f"withheld", file=sys.stderr)

    out = []

    def emit(r, age, geo, series):
        for sex in ("male", "female", "total"):
            out.append({"series_type": series, "sex": sex, "age_group": age,
                        "geography": geo, "period": r["year"], "frequency": "annual",
                        "measure": "count", "value": r[sex], "unit": "persons",
                        "series_code": f"INE-STP Projecções 2012-2035 T{r['table']}"})

    for _, r in nat.iterrows():
        emit(r, r["label"], "Total country", "projection")
    for _, r in dist[dist.label != "Total"].iterrows():
        emit(r, "Total", r["label"],
             "census" if r["year"] in ("2001", "2012") else "projection")
    for _, r in ages[ages.label != "Total"].iterrows():
        if (r["geo"], r["year"]) in withheld:
            continue
        emit(r, r["label"], r["geo"],
             "census" if r["year"] in ("2001", "2012") else "projection")
    return pd.DataFrame(out)
