"""Parser for INSTAT Mali "Annuaire du Commerce International des Marchandises" (Tier 3 PDF).

www.instat-mali.org/laravel-filemanager/files/shares/pub/anuair-stat-cmext<YY>_pub.pdf.
From the 2020 edition the annual tables print, per row, a code, a label, the value
("VALEUR: CFA", francs CFA -- units) and the net weight ("Poids Net: KG"):

* "Exportations / Importations de marchandises par chapitre [en <année>]" -> HS chapters
  (code printed);
* "... par pays [en <année>]" -> partner countries (ISO alpha-2 code printed);
the line of two figures before the first coded row is the table total (all products /
all partners). Country x chapter, zone x country and AES / CEDEAO / UEMOA x chapter
tables are not read (cross-tabulations). The 2017-2019 editions print two years with
shares in another layout and are not read.
A row is kept only with exactly two figures (value, weight) after its label.
"""
from __future__ import annotations

import os
import re

import pandas as pd

from ._common import row, to_number

_TITLE = re.compile(r"Tableau\s*\d+\s*:\s*(Exportations|Importations)(?:\s+annuelles)?\s+de\s+marchandises\s+par\s+"
                    r"(chapitre|pays)(?:\s+en)?\s*(\d{4})?\s*$", re.I)
_ANY = re.compile(r"^\s*Tableau\s*\d+\s*:", re.I)
_NUM = re.compile(r"^-?\d{1,3}(?:[   ]\d{3})*$")
_NOT_COUNTRY = {"XX", "QU", "QZ", "ZZ", "QS", "QR", "QW", "XZ", "ND", "ZA0"}


def _book_year(path):
    m = re.search(r"cmext(\d{2})", os.path.basename(path))
    return f"20{m.group(1)}" if m else None


def _parse_book(path: str) -> list[dict]:
    import fitz
    by = _book_year(path)
    if not by or int(by) < 2020:
        return []
    doc = fitz.open(path)
    try:
        lines = [ln for p in doc for ln in p.get_text().split("\n")]
    finally:
        doc.close()
    out, cur = [], None
    code = lab = None
    nums: list = []
    seen_total = False

    def emit(c, l, ns):
        flow, kind, y = cur
        v, w = to_number(ns[0]), to_number(ns[1])
        sc = f"Annuaire {by} {flow} par {kind}"
        common = dict(tradeflow=flow, period=y, frequency="annual", series_code=sc,
                      price_basis="fob" if flow == "export" else "cif")
        if c is None:
            kw = {}
        elif kind == "chapitre":
            kw = dict(commodity=l, commodity_classification="hs2", commodity_code_nso=c.zfill(2))
        else:
            kw = dict(partner=l, partner_type="group" if c in _NOT_COUNTRY else "country")
        if v is not None:
            out.append(row(value=v, unit="XOF", unit_multiplier=1, **common, **kw))
        if w is not None:
            common.pop("price_basis")
            out.append(row(value=w, unit="kg", unit_multiplier=1, measure="net_weight", **common, **kw))

    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if _ANY.match(s):
            m = _TITLE.match(re.sub(r"\s+", " ", s))
            if m:
                y = m.group(3) or by
                new = ("export" if m.group(1).lower().startswith("export") else "import", m.group(2).lower(), y)
                if new != cur:
                    cur, seen_total = new, False
            else:
                cur = None
            code, lab, nums = None, None, []
            continue
        if cur is None:
            continue
        toks = [t.strip() for t in re.split(r"\s{2,}", s) if t.strip()]
        for t in toks:
            is_code = (re.fullmatch(r"\d{1,2}", t) if cur[1] == "chapitre" else re.fullmatch(r"[A-Z]{2}", t))
            if _NUM.match(t) and not (is_code and lab is None and not nums and code is None):
                nums.append(t)
                if len(nums) == 2:
                    if code is None and lab is None and not seen_total:
                        emit(None, None, nums)
                        seen_total = True
                    elif code is not None and lab:
                        emit(code, re.sub(r"\s+", " ", lab).strip(), nums)
                    code, lab, nums = None, None, []
                continue
            if is_code and not nums:
                code, lab = t, None
                continue
            if code is not None and not nums:
                lab = f"{lab} {t}" if lab else t
            else:
                code, lab, nums = None, None, []
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    frames = []
    for p in [path] + list(extras or []):
        if p.lower().endswith(".pdf"):
            rs = _parse_book(p)
            if rs:
                df = pd.DataFrame(rs)
                # CHECK, never emitted: a table is kept only when its rows add up to its own
                # total (value and weight, within 0.1 %); tables whose total line or rows were
                # misread (several editions) are dropped whole.
                keep = []
                for sc, g in df.groupby("series_code"):
                    ok = True
                    for meas, gm in g.groupby("measure"):
                        tot = gm[(gm["commodity"] == "All products") & (gm["partner"] == "All partners")]["value"]
                        parts = gm[~((gm["commodity"] == "All products") & (gm["partner"] == "All partners"))]["value"].sum()
                        if len(tot) != 1 or len(gm) < 10 or abs(parts - tot.iloc[0]) > 0.001 * abs(tot.iloc[0]):
                            ok = False
                    if ok:
                        keep.append(sc)
                df = df[df["series_code"].isin(keep)]
                if df.empty:
                    continue
                df["_ed"] = _book_year(p)
                frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    key = ["tradeflow", "commodity", "commodity_code_nso", "partner", "partner_type", "measure", "period", "unit"]
    df = df.sort_values("_ed", kind="stable").drop_duplicates(key + ["_ed"])
    # within one edition a key printed twice with different figures is dropped
    dup = df.duplicated(key + ["_ed"], keep=False)
    df = df[~dup].drop_duplicates(key, keep="last")
    return df.drop(columns="_ed").reset_index(drop=True)
