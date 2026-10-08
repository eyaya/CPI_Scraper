"""Parser for INE Guiné-Bissau's "Síntese das Contas Nacionais da Guiné-Bissau"
(PDF, Portuguese; SCN 2008, base 2015), Anexo 1 "Tabelas Estatísticas".

The 2020 synthesis covers 2011-2020 (Table 3.7 runs from 2010). Read:

  1.1 / 2.1 / 3.1  production / expenditure / value added by sector, current prices
  1.2 / 2.2 / 3.2  the same in chained volume (ano base 2015), FCFA million
  1.3 / 2.3 / 3.3  volume growth, %                                  growth_yoy
  1.4 / 2.4 / 3.4  implicit deflators, 2015 = 100                    deflator
  2.7 / 3.7        contribution to volume GDP growth, points        contribution

Production: production, intermediate consumption, VAB, net taxes on products,
PIB (and, in volume, the chain-linking discrepancy). Expenditure: final
consumption (households, government, NPISH), gross capital formation (GFCF,
change in inventories), net exports, exports and imports of goods and
services, PIB. Sectors: primary / secondary / tertiary and their branches.

NOT READ: 1.5 / 2.5 / 3.5 (growth of the deflators -- no measure in this
schema) and 2.6 / 3.6 (structure in volume) -- 2.6 prints NINE values per row
under TEN year headers, so no value can be placed in its year.

TRAPS, EACH HANDLED BY RULE:

* THE THOUSANDS SEPARATOR CHANGES INSIDE A ROW. Table 2.1 prints 2011-2019 as
  "513.511" and 2020 as "841 370". In LEVEL tables every value is a whole number
  of FCFA million, so both "." and " " are thousands separators; in RATE tables
  "," is the decimal mark. Values are read one cell per line (PyMuPDF), so a
  grouped number is never split.
* A ROW WHOSE VALUE COUNT DOES NOT MATCH THE HEADER IS REFUSED, never shifted:
  Table 2.1's "Aquisição líquida de objetos de valor" prints six zeros for ten
  years. Refusals are counted and printed.
* TWO TABLES PER PAGE: a page's captions and its "Rubricas" header blocks are
  paired in order; lines before a page's first caption continue the previous
  page's table.
* THE 2015 REBASE BREAKS THE CONTRIBUTIONS: Table 3.7 prints 2015 contributions
  of -34.8 (primary sector) in a year volume GDP grew 6.1%. Contributions are
  kept only for years where the branch contributions of the three sectors sum
  to the published volume growth of PIB (Table 1.3) within 0.6 points; other
  years are refused and printed.

Identities checked at current prices every year: VAB + net taxes = PIB
(production) and consumption + GCF + net exports = PIB (expenditure), within
2 FCFA million of rounding; production PIB = expenditure PIB within 2.

CROSS-CHECK (2020 synthesis): PIB current 2011 545 270, 2020 894 367 FCFA
million; volume (2015 prices) 2020 795 321; volume growth 2015 6.1%, 2020
-1.4%; GDP deflator 2020 112.5; agriculture VAB 2020 229 639.
"""
from __future__ import annotations

import re

import fitz  # PyMuPDF
import pandas as pd

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]
_CAP = re.compile(r"^Tabela (\d\.\d):\s*(.*)")
# table -> (approach, price_basis, measure, unit, base_period)
_SPEC = {
    "1": "production", "2": "expenditure", "3": "production"}
_KIND = {
    "1": ("current", "level", "FCFA million", ""),
    "2": ("constant", "level", "FCFA million", "Chained volume, base year 2015"),
    "3": ("constant", "growth_yoy", "percent", ""),
    "4": ("not_applicable", "deflator", "index", "2015=100"),
    "7": ("constant", "contribution", "percentage points", ""),
}
# Levels: whole FCFA million, grouped by "." or " " or not at all ("-27004").
_LEVEL_TOK = re.compile(r"^-?(?:\d{1,3}(?:[. ]\d{3})+|\d+)$")
# Rates: "," is the decimal mark, "." may group thousands ("1.244,4").
_RATE_TOK = re.compile(r"^-?(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d+)?$")
_SUB = ("Bens", "Serviços")


