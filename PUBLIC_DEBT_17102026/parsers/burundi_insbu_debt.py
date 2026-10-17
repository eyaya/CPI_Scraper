"""Burundi -- INSBU Annuaire statistique, chapter 15 "Finances publiques":
Tableau 15.06 "Dette publique" and Tableau 15.07 "Dette publique extérieure
par secteurs" (millions de FBU).

PUBLISHER: INSBU (the statistics office), reprinting the Ministère des
Finances' debt figures -- the source line reads "B.R.B/Rapports annuels
(2010-2012), Ministère des Finances à partir de 2013" (15.07: "B.R.B/Rapports
annuels"). COVERAGE: the State's debt, domestic + external; the yearbook does
not define the perimeter further, so it is recorded as "not stated".

COMPONENTS
* 15.06 -- I. Dette intérieure (Bons du trésor, Avances de la BRB, Autres
  dettes intérieures), II. Dette extérieure (Dette directe, Dette indirecte),
  Total. "Bons d'investissements" and "Certificats du trésor" print no values.
* 15.07 -- external debt by the SECTOR it financed, under "I. Dette directe"
  and "II. Dette rétrocédée". Labels recur under both (Equipements publics,
  Agriculture & élevage ...), so each is prefixed with its section. "ND" is a
  missing cell.

EDITIONS: the 2024 edition (primary) prints 2015-2024; the 2021 edition
(extra) adds 2013-2014 to 15.06 and 2012-2014 to 15.07, rounded to whole
millions. The newer edition wins each year both print. Labels are taken in the
newest edition's wording (the 2021 edition wraps "Bons du trésor(titres de
creance= BT et OT)").

PUBLISHED DEFECTS, HANDLED EXPLICITLY
* THE 2024 COLUMN OF 15.06 (2024 edition) IS A COPY OF 15.05's INTEREST LINES:
  "Dette intérieure 2 306 226,1" and "Dette extérieure 799 747,3" are exactly
  15.05's interest payments on domestic and external debt, "Dette directe"
  prints 0,0, and domestic debt is not the sum of its own parts (1 868 191,3).
  The whole 2024 column of 15.06 is refused; 2024 external debt comes from
  15.07 (1 871 420,1). `_REFUSED` pins it, and the parse raises if the column
  ever starts adding up (a correction to adopt) or another year stops adding up.
* "Autres dettes intérieures" prints one cell fewer than there are years (a
  blank, not a dash). Its cells are placed by the table's own identity --
  domestic = bons + avances + autres -- trying each placement and requiring
  exactly one to hold. 2019 is the blank in both editions.
* 15.07's "Agro-industrie" and "Energie" rows print the wrong number of cells
  (their values are spread across two lines) and are not collected.
* 15.06 and 15.07 disagree on external debt from 2022 (15.06: 1 174 445,5;
  15.07: 1 637 462,8 -- 15.06's 2023 figure). Both are kept as published,
  told apart by series_code; neither is "corrected".
* 2020 domestic debt (934 799,5, with bons du trésor 133 121,0 against 1,4 and
  2,0 million either side) is an outlier but internally consistent, and is
  kept as published.

CROSS-CHECK (2024 edition): Total 2015 1 761 807,3; Dette intérieure 2023
3 772 534,8; Avances de la BRB 2022 690 669,1; 15.07 Dette exterieur 2024
1 871 420,1. 2021 edition: Total 2013 1 213 669; Dette extérieure 2014 656 564.
"""
from __future__ import annotations

import itertools
import re

import fitz  # PyMuPDF
import pandas as pd

_T06 = re.compile(r"Tableau 15\.06\. (?:Evolution de la )?[Dd]ette publique \(en millions de FBU\)\.?\s*\n"
                  r"\s*Dette publique\s*\n")
_T07 = re.compile(r"Tableau 15\.07\. Dette publique ext.rieure par secteurs "
                  r"\(en millions de FBU\)\s*\n\s*Rubriques\s*\n")
_YEAR = re.compile(r"^2\s?0\s?\d\s?\d$")
_CELL = re.compile(r"^(?:\d{1,3}(?: \d{3})*(?:,\d+)?|ND|-)$")
_UNIT = "FBU million"

# (edition first year printed, year) of a 15.06 column refused -- see docstring.
_REFUSED = {"2024"}


def _num(c: str):
    return None if c in ("ND", "-") else float(c.replace(" ", "").replace(",", "."))


def _rows(text: str, caption: re.Pattern) -> tuple[list[str], list[tuple[str, list[str]]]]:
    m = caption.search(text)
    lines = [ln.strip() for ln in text[m.end():].splitlines() if ln.strip()]
    years, i = [], 0
    while _YEAR.match(lines[i]):
        years.append(lines[i].replace(" ", ""))
        i += 1
    rows, label = [], []
    while i < len(lines) and not lines[i].startswith("Source"):
        if _CELL.match(lines[i]) and label:
            cells = []
            while i < len(lines) and _CELL.match(lines[i]):
                cells.append(lines[i])
                i += 1
            rows.append((re.sub(r"\s+", " ", " ".join(label)).strip(), cells))
            label = []
            continue
        if not _CELL.match(lines[i]):
            # A label line with no values under it is a valueless row ("Bons
            # d'investissements") and is replaced by the next -- unless it
            # visibly wraps ("Bons du trésor(titres de creance=").
            if label and not label[-1].endswith(("=", "(", ",")):
                label = []
            label.append(lines[i])
        i += 1
    return years, rows


