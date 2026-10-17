"""Guinea -- Ministère de l'Économie et des Finances (MEF), Direction Nationale
de la Dette et de l'Aide Publique au Développement (DNDAPD): "Bulletin
statistique de la dette", quarterly; plus the BCRG's "Dette extérieure"
workbook as an extra.

PUBLISHER: MEF / DNDAPD (an official national debt compiler, accepted for this
indicator). COVERAGE, as the bulletin states it: CENTRAL GOVERNMENT
(Administration centrale) debt, external + domestic; "les garanties explicites
ou implicites ne sont pas incluses dans l'encours", and public-enterprise debt
is "pas disponible". Stocks are converted at the end-of-period exchange rate.

TWO LAYOUTS, BOTH READ
* PDF issues (the 2022 annual issue, 2023-Q1 .. 2023-Q3; the 2022-Q1..Q3
  issues use a different layout and perimeter -- "Dette publique et dette
  garantie", headed "millier USD" over USD-million figures -- and are not
  read): "Tableau 1: Encours de la dette de
  l'Administration Centrale" -- Dette Totale / Extérieure / Intérieure in USD
  million and GNF million for several periods side by side (end-years 2020-2022
  as `annual`, quarters "T1 2023" as `quarterly`), plus the printed % share of
  each in the total. Read from PyMuPDF WORD POSITIONS: each period label heads
  a group of USD / GNF / % sub-columns, and each number is assigned to the
  nearest sub-column. Only the STOCK block is read (the rows before "Total de
  Tirages / Emissions" -- drawings and debt service are flows).
* DOCX issues (2024-Q4 .. 2025-Q3): the stock tables are pasted in as IMAGES
  (not read -- no OCR). The one text table is "Indicateurs de risque": stock in
  GNF and USD million and "Dette nominale en % du PIB" for external, domestic
  and total debt at the quarter end on the cover ("AU 30 SEPTEMBRE 2025"). Read
  from the docx XML directly (no extra dependency).

PUBLISHED DEFECTS, HANDLED EXPLICITLY
* THE T1 2025 AND T2 2025 ISSUES PRINT THE SAME RISK TABLE, digit for digit
  (35 949 647,1 / 28 561 670,7 / 64 511 317,8 GNF million). One is a copy and
  nothing says which, so neither quarter is collected; `_identical_issues`
  raises if any OTHER pair of issues repeats a table.
* T3 2025 prints external debt as "4O 102 175,71" -- a letter O for a zero.
  Read as 40 102 175,71 only because external + domestic then equals the
  printed total exactly; any other non-digit raises.
* T3 2025's domestic debt (72 813 425,87, 23,5% of GDP) is far above the
  quarters before it (28 561 670,7 at mid-2025). Internally consistent and
  kept as published; the issue is labelled "VP_PROJET" (provisional).

BCRG EXTRA. The central bank's "Dette Extérieure" workbook (source line
"DNDAPD&DNP") gives "Encours de la Dette (millions USD)" and "(en % du PIB)"
annually 2013-2022 and for 2023-Q1/Q2. ITS PERIMETER IS NOT STABLE: from 2020
its stock equals the MEF's TOTAL central-government debt (2020: 5 217,50;
2021: 6 210,28; 2022: 6 757,80), not external debt. Kept as published under
its own series code, with that stated in `coverage`. Its % of GDP cells are
stored as fractions (0.1774, the first cell formatted "17.7%", the rest left
as plain decimals that display "0.2") and are emitted as percent -- the Eswatini
GDP precedent. Debt SERVICE rows (flows) are not collected.

CROSS-CHECK: PDF Tableau 1 -- Dette Totale 2022 6 757,80 USD / 57 801 339,93
GNF million; T3 2023 9 159,64 USD. DOCX -- end-2024 total 79 042 500,4 GNF
million (40,4% of GDP). BCRG -- 2013 1 085,6 USD million (17,7% of GDP).
"""
from __future__ import annotations

import os
import re
import zipfile
import xml.etree.ElementTree as ET

