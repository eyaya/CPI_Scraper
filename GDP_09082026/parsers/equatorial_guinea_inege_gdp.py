"""Parser for INEGE Equatorial Guinea national accounts.

Two INEGE publications, both on the 2006 base (SCN 93), read together:

* INFORME DE LAS CUENTAS NACIONALES TRIMESTRALES (quarterly, primary file and
  the previous issue as an extra) -- Anexos 1-6, six quarters per issue
  (e.g. 2025 T1 .. 2026 T2), FCFA millions:
    Anexo 1  PIB a precios corrientes        -> level, current
    Anexo 2  PIB a precios constantes        -> level, constant (2006)
    Anexo 3  Variación interanual (%)        -> growth_yoy, constant
    Anexo 4  Variación trimestral (%)        -> growth_qoq, constant
    Anexo 5  Contribuciones interanuales (%) -> contribution
    Anexo 6  Contribuciones trimestrales (%) -> contribution
  Production side only (sector -> branch, with PIB petrolero / no petrolero).
  No seasonal adjustment is stated anywhere in the report -> `nsa`.

* ANUARIO ESTADÍSTICO DE GUINEA ECUATORIAL, "Contabilidad Nacional" section
  (annual, five years per edition, FCFA thousand millions -- "miles de
  millones"). AEGE 2026 (2021-2025) and AEGE 2023 (2018-2022) are read; the
  NEWER edition wins every year both print (INEGE revises: AEGE 2026 restates
  2022 nominal GDP as 8 537,8 against 7 503,6 in AEGE 2023 -- a large revision,
  taken as published). Tables, by role (numbering changes each edition, so
  series codes name the ROLE, not the table number):
    Síntesis de agregados   -> aggregate: PIB, deflator, growth, the income /
                               saving / financing balances, per-capita GDP
    PIB corrientes / constantes, óptica OFERTA  -> production levels
    Deflactores                                  -> deflator (index, 2006=100)
    Crecimiento / Contribuciones (oferta)        -> growth_yoy / contribution
    PIB corrientes / constantes, óptica DEMANDA -> expenditure levels
    Crecimiento / Contribuciones (demanda)       -> growth_yoy / contribution
  Columns marked "Est"/"Estim" (the last two years of each edition) are
  INEGE's estimates; the mark is part of the published header, recorded in
  `category_group` together with the edition each year was taken from, so
  the splice between vintages (2018-2020 from AEGE 2023, 2021-2025 from AEGE
  2026) is visible on every row.

PUBLISHED INCONSISTENCIES KEPT, NOT RECONCILED:
* AEGE 2026, 2024: nominal GDP is 8 262,5 in the synthesis and demand tables
  but 8 036,7 in the supply table (whose branches do sum to 8 036,7); the
  deflator is 176,3 in the synthesis and 171,5 in the deflator table. Each is
  kept under its own approach / series code: the supply total under
  `production`, the demand total under `expenditure`, the synthesis under
  `aggregate`.
* Each table is held to its own identities (sector = sum of its branches;
  PIB = primario + secundario + terciario + impuestos netos; demand: PIB =
  consumo + FBCF + variación de existencias + exportaciones netas at current
  prices, and consumo / FBCF / exportaciones netas against their parts at
  both) within rounding; a break raises, unless pinned in `_KNOWN`.

PINNED DEFECTS (`_KNOWN`, re-checked every run so a correction is noticed):
* AEGE 2023, oferta corrientes, SECTOR TERCIARIO 2021 prints "3.047.643,5";
  its branches sum to 3 047,6. Not collected.
* AEGE 2026, demanda constantes, Gastos de Consumo Final 2021 prints 3 140,8,
  but Público + Hogares = 3 190,2 and PIB real (4 885,3) adds up only with
  3 190,2. Every other year of both editions is additive. Not collected.

NOT COLLECTED: the synthesis table's ratios (tasas, propensión, cobertura,
competitividad, apertura, "% del PIB"), "Crecimiento en precio" and the
population estimate -- no GDP measure holds them; Anexos 7-25 of the quarterly
report (physical production, trade, prices).

READ BY WORD GEOMETRY (PyMuPDF). The text layer wraps long labels and drops a
row's last value onto the next line ("Agricultura 119,7 127,4 139,0 145,0" /
"159,1"), so rows are rebuilt from positions: columns from the header's x
centres, each column's values ordered top to bottom, and label fragments
attached to the nearest row.

CROSS-CHECK: quarterly 2026 T2 PIB corriente 1 920 402, constante 1 086 775,
interanual -1,9; AEGE 2026 PIB real 2025 4 412,8, crecimiento -5,8;
AEGE 2023 PIB nominal 2018 7 274,7.
"""
from __future__ import annotations