def _canon(label: str) -> str:
    return "Bons du trésor(titres de creance= BT et OT)" if label.startswith("Bons du tr") else label


def _t06(text: str, edition: str) -> list[dict]:
    years, rows = _rows(text, _T06)
    n = len(years)
    got: dict[str, list] = {}
    autres = None
    for lab, cells in rows:
        lab = _canon(lab)
        if len(cells) == n:
            got[lab] = [_num(c) for c in cells]
        elif lab.startswith("Autres dettes"):
            autres = cells
    dom, bt, brb = (got["I. Dette intérieure"], got["Bons du trésor(titres de creance= BT et OT)"],
                    got["Avances de la BRB"])
    tol = 1.0 if edition == "2024" else 2.0   # the 2021 edition rounds to units

    def holds(y, a):
        return abs(dom[y] - (bt[y] + brb[y] + (a or 0))) <= tol

    if autres is not None:
        vals = [_num(c) for c in autres]
        fits = []
        for gap in itertools.combinations(range(n), n - len(vals)):
            placed = iter(vals)
            cand = [None if k in gap else next(placed) for k in range(n)]
            if all(holds(k, cand[k]) for k in range(n) if years[k] not in _REFUSED):
                fits.append(cand)
        if not fits:
            raise ValueError(f"INSBU 15.06 ({edition}): no placement of 'Autres "
                             f"dettes intérieures' satisfies the table's identity")
        # Several placements can fit when a ZERO sits next to the blank: the
        # 2024 edition's "0,0" balances 2018 and 2019 equally (both years need
        # nothing from "autres"). A cell the fits disagree on is not emitted --
        # which year the printed zero belongs to is not knowable.
        got["Autres dettes intérieures"] = [
            vals_k[0] if len(set(vals_k)) == 1 else None
            for vals_k in zip(*fits)]
    else:
        raise ValueError(f"INSBU 15.06 ({edition}): no 'Autres dettes intérieures' row")

    ext, dd, di, tot = (got["II. Dette extérieure"], got["Dette directe"],
                        got["Dette indirecte"], got["Total"])
    out = []
    for k, y in enumerate(years):
        ok = (abs((ext[k] or 0) - ((dd[k] or 0) + (di[k] or 0))) <= tol
              and abs((tot[k] or 0) - ((dom[k] or 0) + (ext[k] or 0))) <= tol
              and holds(k, got["Autres dettes intérieures"][k]))
        if y in _REFUSED:
            if ok:
                raise ValueError(f"INSBU 15.06: the refused {y} column now adds up "
                                 f"-- INSBU corrected it; remove it from _REFUSED")
            continue
        if not ok:
            raise ValueError(f"INSBU 15.06 ({edition}) {y}: identities fail")
        for lab, vals in got.items():
            if vals[k] is not None:
                out.append({"component": lab, "period": y, "value": vals[k],
                            "series_code": "INSBU Annuaire T15.06"})
    return out


def _t07(text: str) -> list[dict]:
    years, rows = _rows(text, _T07)
    out, section = [], ""
    for lab, cells in rows:
        if lab.startswith("I. Dette directe"):
            section = "I. Dette directe"
        elif lab.startswith("II. Dette rétrocédée"):
            section = "II. Dette rétrocédée"
        if len(cells) != len(years):
            continue                         # Agro-industrie / Energie: misaligned
        comp = lab if lab in ("Dette exterieur", "Total") or lab == section \
            else f"{section}: {lab}"
        for y, c in zip(years, cells):
            v = _num(c)
            if v is not None:
                out.append({"component": comp, "period": y, "value": v,
                            "series_code": "INSBU Annuaire T15.07"})
    return out


def _edition(path: str) -> tuple[str, list[dict]]:
    with fitz.open(path) as doc:
        pages = [p.get_text() for p in doc]
    t06 = next((t for t in pages if _T06.search(t)), None)
    t07 = next((t for t in pages if _T07.search(t)), None)
    if t06 is None or t07 is None:
        raise ValueError(f"INSBU debt tables not found in {path}")
    years, _ = _rows(t06, _T06)
    edition = years[-1]
    return edition, _t06(t06, edition) + _t07(t07)


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    seen, rows = set(), []
    for p in [path, *(extras or [])]:           # newest edition first
        _, recs = _edition(p)
        for r in recs:
            key = (r["series_code"], r["component"], r["period"])
            if key in seen:
                continue
            seen.add(key)
            rows.append({**r, "frequency": "annual", "measure": "stock",
                         "unit": _UNIT})
    return pd.DataFrame(rows)
