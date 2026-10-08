"""HCP Morocco "Situation économique nationale" notes -- the national-accounts
LEVELS and sector detail the one-series Google Sheets (`morocco_hcp_gdp`) do
not carry. Two kinds of note, both PDF attachments of HCP articles:

* QUARTERLY ("... au deuxième trimestre 2026", comptes_nat_t<q>_<yyyy>_fr.pdf)
  Tableau 1 -- value added by 16 sectors + taxes + PIB in volume (chained
  previous-year prices, base 2014, SEASONALLY ADJUSTED "cvs"), PIB hors
  agriculture, PIB en valeur; Tableau 2 -- the main uses in volume (same
  basis; HCP does not say cvs here, so seasonal adjustment is recorded
  `not_applicable`, not guessed). Each prints the quarter, the same quarter a
  year earlier and the year-on-year change.
* ANNUAL ("... de l'année 2025", ni_comptes_nat_provisoires_<yyyy>_fr.pdf)
  value-added growth by 16 coded sectors; the main aggregates' volume growth
  and current-price levels (PIB, VA, agriculture / non-agriculture, taxes, PIB
  non agricole, household / government / NPISH consumption, GFCF, imports,
  exports); PIB per capita; and the uses as a share of PIB. Columns are 2023
  (définitif), 2024 (semi-définitif) and the note's year (provisoire) -- the
  vintage is recorded in `category_group`.

NOT COLLECTED: Tableau 3 and the annual RNBD / épargne / besoin de financement
lines and their ratios (national income and saving, not GDP).

READING. Integer levels use SPACE thousands ("28 076 34 015 21,2"), which a
line cannot split reliably, so each value's words are grouped by gap and the
values are assigned to columns by their right edge, the columns being found by
clustering the right edges of the table's own rows. Every quarterly row is
then held to its printed change: (t / t-4 - 1) x 100 must round to the printed
"Glissement" (+-0,1), which also proves the split. Annual current-price levels
are held to VA = agriculture + hors agriculture and PIB = VA + impôts.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]
_NUM = re.compile(r"^-?\d+(?:,\d+)?$")
_ORD = {"1er": 1, "1ère": 1, "2éme": 2, "2ème": 2, "3éme": 3, "3ème": 3,
        "4éme": 4, "4ème": 4}
_CHAIN = "Prix de l'année précédente chaînés, base 2014"
# (quarter, label) -> (computed, printed) change: a published inconsistency
# between a row's two levels and its printed "Glissement", every other row of
# the note reconciling. Kept AS PRINTED; pinned so any other mismatch raises.
_KNOWN_GROWTH_GAPS = {
    ("2026-Q2", "Industrie d’extraction"): (-30.1, -28.6),
}
_PREV = "Prix de l'année précédente"


def _lines(page):
    words = page.extract_words()
    out = []
    for w in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        if out and abs(out[-1][0]["top"] - w["top"]) < 3:
            out[-1].append(w)
        else:
            out.append([w])
    return [sorted(l, key=lambda w: w["x0"]) for l in out]


def _split(line, xmin):
    """(label words, numeric runs [(text, x1)]) -- runs = values."""
    lab, runs = [], []
    for w in line:
        if _NUM.match(w["text"]) and w["x0"] > xmin:
            if runs and w["x0"] - runs[-1][2] < 5 and "," not in runs[-1][0]:
                t, x0, _ = runs[-1]
                runs[-1] = (t + w["text"], x0, w["x1"])
            else:
                runs.append((w["text"], w["x0"], w["x1"]))
        else:
            lab.append(w["text"])
    return " ".join(lab).strip(), [(t, x1) for t, _, x1 in runs]


def _value(t: str) -> float:
    return float(t.replace(",", "."))


def _columns(xs: list[float], k: int) -> list[float]:
    """1-D clustering of right edges into k column positions."""
    xs = sorted(xs)
    cents = [xs[int(i * (len(xs) - 1) / max(k - 1, 1))] for i in range(k)]
    for _ in range(20):
        groups = [[] for _ in cents]
        for x in xs:
            groups[min(range(k), key=lambda i: abs(cents[i] - x))].append(x)
        cents = [sum(g) / len(g) if g else c for g, c in zip(groups, cents)]
    return sorted(cents)


def _rows(lines, k, xmin=200):
    """Assemble (label, [k values]) from a table region, rejoining labels that
    wrap above/below their numbers and prefixing group headers ("Dépenses de
    consommation finale" over "- des ménages")."""
    parsed = [_split(l, xmin) for l in lines]
    xs = [x for _, runs in parsed for _, x in runs if len(runs) == k]
    if not xs:
        return []
    cols = _columns(xs, k)
    out, pending, group = [], "", ""
    for lab, runs in parsed:
        if not runs:
            if out and re.match(r"^[a-zàâéèêîôûç'’(]", lab):
                out[-1][0] = f"{out[-1][0]} {lab}".strip()
            else:
                pending = f"{pending} {lab}".strip() if pending else lab
            continue
        if len(runs) != k:
            pending = ""
            continue
        vals = [None] * k
        for t, x in runs:
            j = min(range(k), key=lambda i: abs(cols[i] - x))
            if vals[j] is not None:
                vals = None
                break
            vals[j] = _value(t)
        if vals is None or None in vals:
            pending = ""
            continue
        if lab.startswith("-"):
            if pending:
                group, pending = pending, ""
            lab = f"{group} {lab}".strip()
        elif (not lab or re.match(r"^[a-zàâéèêîôûç]", lab)
              or re.fullmatch(r"[A-Z]{1,2}\d{1,2}|[A-Z]{2}\d", lab)):
            # A row printed as a bare sector code ("DE0") between the two
            # halves of its name takes the half above; the half below joins
            # on the next line.
            lab = (f"{lab} {pending}" if re.fullmatch(r"[A-Z]{1,2}\d{1,2}|[A-Z]{2}\d", lab)
                   else f"{pending} {lab}").strip()
            pending, group = "", ""
        else:
            pending, group = "", ""
        out.append([lab, vals])
    return out


def _row(approach, cat, grp, code, per, freq, price, sa, measure, v, unit, base):
    return {"approach": approach, "category": cat, "category_group": grp,
            "series_code": code, "geography": "National", "period": per,
            "frequency": freq, "price_basis": price, "seasonal_adjustment": sa,
            "measure": measure, "value": v, "unit": unit, "base_period": base}


def _approach(label: str, expenditure: bool) -> str:
    if re.match(r"^(Produit intérieur brut|PIB)", label, re.I):
        return "aggregate"
    return "expenditure" if expenditure else "production"


def _quarterly(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        lines = [l for p in pdf.pages for l in _lines(p)]
    text = [" ".join(w["text"] for w in l) for l in lines]
    out = []
    for tno, expend in (("1", False), ("2", True)):
        start = next((i for i, t in enumerate(text)
                      if re.match(rf"^Tableau {tno}\s*-", t)), None)
        if start is None:
            raise ValueError(f"HCP note {path}: Tableau {tno} not found")
        end = next((i for i in range(start + 1, len(text))
                    if re.match(r"^(Tableau \d|-\d+-$)", text[i])), len(text))
        # The header prints the two ordinals on one line ("2éme Trimestre
        # 2éme Trimestre Glissement") and their years on the next ("2025 2026
        # Annuel en %"): pair them in order.
        head = " ".join(text[start:start + 6])
        ords = re.findall(r"(1er|1ère|2éme|2ème|3éme|3ème|4éme|4ème)\s+Trimestre", head)
        after = head.split("DH)", 1)[-1]
        yrs = re.findall(r"(?<!\d)(20\d\d)(?!\d)", after.split("Annuel")[0])
        if len(ords) != 2 or len(yrs) < 2:
            raise ValueError(f"HCP note {path} T{tno}: header {head!r}")
        (o1, y1), (o2, y2) = zip(ords, yrs[:2])
        p1, p2 = f"{y1}-Q{_ORD[o1]}", f"{y2}-Q{_ORD[o2]}"
        body = [l for l in lines[start + 1:end]
                if not re.search(r"Trimestre|Glissement|Annuel en %|en millions DH|base$|^2014",
                                 " ".join(w["text"] for w in l))]
        rows = _rows(body, 3)
        if len(rows) < (18 if tno == "1" else 6):
            raise ValueError(f"HCP note {path} T{tno}: only {len(rows)} rows")
        sa = "saa" if tno == "1" else "not_applicable"
        grp = ("Tableau 1 - Valeurs ajoutées (cvs) aux prix de l'année précédente "
               "chaînées base 2014" if tno == "1" else
               "Tableau 2 - Principaux emplois du PIB en volume")
        code = f"HCP-CNT-T{tno}"
        for lab, (a, b, g) in rows:
            calc = round((b / a - 1) * 100, 1)
            if abs(calc - g) > 0.11 and _KNOWN_GROWTH_GAPS.get((p2, lab)) != (calc, g):
                raise ValueError(f"HCP note {path} T{tno} {lab!r}: {a} -> {b} "
                                 f"is not {g}% (column split?)")
            value_row = "en valeur" in lab
            price = "current" if value_row else "constant"
            base = "" if value_row else _CHAIN
            ap = _approach(lab, expend)
            for per, v in ((p1, a), (p2, b)):
                out.append(_row(ap, lab, grp, code, per, "quarterly", price, sa,
                                "level", v, "MAD million", base))
            out.append(_row(ap, lab, grp, code, p2, "quarterly", price, sa,
                            "growth_yoy", g, "percent", base))
    return out


def _annual(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        lines = [l for p in pdf.pages for l in _lines(p)]
    text = [" ".join(w["text"] for w in l) for l in lines]
    hdr = next((t for t in text if re.match(r"^(Code Secteur|Opérations)\b", t)), "")
    years = re.findall(r"(\d{4})(\*{0,2})", hdr)
    if len(years) != 3:
        raise ValueError(f"HCP annual note {path}: header {hdr!r}")
    status = {"**": "définitif", "*": "semi définitif", "": "provisoire"}
    vint = ", ".join(f"{y} {status[s]}" for y, s in years)
    yrs = [y for y, _ in years]
    out = []

    # Sector growth table.
    s = next(i for i, t in enumerate(text) if t.startswith("Code Secteur"))
    e = next(i for i in range(s, len(text)) if text[i].startswith("TOTAL")) + 1
    sec = _rows(lines[s + 1:e], 3, xmin=380)
    if len(sec) < 15:
        raise ValueError(f"HCP annual note {path}: {len(sec)} sector rows")
    grp = f"Valeurs ajoutées en volume par secteurs d'activité ({vint})"
    for lab, vals in sec:
        lab = re.sub(r"^[A-Z]{1,2}\d{1,2}\s+|^[A-Z]{2}\d\s+", "", lab)
        for y, v in zip(yrs, vals):
            out.append(_row("production", lab, grp, "HCP-CNA-VA", y, "annual",
                            "constant", "not_applicable", "growth_yoy", v,
                            "percent", _PREV))

    # Aggregates: growth, current-price levels, ratios.
    s = next(i for i, t in enumerate(text) if t.startswith("Evolution des principaux"))
    sections = []
    for i in range(s, len(text)):
        t = text[i]
        if t.startswith("Décomposition du PIB Croissance"):
            sections.append(("growth", i))
        elif t.startswith("Décomposition du PIB Aux prix courants"):
            sections.append(("level", i))
        elif t.startswith("Quelques ratios"):
            sections.append(("ratio", i))
        elif t.startswith("(*)") and sections:
            sections.append(("end", i))
            break
    grp = f"Evolution des principaux agrégats ({vint})"
    levels = {}
    for (kind, a), (_, b) in zip(sections, sections[1:]):
        rows = _rows([l for l in lines[a + 1:b]
                      if " ".join(w["text"] for w in l) != "Demande"], 3, xmin=300)
        for lab, vals in rows:
            demand = lab.startswith(("Dépenses", "Formation", "Importations",
                                     "Exportations", "Taux d"))
            if kind == "growth":
                rec = ("growth_yoy", "constant", "percent", _PREV)
            elif kind == "level":
                if re.match(r"^(Revenu national|Epargne|Besoin)", lab):
                    continue
                rec = ("level", "current", "MAD million", "")
                levels[lab] = vals
            else:
                if lab.startswith("PIB par habitant"):
                    rec = ("per_capita", "current", "MAD", "")
                elif re.search(r"/PIB$|\(FBC/PIB\)$", lab) and not re.match(
                        r"^(Taux d.épargne|Besoin)", lab):
                    rec = ("share", "current", "percent", "")
                else:
                    continue
            measure, price, unit, base = rec
            for y, v in zip(yrs, vals):
                out.append(_row(_approach(lab, demand), lab, grp, "HCP-CNA-AGG",
                                y, "annual", price, "not_applicable", measure, v,
                                unit, base))
    need = ["Produit intérieur brut", "Valeur ajoutée totale aux prix de base",
            "Agriculture", "Hors agriculture",
            "Impôts sur les produits nets des subventions"]
    if not all(n in levels for n in need):
        raise ValueError(f"HCP annual note {path}: levels {list(levels)}")
    for j, y in enumerate(yrs):
        L = {n: levels[n][j] for n in need}
        if abs(L["Agriculture"] + L["Hors agriculture"] - L[need[1]]) > 1.5 \
                or abs(L[need[1]] + L[need[4]] - L[need[0]]) > 1.5:
            raise ValueError(f"HCP annual note {path} {y}: level identities fail {L}")
    return out


def parse_notes(paths: list[str]) -> pd.DataFrame:
    rows = []
    for p in paths:
        name = p.lower()
        rows += _annual(p) if "annuel" in name else _quarterly(p)
    df = pd.DataFrame.from_records(rows)[_OUT_COLS]
    # The newest quarterly note is also pinned as an extra: same rows twice.
    return df.drop_duplicates(["series_code", "category", "period", "measure",
                               "price_basis"])