import os
import re
import statistics
import unicodedata

import fitz  # PyMuPDF
import pandas as pd

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]
_BASE = "Constant 2006 prices"

_NUM = re.compile(r"^-?\d{1,3}(?:\.\d{3})*(?:,\d+)?$|^-?\d+(?:,\d+)?$")
_YEAR = re.compile(r"^(20\d\d)(Est\w*)?$")

# (edition, role, category normalised, period) -> printed token that is dropped
_KNOWN = {("AEGE 2023", "OF-CUR", "sector terciario", "2021"): "3.047.643,5",
          ("AEGE 2026", "DE-CON", "gastos de consumo final", "2021"): "3.140,8"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s).strip().lower()


def _num(tok: str) -> float:
    return float(tok.replace(".", "").replace(",", "."))


# ---------------------------------------------------------------------------
# Generic geometric table reader
# ---------------------------------------------------------------------------

def _words(page):
    return [(w[0], w[1], w[2], w[3], w[4]) for w in page.get_text("words")]


def _read_region(words, y0, y1, quarterly, where):
    """Rows of (label, {period: token}) between y0 and y1."""
    ws = [w for w in words if y0 <= w[1] < y1]
    # header: years (and quarter tokens for the quarterly report)
    if quarterly:
        years = sorted([w for w in ws if re.fullmatch(r"20\d\d", w[4])], key=lambda w: w[0])
        qs = sorted([w for w in ws if re.fullmatch(r"T[1-4]", w[4])], key=lambda w: w[0])
        if not years or len(qs) < 2:
            raise ValueError(f"{where}: no quarter header")
        hy = max(w[3] for w in qs)
        yr, cols = int(years[0][4]), []
        prev = 0
        for w in qs:
            q = int(w[4][1])
            if q <= prev:
                yr += 1
            prev = q
            cols.append(((w[0] + w[2]) / 2, f"{yr}-Q{q}", w[4]))
        if yr != int(years[-1][4]):
            raise ValueError(f"{where}: quarter header {[c[1] for c in cols]} "
                             f"does not end in {years[-1][4]}")
    else:
        # The header is the TOPMOST line with three or more years; a year inside
        # a label ("precios constantes de 2006") is not a column.
        by_line = {}
        for w in ws:
            if _YEAR.fullmatch(w[4]):
                by_line.setdefault(round(w[1]), []).append(w)
        lines = [(y, v) for y, v in sorted(by_line.items()) if len(v) >= 3]
        if not lines:
            raise ValueError(f"{where}: no year header")
        # "2024Est" / "2025Est" can sit a point below the plain years.
        y_top = lines[0][0]
        hdr = [w for y, v in by_line.items() if abs(y - y_top) <= 4 for w in v]
        hy = max(w[3] for w in hdr)
        cols = [((w[0] + w[2]) / 2, _YEAR.fullmatch(w[4]).group(1), w[4])
                for w in sorted(hdr, key=lambda w: w[0])]
    xs = [c[0] for c in cols]
    gap = min(b - a for a, b in zip(xs, xs[1:])) if len(xs) > 1 else 60
    # The first data row's top can touch the header's bottom edge exactly.
    body = [w for w in ws if w[1] >= hy - 2 and w[4] not in
            {c[2] for c in cols} | {"Indicador", "Concepto", "Contribuciones"}]
    # Note / source / footnote lines go whole, numbers included: "Nota: las
    # estimaciones de los años 2021 y 2022 han sido revisadas" carries two
    # "values" that would land in the first columns.
    note_y = [w[1] for w in body if re.match(r"^(Nota|Fuente|Estim)\b", w[4])
              and w[0] < xs[0] - gap * 0.45]
    body = [w for w in body if not any(abs(w[1] - y) < 4 for y in note_y)]
    per_col = {i: [] for i in range(len(cols))}
    label_words = []
    for w in body:
        cx = (w[0] + w[2]) / 2
        if _NUM.fullmatch(w[4]) and cx > xs[0] - gap * 0.6:
            i = min(range(len(xs)), key=lambda k: abs(xs[k] - cx))
            if abs(xs[i] - cx) < gap * 0.55:
                per_col[i].append(w)
                continue
        if w[2] < xs[0] - gap * 0.45:
            label_words.append(w)
    # Footnotes, notes and sources ("1 Año base 2006", "Nota: ...", "Estim:
    # Estimaciones revisadas") are not row labels.
    foot = set()
    for y in {round(w[1]) for w in label_words}:
        line = sorted([w for w in label_words if round(w[1]) == y], key=lambda w: w[0])
        if re.match(r"^(\d+\s|Nota\b|Estim\b|Fuente\b)",
                    " ".join(t[4] for t in line)):
            foot.add(y)
    label_words = [w for w in label_words if round(w[1]) not in foot]
    # A value well below the last label line belongs to no row: it is the page
    # number, which sits in the last value column.
    if label_words:
        last_label = max(w[3] for w in label_words)
        for i in per_col:
            per_col[i] = [w for w in per_col[i] if w[1] <= last_label + 25]
    # ... and the page number can also sit below a footnote that counted as a
    # label: drop a column's trailing value cut off from the rest by > 80pt.
    for i in per_col:
        col = sorted(per_col[i], key=lambda w: w[1])
        while len(col) > 1 and col[-1][1] - col[-2][3] > 80:
            col.pop()
        per_col[i] = col
    counts = {len(v) for v in per_col.values()}
    if len(counts) != 1:
        raise ValueError(f"{where}: columns hold {[len(v) for v in per_col.values()]} values")
    n = counts.pop()
    for i in per_col:
        per_col[i].sort(key=lambda w: w[1])
    row_y = [statistics.median((per_col[i][r][1] + per_col[i][r][3]) / 2
                               for i in per_col) for r in range(n)]
    # label lines -> nearest row
    lines = {}
    for w in label_words:
        key = round((w[1] + w[3]) / 2)
        lines.setdefault(key, []).append(w)
    frags = {r: [] for r in range(n)}
    for y, lw in sorted(lines.items()):
        text = " ".join(t[4] for t in sorted(lw, key=lambda t: t[0]))
        if y < row_y[0] - 14 or y > row_y[-1] + 14:
            continue
        r = min(range(n), key=lambda k: abs(row_y[k] - y))
        frags[r].append((y, text))
    rows = []
    for r in range(n):
        label = " ".join(t for _, t in sorted(frags[r]))
        label = re.sub(r"\s+", " ", label).strip()
        label = re.sub(r"(?<=[a-zé])\d$", "", label)          # footnote mark
        if not label:
            raise ValueError(f"{where}: row {r} has values but no label")
        rows.append((label, {c[1]: per_col[i][r][4] for i, c in enumerate(cols)},
                     {c[1]: c[2] for c in cols}))
    return rows


