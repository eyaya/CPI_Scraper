"""Senegal -- ANSD, Indice des Prix de Production Industrielle (IPPI).

TWO SERIES, kept apart by base_period (and index_name):

parse_serie -- the renovated IPPI, base 100 en 2015. ANSD's IPPI indicator page
  (ansd.sn/Indicateur/indice-des-prix-la-production-industrielle-ippi) links
  "Série IPPI" (sites/default/files/2026-07/Série IPPI (1).xlsx): one sheet
  "CALCUL DES INDICES DE PRIX DES PRODUITS AGREGES -- INDICES MENSUELS", header
  "Codes Produits agrégés NOPEMA rev1 | Branche d'activités | <month datetimes>",
  2015-01..2026-05, 33 aggregates (05-39 ENSEMBLE HORS EGRENAGE DE COTON, types,
  divisions; 01 Egrenage de coton shown apart). The sheet does not print its
  base; the renovated monthly notes do ("Cet indice rénové, base 100 en 2015")
  and their values match it (IPPI rénové juin 2022: Minerais métalliques
  140,3 / 156,9 / 167,2 / 168,2 / 167,3 / 162,1 for juin-21, févr..juin-22 --
  identical; later months of the note were since revised). Stored (unrounded)
  values emitted as stored; "#N/A" and 0 (Equipements électriques) are not
  price levels and are skipped.

parse_note -- the earlier IPPI, base 100 en 2006, monthly notes 2010-2020
  (sites/default/files/2022-11/IPPI_MM_YY.pdf ...). Tableau 1 "INDICE DES PRIX
  A LA PRODUCTION INDUSTRIELLE BASE 100 EN 2006": label | Pond. (per mille) |
  13 months | variation on the previous month | on the cumulated months of the
  year (inflation_ytd_avg, since 2026-11-08) | on the same month a year earlier.
"""
from __future__ import annotations

import datetime as dt
import re

import pandas as pd

from . import _common as C

SERIE_NAME = "Indice des Prix de Production Industrielle (IPPI rénové)"
NOTE_NAME = "Indice des Prix à la Production Industrielle (IPPI)"


def parse_serie(path: str) -> pd.DataFrame:
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb.worksheets[0]
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    hdr = next(i for i, r in enumerate(rows) if r and str(r[0] or "").startswith("Codes Produits"))
    periods = [f"{c.year:04d}-{c.month:02d}" if isinstance(c, (dt.datetime, dt.date)) else None
               for c in rows[hdr][2:]]
    if sum(p is not None for p in periods) < 100:
        raise ValueError(f"{path}: header has {sum(p is not None for p in periods)} months")
    out = []
    for r in rows[hdr + 1:]:
        if not r or r[0] is None or r[1] is None:
            continue
        code = str(r[0]).strip()
        code = code.zfill(2) if code.isdigit() else code
        label = re.sub(r"\s+", " ", str(r[1])).strip()
        for p, v in zip(periods, r[2:]):
            x = C.to_number(v)
            if p is None or x is None or x == 0:
                continue
            out.append(C.row(index_name=SERIE_NAME, industry=label, industry_code_nso=code, period=p,
                             frequency="monthly", measure="index", value=x, base_period="2015=100"))
    if not out:
        raise ValueError(f"{path}: no IPPI rows")
    return pd.DataFrame(out)


_NUM = re.compile(r"-?\d+,\d\*?")
_MON = re.compile(r"(janv|jan|f[ée]vr?|mars|avr(?:il)?|mai|juin|juil|ao[uû]t|sept|oct|nov|d[ée]c)[a-zéû]*\.?\s*-?\s*(\d{2})?(?![\d,])",
                  re.I)
_MNUM = {"jan": 1, "fev": 2, "fév": 2, "mar": 3, "avr": 4, "mai": 5, "jui": 6, "aou": 8, "aoû": 8,
         "sep": 9, "oct": 10, "nov": 11, "dec": 12, "déc": 12}


def _month_no(name: str) -> int:
    n = name.lower()
    if n.startswith("juil"):
        return 7
    if n.startswith("juin"):
        return 6
    return _MNUM[n[:3]]


def _header_months(text: str):
    """Months of the 'Pond.' header in order. A month printed without its year
    ("... juil-20 août", 2020-08 note) takes the year of the month before it."""
    out, year = [], None
    for m in _MON.finditer(text):
        mo = _month_no(m.group(1))
        if m.group(2):
            year = 2000 + int(m.group(2))
        elif year is None:
            continue
        elif out and mo < int(out[-1][5:]):
            year += 1
        out.append(f"{year:04d}-{mo:02d}")
    return out


