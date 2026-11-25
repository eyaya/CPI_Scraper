"""Parser for ONS Algeria "Rétrospective Statistique 1962-2020", chapter X "Commerce extérieur" (PDF).

ONS republishes the customs (Direction Générale des Douanes / CNIS) foreign-trade
statistics in its statistical retrospective; the chapter is a text-layer PDF of
annual tables in millions (10^6) or thousands (10^3) of dinars:
  Tableau 1.1      imports and exports 1963-1966
  Tableau 1.2/1.3  imports / exports by zone 1964-1966
  Tableaux 2.1-2.8 imports / exports by broad economic category (C.G.C.E.)
                   1967-2020, with the total
  Tableaux 3.1-3.10 imports by geographical zone and main countries 1967-2020
  Tableaux 4.1-4.9 exports by geographical zone and main countries 1967-2020
  Tableaux 5.x / 6.x principal products exported / imported (national list)
Not read: Tableaux 7.x (the ten first clients / suppliers -- rank tables whose
country changes by year).

THOUSANDS ARE SEPARATED BY SPACES ("1 669 026,5"), so a line cannot be split on
blanks. Columns are located from the x-position of the year headers, and every
word of a data line is assigned to the nearest year column; the words of one
column form one number. A cell that does not read as a well-formed number
(groups of exactly three digits after the first, decimal comma) -- e.g. the
misprint "307 5444,9" -- is dropped, never repaired. "-", "...", "---" are blank.
The partner and product tables' "Total" lines are not emitted (the totals come
from Tableaux 1.1 and 2.x).
"""
from __future__ import annotations

import re

import pandas as pd

from ._common import row

_YEAR = re.compile(r"^(19[6-9]\d|20[0-2]\d)(?:à|\*)?$")
_CELL = re.compile(r"^\d{1,3}(?: \d{3})*(?:,\d+)?$|^\d+(?:,\d+)?$")
_BLANK = {"-", "--", "---", "…", "...", "....", "n.d", "nd"}
_GROUP = re.compile(r"dont|^pays(?! bas)|^autres?\b|reste du monde|ind[ée]termin|^am[ée]rique|^asie\b|^afrique\b|"
                    r"^europe|^c\.e\.e|^u\.e|union europ|^maghreb|^o\.c\.d\.e|zone franc|^total|"
                    r"^oc[ée]anie|^proche|^moyen", re.I)


def _lines_of(page):
    words = page.extract_words(x_tolerance=1.5, y_tolerance=2, keep_blank_chars=False)
    words.sort(key=lambda w: (round(w["top"]), w["x0"]))
    lines, cur, top = [], [], None
    for w in words:
        if top is None or abs(w["top"] - top) > 3:
            if cur:
                lines.append(sorted(cur, key=lambda w: w["x0"]))
            cur, top = [w], w["top"]
        else:
            cur.append(w)
    if cur:
        lines.append(sorted(cur, key=lambda w: w["x0"]))
    return lines


def _num(cell: str):
    c = cell.strip()
    if not c or c.lower() in _BLANK or set(c) <= set(".…-"):
        return None, True
    if not _CELL.match(c):
        return None, False
    return float(c.replace(" ", "").replace(",", ".")), True


