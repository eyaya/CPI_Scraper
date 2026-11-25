"""Parser for INS Congo "Bulletin (des statistiques) du Commerce Extérieur"
(quarterly from 2022 Q1, annual bulletins 2023-2025; customs data).

INS posts each bulletin as a PDF and, from late 2025, also as an Excel
conversion of the same document. Both are read as one STREAM of rows (Excel
rows; or PDF text lines split into a label and its trailing numbers -- every
figure in these annexes carries a decimal comma, so "1 147,5 949,8" splits
unambiguously). Tables are found by their caption "Tableau N : ..." and read
only when the caption is one of:

  "Caractéristiques du commerce extérieur"  -> Exportations / Importations /
      Balance commerciale over 6 quarters ("1T25" ... "2T26") or 5 years; the
      unit column prints "10^9 FCFA" (rendered "109 FCFA") -> XAF x 1e9.
      Taux de couverture (a ratio) is not read.
  "principaux pays partenaires ... à l'exportation / l'importation" (top 10,
      the bulletin's own quarter or year) -> partner countries
  "principaux produits ... à l'exportation / l'importation" (top 10) and
      "Evolution de quelques produits" (6 quarters / 5 years) -> national
      commodity list
  "Répartition ... par zone géographique / zone économique" -> groups
Not read: shares, indices, transport modes, partner x product tables.
Scale from "Unité : milliards / millions de FCFA" (or the unit column);
a table without a readable scale is dropped. The newest bulletin wins a key.
"""
from __future__ import annotations

import os
import re

import openpyxl
import pandas as pd
import pdfplumber

from ._common import row, to_number, _fold
from ..schema import KEY

_NUMTOK = re.compile(r"(?<![\w,])(-?\d{1,3}(?:[   ]\d{3})*,\d+|-?\d+,\d+)(?![\w,])")
_QW = {"premier": 1, "1er": 1, "deuxieme": 2, "2eme": 2, "2ieme": 2, "2e": 2, "troisieme": 3, "3eme": 3,
       "3ieme": 3, "quatrieme": 4, "4eme": 4, "4ieme": 4}