def _regions(doc, caption_re, quarterly):
    """Yield (page, y0, y1) for each caption matching `caption_re` outside the
    list of tables (dot leaders)."""
    out = []
    for page in doc:
        text = page.get_text()
        if re.search(r"\.{5}", text) and re.search(r"(ÍNDICE|CONTENIDO|INDICE)", text):
            continue
        blocks = sorted(page.get_text("blocks"), key=lambda b: b[1])
        caps = [(b[1], b[4]) for b in blocks
                if re.match(r"\s*(Tabla \d+|Anexo \d+)\s*:", b[4])]
        for k, (y, t) in enumerate(caps):
            # A list-of-tables entry carries dot leaders to its page number.
            if re.search(caption_re, t.replace("\n", " "), re.I) and "....." not in t:
                # To the next caption, or to the footer (the page number sits
                # in the last value column and would be read as a value).
                y1 = caps[k + 1][0] if k + 1 < len(caps) else page.rect.y1 * 0.93
                out.append((page, y, y1, t.replace("\n", " ").strip()))
    return out


# ---------------------------------------------------------------------------
# The quarterly report
# ---------------------------------------------------------------------------

_Q_ANEXOS = [
    (r"Anexo 1\s*:\s*Evoluci.n del PIB a precios corrientes", "level", "current", "CNT-A1"),
    (r"Anexo 2\s*:\s*Evoluci.n del PIB a precios constantes", "level", "constant", "CNT-A2"),
    (r"Anexo 3\s*:\s*Variaci.n Interanual del PIB", "growth_yoy", "constant", "CNT-A3"),
    (r"Anexo 4\s*:\s*Variaci.n Trimestral del PIB", "growth_qoq", "constant", "CNT-A4"),
    (r"Anexo 5\s*:\s*Contribuciones al crecimiento interanual", "contribution", "constant", "CNT-A5"),
    (r"Anexo 6\s*:\s*Contribuciones al crecimiento trimestral", "contribution", "constant", "CNT-A6"),
]
_SECTORS = ["sector primario", "sector secundario", "sector terciario"]


