"""Cabo Verde -- INE poverty publications on the IDRF 2001/02 RELATIVE method
(before the 2015 absolute-poverty methodology the main descriptor collects).

1. `parse_quibb2007` -- "Dinâmica da Pobreza - Resultados QUIBB 2007".
   Quadros IX-1 / IX-2: incidence, depth and "intensidade" (P0, P1, P2 --
   the third FGT index, as the values show: 26,6 / 8,1 / 3,4) for urban,
   rural and national, by milieu, the six IDRF 2001/02 study domains, 22
   concelhos and characteristics of the head; Quadros X-1 / X-2: population
   share, number of poor and contribution to poverty for the same groups.
   QUIBB 2007 is measured "to allow comparison with IDRF 2001/02" (36,7% in
   2001/02, 49% in 1988/89), i.e. on the RELATIVE line of that survey --
   filed line_type relative so it never shares an ID with the 2015-method
   absolute series (which re-estimates 2007 at 45,4).
2. `parse_idrf2001` -- "O Perfil da Pobreza em Cabo Verde, IDRF 2001/2002"
   (INE 2004), Quadro 5: FGT measures for 2001/02 and 1988/89 on the
   relative lines (moderate = "pobres", ECV 43.250; extreme = "muito
   pobres", ECV 28.833 per person per year in 2001/02), and 1988/89 on the
   2001/02 line ("absoluta (correspondente ao limiar de pobreza de
   2001-02)"). The caption says "1998-99"; its column headers and Quadro 1
   date the earlier survey 1988-89 -- and INE ran IDRF in 1988/89, not
   1998/99 -- so it is dated 1988. Quadro 5 is a simulation (SimSIP) by the
   report's authors from the two IDRF rounds.
   NOT READ: the "Quadro síntese" (p. 132) prints P0/P1/P2 as 0-1 fractions
   ("0,28") -- the schema takes headcounts only as percentages; the person
   counts by status (p. 32) have a garbled "Outras Ilhas" row.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

_REL = {"line_type": "relative", "line_level": "overall",
        "line_name": "Relative poverty line, IDRF 2001/02 method (ECV 43.250 in 2001/02)"}
_REL_EXT = {"line_type": "relative", "line_level": "extreme",
            "line_name": "Relative extreme poverty line, IDRF 2001/02 method (ECV 28.833 in 2001/02)"}
_ABS0102 = {"line_type": "national", "line_level": "other",
            "line_name": "IDRF 2001/02 poverty line applied to 1988/89 (SimSIP)"}
_ABS0102_EXT = {"line_type": "national", "line_level": "other",
                "line_name": "IDRF 2001/02 extreme poverty line applied to 1988/89 (SimSIP)"}

LAYOUT_QUIBB2007 = {"survey": "QUIBB 2007", "welfare_aggregate": "consumption",
                    "unit_of_analysis": "person", "frequency": "ad_hoc", **_REL,
                    "period": "2007", "reference_period": "2007", "tables": []}
LAYOUT_IDRF2001 = {**LAYOUT_QUIBB2007, "survey": "IDRF 2001/02", "period": "2001",
                   "reference_period": "2001/02"}

_DOMAINS = {"Praia": "Praia", "Resto Santiago": "Resto de Santiago", "S. Antão": "Santo Antão",
            "S. Vicente": "São Vicente", "Fogo": "Fogo", "Outras ilhas": "Outras Ilhas"}
_CONCELHO = {"Paul": "Paúl", "Tarrafal de S. N.": "Tarrafal de São Nicolau",
             "Tarrafal de S. Nicolau": "Tarrafal de São Nicolau",
             "Tarrafal de Santiago": "Tarrafal", "São Domingo": "São Domingos",
             "Calheta S. Miguel": "São Miguel"}
_SECTIONS = {"Sexo": "sex_of_head", "Estado civil": "marital_status_of_head",
             "Nivel de instrução": "education_of_head", "Nível de instrução": "education_of_head",
             "Grupo sócio-económico": "employment_of_head", "Idade": "age_of_head",
             "Dimensão do agregado": "household_size",
             "Meio de residência": "milieu", "Domínios 2001/02": "domain", "Concelho": "concelho"}
_CELL = r"(-{1,4}|\d{1,3}(?:\.\d{3})*(?:,\d+)?)"


def _num(tok: str):
    if set(tok) == {"-"}:
        return None
    return float(tok.replace(".", "").replace(",", "."))


def _rows9(text: str):
    """Yield (section, label, [9 cells]) from a Quadro, re-joining labels the
    PDF wraps around their numbers ("Tarrafal de" / numbers / "Santiago",
    "São Lourenço - - -" / numbers / "dos Órgãos")."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    section, i = None, 0
    while i < len(lines):
        s = lines[i]
        if s in _SECTIONS or s.rstrip() in ("Meio de",):
            section = _SECTIONS.get(s, "milieu" if s == "Meio de" else section)
            i += 1
            continue
        if s == "residência":
            i += 1
            continue
        hm = re.match(r"^(\d+ a \d+|7 ou mais)\s+(.*)$", s) if section == "household_size" else None
        if hm:
            label, cells = hm.group(1), re.findall(_CELL, hm.group(2))
        else:
            m = re.match(r"^(.*?)\s*((?:" + _CELL + r"\s*)+)$", s)
            cells = re.findall(_CELL, m.group(2)) if m else []
            label = (m.group(1) if m else s).strip()
        if len(cells) < 9 and i + 1 < len(lines):
            # label (possibly with leading dashes) on this line, cells on the next
            nm = re.match(r"^((?:" + _CELL + r"\s*)+)$", lines[i + 1])
            if nm:
                more = re.findall(_CELL, nm.group(1))
                if len(cells) == 3 and all(set(c) == {"-"} for c in cells) and len(more) == 6:
                    # "São Lourenço - - -" / "34,8 34,8 9,4 9,4 3,5 3,5": the
                    # dashes are the URBAN cell of each of the three blocks
                    cells = [cells[0], *more[0:2], cells[1], *more[2:4], cells[2], *more[4:6]]
                else:
                    cells = cells + more
                i += 1
        if len(cells) == 9:
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if nxt and not re.search(r"\d", nxt) and nxt not in _SECTIONS and not nxt.startswith(("Quadro", "INE")) \
                    and nxt[:1].islower() or nxt in ("Santiago", "Miguel", "Fogo", "Mundo", "família",
                                                     "pública", "publica", "Separado(a)"):
                if not re.search(r"\d", nxt):
                    label = f"{label} {nxt}".strip()
                    i += 1
            yield section, label, cells
        i += 1