import fitz  # PyMuPDF
import openpyxl
import pandas as pd

_ROWS = ("Dette Totale", "Dette Extérieure", "Dette Intérieure")
_NUM = re.compile(r"^\d{1,3}(?:[  \xa0]\d{3})*(?:,\d+)?$")
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
_MONTHS = {"MARS": 1, "JUIN": 2, "SEPTEMBRE": 3, "DECEMBRE": 4, "DÉCEMBRE": 4}
_COV = ("Central government (Administration centrale), external + domestic; "
        "guarantees and public-enterprise debt excluded")


def _num(s: str) -> float:
    return float(re.sub(r"[  \xa0]", "", s).replace(",", "."))


# --- PDF issues: Tableau 1 by word position --------------------------------

def _period(label: str) -> tuple[str, str] | None:
    m = re.fullmatch(r"T([1-4]) (20\d\d)", label)
    if m:
        return f"{m.group(2)}-Q{m.group(1)}", "quarterly"
    if re.fullmatch(r"20\d\d", label):
        return label, "annual"
    return None                                   # "2018-2019": printed as dashes


def _pdf(path: str) -> list[dict]:
    with fitz.open(path) as doc:
        # The list of tables carries the caption too: take the page that also
        # has the USD / GNF column heads.
        page = next((p for p in doc
                     if "Tableau 1: Encours de la dette de l'Administration" in p.get_text()
                     and len(re.findall(r"\bUSD\b", p.get_text())) >= 3), None)
        if page is None:
            raise ValueError(f"MEF Guinea Tableau 1 not found in {path}")
        words = page.get_text("words")
    lines: dict[int, list] = {}
    for w in words:
        lines.setdefault(round(w[1]), []).append((w[0], w[2], w[4]))
    ys = sorted(lines)
    sub_y = next(y for y in ys if sum(t == "USD" for *_, t in lines[y]) >= 2)
    head_y = max(y for y in ys if y < sub_y)
    # Period labels: "2021", "T1 2023", "2018-2019" (tokens joined left to right).
    toks = sorted(lines[head_y])
    labels, k = [], 0
    while k < len(toks):
        x0, x1, t = toks[k]
        if re.fullmatch(r"T[1-4]", t) and k + 1 < len(toks):
            labels.append((x0, f"{t} {toks[k + 1][2]}"))
            k += 2
            continue
        labels.append((x0, t))
        k += 1
    subs = sorted((x0, x1, t) for x0, x1, t in lines[sub_y] if t in ("USD", "GNF", "%"))
    groups, cur = [], None
    for s in subs:
        if s[2] == "USD":
            cur = []
            groups.append(cur)
        cur.append(s)
    if len(groups) != len(labels):
        raise ValueError(f"MEF Guinea {os.path.basename(path)}: {len(labels)} period "
                         f"labels for {len(groups)} USD/GNF groups")
    centres = [((x0 + x1) / 2, gi, t) for gi, g in enumerate(groups) for x0, x1, t in g]
    right_edge = max(x1 for _, x1, _ in subs) + 45

    out, seen = [], set()
    for y in ys:
        if y <= sub_y:
            continue
        toks = sorted(lines[y])
        label = " ".join(t for x0, x1, t in toks if x0 < 150)
        label = re.sub(r"\s+", " ", label)
        if label.startswith("Total de Tirages"):
            break
        row = next((r for r in _ROWS if label.replace(" ", "") == r.replace(" ", "")), None)
        if row is None or row in seen:
            continue
        seen.add(row)
        # Rebuild numbers: adjacent tokens closer than 6pt are one number.
        nums, run = [], None
        for x0, x1, t in toks:
            # Left of 150pt is the row label; right of the last sub-column (+ a
            # share cell's width) is page text -- the 2022 issue sets
            # "Graphique 1: Encours ..." on the same line as "Dette Totale".
            if x0 < 150 or x0 > right_edge:
                continue
            if run and x0 - run[1] < 6 and re.fullmatch(r"[\d,%]+", t):
                run = (run[0], x1, run[2] + " " + t)
            else:
                if run:
                    nums.append(run)
                run = (x0, x1, t)
        if run:
            nums.append(run)
        for x0, x1, t in nums:
            if t == "-":
                continue
            c = (x0 + x1) / 2
            _, gi, kind = min(centres, key=lambda z: abs(z[0] - c))
            per = _period(labels[gi][1])
            if per is None:
                continue
            period, freq = per
            # A share cell is recognised by its own "%" -- the 2022 annual issue
            # prints one after the last period with no "%" sub-header above it.
            if kind == "%" or t.endswith("%"):
                if not t.endswith("%"):
                    raise ValueError(f"MEF Guinea {row} {period}: {t!r} under a % head")
                v, unit, meas = float(t.rstrip("%").replace(",", ".")), "percent", "share"
            else:
                if not _NUM.match(t):
                    raise ValueError(f"MEF Guinea {row} {period}: unreadable {t!r}")
                v, unit, meas = _num(t), f"{kind} million", "stock"
            out.append({"component": row, "period": period, "frequency": freq,
                        "measure": meas, "value": v, "unit": unit,
                        "series_code": "MEF-DNDAPD Bulletin Tableau 1"})
    if seen != set(_ROWS):
        raise ValueError(f"MEF Guinea {os.path.basename(path)}: rows {sorted(seen)}")
    # The stocks must add up in each currency and period.
    st = {(r["component"], r["period"], r["unit"]): r["value"] for r in out
          if r["measure"] == "stock"}
    for (comp, per, unit), tot in st.items():
        if comp == "Dette Totale":
            parts = st.get(("Dette Extérieure", per, unit), 0) + st.get(("Dette Intérieure", per, unit), 0)
            if abs(parts - tot) > 0.05:
                raise ValueError(f"MEF Guinea {per} {unit}: parts {parts} != total {tot}")
    return out


