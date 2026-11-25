"""Parser for INE Guinea-Bissau annual "Comércio Externo" yearbooks (Tier 3 PDF).

INE (Instituto Nacional de Estatística) published one book per year (2001/2002 ..
2010) at www.stat-guinebissau.com/Menu_principal/Pubicações/Comercio_externo/<ano>.pdf:

* "RESULTADOS GERAIS - ANO <ano>" (Unidade: 10^3 XOF): Importação (CIF), Exportação
  Nacional (FOB), Saldo Comercial -> import / export / balance;
* "REPARTIÇÃO POR ZONAS ECONOMICAS E PAISES" (10^3 XOF): imports, %, exports, % per
  zone (CEDEAO, UE, AFRICA, EUROPA, AMERICA ..., partner_type group) and country
  (printed indented under its zone), and "TOTAL GERAL";
* "IMPORTAÇÃO / EXPORTAÇÃO DE MERCADORIAS SEGUNDO AS SECÇÕES E CAPÍTULOS" -- HS
  chapters ("CAP 42", code printed), quantity in tonnes and value in 10^3 XOF;
  section ("SEC IX") subtotals are skipped.

Printed signs: ".." = nil, "º" = below half the unit -- both skipped (never 0).
A table continues on the following pages until another table title appears. A row
is kept only when its label is followed by exactly the expected number of cells.
"""
from __future__ import annotations

import re

import pandas as pd

from ._common import row, to_number

_CELL = re.compile(r"^(-?\d{1,3}(?:[   ]\d{3})*(?:,\d+)?|-?\d+(?:,\d+)?|\.\.|º|-)$")
_HEAD = re.compile(r"RESULTADOS GERAIS\s*-\s*ANO\s*(\d{4})", re.I)
_PART = re.compile(r"REPARTI[ÇC][ÃA]O POR ZONAS ECON[OÓ]MICAS E PA[IÍ]SES\s*-\s*ANO\s*(\d{4})", re.I)
_CHAP = re.compile(r"(IMPORTA[ÇC][ÃA]O|EXPORTA[ÇC][ÃA]O) DE MERCADORIAS SEGUNDO AS SEC[ÇC][OÕ]ES E CAP[IÍ]TULOS?.*?ANO\s*(\d{4})(?:\s*E\s*(\d{4}))?", re.I)
_ANYTITLE = re.compile(r"\bANO\s*\d{4}\b")


def _v(c: str):
    return None if c in ("..", "º", "-") else to_number(c, decimal=",")