def _check_production(rows, where, total_label, taxes_label, tol):
    """sector = sum of branches; PIB = sectors + net taxes. `rows` in order."""
    labels = [_norm(r[0]) for r in rows]
    periods = list(rows[0][1])
    for p in periods:
        v = {}
        for lab, vals in zip(labels, (r[1] for r in rows)):
            if vals.get(p) is not None:
                v.setdefault(lab, vals[p])
        labels_present = set(labels)
        missing = [s for s in [*_SECTORS, total_label, taxes_label]
                   if s not in labels_present]
        if missing:
            raise ValueError(f"{where}: missing row(s) {missing}")
        if any(s not in v for s in [*_SECTORS, total_label, taxes_label]):
            continue          # a pinned (dropped) cell in this period
        sect = [v[s] for s in _SECTORS]
        tot, tax = v[total_label], v[taxes_label]
        if abs(sum(sect) + tax - tot) > tol:
            raise ValueError(f"{where} {p}: sectors + taxes = {sum(sect) + tax:.1f}, "
                             f"PIB = {tot}")
        # each sector against its branches (rows until the next sector/taxes)
        for i, lab in enumerate(labels):
            if lab in _SECTORS:
                parts = []
                for lab2, vals in zip(labels[i + 1:], (r[1] for r in rows[i + 1:])):
                    if lab2 in _SECTORS or lab2 == taxes_label:
                        break
                    parts.append(vals[p])
                if parts and None not in parts and abs(sum(parts) - v[lab]) > tol:
                    raise ValueError(f"{where} {p}: {lab} {v[lab]} vs branches "
                                     f"{sum(parts):.1f}")


