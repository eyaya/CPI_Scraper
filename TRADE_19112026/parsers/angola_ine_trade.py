"""Parser for Angola merchandise trade -- Instituto Nacional de Estatística
(INE), "Comércio Internacional" workbooks (ine.gov.ao, directory tree
Publicações > Comércio Internacional > Mensal / Anual, downloaded by POST).

Each workbook has four sheets: exports and imports (or re-exports and
re-imports), in kwanzas and in US dollars; the caption's "U.M." gives the
scale ("milhões de kwanzas", "milhares de USD"), read per sheet.
  * por Secções e Capítulos: HS sections ("Secção I", national with the roman
    code) and chapters ("Cap. 01" -> hs2), and the "Total Geral";
  * por Países Parceiros: every partner (ISO2 code printed; "Desconhecido" =
    unknown, a group);
  * por Grandes Categorias Económicas: BEC categories (bec, printed code);
  * por Reexportação e Reimportação (annual): re-exports by section/chapter
    (re-imports have no flow in the schema and are not taken).
The monthly workbooks run January 2004 - the latest month, with quarters
("I TRIM") and annual columns ("Ano 2004"); the annual workbooks repeat the
annual columns. Exact zeros are not emitted (empty cells of the partner x month
and chapter x month grids).
"""
from __future__ import annotations

import os
import re
import warnings

import pandas as pd

from ._common import row

_MON = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9,
        "out": 10, "nov": 11, "dez": 12}
_Q = {"i": 1, "ii": 2, "iii": 3, "iv": 4}


def _num(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def _sheet(df, base, sheet) -> list[dict]:
    rows = []
    cap = str(df.iat[0, 0]) + " " + str(df.iat[0, 1] if df.shape[1] > 1 else "")
    um = " ".join(str(v) for v in df.iloc[1, :3].tolist()).lower()
    capl = cap.lower()
    if "reimporta" in capl:
        return rows
    flow = "re_export" if "reexporta" in capl else "export" if "exporta" in capl else \
        "import" if "importa" in capl else None
    cur = "AOA" if "kwanza" in um else "USD" if ("usd" in um or "dólar" in um or "dolar" in um) else None
    mult = 1e6 if "milh" in um and "milhares" not in um else 1e3 if "milhares" in um else None
    if not flow or not cur or not mult:
        return rows
    kind = "section" if "secç" in capl or "secc" in capl else "partner" if "países" in capl or "paises" in capl \
        else "bec" if "categorias" in capl else None
    if not kind:
        return rows
    # columns -> (period, frequency)
    cols, year = {}, None
    for j in range(df.shape[1]):
        top = str(df.iat[2, j]) if not pd.isna(df.iat[2, j]) else ""
        sub = str(df.iat[3, j]).strip().lower() if not pd.isna(df.iat[3, j]) else ""
        m = re.match(r"^ano\s*(\d{4})$", " ".join(top.split()).lower())
        if m:
            cols[j] = (m.group(1), "annual")
            continue
        m = re.match(r"^(\d{4})(\.0)?$", top.strip())
        if m:
            year = int(m.group(1))
        if year is None or not sub:
            continue
        mm = re.match(r"^([a-z]{3})\.?$", sub)
        if mm and mm.group(1) in _MON:
            cols[j] = (f"{year}-{_MON[mm.group(1)]:02d}", "monthly")
            continue
        mq = re.match(r"^(i{1,3}|iv)\s*trim", sub)
        if mq:
            cols[j] = (f"{year}-Q{_Q[mq.group(1)]}", "quarterly")
    tag = f"{base}: {sheet}"
    for i in range(4, len(df)):
        c0, c1 = df.iat[i, 0], df.iat[i, 1]
        c2 = df.iat[i, 2] if df.shape[1] > 2 else None
        s0, s1, s2 = (str(x).strip() if not pd.isna(x) else "" for x in (c0, c1, c2))
        if s0.startswith("Fonte") or s1.startswith("Fonte"):
            break
        kw = None
        if "total geral" in (s0 + s1 + s2).lower():
            kw = {}
        elif kind == "section":
            m = re.match(r"^Sec[çc][ãa]o\s+([IVXL]+)$", s1)
            mc = re.match(r"^Cap\.?\s*(\d{2})$", s1)
            if m:
                kw = dict(commodity=s2, commodity_classification="national", commodity_code_nso=m.group(1))
            elif mc:
                kw = dict(commodity=s2, commodity_classification="hs2", commodity_code_nso=mc.group(1))
        elif kind == "partner":
            if s1:
                kw = dict(partner=s1, partner_type="group" if s0 == "ZZ" or "desconhec" in s1.lower() else "country")
        elif kind == "bec":
            code = s0.replace(".0", "")
            if re.fullmatch(r"\d{1,3}", code) and s1:
                kw = dict(commodity=s1, commodity_classification="bec", commodity_code_nso=code)
        if kw is None:
            continue
        first = 2 if kind == "partner" or kind == "bec" else 3
        for j, (per, freq) in cols.items():
            if j < first:
                continue
            v = _num(df.iat[i, j])
            if v is None or v <= 0:   # 0: empty grid cell, or a month not yet published
                continue
            rows.append(row(tradeflow=flow, period=per, frequency=freq, value=v, unit=cur,
                            unit_multiplier=mult, series_code=tag, **kw))
    return rows


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    # annual workbooks first, monthly last: the monthly workbook (newer, with
    # the current year) wins for the annual columns both carry
    paths = sorted(set([path] + [p for p in (extras or []) if p.lower().endswith(".xlsx")]),
                   key=lambda p: (0 if "anual" in os.path.basename(p).lower() else 1, p))
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for p in paths:
            xl = pd.ExcelFile(p)
            for sh in xl.sheet_names:
                rows += _sheet(xl.parse(sh, header=None), os.path.basename(p), sh)
            xl.close()
    if not rows:
        raise ValueError("angola_ine: no rows decoded")
    df = pd.DataFrame.from_records(rows)
    key = ["tradeflow", "commodity_code_nso", "commodity", "partner", "frequency", "period", "unit"]
    df = df.drop_duplicates(key, keep="last")
    # the current year's "Ano" column is year-to-date: annual kept for complete years only
    tot = df[(df["frequency"] == "monthly") & (df["commodity"] == "All products")
             & (df["partner"] == "All partners") & (df["tradeflow"] == "export")]
    full = {y for y, n in tot["period"].str[:4].value_counts().items() if n == 12 * tot["unit"].nunique()}
    df = df[(df["frequency"] != "annual") | df["period"].isin(full)]
    return df.reset_index(drop=True)