def _blocks(doc):
    """[(table_id, caption, [lines after its 'Rubricas'])] across the annex."""
    out = []
    for page in doc:
        lines = [ln.strip() for ln in page.get_text().splitlines()]
        caps = [(i, m.group(1), m.group(2)) for i, ln in enumerate(lines)
                if (m := _CAP.match(ln))]
        rub = [i for i, ln in enumerate(lines) if ln == "Rubricas"]
        first_cap = caps[0][0] if caps else len(lines)
        if out and caps and first_cap > 0:
            # continuation of the previous page's table, before any caption
            cont = [ln for ln in lines[:first_cap] if ln]
            if any(_LEVEL_TOK.match(x) or _RATE_TOK.match(x) for x in cont):
                out[-1][2].extend(lines[:first_cap])
        if len(rub) != len(caps):
            if caps:
                raise ValueError(f"INE GB: page {page.number + 1} has {len(caps)} "
                                 f"captions but {len(rub)} header blocks")
            continue
        for k, (ci, tid, cap) in enumerate(caps):
            start = rub[k]
            end = rub[k + 1] if k + 1 < len(rub) else len(lines)
            # the next caption on the page may sit before the next 'Rubricas'
            nxt = [c for c, *_ in caps if c > start]
            if nxt:
                end = min(end, nxt[0])
            out.append((tid, cap, lines[start:end]))
    return out