def _check_demand(rows, where, tol=1.5):
    """PIB = consumo final + FBCF + variación de existencias + exportaciones
    netas; consumo = público + hogares; FBCF = pública + privada; exportaciones
    netas = exportaciones - importaciones. Rows are matched by position, since
    "Público"/"Pública" sub-rows repeat under each parent."""
    labs = [_norm(r[0]) for r in rows]
    want = ["pib", "gastos de consumo final", "publico", "hogares",
            "formacion bruta de capital fijo", "publica", "privada",
            "variacion de existencias", "exportaciones netas", "exportaciones",
            "importaciones"]
    if len(labs) != len(want) or not all(l.startswith(w) for l, w in zip(labs, want)):
        raise ValueError(f"{where}: rows {labs}")
    for p in rows[0][1]:
        v = [r[1][p] for r in rows]
        if None in v:
            continue
        pib, gcf, pub, hog, fbcf, fpub, fpri, ve, xn, x, m = v
        for name, a, b in [("PIB", pib, gcf + fbcf + ve + xn),
                           ("consumo", gcf, pub + hog),
                           ("FBCF", fbcf, fpub + fpri),
                           ("exportaciones netas", xn, x - m)]:
            if abs(a - b) > tol:
                raise ValueError(f"{where} {p}: {name} {a} vs parts {b:.1f}")


def _quarterly(path):
    doc = fitz.open(path)
    out = []
    for cap, measure, basis, code in _Q_ANEXOS:
        regs = _regions(doc, cap, True)
        if len(regs) != 1:
            raise ValueError(f"INEGE CNT {code}: {len(regs)} regions in {os.path.basename(path)}")
        page, y0, y1, title = regs[0]
        rows = _read_region(_words(page), y0, y1, True, f"INEGE CNT {code}")
        parsed = [(lab, {p: _num(t) for p, t in vals.items()}) for lab, vals, _ in rows]
        if _norm(parsed[0][0]) != "pib total":
            raise ValueError(f"INEGE CNT {code}: first row {parsed[0][0]!r}")
        if measure == "level":
            _check_production(parsed, f"INEGE CNT {code}", "pib total",
                              "impuestos netos", tol=3)
        for lab, vals in parsed:
            approach = "aggregate" if _norm(lab) == "pib total" else "production"
            unit = ("FCFA million" if measure == "level" else
                    "percentage points" if measure == "contribution" else "percent")
            for p, v in vals.items():
                out.append(dict(approach=approach, category=lab,
                                category_group=title.split(":", 1)[1].strip(),
                                series_code=code, geography="National", period=p,
                                frequency="quarterly", price_basis=basis,
                                seasonal_adjustment="nsa", measure=measure,
                                value=v, unit=unit,
                                base_period=_BASE if (measure == "level" and basis == "constant") else ""))
    return out


# ---------------------------------------------------------------------------
# The yearbook
# ---------------------------------------------------------------------------

# role, caption regex, approach, measure, price basis
_A_TABLES = [
    ("SYN", r"S.ntesis de Agregados Macroecon.micos", "aggregate", None, None),
    ("OF-CUR", r"PIB a Precios corrientes", "production", "level", "current"),
    ("OF-CON", r"PIB a Precios Constantes \(Miles", "production", "level", "constant"),
    ("OF-DEF", r"Deflactores del PIB", "production", "deflator", "not_applicable"),
    ("OF-GRO", r"Crecimiento del PIB a Precios Constantes", "production", "growth_yoy", "constant"),
    ("OF-CTR", r"Contribuciones al crecimiento real del PIB", "production", "contribution", "constant"),
    ("DE-CUR", r"PIB a Precios Corrientes", "expenditure", "level", "current"),
    ("DE-CON", r"PIB a Precios Constantes \(Miles", "expenditure", "level", "constant"),
    ("DE-GRO", r"Crecimiento del PIB Real", "expenditure", "growth_yoy", "constant"),
    ("DE-CTR", r"Contribuciones al crecimiento del PIB real", "expenditure", "contribution", "constant"),
]