def parse_note(path: str) -> pd.DataFrame:
    """Tableau 1 of a base-2006 monthly note. Layouts drift over 2010-2020:
    caption "INDICE DES PRIX A LA PRODUCTION INDUSTRIELLE" / "DE PRODUCTION DANS
    L'INDUSTRIE", 13 months or fewer (2020-08: août-19, déc-19..août-20), a
    trailing '*' on provisional cells, and the three change columns in varying
    order (m/m, cumulated months, y/y in 2010; m/m, y/y, cumulated in 2020).
    Which column is which is settled on the ENSEMBLE INDUSTRIE row: the m/m
    column must equal its last two indices' change and the y/y column its
    change on the same month a year earlier (both within rounding, 0,3 pt);
    the remaining column is the cumulated-months change. A note where neither identity holds
    emits indices only."""
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        lines = [l.strip() for pg in pdf.pages for l in (pg.extract_text() or "").splitlines()]
    cap = next((i for i, l in enumerate(lines)
                if re.search(r"Tableau\s*1\s*:\s*INDICE DES PRIX (?:A LA|DE) PRODUCTION", l, re.I)), None)
    if cap is None:
        raise ValueError(f"{path}: no Tableau 1")
    bm = re.search(r"BASE\s+100\s+EN\s+(\d{4})", lines[cap], re.I)
    base = f"{bm.group(1)}=100" if bm else ""
    hdr = next(i for i in range(cap, min(cap + 6, len(lines))) if lines[i].startswith("Pond"))
    months = _header_months(lines[hdr][5:])
    # the header's own text also names the change columns' months ("août-19"
    # after the last index month): keep the first run of consecutive-or-later months
    k = 1
    while k < len(months) and months[k] > months[k - 1]:
        k += 1
    months = months[:k]
    if len(months) < 6:
        raise ValueError(f"{path}: {len(months)} months in header {lines[hdr]!r}")
    cand = []
    for ln in lines[hdr + 1:]:
        if ln.startswith(("Source", "Tableau", "Graphique")):
            break
        toks = ln.split()
        j = len(toks)
        while j > 0 and (_NUM.fullmatch(toks[j - 1]) or toks[j - 1] in ("-",)):
            j -= 1
        if j == 0 or not re.fullmatch(r"\d{1,4}", toks[j - 1]) or len(toks) - j < 8:
            continue
        cand.append((" ".join(toks[:j - 1]).strip(), [C.to_number(x.rstrip("*"), decimal=",") for x in toks[j:]]))
    ens = next((v for l, v in cand if l.upper().startswith("ENSEMBLE")), None)
    if not ens:
        raise ValueError(f"{path}: Tableau 1 has no ENSEMBLE row")
    width = len(ens)

    def consecutive(first, n):
        y, m = int(first[:4]), int(first[5:])
        return [f"{y + (m - 1 + k) // 12:04d}-{(m - 1 + k) % 12 + 1:02d}" for k in range(n)]

    # 2 change columns (January notes: m/m, y/y) or 3. When the header prints
    # fewer months than the row has indices (2017-01: "mars-16" and "janv.-17"
    # wrap onto other lines), the months are the consecutive run from the first
    # header month -- accepted only if every printed month lies in it.
    def fit(mon, n_var):
        """(months, roles, n_matched) for one reading of the columns."""
        n = width - n_var
        cur = mon[-1]
        prev = f"{(int(cur[:4]) * 12 + int(cur[5:]) - 2) // 12:04d}-{(int(cur[5:]) - 2) % 12 + 1:02d}"
        year_ago = f"{int(cur[:4]) - 1:04d}{cur[4:]}"
        idx = dict(zip(mon, ens[:n]))
        var = ens[n:]
        roles, hit = [None] * n_var, 0
        for r, implied in (("inflation_mom", (idx[cur] / idx[prev] - 1) * 100 if prev in idx else None),
                           ("inflation_yoy", (idx[cur] / idx[year_ago] - 1) * 100 if year_ago in idx else None)):
            if implied is None:
                continue
            best = min(range(n_var), key=lambda c: abs((var[c] if var[c] is not None else 1e9) - implied))
            if var[best] is not None and abs(var[best] - implied) <= 0.3 and roles[best] is None:
                roles[best], hit = r, hit + 1
        return mon, roles, hit

    # 2 change columns (January notes: m/m, y/y) or 3. When the header prints
    # fewer months than the row has indices (2017-01: "mars-16" and "janv.-17"
    # wrap onto other lines), the months are the consecutive run from the first
    # header month -- a reading is accepted only if every printed month lies in
    # it, and among readings the one whose m/m AND y/y identities hold wins.
    options = []
    for n_var in (3, 2):
        n = width - n_var
        if len(months) == n:
            options.append(fit(months, n_var))
        elif len(months) < n:
            seq = consecutive(months[0], n)
            if set(months) <= set(seq):
                options.append(fit(seq, n_var))
    if not options:
        raise ValueError(f"{path}: {width} cells do not fit header months {months}")
    months, roles, hit = max(options, key=lambda o: o[2])
    if hit < 2 and len(options) > 1:
        raise ValueError(f"{path}: no column reading satisfies the m/m and y/y identities")
    # Three change columns with m/m and y/y proved: the third is the
    # "variation des cumuls" -- the January-to-date average on the same months a
    # year earlier (tested on ENSEMBLE: printed -2,7 / -0,8 / -4,5 / 0,4 for
    # 2013/2014/2015/2017-12 against -2,71 / -0,93 / -4,49 / 0,43 from the
    # indices; the change since December gives -1,69 / -3,09 / -3,45 / -1,57).
    if len(roles) == 3 and hit == 2:
        roles = [r or "inflation_ytd_avg" for r in roles]
    rows = [(l, v) for l, v in cand if len(v) == width]
    cur = months[-1]
    out, seen = [], set()
    for label, vals in rows:
        cols = [(p, "index") for p in months] + [(cur, r) for r in roles]
        for (p, meas), v in zip(cols, vals):
            if meas is None or v is None or (meas == "index" and v == 0) or (label, p, meas) in seen:
                continue
            seen.add((label, p, meas))
            out.append(C.row(index_name=NOTE_NAME, industry=label, period=p, frequency="monthly",
                             measure=meas, value=v, base_period=base if meas == "index" else ""))
    return pd.DataFrame(out)


# A % change carries the base of its index (set from this output; see _base_carry).
from ._base_carry import carry_base  # noqa: E402
parse_note = carry_base(parse_note)
parse_serie = carry_base(parse_serie)
