"""Benin — Bulletin statistique de la dette publique (Caisse Autonome de
Gestion de la Dette, CAGD, Ministère de l'Economie et des Finances),
quarterly, on cagd.bj.

COVERAGE. Tableau 1 "Evolution de l'encours de la dette et du taux
d'endettement public" -- "Encours dette publique", the debt the CAGD manages
for the State. The bulletin presents state guarantees (Tableau 3), the
non-guaranteed bank debt of public enterprises (Tableau 4) and on-lent loans
(Tableau 5) SEPARATELY, so they are not part of this total; recorded as the
descriptor's coverage.

WHAT IS READ: Tableau 1, three columns per period -- Encours (milliards FCFA),
Part (% of total debt) and "En % du PIB" -- for the previous year-end and the
quarters printed ("2025 | Fin mars 2026 | Fin juin 2026"). Every row carries
nine values; the labels are stated (`_LABELS`, as printed), because two of
them wrap around their own numbers ("Autres dettes en monnaie" / numbers /
"en monnaie locale)"). Checked every run, per period:
  devises  = bilatérale + multilatérale + commerciale        (to 0,2)
  locale   = Obligations + Bons + autres dettes en monnaie locale
  publique = devises + locale
  shares of the nine rows ... publique = 100,0 %

Tableaux 2-5 (securities characteristics, guarantees, SOE debt, on-lent
loans) are not read: different perimeters or not stocks of public debt.

CROSS-CHECK (Q2-2026 issue): encours dette publique end-June 2026
9 122,2 milliards FCFA = 50,1 % of GDP; end-2025 8 472,2 (50,0 %); dette
multilatérale 3 428,2.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_LABELS = ["Dette bilatérale", "Dette multilatérale", "Dette commerciale",
           "Encours dette en devises", "Obligations du Trésor", "Bons du Trésor",
           "Autres dettes en monnaie locale (financement bancaire en monnaie locale)",
           "Encours dette en monnaie locale", "Encours dette publique"]
_VAL = re.compile(r"\d{1,3}(?: \d{3})*,\d%?")
_MOIS_Q = {"mars": 1, "juin": 2, "septembre": 3, "décembre": 4, "decembre": 4}


def _num(s: str) -> float:
    return float(s.rstrip("%").replace(" ", "").replace(",", "."))


def _periods(header: str) -> list[tuple[str, str]]:
    out = []
    for m in re.finditer(r"(?:Fin\s+([a-zéû]+)\s+)?(20\d\d)", header, re.I):
        if m.group(1):
            q = _MOIS_Q.get(m.group(1).lower())
            if q is None:
                raise ValueError(f"CAGD BJ: unknown month in {header!r}")
            out.append((f"{m.group(2)}-Q{q}", "quarterly"))
        else:
            out.append((m.group(2), "annual"))
    return out


def _layout_a(text: str) -> pd.DataFrame:
    lines = text.splitlines()
    # "2025 Fin mars 2026 Fin juin 2026" or, in Q1 issues, "2024 2025 Fin mars 2026".
    hdr = next(ln for ln in lines if re.match(r"\s*(?:20\d\d\s+)+Fin", ln))
    periods = _periods(hdr)
    rows9 = []
    for ln in lines:
        vals = _VAL.findall(ln)
        if len(vals) == 3 * len(periods):
            rows9.append([_num(v) for v in vals])
    if len(rows9) != len(_LABELS):
        raise ValueError(f"CAGD BJ: {len(rows9)} data rows for {len(_LABELS)} labels")
    flat = " ".join(lines)
    pos = 0
    for lab in _LABELS:                    # labels must appear, in order
        for w in lab.replace("(", " ").replace(")", " ").split():
            k = flat.find(w, pos)
            if k < 0:
                raise ValueError(f"CAGD BJ: label {lab!r} not in order")
            pos = k + len(w)
    tab = dict(zip(_LABELS, rows9))
    for k in range(len(periods)):
        s = lambda lab: tab[lab][3 * k]
        checks = [(s("Encours dette en devises"),
                   s("Dette bilatérale") + s("Dette multilatérale") + s("Dette commerciale")),
                  (s("Encours dette en monnaie locale"),
                   s("Obligations du Trésor") + s("Bons du Trésor") + s(_LABELS[6])),
                  (s("Encours dette publique"),
                   s("Encours dette en devises") + s("Encours dette en monnaie locale"))]
        for want, got in checks:
            if abs(want - got) > 0.2:
                raise ValueError(f"CAGD BJ {periods[k][0]}: {want} != {got}")
        if tab["Encours dette publique"][3 * k + 1] != 100.0:
            raise ValueError(f"CAGD BJ {periods[k][0]}: total share is not 100 %")
    out = []
    for lab, vals in tab.items():
        for k, (period, freq) in enumerate(periods):
            for v, meas, unit, code in (
                    (vals[3 * k], "stock", "FCFA milliards", "CAGD BSDP T1"),
                    (vals[3 * k + 1], "share", "percent", "CAGD BSDP T1 part"),
                    (vals[3 * k + 2], "share_of_gdp", "percent", "CAGD BSDP T1 %PIB")):
                out.append({"component": lab, "period": period, "frequency": freq,
                            "measure": meas, "value": v, "unit": unit,
                            "series_code": code})
    return pd.DataFrame(out)


# ---------------------------------------------------------------------------
# BACK ISSUES (`extras`). Two more Tableau 1 layouts are read:
#
# LAYOUT B -- the 2020-2025 quarterly-window issues (CAA, then CAGD): STOCKS
# for up to eight quarters of two years ("2021 2022" over "1er trim ... 4ème
# trim"), then three "Taux d'endettement" rows (% of GDP) for devises, monnaie
# locale and public. Labels wrap around their own numbers in most issues, so
# the NUMBER rows are read in order and matched to the expected label
# sequence; the sums below confirm the alignment (a shifted row cannot pass).
#   devises  = bilatérale + multilatérale + commerciale [+ Eurobond, 2020]
#   locale   = Obligations + Bons + autres dettes en monnaie locale
#   publique = devises + locale                         (to 0,05)
# EUROBOND. The 2020 issues print "Eurobond" as a SIBLING of "Dette
# commerciale" (2019-Q2: 252,89 + 1 145,11 + 290,08 + 327,98 = 2 016,06);
# from 2021 it is a "Dont Eurobond" memo line INSIDE Dette commerciale. The
# 2020-issue figure is therefore filed as "Dette commerciale (hors Eurobond)",
# never under the inclusive label.
# PUBLISHED MISPRINT, pinned: the Q1-2021 issue prints Obligations du Trésor
# 2021-Q1 as "1 5333,88" (1 533,88 in every later issue); that issue's
# 2021-Q1 cell is not read, and its 2021-Q1 sums are not checked.
# Issues before 2020-Q2 print a different Tableau 1 and are not read.

_B_NUM = re.compile(r"[1-9]\d{0,2}(?: \d{3})+,\d+%?|\d+,\d+%?|(?<![\d,])0(?![\d,])")
_B_MISPRINT = {("2021-Q1", "1 5333,88")}
_B_RATIO_FOR = ["Encours dette en devises", "Encours dette en monnaie locale",
                "Encours dette publique"]


def _b_labels(text: str) -> list[str]:
    if re.search(r"Dont\s+Eurobond", text):
        eb = ["Dette commerciale", "Dont Eurobond"]
    elif re.search(r"(?m)^\s*Eurobond\b", text):
        eb = ["Dette commerciale (hors Eurobond)", "Eurobond"]
    else:
        eb = ["Dette commerciale"]
    return (["Dette bilatérale", "Dette multilatérale"] + eb +
            ["Encours dette en devises", "Obligations du Trésor", "Bons du Trésor",
             "Autres dettes en monnaie locale (financement bancaire en monnaie locale)",
             "Encours dette en monnaie locale", "Encours dette publique",
             "Taux devises", "Taux locale", "Taux public"])


def _layout_b(text: str) -> pd.DataFrame:
    lines = text.splitlines()
    i = next(k for k, ln in enumerate(lines) if re.fullmatch(r"\s*20\d\d\s+20\d\d\s*", ln))
    y1, y2 = (int(y) for y in lines[i].split())
    qtext = " ".join(lines[i + 1:i + 6])
    qs = [int(q) for q in re.findall(r"([1-4])(?:er|ème|eme|nd)\s+trim", qtext)]
    periods, y = [], y1
    for a, b in zip([None] + qs, qs):
        if a is not None and b <= a:
            y += 1
        periods.append(f"{y}-Q{b}")
    if y not in (y1, y2) or not periods:
        raise ValueError(f"CAGD BJ (B): quarters {qs} under {y1} {y2}")
    n = len(periods)
    rows, skip = [], set()
    for ln in lines[i + 1:]:
        if ln.startswith("Source"):
            break
        raw = ln
        cell = None
        for per, bad in _B_MISPRINT:
            if bad in raw and per in periods:
                raw, cell = raw.replace(bad, " "), periods.index(per)
                skip.add(per)
        toks = _B_NUM.findall(raw)
        if cell is not None:
            toks.insert(cell, None)
        if len(toks) == n:
            rows.append(toks)
    labels = _b_labels(text)
    if len(rows) != len(labels):
        raise ValueError(f"CAGD BJ (B) {periods[-1]}: {len(rows)} number rows "
                         f"for {len(labels)} labels")
    v = {lab: [None if t is None else _num(t) for t in r] for lab, r in zip(labels, rows)}
    dev_parts = [l for l in labels[:labels.index("Encours dette en devises")]
                 if l != "Dont Eurobond"]
    sums = (("Encours dette en devises", dev_parts),
            ("Encours dette en monnaie locale", labels[labels.index("Obligations du Trésor"):
                                                       labels.index("Encours dette en monnaie locale")]),
            ("Encours dette publique", ["Encours dette en devises",
                                        "Encours dette en monnaie locale"]))
    for j, per in enumerate(periods):
        if per in skip:
            continue
        for want, parts in sums:
            tot = sum(v[p][j] for p in parts)
            if abs(v[want][j] - tot) > 0.05:
                raise ValueError(f"CAGD BJ (B) {per}: {want} {v[want][j]} != {tot:.2f}")
    out = []
    for lab in labels:
        if lab.startswith("Taux "):
            comp, meas, unit, code = (_B_RATIO_FOR[["Taux devises", "Taux locale", "Taux public"].index(lab)],
                                      "share_of_gdp", "percent", "CAGD BSDP T1 %PIB")
        else:
            comp, meas, unit, code = lab, "stock", "FCFA milliards", "CAGD BSDP T1"
        for per, x in zip(periods, v[lab]):
            if x is not None:
                out.append({"component": comp, "period": per, "frequency": "quarterly",
                            "measure": meas, "value": x, "unit": unit, "series_code": code})
    return pd.DataFrame(out)


def _table1(path: str) -> str | None:
    """Tableau 1's page text (pdfplumber), located with PyMuPDF."""
    import fitz
    with fitz.open(path) as doc:
        idx = [k for k, pg in enumerate(doc)
               if re.search(r"TABLEAU\s*1\s*:", pg.get_text())
               and "Encours dette publique" in pg.get_text()]
    with pdfplumber.open(path) as pdf:
        for k in idx:
            t = pdf.pages[k].extract_text() or ""
            if "TABLEAU 1" in t and "Encours dette publique" in t:
                return t[t.find("TABLEAU 1"):]
    return None


def _read(path: str) -> pd.DataFrame:
    text = _table1(path)
    if text is None:
        raise ValueError(f"CAGD BJ: no Tableau 1 in {path}")
    if re.search(r"(?m)^\s*(?:20\d\d\s+)+Fin", text):
        return _layout_a(text)
    return _layout_b(text)


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    """The primary (newest issue) plus back issues in `extras`. Issues are read
    oldest first by their latest period, so the NEWEST issue's printing wins
    where windows overlap (the CAGD revises)."""
    frames = [_read(f) for f in sorted(set(extras or []) - {path})]
    frames.sort(key=lambda d: max(d["period"].astype(str)))
    frames.append(_read(path))
    df = pd.concat(frames, ignore_index=True)
    df = df.drop_duplicates(["component", "period", "frequency", "measure", "unit",
                             "series_code"], keep="last")
    return df.reset_index(drop=True)