# Synthesis rows taken, by normalised label prefix -> (measure, basis, unit)
_SYN = [
    ("pib nominal", "level", "current", "FCFA thousand million"),
    ("pib real", "level", "constant", "FCFA thousand million"),
    ("crecimiento del pib nominal", "growth_yoy", "current", "percent"),
    ("crecimiento del pib real", "growth_yoy", "constant", "percent"),
    ("deflat", "deflator", "not_applicable", "index"),
    ("deflact", "deflator", "not_applicable", "index"),
    ("impuestos sobre productos", "level", "current", "FCFA thousand million"),
    ("subvenciones sobre productos", "level", "current", "FCFA thousand million"),
    ("balance de ingresos", "level", "current", "FCFA thousand million"),
    ("saldo bruto de los ingresos primarios", "level", "current", "FCFA thousand million"),
    ("saldo de las transferencias corrientes", "level", "current", "FCFA thousand million"),
    ("saldo de los ingresos disponibles brutos", "level", "current", "FCFA thousand million"),
    ("consumo final", "level", "current", "FCFA thousand million"),
    ("ahorro nacional bruto", "level", "current", "FCFA thousand million"),
    ("saldo de las transferencias netas en capital", "level", "current", "FCFA thousand million"),
    ("formacion bruta de capital fijo", "level", "current", "FCFA thousand million"),
    ("variacion de existencias", "level", "current", "FCFA thousand million"),
    ("capacidad/necesidad nacional de financiamiento", "level", "current", "FCFA thousand million"),
    ("exportaciones", "level", "current", "FCFA thousand million"),
    ("importaciones", "level", "current", "FCFA thousand million"),
    ("demanda interior final", "level", "current", "FCFA thousand million"),
    ("pib per capita a precios corrientes", "per_capita", "current", "FCFA thousand"),
    ("pib par capita a precios constantes", "per_capita", "constant", "FCFA thousand"),
]


def _syn_spec(label):
    """(canonical key, measure, basis, unit) for a synthesis row, or None.
    The key, not the printed label, decides which edition wins a year: the
    label is respelled between editions ("Deflactores" / "Deflatores",
    "Crecimiento del PIB real (%)" / "Crecimiento del PIB real")."""
    n = _norm(label)
    for pre, *spec in _SYN:
        if n.startswith(pre):
            return ("deflat" if pre.startswith("deflac") else pre, *spec)
    return None


def _edition(doc, path):
    head = " ".join(doc[i].get_text() for i in range(min(3, len(doc))))
    m = re.search(r"Anuario Estad.stico[^\n]{0,40}?(20\d\d)", head, re.I) or \
        re.search(r"(20\d\d)", os.path.basename(path))
    return f"AEGE {m.group(1)}"