def _cell(section: str, label: str) -> dict | None:
    if label == "Cabo Verde":
        return {}
    if section == "milieu":
        return {"topic": "locality", "locality": "urban" if label == "Urbano" else "rural",
                "locality_label": label}
    if section == "domain":
        return {"geography": _DOMAINS[label]} if label in _DOMAINS else None
    if section == "concelho":
        return {"geography": _CONCELHO.get(label, label)}
    if section in ("sex_of_head", "marital_status_of_head", "education_of_head",
                   "employment_of_head", "age_of_head", "household_size"):
        lab = re.sub(r"\s+", " ", label).replace("Divorciado/ Separado(a)", "Divorciado/Separado(a)")
        lab = lab.replace("administração publica", "administração pública")
        if section == "employment_of_head":
            lab = f"Grupo sócio-económico: {lab}"
        if section == "household_size":
            lab = f"{lab} pessoas"
        c = {"topic": section, "characteristic": lab}
        if section == "sex_of_head":
            c["sex"] = "male" if label.startswith("Masc") else "female"
        return c
    return None


def _row(lay, line, metric, value, loc=None, **cell):
    a = {**lay, **line}
    locality = {"topic": cell.pop("topic", "total"), "locality": "all", "locality_label": "Total"}
    if cell.get("_loc"):
        pass
    sex = cell.pop("sex", "total")
    r = C.row(metric=metric, value=value, survey=a["survey"], welfare_aggregate="consumption",
              line_type=a["line_type"], line_level=a["line_level"], line_name=a["line_name"],
              period=a["period"], reference_period=a["reference_period"], frequency="ad_hoc",
              unit_of_analysis="person", sex=sex, topic=locality["topic"],
              characteristic=cell.get("characteristic", "Total"),
              geography=cell.get("geography", "Total country"),
              locality=cell.get("locality", "all"), locality_label=cell.get("locality_label", "Total"))
    if loc:
        # a group crossed with the urban/rural split of the column
        r["locality"], r["locality_label"] = loc, {"urban": "Urbano", "rural": "Rural"}[loc]
    return r


