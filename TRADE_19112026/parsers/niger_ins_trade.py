"""Parser for INS Niger merchandise-trade bulletins (Tier 3 PDF).

INS Niger (Service des statistiques du commerce extérieur) publishes a quarterly
"Bulletin des statistiques du commerce extérieur" and an annual "Bulletin des
statistiques annuelles (provisoires / définitives)". Values in millions of FCFA
("Unité : Millions Fcfa"), exports FOB ("FAB"), imports CIF ("CAF").

Read, per issue:
* the continent tables -- "Importations (CAF) par continent", "Exportations (FAB) par
  continent", "Balances commerciales (FAB / CAF) par continent": 5 periods per row
  (continents -> group; the "Total" row is printed with cells run together and is
  dropped);
* "Exportations selon les principaux pays de destination finale" / "Importations selon
  les principaux pays d'origine" and "... selon les groupes de produits": two blocks of 5
  periods -- quantities, then values. Only the VALUE block is read (identified because
  its AFRIQUE line equals the continent table's Afrique line; checked per issue);
* annual bulletin Tableau 1 "Evolution des échanges extérieurs : 1996-<année>": per year
  exports (1000 t, Mds FCFA), imports (1000 t, Mds FCFA), balance (Mds FCFA).

Periods: the quarterly bulletin's 5 columns are the 5 quarters ending with the issue's
quarter (the year captions are scrambled in the text layer; the quarter sequence is
not); the annual bulletin's are the years printed in the header. A row is kept only
with exactly the expected number of cells.
"""
from __future__ import annotations

import os
import re

import pandas as pd

from ._common import row, to_number

_CELL = re.compile(r"^(-?\d{1,3}(?:[   ]\d{3})*(?:,\d+)?|-)$")
_GROUPS = re.compile(r"^(AFRIQUE|AMERIQUE|ASIE|EUROPE|OCEANIE|Uemoa|UEMOA|AES|CEDEAO|Afrique|Am[ée]rique|Asie|Europe|"
                     r"Oc[ée]anie|Union|Autres|Reste|Pays et territoires|Moyen|Proche|Extr[eê]me)", re.I)


def _issue(path: str):
    b = os.path.basename(path)
    m = re.search(r"_(\d)T_(\d{4})", b)
    if m:
        return ("q", int(m.group(2)), int(m.group(1)))
    m = re.search(r"annuelles_(?:provisoires?|provosoires|d.finitives)_(\d{4})", b)
    if m:
        return ("a", int(m.group(1)), None)
    return None


def _quarters(y, q, n=5):
    out = []
    for _ in range(n):
        out.append(f"{y}-Q{q}")
        q -= 1
        if q == 0:
            y, q = y - 1, 4
    return out[::-1]


def _num(c):
    return None if c == "-" else to_number(c, decimal=",")


def _rows(lines, k):
    """(label, cells) for every label followed by exactly k cells."""
    out, lab, cells = [], None, []
    for s in lines:
        if _CELL.match(s):
            if lab is not None:
                cells.append(s)
            continue
        if lab is not None and len(cells) == k:
            out.append((lab, cells))
        # a label must carry letters (cells run together are not a label)
        lab, cells = (re.sub(r"\s+", " ", s).strip(), []) if re.search(r"[A-Za-zÀ-ÿ]", s) else (None, [])
    if lab is not None and len(cells) == k:
        out.append((lab, cells))
    return out