def _rows_xlsx(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        for ws in wb.worksheets:
            for r in ws.iter_rows(values_only=True):
                cells = [c for c in r if c is not None and str(c).strip() != ""]
                if cells:
                    yield cells
    finally:
        wb.close()


def _rows_pdf(path):
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").split("\n"):
                line = line.strip()
                if not line:
                    continue
                toks = list(_NUMTOK.finditer(line))
                # trailing numbers only: the label is what precedes the first one
                # that is followed by numbers / dashes to the end of the line
                cut = None
                for m in toks:
                    rest = line[m.start():]
                    if re.fullmatch(r"(?:\s*(?:-?\d{1,3}(?:[   ]\d{3})*,\d+|-?\d+,\d+|-))+\s*", rest):
                        cut = m.start()
                        break
                if cut is None:
                    yield _Line([line], line)
                    continue
                lab = line[:cut].strip()
                nums = re.findall(r"-?\d{1,3}(?:[   ]\d{3})*,\d+|-?\d+,\d+|(?<!\S)-(?!\S)", line[cut:])
                yield _Line(([lab] if lab else []) + nums, line)


class _Line(list):
    """A PDF text line split into cells, keeping the raw line so a single-period
    "Valeur | Pourcentage" table can be re-split (see _split_vp)."""
    def __init__(self, cells, raw=None):
        super().__init__(cells)
        self.raw = raw


# "Chine 85 161 25,50": label, value, percentage. The 2022 bulletins print the
# value as an INTEGER, which the decimal-comma tokeniser cannot see, so it stayed
# in the label and the percentage was read as the value. The label is matched
# lazily, so the value takes every digit group the line allows; the split is then
# PROVED per table by _vp_consistent (value / percentage is one total for every row).
_VP = re.compile(r"^(?P<lab>.*?\S)\s+(?P<v>\d{1,3}(?:[   ]\d{3})*(?:,\d+)?|\d+,\d+)\s+(?P<p>\d{1,3},\d+)$")

_VP_NUMS = re.compile(r"(\d{1,3}(?:[   ]\d{3})*(?:,\d+)?|\d+,\d+)\s+(\d{1,3},\d+)")


def _split_vp(raw):
    m = _VP.match((raw or "").strip())
    return (m.group("lab"), m.group("v"), m.group("p")) if m else None


def _vp_consistent(pairs):
    """[(value, value_token, pct)] of one table: every row must imply the same
    total (value * 100 / pct) within the rounding of both printed figures."""
    pts = [(v, tok, p, ptok) for v, tok, p, ptok in pairs if p > 0]
    if len(pts) < 2:
        return False
    # Each row bounds the total: (v -+ half a printed unit) * 100 / (p +- half a
    # printed percentage unit). The bounds of all rows must overlap (0.5 % slack
    # for NSO rounding).
    lo, hi = 0.0, float("inf")
    for v, tok, p, ptok in pts:
        half = 0.5 * (10.0 ** -len(tok.split(",")[1]) if "," in tok else 1.0)
        dp = 0.5 * 10.0 ** -len(ptok.split(",")[1]) if "," in ptok else 0.005
        dp = min(dp, p / 2)
        lo = max(lo, (v - half) * 100 / (p + dp))
        hi = min(hi, (v + half) * 100 / (p - dp))
    return lo <= hi * 1.005


def _period_label(s):
    s = str(s).strip()
    m = re.fullmatch(r"([1-4])\s*T\s*(\d{2})", s, re.I)
    if m:
        return f"20{m.group(2)}-Q{m.group(1)}", "quarterly"
    if re.fullmatch(r"(19|20)\d\d", s.split(".")[0]):
        return s.split(".")[0], "annual"
    return None


def _caption_period(cap):
    t = _fold(cap)
    m = re.search(r"(premier|1er|deuxieme|2eme|2ieme|2e|troisieme|3eme|3ieme|quatrieme|4eme|4ieme)\s+trimestre\s+(\d{4})", t)
    if m:
        return f"{m.group(2)}-Q{_QW[m.group(1)]}", "quarterly"
    m = re.search(r"\ben\s+((?:19|20)\d\d)\b", t)
    if m:
        return m.group(1), "annual"
    return None


def _kind(cap):
    t = _fold(cap)
    if "par produit" in t or "indice" in t or "transport" in t or "termes" in t:
        return None
    if "caracteristiques" in t:
        return "head"
    if "principaux pays partenaires" in t:
        return "partner"
    if "principaux produits" in t or "quelques produits" in t:
        return "product"
    if "zone geographique" in t or "zone economique" in t:
        return "zone"
    return None


def _flow(cap):
    t = _fold(cap)
    return "export" if "exportation" in t else "import" if "importation" in t else None


def _scale(text):
    t = _fold(text)
    if re.search(r"milliards?\s+de\s+f\s*cfa|10\s*9\s*f\s*cfa|\b109\s+fcfa", t):
        return 1e9
    if re.search(r"millions?\s+de\s+f\s*cfa", t):
        return 1e6
    return None


def _num(c):
    if isinstance(c, (int, float)):
        return float(c)
    s = str(c).strip()
    if s in ("-", "") or s.endswith("*"):
        return None
    return to_number(s, decimal=",")


DROPPED: list = []   # (file, caption, rows) of tables whose row split could not be proved


def parse_bulletin(path: str) -> pd.DataFrame:
    rows = _rows_xlsx(path) if path.lower().endswith(".xlsx") else _rows_pdf(path)
    out, cap, kind, cols, unit, single = [], "", None, None, None, None
    # Rows of the current table are held until it ends and kept only if its row
    # split is proved: a single-period table's value / percentage pairs must all
    # imply one total (_vp_consistent); a multi-period row must carry exactly one
    # cell per period column, else its values would slide onto other periods.
    tbl, tbl_bad, pairs, pend, last_start, frag = [], False, [], None, None, False

    def flush():
        nonlocal tbl, tbl_bad, pairs, pend, last_start, frag
        pend, last_start, frag = None, None, False
        if tbl and not tbl_bad and (not pairs or _vp_consistent(pairs)):
            out.extend(tbl)
        elif tbl:
            DROPPED.append((os.path.basename(path), re.sub(r"\s+", " ", cap)[:60], len(tbl)))
        tbl, tbl_bad, pairs = [], False, []

    for cells in rows:
        first = str(cells[0])
        f0 = _fold(first)
        mcap = re.search(r"tableau\s*\d+\s*:", f0)
        if mcap and (mcap.start() == 0 or f0[:mcap.start()].strip() in ("annexes",)):
            flush()
            first = first[mcap.start():] if len(first) == len(f0) else first
            cap, kind, cols, single = first, _kind(first), None, None
            unit = _scale(first)
            continue
        if kind is None:
            continue
        if cols is None and single is None:
            if len(cells) == 1 and len(first.split()) > 1 and not f0.startswith(("unite", "valeur :", "valeur:")):
                toks = first.split()
                if any(_period_label(t) for t in toks) or any(_fold(t).startswith("valeur") for t in toks):
                    cells = toks
            if f0.startswith(("unite", "valeur :", "valeur:")):
                unit = _scale(" ".join(map(str, cells))) or unit
                continue
            labs = [_period_label(c) for c in cells]
            # a header has >= 2 period columns; one year alone is a caption wrapped
            # onto the next line ("premier trimestre 2025"), which used to become a
            # one-column "2025" header that filed 1T24 figures under the year 2025
            if sum(1 for l in labs if l) >= 2:
                cols = [l for l in labs if l]
                continue
            if any(_fold(str(c)).startswith("valeur") for c in cells):
                single = _caption_period(cap)
                if single is None:
                    kind = None
                continue
            if len(cells) == 1 and not any(_num(c) is not None for c in cells):
                cap += " " + first          # a caption wrapped onto the next line
                kind = _kind(cap)
                unit = unit or _scale(first)
                continue
            continue
        if f0.startswith(("source", "tableau", "graphique")):
            flush()
            kind = None
            continue
        label = first.strip()
        vals = [c for c in cells[1:]]
        if not single and cols and kind != "head" and getattr(cells, "raw", None) is not None:
            # Multi-period PDF table ("Evolution de quelques produits"): a label may
            # wrap DOWN onto its figures' line ("Froment [blé] et" / "méteil 14,268 ...")
            # or AROUND them ("Sucres de canne ou de" / figures / "betterave"), so a
            # text-only line cannot be given to the row above or below with certainty.
            # Both neighbours of such a line are dropped (Excel versions are unaffected).
            if not any(_num(v) is not None for v in vals):
                if last_start is not None and len(tbl) > last_start:
                    DROPPED.append((os.path.basename(path), re.sub(r"\s+", " ", cap)[:40]
                                    + " | wrapped label after row", len(tbl) - last_start))
                    del tbl[last_start:]
                last_start, frag = None, True
                continue
            if frag:
                frag, last_start = False, None
                DROPPED.append((os.path.basename(path), re.sub(r"\s+", " ", cap)[:40]
                                + " | wrapped label before row " + label[:20], 1))
                continue
            last_start = len(tbl)
        if single and getattr(cells, "raw", None) is not None:
            # PDF line of a "Valeur | Pourcentage" table: re-split it
            raw = cells.raw.strip()
            only = _VP_NUMS.fullmatch(raw)
            if only and pend:
                # a label wrapped ABOVE its figures ("Huiles brutes de pétrole" /
                # "1 136 929 89,09", 2022-Q4 Tableau 4): the figures alone fully
                # match one value + one percentage, the label is the line above
                sp = (pend, only.group(1), only.group(2))
            else:
                sp = None if only else _split_vp(raw)
            if sp is None:
                if re.fullmatch(r"\d{1,3}", raw) or "institut national de la statistique" in _fold(raw):
                    continue            # page number / running footer inside the table
                if re.search(r"\d", raw):
                    tbl_bad = True      # a data line that is not label + value + %
                else:
                    pend = raw
                continue
            if pend and not only:
                sp = (pend + " " + sp[0], sp[1], sp[2])   # label wrapped over two lines
            pend = None
            label, vtok, ptok = sp
            vals = [vtok, ptok]
        if single and len(vals) >= 2 and _num(vals[0]) is not None and _num(vals[1]) is not None:
            tok = [c.strip() if isinstance(c, str) else repr(float(c)).replace(".", ",") for c in vals[:2]]
            pairs.append((_num(vals[0]), tok[0], _num(vals[1]), tok[1]))
        u = unit
        if kind == "head":
            if vals and isinstance(vals[0], str) and _scale(vals[0]):
                u = _scale(vals[0])
                vals = vals[1:]
            elif re.search(r"10\s*9\s*FCFA|109\s+FCFA", label):
                u = 1e9
                label = re.sub(r"\s*(10\s*9|109)\s+FCFA", "", label).strip()
        if u is None:
            continue
        fl = _fold(label)
        if kind == "head":
            flow = {"exportations": "export", "importations": "import",
                    "balance commerciale": "balance"}.get(fl)
            if flow is None:
                continue
            kw = dict(commodity=None, partner=None)
        else:
            flow = _flow(cap)
            if flow is None or fl.startswith(("total", "ensemble")):
                continue
            if kind == "partner":
                kw = dict(partner=label, partner_type="country")
            elif kind == "zone":
                kw = dict(partner=label, partner_type="group")
            else:
                kw = dict(commodity=label, commodity_classification="national")
        pers = [single] if single else cols
        if not single and len(vals) != len(cols):
            # cells and period columns do not line up (a fused cell "280,943    227,038",
            # an empty cell, or a figure swallowed by the label): the ROW is dropped,
            # never aligned from the left. A row of dashes only carries nothing.
            if any(_num(v) is not None for v in vals):
                DROPPED.append((os.path.basename(path), re.sub(r"\s+", " ", cap)[:40] + " | row " + label[:30], 1))
            continue
        nums = [_num(v) for v in vals]
        for (per, freq), v in zip(pers, nums):
            if v is None:
                continue
            if flow != "balance" and v < 0:
                continue
            tbl.append(row(tradeflow=flow, period=per, frequency=freq, value=v, unit="XAF",
                           unit_multiplier=u, series_code=re.sub(r"\s+", " ", cap)[:12], **kw))
    flush()
    df = pd.DataFrame.from_records(out)
    if df.empty:
        return df
    # TWO CAPTIONS, ONE FIGURE. The same figure printed in two tables of one bulletin
    # under different scales ("Huiles brutes de pétrole 1 039,707" for 1T24 in Tableau 4,
    # "milliards", and Tableau 10, "millions", 2024-Q1 bulletin): one caption is wrong and
    # the text cannot say which, so every table involved is dropped. (Repaired 2026-11-12.)
    k = [c for c in KEY if c in df.columns]
    g = df.groupby(k, dropna=False)
    clash = g["unit_multiplier"].transform("nunique") > 1
    same = (g["value"].transform("max") - g["value"].transform("min")).abs() <= 0.0005
    bad = set(df.loc[clash & same, "series_code"])
    if bad:
        DROPPED.append((os.path.basename(path), "scale clash: " + ", ".join(sorted(bad)),
                        int(df["series_code"].isin(bad).sum())))
        df = df[~df["series_code"].isin(bad)]
    return df.drop_duplicates(k).reset_index(drop=True)


def bulletin_key(path: str) -> str:
    b = _fold(os.path.basename(path))
    m = re.search(r"(\d{4})q(\d)", b)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(r"(premier|1|deuxieme|troisieme|quatrieme)-?trimestre-(\d{4})", b)
    if m:
        q = {"premier": 1, "1": 1, "deuxieme": 2, "troisieme": 3, "quatrieme": 4}[m.group(1)]
        return f"{m.group(2)}-{q}"
    m = re.search(r"(20\d\d)", b)
    return f"{m.group(1)}-5" if m else b


def parse(path: str, extras=None) -> pd.DataFrame:
    files = sorted({path, *(extras or [])}, key=bulletin_key)
    df = pd.concat([parse_bulletin(f) for f in files], ignore_index=True)
    return df.drop_duplicates([k for k in KEY if k in df.columns], keep="last").reset_index(drop=True)