def _parse_book(path: str) -> list[dict]:
    import fitz
    doc = fitz.open(path)
    out = []
    state = None                       # ("part", year) | ("chap", flow, years)
    import os
    book = re.findall(r"(\d{4})", os.path.basename(path))
    book_year = book[-1] if book else None
    try:
        for page in doc:
            raw = page.get_text()
            top = "\n".join(raw.split("\n")[:4])
            m = _HEAD.search(top)
            if m:
                state = None
                y = m.group(1)
                # the 2009 book titles its general results "ANO 2008" over the 2009 figures:
                # a year that is not the book's own is not trusted
                if y != book_year or "103 XOF" not in raw.replace("10³", "103"):
                    continue
                lines = [ln.strip() for ln in raw.split("\n") if ln.strip()]
                for i, ln in enumerate(lines[:-1]):
                    f = ("import" if ln.lower().startswith("importa") else
                         "export" if ln.lower().startswith("exporta") else
                         "balance" if ln.lower().startswith("saldo") else None)
                    if f and _CELL.match(lines[i + 1]):
                        v = _v(lines[i + 1])
                        if v is not None:
                            out.append(row(tradeflow=f, period=y, frequency="annual", value=v, unit="XOF",
                                           unit_multiplier=1e3,
                                           price_basis={"import": "cif", "export": "fob"}.get(f, ""),
                                           series_code="Resultados gerais"))
                continue
            m = _PART.search(top)
            if m:
                # two-year books (2001 e 2002) print two column pairs: not read
                state = ("part", m.group(1)) if not re.search(r"ANO\s*\d{4}\s*E\s*\d{4}", top) else ("skip",)
            else:
                m = _CHAP.search(top)
                if m:
                    yrs = [m.group(2)] + ([m.group(3)] if m.group(3) else [])
                    state = ("chap", "import" if m.group(1).upper().startswith("IMPORT") else "export", yrs)
                elif _ANYTITLE.search(top):
                    state = None             # another table begins
            if state is None or state[0] == "skip":
                continue
            lines = [ln.rstrip() for ln in raw.split("\n") if ln.strip()]
            if state[0] == "part":
                y = state[1]
                lab, cells = None, []
                for ln in lines:
                    s = ln.strip()
                    if _CELL.match(s):
                        if lab is not None:
                            cells.append(s)
                            if len(cells) == 4:
                                _part_row(out, lab, cells, y)
                                lab, cells = None, []
                        continue
                    if re.search(r"ZONAS ECON|ESTAT[IÍ]S|IMPORTA|EXPORTA|^%$|10\d? XOF|TICOS OU", s) or s == "%":
                        lab, cells = None, []
                        continue
                    lab, cells = ln, []
            else:
                _, flow, yrs = state
                need = 2 * len(yrs)
                code, lab, cells = None, "", []
                for ln in lines:
                    s = ln.strip()
                    mc = re.match(r"^(CAP|SEC)\s+(\w+)$", s)
                    if mc:
                        code, lab, cells = (mc.group(2) if mc.group(1) == "CAP" else None), "", []
                        sec = mc.group(1) == "SEC"
                        if sec:
                            code = "SEC"
                        continue
                    if code is None:
                        continue
                    if _CELL.match(s):
                        cells.append(s)
                        if len(cells) == need:
                          for k, y in enumerate(yrs):
                            if code != "SEC" and code.isdigit() and lab:
                                q, v = _v(cells[2 * k]), _v(cells[2 * k + 1])
                                cc = code.zfill(2)
                                name = re.sub(r"\s+", " ", lab).strip()
                                sc = f"Comercio externo {y} capitulos"
                                if v is not None:
                                    out.append(row(tradeflow=flow, period=y, frequency="annual", value=v, unit="XOF",
                                                   unit_multiplier=1e3, commodity=name, commodity_classification="hs2",
                                                   commodity_code_nso=cc,
                                                   price_basis="cif" if flow == "import" else "fob", series_code=sc))
                                if q is not None:
                                    out.append(row(tradeflow=flow, period=y, frequency="annual", value=q, unit="tonnes",
                                                   unit_multiplier=1, measure="net_weight", commodity=name,
                                                   commodity_classification="hs2", commodity_code_nso=cc,
                                                   series_code=sc))
                          code, lab, cells = None, "", []
                        continue
                    lab = f"{lab} {s}"
    finally:
        doc.close()
    return out


def _part_row(out, lab, cells, y):
    name = lab.strip()
    total = name.upper().startswith("TOTAL")
    pt = "world" if total else ("country" if lab.startswith(" ") else "group")
    for flow, c in (("import", cells[0]), ("export", cells[2])):
        v = _v(c)
        if v is None:
            continue
        out.append(row(tradeflow=flow, period=y, frequency="annual", value=v, unit="XOF", unit_multiplier=1e3,
                       partner=None if total else name, partner_type=pt,
                       price_basis="cif" if flow == "import" else "fob", series_code=f"Comercio externo {y} paises"))


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    for p in [path] + list(extras or []):
        if p.lower().endswith(".pdf"):
            rows += _parse_book(p)
    df = pd.DataFrame(rows)
    # A partner printed twice in one year's table with DIFFERENT values (Singapore under
    # two zones in 2007) cannot be told apart: both are dropped. Exact repeats collapse.
    key = ["tradeflow", "commodity", "commodity_code_nso", "partner", "partner_type", "measure", "period", "unit"]
    df = df.drop_duplicates(key + ["value"])
    df = df[~df.duplicated(key, keep=False)]
    return df.reset_index(drop=True)