# --- DOCX issues: the "Indicateurs de risque" table ------------------------

def _docx_table(path: str) -> tuple[str, dict]:
    x = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    text = "".join(t.text or "" for t in x.iter(_W + "t"))
    m = re.search(r"AU (\d{2}) (MARS|JUIN|SEPTEMBRE|D[EÉ]CEMBRE) (20\d\d)", text)
    if not m:
        raise ValueError(f"MEF Guinea: no reference date on the cover of {path}")
    period = f"{m.group(3)}-Q{_MONTHS[m.group(2)]}"
    for tbl in x.iter(_W + "tbl"):
        rows = [[re.sub(r"\s+", " ", "".join(t.text or "" for t in tc.iter(_W + "t"))).strip()
                 for tc in tr.iter(_W + "tc")] for tr in tbl.iter(_W + "tr")]
        if rows and rows[0] and rows[0][0].startswith("Indicateurs de risque"):
            return period, {r[0]: r[1:4] for r in rows[1:] if r}
    raise ValueError(f"MEF Guinea: no 'Indicateurs de risque' table in {path}")


def _cell(s: str, where: str) -> float:
    # T3 2025 prints a letter O for a zero ("4O 102 175,71"); allowed only
    # between digits, and the sum check below must then hold exactly.
    s2 = re.sub(r"(?<=\d)O(?=[\d ])|(?<=\d)O$", "0", s.replace("\xa0", " ").replace(" ", " "))
    if not _NUM.match(s2) and not re.fullmatch(r"\d+(?:,\d+)?", s2):
        raise ValueError(f"MEF Guinea {where}: unreadable cell {s!r}")
    return _num(s2)