def _kind(title: str):
    t = title.lower()
    if "dix premiers" in t or "premiers clients" in t or "premiers fournisseurs" in t:
        return None, None
    if "evolution des importations et exportations" in t:
        return "headline", None
    if "c.g.c.e" in t or "catégories économiques" in t:
        return "bec", None
    if "par zones" in t:
        return "partner", ("import" if "importations" in t else "export")
    if "produits export" in t:
        return "product", "export"
    if "produits import" in t:
        return "product", "import"
    return None, None


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    import pdfplumber
    out = []
    state = {"kind": None, "flow": None, "mult": None, "cols": None, "tid": "", "pending": ""}
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for ln in _lines_of(page):
                text = " ".join(w["text"] for w in ln).strip()
                m = re.match(r"^Tableau\s*(\d+)\s*\.?\s*(\d+)\s*:", text)
                if m:
                    kind, flow = _kind(text)
                    state.update(kind=kind, flow=flow, mult=None, cols=None,
                                 tid=f"Tableau {m.group(1)}.{m.group(2)}", pending="")
                    continue
                if state["kind"] is None:
                    continue
                if re.match(r"^(Table\s+\d|Rétrospective|Statistical Retrospective)", text):
                    continue
                if re.search(r"Unit[ée]\s*:?\s*10\s*6|Unit[ée]\s*:?\s*106|En Millions", text, re.I):
                    state["mult"] = 1e6
                    continue
                if re.search(r"Unit[ée]\s*:?\s*10\s*3|Unit[ée]\s*:?\s*103|En Milliers", text, re.I):
                    state["mult"] = 1e3
                    continue
                years = [(w, int(_YEAR.match(w["text"]).group(1))) for w in ln if _YEAR.match(w["text"])]
                if len(years) >= 2 and len(years) >= len(ln) - 6:
                    state["cols"] = [((w["x0"] + w["x1"]) / 2, y) for w, y in years]
                    state["right"] = [(w["x1"], y) for w, y in years]
                    state["pending"] = ""
                    continue
                if state["cols"] is None or state["mult"] is None:
                    continue
                if text.startswith(("(", "*", "Source", "Note")):
                    continue
                low = text.lower()
                if state["kind"] == "bec" and low in ("importations", "exportations"):
                    state["flow"] = "import" if low == "importations" else "export"
                    continue
                cols = state["cols"]
                left = cols[0][0] - (cols[1][0] - cols[0][0]) * 0.6
                label_w, nums = [], []
                for w in ln:
                    xc = (w["x0"] + w["x1"]) / 2
                    if xc < left or not re.match(r"^[\d,.…\-]+$", w["text"]):
                        label_w.append(w["text"])
                    else:
                        nums.append(w)
                # Thousands groups sit ~2pt apart, columns ~20pt: merge on the gap,
                # then file each number under the year whose (right-aligned)
                # header ends nearest to it.
                groups = []
                for w in nums:
                    if groups and w["x0"] - groups[-1][-1]["x1"] < 4:
                        groups[-1].append(w)
                    else:
                        groups.append([w])
                cells = {}
                for g in groups:
                    x1 = g[-1]["x1"]
                    y = min(state["right"], key=lambda c: abs(c[0] - x1))[1]
                    if y in cells:           # two numbers claim one column: unreadable
                        cells[y] = None
                    else:
                        cells[y] = " ".join(w["text"] for w in g)
                label = " ".join(label_w).strip()
                vals = {y: t for y, t in cells.items() if t}
                if not vals:
                    state["pending"] = label
                    continue
                if not label:
                    label = state["pending"]
                state["pending"] = ""
                label = re.sub(r"\s*\(\d\)\s*", " ", label).strip()
                label = re.sub(r"\s+", " ", label)
                if not label or "à partir" in label or len(label) > 90:
                    continue                  # a footnote sentence carrying years, not a row
                kind, flow = state["kind"], state["flow"]
                is_total = label.lower().startswith("total")
                for y, cell in vals.items():
                    v, ok = _num(cell)
                    if v is None:
                        continue
                    kw = dict(period=str(y), frequency="annual", value=v, unit="DZD",
                              unit_multiplier=state["mult"], series_code=state["tid"])
                    if kind == "headline":
                        fl = {"importations": "import", "exportations": "export"}.get(label.lower())
                        if fl:
                            out.append(row(tradeflow=fl, **kw))
                    elif kind == "bec" and flow:
                        if is_total:
                            out.append(row(tradeflow=flow, **kw))
                        else:
                            out.append(row(tradeflow=flow, commodity=label.replace(" (*)", "").strip(),
                                           commodity_classification="bec", **kw))
                    elif kind == "partner" and flow and not is_total:
                        name = re.sub(r"\s*\*?\s*dont\s*:?$", "", label).strip(" *")
                        ptype = "group" if _GROUP.search(label) else "country"
                        out.append(row(tradeflow=flow, partner=name, partner_type=ptype, **kw))
                    elif kind == "product" and flow and not is_total:
                        out.append(row(tradeflow=flow, commodity=label, commodity_classification="national", **kw))
    return pd.DataFrame(out)