def _parse_block(lines, level):
    tok = _LEVEL_TOK if level else _RATE_TOK
    years = []
    i = 1
    while i < len(lines) and re.fullmatch(r"(19|20)\d\d", lines[i]):
        years.append(lines[i])
        i += 1
    rows, label, vals, refused = [], [], [], []

    def flush():
        if label and vals:
            lab = re.sub(r"\s+", " ", " ".join(label)).strip()
            if len(vals) == len(years):
                rows.append((lab, vals[:]))
            else:
                refused.append((lab, len(vals)))

    for ln in lines[i:]:
        if not ln or re.fullmatch(r"República da Guiné-Bissau|\d{1,2}", ln):
            continue
        if tok.match(ln):
            vals.append(float(ln.replace(" ", "").replace(".", "")) if level
                        else float(ln.replace(".", "").replace(",", ".")))
            continue
        if vals:
            flush()
            label, vals = [], []
        # A CAPITALISED line while the current label has no values means that
        # row printed none here: close it as refused rather than fuse two
        # labels ("Aquisição líquida de objetos de valor" + "Exportação
        # líquida" -- a well-formed row under the wrong name). Wrapped label
        # tails start lower-case or with "(".
        if label and re.match(r"[A-ZÀ-Ý]", ln):
            refused.append((re.sub(r"\s+", " ", " ".join(label)).strip(), 0))
            label = []
        label.append(ln)
    flush()
    # "Bens" / "Serviços" sit under both Exportações and Importações: qualify
    # them with the parent row printed above, or their keys collide.
    parent, named = None, []
    for lab, v in rows:
        if lab.startswith(("Exportações", "Importações")):
            parent = lab
        named.append((f"{parent} - {lab}" if lab in _SUB and parent else lab, v))
    return years, named, refused


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    doc = fitz.open(path)
    out: list[dict] = []
    tables = {}
    for tid, cap, lines in _blocks(doc):
        part, kind = tid.split(".")
        if kind not in _KIND:
            continue
        basis, measure, unit, base = _KIND[kind]
        years, rows, refused = _parse_block(lines, measure == "level")
        if len(years) < 5 or not rows:
            raise ValueError(f"INE GB Tabela {tid}: years {years}, {len(rows)} rows")
        for lab, n in refused:
            print(f"[guinea_bissau] refused: Tabela {tid} {lab!r} prints {n} values "
                  f"for {len(years)} years")
        tables[tid] = (years, rows, cap, basis, measure, unit, base)

    # --- identities at current prices ---------------------------------------
    def table_dict(tid):
        years, rows, *_ = tables[tid]
        return {lab: dict(zip(years, v)) for lab, v in rows}

    t11, t21 = table_dict("1.1"), table_dict("2.1")
    gdp_p = next(v for k, v in t11.items() if k.startswith("Produto Interno Bruto"))
    gdp_e = next(v for k, v in t21.items() if k.startswith("Produto Interno Bruto"))
    vab = next(v for k, v in t11.items() if k.startswith("Valor Acrescentado"))
    tax = next(v for k, v in t11.items() if k.startswith("Impostos"))
    for y in gdp_p:
        if abs(vab[y] + tax[y] - gdp_p[y]) > 2 or abs(gdp_p[y] - gdp_e[y]) > 2:
            raise ValueError(f"INE GB {y}: VAB+taxes {vab[y] + tax[y]}, production "
                             f"PIB {gdp_p[y]}, expenditure PIB {gdp_e[y]}")
        e = sum(t21[k][y] for k in t21 if k.startswith(("Consumo Final",
                "Formação Bruta de Capital", "Exportação líquida"))
                and not k.startswith("Formação Bruta de Capital Fixo"))
        if abs(e - gdp_e[y]) > 2:
            raise ValueError(f"INE GB {y}: C+GCF+NX {e} != PIB {gdp_e[y]}")

    # --- contributions: keep a year only if they add up to PIB growth -------
    g13 = next(v for k, v in table_dict("1.3").items()
               if k.startswith("Produto Interno Bruto"))
    # Table 1.3 starts in 2011; Table 3.3 also prints 2010, and its PIB growth
    # is the reference for 3.7's 2010 column.
    g33 = next((v for k, v in table_dict("3.3").items()
                if k.startswith("Produto Interno Bruto")), {})
    g13 = {**g33, **g13}
    keep_contrib = {}
    for tid in ("2.7", "3.7"):
        if tid not in tables:
            continue
        d = table_dict(tid)
        if tid == "3.7":
            parts = [k for k in d if k.startswith("Setor ")] + \
                [k for k in d if k.startswith("Impostos")]
        else:
            parts = [k for k in d if k.startswith(("Consumo Final",
                     "Formação Bruta de Capital", "Exportação líquida"))
                     and not k.startswith("Formação Bruta de Capital Fixo")]
        ok = set()
        for y in tables[tid][0]:
            if y in g13 and abs(sum(d[k][y] for k in parts) - g13[y]) <= 0.6:
                ok.add(y)
            else:
                print(f"[guinea_bissau] refused: Tabela {tid} {y} contributions sum "
                      f"to {sum(d[k][y] for k in parts):.1f}, PIB volume growth "
                      f"{g13.get(y)}")
        keep_contrib[tid] = ok

    for tid, (years, rows, cap, basis, measure, unit, base) in tables.items():
        approach = _SPEC[tid.split(".")[0]]
        for lab, vals in rows:
            for y, v in zip(years, vals):
                if measure == "contribution" and y not in keep_contrib.get(tid, set()):
                    continue
                out.append({
                    "approach": "aggregate" if lab.startswith("Produto Interno Bruto")
                    else approach,
                    "category": lab, "category_group": f"Tabela {tid}: {cap}",
                    "series_code": f"Tabela {tid}", "geography": "National",
                    "period": y, "frequency": "annual", "price_basis": basis,
                    "seasonal_adjustment": "nsa", "measure": measure, "value": v,
                    "unit": unit, "base_period": base})
    doc.close()
    return pd.DataFrame.from_records(out)[_OUT_COLS]