def _yearbook(path):
    doc = fitz.open(path)
    ed = _edition(doc, path)
    # Section boundaries: oferta tables precede "Óptica demanda".
    out = []
    demand_y = None
    for page in doc:
        if re.search(r"Ó?ptica demanda", page.get_text(), re.I) and \
                not re.search(r"\.{5}", page.get_text()):
            demand_y = page.number
            break
    if demand_y is None:
        raise ValueError(f"INEGE {ed}: no 'Óptica demanda' section")
    used = set()
    for role, cap, approach, measure, basis in _A_TABLES:
        regs = [r for r in _regions(doc, cap, False)
                if (r[0].number >= demand_y) == role.startswith("DE")
                and (r[0].number, round(r[1])) not in used]
        if role == "SYN":
            regs = regs[:1]
        if not regs:
            raise ValueError(f"INEGE {ed}: table {role} not found")
        page, y0, y1, title = regs[0]
        used.add((page.number, round(y0)))
        where = f"INEGE {ed} {role}"
        rows = _read_region(_words(page), y0, y1, False, where)
        parsed = []
        for lab, vals, hdr in rows:
            vv = {}
            for p, tok in vals.items():
                key = (ed, role, _norm(lab), p)
                if key in _KNOWN:
                    if tok != _KNOWN[key]:
                        raise ValueError(f"{where}: pinned cell {key} now reads {tok!r} "
                                         f"-- INEGE corrected it; remove it from _KNOWN")
                    vv[p] = None
                    continue
                vv[p] = _num(tok)
            parsed.append((lab, vv, hdr))
        if role in ("DE-CUR", "DE-CON"):
            _check_demand([(l, v) for l, v, _ in parsed], where)
        if role in ("OF-CUR", "OF-CON"):
            _check_production([(l, v) for l, v, _ in parsed], where,
                              _norm(parsed[0][0]),
                              _norm(parsed[-1][0]), tol=1.2)
        for lab, vals, hdr in parsed:
            n = _norm(lab)
            if role == "SYN":
                spec = _syn_spec(lab)
                if spec is None:
                    continue
                n, meas, pb, unit = spec
                app = "aggregate"
            else:
                meas, pb = measure, basis
                app = approach
                unit = {"level": "FCFA thousand million", "deflator": "index",
                        "growth_yoy": "percent",
                        "contribution": "percentage points"}[measure]
            for p, v in vals.items():
                out.append(dict(approach=app, category=lab,
                                category_group=f"{title.split(':', 1)[1].strip()} "
                                               f"[{hdr[p]}] ({ed})",
                                series_code=f"AEGE-{role}", geography="National",
                                period=p, frequency="annual", price_basis=pb,
                                seasonal_adjustment="not_applicable", measure=meas,
                                value=v, unit=unit,
                                base_period=_BASE if (meas in ("level", "per_capita")
                                                      and pb == "constant") else "",
                                _edition=ed, _norm=n, _dropped=v is None))
    return out


# ---------------------------------------------------------------------------

def _rank(path):
    """Newer publication first: quarterly by (year, quarter) in the file name,
    yearbooks by edition year."""
    b = os.path.basename(path).upper()
    m = re.search(r"T([1-4])[-_ ]?(20\d\d)", b)
    if m:
        return (int(m.group(2)), int(m.group(1)))
    m = re.search(r"(20\d\d)", b)
    return (int(m.group(1)), 9) if m else (0, 0)


def parse(pdf_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    files = [pdf_path, *(extras or [])]
    quarterly = sorted([f for f in files if "TRIMESTRAL" in os.path.basename(f).upper()],
                       key=_rank, reverse=True)
    yearbooks = sorted([f for f in files if f not in quarterly], key=_rank, reverse=True)
    if not quarterly or not yearbooks:
        raise ValueError(f"INEGE: expected quarterly reports and yearbooks, got {files}")

    rows, seen = [], set()
    for f in quarterly:                         # newest issue wins
        for r in _quarterly(f):
            k = (r["series_code"], _norm(r["category"]), r["period"])
            if k not in seen:
                seen.add(k)
                rows.append(r)

    # Yearbooks: newest edition wins; an older edition's label is replaced by
    # the newest edition's spelling of the same (normalised) label.
    spelled = {}
    for f in yearbooks:
        for r in _yearbook(f):
            k = (r["series_code"], r["_norm"], r["period"])
            spelled.setdefault((r["series_code"], r["_norm"]), r["category"])
            if k in seen:
                continue
            seen.add(k)
            # A cell the newer edition prints but we refuse (pinned in _KNOWN)
            # must not be back-filled from an OLDER edition's vintage.
            if r["_dropped"]:
                continue
            r["category"] = spelled[(r["series_code"], r["_norm"])]
            rows.append({c: r[c] for c in _OUT_COLS})
    df = pd.DataFrame(rows)[_OUT_COLS]
    key = ["approach", "category", "series_code", "period", "frequency",
           "price_basis", "measure"]
    if df.duplicated(key).any():
        raise ValueError(f"INEGE: duplicate keys {df[df.duplicated(key)].head()}")
    return df
