"""Mozambique — INE "Projecções da População 2017-2050" (IV RGPH 2017 base),
one .xls workbook for the country and one per province.

WHERE IT IS. INE's Liferay document library, folder 92163 ("Projecções da
população 2017 - 2050", reached from the Censo 2017 page). The folder page
shows one entry at a time and the headless API answers 403, so each file's
download path (/documents/20119/92163/<name>.xls/<uuid>) was read off its
`view_file/<id>` page; the descriptor pins the twelve. Mozambique had been
recorded as rejected ("no population file surfaced") -- the files are there,
behind the census page rather than under Estatísticas > Demográficas.

WHAT IS READ. Each workbook has a sheet per year, "2017" .. "2050" (QUADRO
1..34, "População projectada por área de residência e sexo segundo idade.
<Geography>, <year>"): five-year age groups 0-4 .. 80+ and Total, by sex
(Total / Homens / Mulheres), for TOTAL / URBANA / RURAL.

* Taken: the TOTAL residence block -- 17 five-year bands + Total, three sexes,
  34 years, for Moçambique ("Total country") and the 11 provinces, named as
  each sheet's own title prints them.
* Not taken: the URBANA / RURAL blocks (this schema has no residence column;
  filing them as geographies would invent places), and the "Grupos etários
  seleccionados" block (0, 1-4, 0-14, 15-24, 15-44, 15-49, 15-64, 50-64, 55+,
  ...) -- overlapping analytical bands that are sums of the five-year bands.
* "Quadro resumo" (totals by year) repeats the year sheets' Total row and is
  used as a check, not emitted.

CHECKS, every run: each sheet's bands sum to its Total for each sex; Homens +
Mulheres = Total on every row; the Quadro resumo equals the year sheets; and
the 11 provinces sum to Moçambique for every year and sex (a difference of a
few persons from independent rounding is allowed and reported).

TWO CAPTION SLIPS, NOT DATA ERRORS: Sofala's 2050 table is captioned
"Indicadores" (accepted only with the age-table layout and a matching sheet
name), and Manica's 2034 Total row is labelled "Q19" (the first data row is
the Total and is held to its bands). Sheet names vary by workbook ("2017",
" 2017", "Q1_2017"), so year tables are found and dated by their titles.

A SLIP IN INE'S INDEX, NOT IN THE DATA: the national workbook's index sheet
captions its summary "QUADRO 00 ... Niassa, 2017-2050" (copied from the Niassa
workbook); the summary sheet itself is titled Moçambique and its values are
national. Geography is taken from each data sheet's own title.

CROSS-CHECK: Moçambique 2017 27,864,265 (13,394,977 H / 14,469,288 M); 2025
34,090,466 (= yearbook Quadro 2.1.1's 34 090 thousand); Niassa 2050 4,773,510.
"""
from __future__ import annotations

import os
import re

import pandas as pd

_TITLE = re.compile(r"segundo\s+idade\.\s*(.+?),\s*(20\d\d)\s*$")
_MISCAPTION = re.compile(r"QUADRO\s+\d+\.?\s+Indicadores\.\s*(.+?),\s*(20\d\d)\s*$")
_BAND = re.compile(r"^\d{1,2}\s*-\s*\d{1,2}$|^80\+$")