def _parse_issue(path: str) -> list[dict]:
    import fitz
    iss = _issue(path)
    if iss is None:
        return []
    doc = fitz.open(path)
    try:
        text = "\n".join(p.get_text() for p in doc)
    finally:
        doc.close()
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    kind, y, q = iss
    freq = "quarterly" if kind == "q" else "annual"
    out = []

    def periods_after(i):
        if kind == "q":
            return _quarters(y, q)
        ys = []
        for s in lines[i:i + 40]:
            if re.fullmatch(r"(19|20)\d{2}", s):
                ys.append(s)
                if len(ys) == 5:
                    break
        return ys if len(ys) == 5 and [int(v) for v in ys] == list(range(int(ys[0]), int(ys[0]) + 5)) else None

    # ---- continent tables: the "Unité : Millions" blocks in the order of their titles
    titles = [(i, "import" if "Importations" in s else "export" if "Exportations" in s else "balance")
              for i, s in enumerate(lines) if re.search(r"Tableau\s*\d+\s*:\s*(Importations \(CAF\)|Exportations \(FAB\)|"
                                                        r"Balances commerciales \(FAB / CAF\)) par continent", s)]
    units = [i for i, s in enumerate(lines) if s.startswith("Unité : Millions")]
    cont = {}
    for (ti, flow), ui in zip(titles, [u for u in units if u > titles[0][0]] if titles else []):
        per = periods_after(ui)
        if not per:
            continue
        nxt = next((u for u in units if u > ui), len(lines))
        body = lines[ui + 1:nxt]
        stop = next((j for j, s in enumerate(body) if s.lower().startswith("total")), len(body))
        body = body[:stop]                     # the block ends at its Total line
        for lab, cells in _rows(body, 5):
            if not re.match(r"^(Afrique|Am[ée]rique|Asie|Europe|Oc[ée]anie|Pays et territoires)", lab):
                continue                       # only the continent lines (the block may run on)
            for p, c in zip(per, cells):
                v = _num(c)
                if v is None:
                    continue
                out.append(row(tradeflow=flow, period=p, frequency=freq, value=v, unit="XOF", unit_multiplier=1e6,
                               partner=lab, partner_type="group", series_code="continent",
                               price_basis={"import": "cif", "export": "fob"}.get(flow, "")))
                cont[(flow, lab.lower(), p)] = v
    # ---- partner and product-group tables: value block = last 5 of 10 cells
    for i, s in enumerate(lines):
        m = re.search(r"Tableau\s*\d+\s*:\s*(Exportations?|Importations?) selon (les principaux pays|les groupes de produits)", s)
        if not m:
            continue
        flow = "export" if m.group(1).lower().startswith("export") else "import"
        partner_tab = "pays" in m.group(2)
        per = periods_after(i)
        if not per:
            continue
        end = next((j for j in range(i + 1, len(lines)) if re.match(r"Tableau\s*\d+\s*:", lines[j])), len(lines))
        rows = _rows(lines[i + 1:end], 10)
        # check the value block against the continent table (Afrique line), when both exist
        if partner_tab:
            af = [r for r in rows if r[0].upper() == "AFRIQUE"]
            if af:
                vals = [_num(c) for c in af[0][1][5:]]
                ref = [cont.get((flow, "afrique", p)) for p in per]
                if any(r is not None for r in ref) and any(r is not None and v is not None and abs(r - v) > 0.5
                                                           for r, v in zip(ref, vals)):
                    continue
        for lab, cells in rows:
            if lab.lower().startswith(("total", "source")):
                continue
            for p, c in zip(per, cells[5:]):
                v = _num(c)
                if v is None:
                    continue
                kw = (dict(partner=lab, partner_type="group" if _GROUPS.match(lab) or lab.isupper() else "country")
                      if partner_tab else dict(commodity=lab, commodity_classification="national"))
                out.append(row(tradeflow=flow, period=p, frequency=freq, value=v, unit="XOF", unit_multiplier=1e6,
                               price_basis="fob" if flow == "export" else "cif",
                               series_code="pays" if partner_tab else "groupes de produits", **kw))
    # ---- annual Tableau 1
    if kind == "a":
        hits = [k for k, s in enumerate(lines) if re.search(r"Tableau\s*1\s*:\s*Evolution des [ée]changes", s)]
        i = hits[-1] if hits else None            # the last hit: the first is the list of tables
        if i is not None:
            yr, cells = None, []

            def flush():
                if yr is None:
                    return
                if len(cells) == 8:
                    idx = {"eq": 0, "ev": 1, "iq": 3, "iv": 4, "b": 6}
                elif len(cells) == 6:
                    idx = {"eq": 0, "ev": 1, "iq": 2, "iv": 3, "b": 4}
                else:
                    return
                for k2, (flow, meas) in {"eq": ("export", "net_weight"), "ev": ("export", "value"),
                                         "iq": ("import", "net_weight"), "iv": ("import", "value"),
                                         "b": ("balance", "value")}.items():
                    v = _num(cells[idx[k2]])
                    if v is None:
                        continue
                    out.append(row(tradeflow=flow, period=yr, frequency="annual", value=v,
                                   unit="XOF" if meas == "value" else "tonnes",
                                   unit_multiplier=1e9 if meas == "value" else 1e3, measure=meas,
                                   price_basis={"export": "fob", "import": "cif"}.get(flow, "") if meas == "value" else "",
                                   series_code="Tableau 1"))
            for s in lines[i + 1:]:
                if re.match(r"Tableau\s*2\s*:", s):
                    break
                if re.fullmatch(r"(19|20)\d{2}", s) and (yr is None or int(s) == int(yr) + 1):
                    flush()
                    yr, cells = s, []
                elif yr is not None and _CELL.match(s):
                    cells.append(s)
            flush()
    # a label printed twice in one table with different figures ("Autres" under two
    # zones) cannot be told apart: all its copies are dropped
    if out:
        df = pd.DataFrame(out)
        key = ["tradeflow", "commodity", "partner", "partner_type", "measure", "period", "series_code"]
        df = df.drop_duplicates(key + ["value"])
        out = df[~df.duplicated(key, keep=False)].to_dict("records")
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    frames = []
    for p in [path] + list(extras or []):
        if not p.lower().endswith(".pdf"):
            continue
        rs = _parse_issue(p)
        if not rs:
            continue
        df = pd.DataFrame(rs)
        iss = _issue(p)
        # newest issue wins; a definitive annual bulletin beats a provisional one of the same year
        df["_v"] = f"{iss[1]}{iss[2] or 9}{'1' if 'finitive' in p else '0'}"
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    key = ["tradeflow", "commodity", "commodity_classification", "partner", "partner_type", "measure", "period",
           "frequency", "unit"]
    df = df.sort_values("_v", kind="stable").drop_duplicates(key, keep="last")
    return df.drop(columns="_v").reset_index(drop=True)