def parse_quibb2007(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        pages = [(p.extract_text() or "") for p in pdf.pages]
    rows, seen = [], set()

    def add(r):
        k = tuple(r[c] for c in ("metric", "topic", "characteristic", "geography", "locality",
                                 "locality_label", "sex"))
        if k in seen:
            return
        seen.add(k)
        rows.append(r)

    for cap, kind in (("Quadro NºIX-1", "fgt"), ("Quadro NºIX-2", "fgt"),
                      ("Quadro NºX-1", "share"), ("Quadro NºX-2", "share")):
        page = [p for p in pages if cap in p][-1]
        for section, label, cells in _rows9(page[page.index(cap):]):
            cell = _cell(section, label)
            if cell is None:
                continue
            v = [_num(c) for c in cells]
            metrics = (("headcount", "gap", "severity") if kind == "fgt"
                       else ("population_share", "poor_count", "poor_share"))
            for mi, metric in enumerate(metrics):
                for li, loc in enumerate(("urban", "rural", None)):
                    x = v[mi * 3 + li]
                    if x is None:
                        continue
                    milieu = cell.get("topic") == "locality"
                    if milieu and loc is not None:
                        continue          # the milieu rows repeat their own column
                    if cell == {} and metric in ("population_share", "poor_share"):
                        continue          # 100 by construction
                    if cell == {} and loc is not None:
                        add(_row(LAYOUT_QUIBB2007, _REL, metric, x,
                                 topic="locality", locality=loc,
                                 locality_label={"urban": "Urbano", "rural": "Rural"}[loc]))
                        continue
                    if cell == {} and metric in ("population_share", "poor_share"):
                        continue          # 100 by construction
                    if loc is not None and metric in ("population_share", "poor_share"):
                        continue          # shares WITHIN urban / rural: a different denominator
                    add(_row(LAYOUT_QUIBB2007, _REL, metric, x, loc=loc, **dict(cell)))
    df = pd.DataFrame(rows)
    if len(df) < 400:
        raise ValueError(f"{path}: only {len(df)} rows")
    return df


def parse_idrf2001(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        page = [(p.extract_text() or "") for p in pdf.pages if "Quadro 5: Tend" in (p.extract_text() or "")][-1]
    txt = page[page.index("Quadro 5"):]
    rows = []
    for block, lines in (("Pobreza Moderada", (_ABS0102, _REL, _REL)),
                         ("Pobreza Extrema", (_ABS0102_EXT, _REL_EXT, _REL_EXT))):
        seg = txt[txt.index(block):]
        for label, metric in (("Incid", "headcount"), ("Profundidade", "gap"), ("Gravidade", "severity")):
            m = re.search(label + r"\S*\s+(\d+\.\d+)%\s+(\d+\.\d+)%\s+(\d+\.\d+)%", seg)
            if not m:
                raise ValueError(f"Quadro 5: {block} {label} not found")
            for (survey, period, ref), line, v in zip(
                    (("IDRF 1988/89 (as republished 2004)", "1988", "1988/89"),
                     ("IDRF 1988/89 (as republished 2004)", "1988", "1988/89"),
                     ("IDRF 2001/02", "2001", "2001/02")), lines, m.groups()):
                lay = {**LAYOUT_IDRF2001, "survey": survey, "period": period, "reference_period": ref}
                rows.append(_row(lay, line, metric, float(v)))
    return pd.DataFrame(rows)


LAYOUT = LAYOUT_QUIBB2007
parse = parse_quibb2007