def _docx(path: str) -> tuple[str, list[dict], tuple]:
    period, t = _docx_table(path)
    out = []
    spec = (("Montant (in millions of GNF)", "stock", "GNF million"),
            ("Montant (in millions of USD)", "stock", "USD million"),
            ("Dette nominale en % du PIB", "share_of_gdp", "percent"))
    sig = []
    for key, meas, unit in spec:
        cells = t.get(key)
        if not cells or len(cells) < 3:
            raise ValueError(f"MEF Guinea {period}: row {key!r} missing")
        vals = [_cell(c, f"{period} {key}") for c in cells[:3]]
        sig.extend(vals)
        if meas == "stock" and abs(vals[0] + vals[1] - vals[2]) > 0.2:
            raise ValueError(f"MEF Guinea {period} {key}: {vals[0]} + {vals[1]} != {vals[2]}")
        for comp, v in zip(("Dette Extérieure", "Dette Intérieure", "Dette Totale"), vals):
            out.append({"component": comp, "period": period, "frequency": "quarterly",
                        "measure": meas, "value": v, "unit": unit,
                        "series_code": "MEF-DNDAPD Bulletin Indicateurs de risque"})
    return period, out, tuple(sig)


# --- BCRG extra ----------------------------------------------------------

def _bcrg(path: str) -> list[dict]:
    ws = openpyxl.load_workbook(path, data_only=True).active
    hdr = {c.column: c.value for c in ws[7] if c.value is not None}
    qhdr = {c.column: c.value for c in ws[8] if c.value is not None}
    out = []
    cov = ("As labelled by BCRG ('Dette extérieure'); from 2020 its stock equals "
           "the MEF's TOTAL central-government debt -- the perimeter is not stable")
    for r in ws.iter_rows(min_row=9, max_row=12):
        lab = str(r[0].value or "").strip()
        if lab.startswith("Encours de la Dette (millions USD)"):
            meas, unit, scale = "stock", "USD million", 1
        elif lab.startswith("Encours de la Dette (en % du PIB)"):
            meas, unit, scale = "share_of_gdp", "percent", 100
        else:
            continue                                    # debt service: a flow
        for c in r[1:]:
            if c.value is None:
                continue
            if c.column in qhdr:
                m = re.fullmatch(r"T([1-4]) (20\d\d)", str(qhdr[c.column]).strip())
                period, freq = f"{m.group(2)}-Q{m.group(1)}", "quarterly"
            elif c.column in hdr:
                period, freq = str(hdr[c.column]), "annual"
            else:
                raise ValueError(f"BCRG Guinea: no header over {c.coordinate}")
            out.append({"component": "Encours de la Dette", "coverage": cov,
                        "period": period, "frequency": freq, "measure": meas,
                        "value": round(float(c.value) * scale, 6), "unit": unit,
                        "series_code": "BCRG 8-Dette-Exterieure"})
    if not out:
        raise ValueError("BCRG Guinea: no rows read")
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    files = [path, *(extras or [])]                 # newest issue first
    rows, seen = [], set()
    docx_sigs: dict[tuple, list[str]] = {}
    docx_rows: dict[str, list[dict]] = {}
    for f in files:
        ext = os.path.splitext(f)[1].lower()
        if ext == ".docx":
            period, recs, sig = _docx(f)
            docx_sigs.setdefault(sig, []).append(period)
            docx_rows[period] = recs
            continue
        recs = _pdf(f) if ext == ".pdf" else _bcrg(f)
        for r in recs:
            key = (r["series_code"], r["component"], r["period"], r["measure"], r["unit"])
            if key not in seen:
                seen.add(key)
                rows.append(r)
    # Two issues printing the SAME risk table: one is a copy, neither is kept.
    copied = {p for ps in docx_sigs.values() if len(ps) > 1 for p in ps}
    if copied and copied != _identical_issues:
        raise ValueError(f"MEF Guinea: issues {sorted(copied)} print identical risk "
                         f"tables -- not the known pair {sorted(_identical_issues)}")
    for period, recs in docx_rows.items():
        if period not in copied:
            rows.extend(recs)
    df = pd.DataFrame(rows)
    if "coverage" not in df.columns:
        df["coverage"] = None
    df["coverage"] = df["coverage"].fillna(_COV)
    return df


# The T1 2025 and T2 2025 issues print the same risk table (see docstring).
_identical_issues = {"2025-Q1", "2025-Q2"}
