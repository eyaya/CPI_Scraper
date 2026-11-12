"""Côte d'Ivoire -- Indice de Prix de Production dans l'Industrie (IPPI), base 2015.

parse_ins -- INS (the NSO before ANStat), monthly note "INDICE DE PRIX DE
  PRODUCTION (IPPI) PAR TYPE D'INDUSTRIES / PAR DIVISIONS REGROUPEES / PAR
  DIVISION", "ANNEE DE BASE 2015 ET REFERENCE 2019" (ins.ci/n/templates/ihpi/
  ippi<MM>20.pdf, 2020; Wayback copies). Each table: CODE (NAEMA rev1) | label |
  Pondération (per 10 000) | 13 months | Var m/m % | Var y/y % | Var cumulated
  months % (not emitted) | contribution (not emitted). Weights print with stray
  spaces ("1 0 000", "7 36,6") and are not emitted. Labels are upper-case and
  wrap: a text line opens the NEXT label when it ends on a connective (DE, ET,
  DU, D', a comma ...) or the next number row carries no label of its own;
  otherwise it continues the row above. Three division labels on the DIVISION
  page are overprinted in the text layer ("T CH R A A U VA SS IL U D RE U S
  CUIR ..."); those rows (codes 15, 16, 18) are skipped -- the same codes are
  read cleanly from the DIVISIONS REGROUPEES page where they coincide (15, 16).

parse_anstat -- ANStat monthly note "Indice des Prix de Production
  Industrielle -- IPPI" (anstat.ci/assets/publications/files/
  File_val_indicateur<ts>.pdf), "Tableau 1 : Indice des prix de production
  industrielle rénové par branche d'activité": label | 13 months | variation
  on the same month a year earlier | on the cumulated months (not emitted) |
  2 contributions (not emitted). Base: "L'IPPI rénové base 100 en 2015".
  Labels wrap over up to five lines around their numbers: a line starting
  lower-case or with punctuation continues the current label.

Both: the y/y column is confirmed on the Ensemble / TOTAL INDUSTRIE row
(published change = its own indices a year apart, within rounding) and the
m/m column likewise (INS); a column that fails is not emitted.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

INS_NAME = "Indice de Prix de Production dans l'Industrie (IPPI)"
ANSTAT_NAME = "Indice des Prix de Production Industrielle rénové (IPPI)"
_IDX = re.compile(r"-?\d+,\d")
_PCT = re.compile(r"-?\d+,\d+%")
_CODE = re.compile(r"^(\d{2}(?:-\d{2})?)(?:\s+(.*))?$")
_CONNECT = re.compile(r"(?:\b(?:DE|ET|DU|DES|D[’']|LA|LE|L[’']|AUX|EN|ÉLECTRIQUES ET DE)|,)$", re.I)
_FR_MONTH = {"janv": 1, "fev": 2, "fevr": 2, "mars": 3, "avril": 4, "avr": 4, "mai": 5, "juin": 6,
             "juillet": 7, "juil": 7, "aout": 8, "sept": 9, "oct": 10, "nov": 11, "dec": 12}


def _fold(s):
    import unicodedata
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().strip(".")


def _ins_months(lines, i):
    """'Sept Oct ... Sept' on one line, the years '2019 ... 2020' on a later one."""
    names = [t for t in lines[i].split() if _fold(t) in _FR_MONTH]
    for k in range(i + 1, min(i + 4, len(lines))):
        years = re.findall(r"\b(20\d{2})\b", lines[k])
        if len(years) >= 12 and len(names) >= len(years):
            # extra month names after the 13 columns belong to the "Var Sept 2020/ ..." headers
            return [f"{y}-{_FR_MONTH[_fold(n)]:02d}" for n, y in zip(names, years)]
    return None


def _confirm(idx: dict, cur: str, var: list, kinds: list):
    """Which variation columns are m/m / y/y, judged on the total row."""
    y, m = int(cur[:4]), int(cur[5:])
    prev = f"{(y * 12 + m - 2) // 12:04d}-{(m - 2) % 12 + 1:02d}"
    ago = f"{y - 1:04d}-{m:02d}"
    implied = {"inflation_mom": (idx[cur] / idx[prev] - 1) * 100 if prev in idx else None,
               "inflation_yoy": (idx[cur] / idx[ago] - 1) * 100 if ago in idx else None}
    roles = []
    for k, v in zip(kinds, var):
        ok = k in implied and implied[k] is not None and v is not None and abs(v - implied[k]) <= 0.3
        roles.append(k if ok else None)
    return roles


def parse_ins(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        pages = [[l.strip() for l in (pg.extract_text() or "").splitlines()] for pg in pdf.pages]
    out, seen = [], set()
    for lines in pages:
        if not any("ANNEE DE BASE" in l for l in lines):
            continue
        level = ("TYPE" if any("TYPE D'INDUSTRIES" in l for l in lines[:4]) else
                 "DIVISIONS_REGROUPEES" if any("REGROUPEES" in l for l in lines[:4]) else "DIVISIONS")
        hi = next((i for i, l in enumerate(lines) if len([t for t in l.split() if _fold(t) in _FR_MONTH]) >= 12), None)
        months = _ins_months(lines, hi) if hi is not None else None
        if not months:
            continue
        parsed = []
        for ln in lines[hi + 1:]:
            toks = ln.split()
            if len(toks) >= 17 and _PCT.fullmatch(toks[-2] if len(toks) > 1 else ""):
                tail = toks[-4:]                     # 3 % changes + contribution
                vals = toks[-17:-4]
                if all(_IDX.fullmatch(v) for v in vals) and all(_PCT.fullmatch(t) for t in tail[:3]):
                    head = toks[:-17]
                    while head and re.fullmatch(r"\d[\d,]*|,\d+", head[-1]):
                        head = head[:-1]             # the weight, printed in pieces
                    parsed.append(("row", " ".join(head), vals, tail[:3]))
                    continue
            if re.search(r"\d+,\d+%", ln) or not re.search(r"[A-Z]", ln) or ln.startswith(("CODE", "NAEMA", "REV1", "D'IND", "TYPE", "DIVISION", "REGR", "2020", "Var", "LIBELLE")):
                parsed.append(("junk", ln))
            else:
                parsed.append(("text", ln))
        rows, pending = [], []
        for t, item in enumerate(parsed):
            if item[0] == "junk":
                continue
            if item[0] == "row":
                m = _CODE.match(item[1])
                code, label = (m.group(1), m.group(2) or "") if m else ("", item[1])
                rows.append([code, " ".join(pending + ([label] if label else [])), item[2], item[3]])
                pending = []
                continue
            text = item[1]
            nxt = next((p for p in parsed[t + 1:] if p[0] != "junk"), None)
            nm = _CODE.match(nxt[1]) if nxt is not None and nxt[0] == "row" else None
            nxt_unlabelled = nxt is not None and nxt[0] == "row" and (not nxt[1] or (nm is not None and not nm.group(2)))
            if pending or _CONNECT.search(text) or nxt_unlabelled or not rows:
                pending.append(text)
            else:
                rows[-1][1] += " " + text
        total = next((r for r in rows if r[1].startswith("TOTAL INDUSTRIE") and "HORS" not in r[1]), None)
        cur = months[-1]
        roles = [None, None, None]
        if total:
            idx = dict(zip(months, [C.to_number(v, decimal=",") for v in total[2]]))
            var = [C.to_number(v.rstrip("%"), decimal=",") for v in total[3]]
            roles = _confirm(idx, cur, var, ["inflation_mom", "inflation_yoy", None])
        for code, label, vals, pct in rows:
            label = re.sub(r"\s+", " ", label).strip()
            if len(re.findall(r"\b[A-Z]\b", label)) >= 4:
                continue                             # overprinted label (docstring)
            series = [(p, "index", v) for p, v in zip(months, vals)] + \
                     [(cur, r, x.rstrip("%")) for r, x in zip(roles, pct)]
            for p, meas, x in series:
                v = C.to_number(x, decimal=",")
                if meas is None or v is None or (label, p, meas) in seen:
                    continue
                seen.add((label, p, meas))
                out.append(C.row(index_name=INS_NAME, industry=label, industry_code_nso=code, period=p,
                                 frequency="monthly", measure=meas, value=v,
                                 base_period="2015=100" if meas == "index" else "", series_code=level))
    if not out:
        raise ValueError(f"{path}: no IPPI table found")
    return pd.DataFrame(out)


def parse_anstat(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        lines = [l.strip() for pg in pdf.pages for l in (pg.extract_text() or "").splitlines()]
    full = " ".join(lines)
    bm = re.search(r"rénové\s+base\s+100\s+en\s+(\d{4})", full)
    base = f"{bm.group(1)}=100" if bm else ""
    out, seen = [], set()
    i = 0
    while i < len(lines):
        if not lines[i].startswith("Libellé") or len(re.findall(r"[A-Za-zéû]+-\d{2}", lines[i])) < 12:
            i += 1
            continue
        months = [C.month_period(t) for t in lines[i].split()[1:]]
        months = [m for m in months if m]
        n = len(months)
        rows, pending, k = [], [], i + 1
        while k < len(lines) and not lines[k].startswith(("Source", "Libellé", "Tableau")):
            ln = lines[k]
            k += 1
            if re.fullmatch(r"(?:\w+ \d{4} / )?.*(?:Mois \d{4}|Mai \d{4}).*", ln) and not re.search(r"\d+,\d", ln):
                continue                             # the variation header lines
            toks = ln.split()
            j = len(toks)
            while j > 0 and re.fullmatch(r"-?\d+,\d+", toks[j - 1]):
                j -= 1
            nums, text = toks[j:], " ".join(toks[:j])
            if len(nums) == n + 4:
                rows.append([" ".join(pending + ([text] if text else [])), nums])
                pending = []
            elif nums:
                raise ValueError(f"{path}: {len(nums)} cells for {n} months + 4 at {ln!r}")
            elif rows and not pending and (text[:1].islower() or text[:1] in ";,(" ):
                rows[-1][0] += " " + text
            else:
                pending.append(text)
        total = next((r for r in rows if r[0].strip().lower() == "ensemble"), None)
        cur = months[-1]
        roles = [None] * 4
        if total:
            idx = dict(zip(months, [C.to_number(v, decimal=",") for v in total[1][:n]]))
            roles = _confirm(idx, cur, [C.to_number(v, decimal=",") for v in total[1][n:]],
                             ["inflation_yoy", None, None, None])
        for label, nums in rows:
            label = re.sub(r"\s+", " ", label).strip()
            series = [(p, "index", x) for p, x in zip(months, nums[:n])] + \
                     [(cur, r, x) for r, x in zip(roles, nums[n:])]
            for p, meas, x in series:
                v = C.to_number(x, decimal=",")
                if meas is None or v is None or (label, p, meas) in seen:
                    continue
                seen.add((label, p, meas))
                out.append(C.row(index_name=ANSTAT_NAME, industry=label, period=p, frequency="monthly",
                                 measure=meas, value=v, base_period=base if meas == "index" else ""))
        i = k
    if not out:
        raise ValueError(f"{path}: no IPPI table found")
    return pd.DataFrame(out)


# A % change carries the base of its index (set from this output; see _base_carry).
from ._base_carry import carry_base  # noqa: E402
parse_anstat = carry_base(parse_anstat)
parse_ins = carry_base(parse_ins)