def _read_book(path: str) -> tuple[str, list[dict], dict]:
    xl = pd.ExcelFile(path)
    geo, rows = None, []
    seen_years = set()
    for sheet in xl.sheet_names:
        # SHEET NAMES ARE NOT CONSISTENT across the twelve workbooks ("2017",
        # " 2017", "Q1_2017", "Q2 2018"), so a year sheet is recognised by its
        # own title, and dated by it.
        if sheet.strip().lower().startswith(("indice", "quadro resumo",
                                             "indicadores", "quadro 0")):
            continue
        df = pd.read_excel(path, sheet_name=sheet, header=None, dtype=object)
        title = str(df.iat[0, 0]).strip()
        m = _TITLE.search(title)
        if not m:
            # Sofala's 2050 table is MIS-CAPTIONED "QUADRO 34. Indicadores.
            # Sofala, 2050" (the next sheet is the real indicators table).
            # Accepted only when the sheet is laid out as an age table AND its
            # own sheet name agrees with the caption's year.
            m = _MISCAPTION.search(title)
            if not (m and str(df.iat[1, 0]).strip() == "Idade"
                    and sheet.strip() == m.group(2)):
                raise ValueError(f"INE MZ {os.path.basename(path)} sheet "
                                 f"{sheet!r}: title {title!r}")
        g = m.group(1).strip()
        year = m.group(2)
        if year in seen_years:
            raise ValueError(f"INE MZ {g}: year {year} printed twice")
        seen_years.add(year)
        sheet = year
        if geo is None:
            geo = g
        elif g != geo:
            raise ValueError(f"INE MZ {os.path.basename(path)}: sheet {sheet} "
                             f"names {g!r}, earlier sheets {geo!r}")
        hdr = [str(v).strip().upper() for v in df.iloc[1].tolist()]
        sexes = [str(v).strip() for v in df.iloc[2].tolist()]
        # Maputo Cidade is entirely urban: one block headed "População" instead
        # of TOTAL / URBANA / RURAL. Its first three columns are the same.
        if hdr[1] not in ("TOTAL", "POPULAÇÃO") \
                or sexes[1:4] != ["Total", "Homens", "Mulheres"]:
            raise ValueError(f"INE MZ {g} {sheet}: unexpected header {hdr[:4]} "
                             f"{sexes[:4]}")
        block = {}
        for r in range(3, len(df)):
            lab = str(df.iat[r, 0]).strip()
            if lab.startswith("Grupos"):
                break
            band = re.sub(r"\s+", "", lab)
            # The first data row IS the Total row, however it is labelled:
            # Manica's 2034 sheet labels it "Q19". It is still held to the sum
            # of its bands below, so a wrong row cannot pass as the Total.
            if r == 3 and lab != "Total":
                lab = "Total"
            if lab == "Total" or _BAND.match(lab):
                t, h, mu = (float(df.iat[r, c]) for c in (1, 2, 3))
                if h + mu != t:
                    raise ValueError(f"INE MZ {g} {sheet} {band}: {h}+{mu} != {t}")
                block["Total" if lab == "Total" else band] = (t, h, mu)
        bands = [b for b in block if b != "Total"]
        if len(bands) != 17 or "Total" not in block:
            raise ValueError(f"INE MZ {g} {sheet}: {len(bands)} bands")
        for i, sex in enumerate(("total", "male", "female")):
            s = sum(block[b][i] for b in bands)
            if s != block["Total"][i]:
                raise ValueError(f"INE MZ {g} {sheet} {sex}: bands {s} != Total "
                                 f"{block['Total'][i]}")
        for band, vals in block.items():
            for sex, v in zip(("total", "male", "female"), vals):
                rows.append({"geo": g, "year": sheet, "age_group": band,
                             "sex": sex, "value": v})
    # Quadro resumo: the year sheets' Total rows, restated.
    resumo = {}
    for sheet in xl.sheet_names:
        if sheet.lower().startswith("quadro resumo"):
            df = pd.read_excel(path, sheet_name=sheet, header=None, dtype=object)
            for r in range(3, len(df)):
                y = str(df.iat[r, 0]).strip()
                if re.fullmatch(r"20\d\d", y):
                    resumo[y] = tuple(float(df.iat[r, c]) for c in (1, 2, 3))
    return geo, rows, resumo


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    all_rows, per_geo = [], {}
    for path in [local_path, *(extras or [])]:
        geo, rows, resumo = _read_book(path)
        years = sorted({r["year"] for r in rows})
        if years != [str(y) for y in range(2017, 2051)]:
            raise ValueError(f"INE MZ {geo}: years {years[:3]}..{years[-3:]}")
        tot = {(r["year"], r["sex"]): r["value"] for r in rows
               if r["age_group"] == "Total"}
        for y, vals in resumo.items():
            for sex, v in zip(("total", "male", "female"), vals):
                if tot.get((y, sex)) != v:
                    raise ValueError(f"INE MZ {geo} {y} {sex}: Quadro resumo {v} "
                                     f"!= year sheet {tot.get((y, sex))}")
        per_geo[geo] = tot
        all_rows += rows
    national = [g for g in per_geo if g.startswith("Mo")]
    if len(national) != 1 or len(per_geo) != 12:
        raise ValueError(f"INE MZ: geographies {sorted(per_geo)}")
    nat = national[0]
    for key, v in per_geo[nat].items():
        s = sum(t[key] for g, t in per_geo.items() if g != nat)
        if abs(s - v) > 50:
            raise ValueError(f"INE MZ {key}: provinces sum {s} vs {nat} {v}")
    out = []
    for r in all_rows:
        out.append({"series_type": "projection", "sex": r["sex"],
                    "age_group": r["age_group"],
                    "geography": "Total country" if r["geo"] == nat else r["geo"],
                    "period": r["year"], "frequency": "annual",
                    "measure": "count", "value": r["value"], "unit": "persons",
                    "series_code": "INE-MZ Projecções 2017-2050"})
    return pd.DataFrame(out)
