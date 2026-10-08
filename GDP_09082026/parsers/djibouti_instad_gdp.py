"""Parser for INSTAD Djibouti national accounts, from the Annuaire statistique.

INSTAD publishes no separate national-accounts release (its site's own
category list has none); the accounts are chapter 7.2 of the Annuaire
statistique, four tables, FDJ millions, constant prices "aux prix de 2013":

    Comptes nationaux à prix courants   (Optique production)  -> production, current
    Comptes nationaux à prix constants  (Optique production)  -> production, constant
    Comptes nationaux à prix courants   (Optique emplois)     -> expenditure, current
    Comptes nationaux à prix constants  (Optique emplois)     -> expenditure, constant

The production tables run primaire / secondaire / tertiaire with their
branches, "Valeur ajoutée totale", "Impôts nets de subvention sur produits"
and PIB; the 2025 edition's constant table adds "Taux de croissance du PIB"
(-> growth_yoy, aggregate). The expenditure tables run consommation finale
(ménages / APU / ISBLSM), investissement = FBCF (privée / publique) +
variations des stocks (hors zone franche / zone franche), exportations nettes
and PIB. PIB rows are filed under `aggregate`.

TWO EDITIONS ARE READ, newest winning every year both print: the 2025 edition
(2018-2024: 2018-2022 "compte définitif", 2023-2024 "compte provisoire") and
the 2024 edition for 2014-2017. INSTAD revised heavily between them (2018
primaire 16 150 in the 2024 edition, 7 336 in the 2025 one; PIB 515 333 vs
517 784), so the series SPLICES TWO VINTAGES at 2017/2018. `category_group`
names the edition every value came from, so the splice is visible on each row.

TABLES ARE FOUND BY CAPTION TEXT, not number: the 2025 edition numbers BOTH
production tables "7.2.1". Labels are respelled between editions ("Tertaire"
2025 / "Tertiaire" 2024; "manufactuières" / "manufacturières"); a row from the
older edition is matched to the newer edition's row in the same table by a
close-match on the normalised label, and published under the newer spelling.

READ BY WORD GEOMETRY. Counts use a narrow no-break space (U+202F) as
thousands separator, so a line reads "Primaire 7 336 8 341 11 161 ..." --
ambiguous as text. Each fragment is
assigned to the year column above it and the fragments of a cell are joined.

CHECKED EVERY RUN (FDJ millions, tolerance 3 for rounding): each sector =
its branches; valeur ajoutée totale = primaire + secondaire + tertiaire;
PIB = VA + impôts nets; consommation finale = ménages + APU + ISBLSM;
FBCF = privée + publique; variations des stocks = hors ZF + ZF;
investissement = FBCF + stocks; exportations nettes = X - M;
PIB = consommation + investissement + exportations nettes. A break raises
unless pinned in `_KNOWN`.

PUBLISHED ODDITIES KEPT: the 2024 edition prints ISBLSM consumption for 2015
as "958,9363853" in an integer table -- collected as printed. Its constant-
price production table does not add up in four years: PIB 417 942 / 447 713 /
472 150 / 522 124 against VA + impôts nets 410 410 / 441 548 / 442 166 /
522 901 (2015, 2016, 2017, 2019). The cells are collected as printed and the
breaks pinned in `_KNOWN_BREAKS` (2019 is superseded by the 2025 edition,
which is additive throughout); the 2015-2017 constant-price GDP therefore
does not equal its own components, and a user should know it. The 2024
edition's two sides also disagree for 2015 at constant prices (production
417 942, expenditure 453 387); each is kept under its own approach.

CROSS-CHECK: PIB 2024 737 924 (courant) / 662 943 (prix de 2013), growth
2024 7,0%; 2018 courant 517 784; 2014 courant 393 595 (2024 edition).
"""
from __future__ import annotations

import difflib
import os
import re
import unicodedata

import fitz  # PyMuPDF
import pandas as pd

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]

_TABLES = [  # role, caption, approach, basis
    ("PROD-CUR", r"prix courants \(Optique production\)", "production", "current"),
    ("PROD-CON", r"prix constants.*\(Optique production\)", "production", "constant"),
    ("EMP-CUR", r"prix courants \(Optique emplois\)", "expenditure", "current"),
    ("EMP-CON", r"prix constants.*\(Optique emplois\)", "expenditure", "constant"),
]
_FRAG = re.compile(r"^-?\d[\d ,]*%?$")
_CELL = re.compile(r"^-?\d{1,3}(?: \d{3})*(?:,\d+)?%?$")
_SKIP_LINE = re.compile(r"^(Unit[ée]|Source|Annuaire Statistique|Tableau)", re.I)

# (edition, role, normalised label, period) -> printed cell, dropped
_KNOWN: dict = {}

# Identity breaks INSTAD publishes, kept (every cell is collected as printed)
# and pinned so that any OTHER break -- or a correction of these -- raises.
# (where, period, identity) -> (printed total, sum of its parts)
_KNOWN_BREAKS = {
    ("INSTAD Annuaire 2024 PROD-CON", "2015", "PIB"): (417942, 410410),
    ("INSTAD Annuaire 2024 PROD-CON", "2016", "PIB"): (447713, 441548),
    ("INSTAD Annuaire 2024 PROD-CON", "2017", "PIB"): (472150, 442166),
    ("INSTAD Annuaire 2024 PROD-CON", "2019", "PIB"): (522124, 522901),
}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]+", " ", s.lower()).strip()


def _num(cell: str) -> float:
    return float(cell.rstrip("%").replace(" ", "").replace(",", "."))


def _edition(path: str, doc) -> str:
    m = re.search(r"Edition (20\d\d)", doc[min(5, len(doc) - 1)].get_text()) or \
        re.search(r"(20\d\d)", os.path.basename(path))
    return m.group(1)


def _lines(words, y0, y1):
    # The thousands separator is U+202F (narrow no-break space) INSIDE a word
    # ("4 197"); some cells instead split into words at a plain space.
    words = [(*w[:4], w[4].replace(" ", " ").replace(" ", " "))
             for w in words]
    ws = sorted([w for w in words if y0 <= w[1] < y1], key=lambda w: (w[1], w[0]))
    lines, cur = [], []
    for w in ws:
        if cur and abs(w[1] - cur[0][1]) > 3:
            lines.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lines.append(cur)
    return [sorted(l, key=lambda w: w[0]) for l in lines]


def _read(page, y0, y1, where):
    lines = _lines(page.get_text("words"), y0, y1)
    hdr_i = next((i for i, l in enumerate(lines)
                  if len(l) >= 4 and all(re.fullmatch(r"20\d\d", w[4]) for w in l)), None)
    if hdr_i is None:
        raise ValueError(f"{where}: no year header")
    cols = [((w[0] + w[2]) / 2, w[4]) for w in lines[hdr_i]]
    xs = [c[0] for c in cols]
    gap = min(b - a for a, b in zip(xs, xs[1:]))
    data, loose = [], []
    for l in lines[hdr_i + 1:]:
        text = " ".join(w[4] for w in l)
        if _SKIP_LINE.match(text):
            continue
        label = [w for w in l if w[2] < xs[0] - gap * 0.5 or not _FRAG.match(w[4])]
        frags = [w for w in l if w not in label]
        y = (l[0][1] + l[0][3]) / 2
        if not frags:
            loose.append((y, " ".join(w[4] for w in label)))
            continue
        cells = {}
        for w in frags:
            cx = (w[0] + w[2]) / 2
            # A cell's fragments are right-aligned under its column: assign by
            # the fragment's RIGHT edge to the nearest column centre's right side.
            i = min(range(len(xs)), key=lambda k: abs(xs[k] - cx))
            cells.setdefault(i, []).append(w[4])
        if sorted(cells) != list(range(len(cols))):
            raise ValueError(f"{where}: {text!r} fills columns {sorted(cells)}")
        vals = {}
        for i, parts in cells.items():
            cell = " ".join(parts)
            if not _CELL.match(cell) and not re.fullmatch(r"-?\d+,\d+%?", cell):
                raise ValueError(f"{where}: unreadable cell {cell!r} in {text!r}")
            vals[cols[i][1]] = cell
        data.append([y, " ".join(w[4] for w in label), vals])
    # Wrapped label fragments ("Formation brute de capitale fixe" / "(FBCF)")
    # join the nearest data row.
    for y, frag in loose:
        row = min(data, key=lambda r: abs(r[0] - y))
        row[1] = f"{row[1]} {frag}".strip() if y > row[0] else f"{frag} {row[1]}".strip()
    for r in data:
        if not r[1]:
            raise ValueError(f"{where}: values with no label at y={r[0]:.0f}")
    return [(r[1], r[2]) for r in data]


def _regions(doc):
    out = {}
    for page in doc:
        if re.search(r"\.{5}", page.get_text()):
            continue
        caps = [(b[1], b[4].replace("\n", " ")) for b in page.get_text("blocks")
                if re.match(r"\s*Tableau\s*7\.2\.\d", b[4])]
        caps.sort()
        for k, (y, t) in enumerate(caps):
            for role, rx, *_ in _TABLES:
                if re.search(rx, t, re.I) and role not in out:
                    y1 = caps[k + 1][0] if k + 1 < len(caps) else page.rect.y1
                    out[role] = (page, y, y1)
    return out


def _check(role, rows, where):
    get = {}
    for lab, vals in rows:
        get.setdefault(_norm(lab), vals)
    periods = list(rows[0][1])

    def v(key, p):
        # Exact label first: "exportations" must not resolve to
        # "exportations nettes".
        hits = [k for k in get if k == key] or [k for k in get if k.startswith(key)]
        if not hits:
            raise ValueError(f"{where}: no row '{key}'")
        c = get[hits[0]].get(p)
        return None if c is None else _num(c)

    def eq(name, p, a, parts):
        if a is None or None in parts:
            return
        if abs(a - sum(parts)) > 3:
            if _KNOWN_BREAKS.get((where, p, name)) == (round(a), round(sum(parts))):
                return
            raise ValueError(f"{where} {p}: {name} {a} vs {sum(parts):.0f}")

    labels = [_norm(l) for l, _ in rows]
    for p in periods:
        if role.startswith("PROD"):
            sect = ["primaire", None, "secondaire", None]
            for s_key in ("primaire", "secondaire", "tert"):
                i = next(i for i, l in enumerate(labels) if l.startswith(s_key))
                parts = []
                for l, (_, vals) in zip(labels[i + 1:], rows[i + 1:]):
                    if l.startswith(("secondaire", "tert", "valeur ajoutee")):
                        break
                    parts.append(_num(vals[p]))
                eq(s_key, p, v(s_key, p), parts)
            eq("VA", p, v("valeur ajoutee totale", p),
               [v("primaire", p), v("secondaire", p), v("tert", p)])
            eq("PIB", p, v("produit interieur brut", p),
               [v("valeur ajoutee totale", p), v("impots nets", p)])
        else:
            eq("consommation", p, v("consommation finale", p),
               [v("menage", p), v("administrations publiques", p), v("isblsm", p)])
            eq("FBCF", p, v("formation brute", p), [v("privee", p), v("publique", p)])
            eq("stocks", p, v("variations des stocks", p),
               [v("hors zone franche", p), v("zone franche", p)])
            eq("investissement", p, v("investissement", p),
               [v("formation brute", p), v("variations des stocks", p)])
            eq("exportations nettes", p, v("exportations nettes", p),
               [v("exportations", p), -v("importations", p)])
            eq("PIB", p, v("pib", p), [v("consommation finale", p),
                                      v("investissement", p),
                                      v("exportations nettes", p)])


def _edition_rows(path):
    doc = fitz.open(path)
    ed = _edition(path, doc)
    regs = _regions(doc)
    missing = [r for r, *_ in _TABLES if r not in regs]
    if missing:
        raise ValueError(f"INSTAD Annuaire {ed}: tables {missing} not found")
    out = []
    for role, _, approach, basis in _TABLES:
        page, y0, y1 = regs[role]
        where = f"INSTAD Annuaire {ed} {role}"
        rows = _read(page, y0, y1, where)
        clean = []
        for lab, vals in rows:
            vv = {}
            for p, cell in vals.items():
                key = (ed, role, _norm(lab), p)
                if key in _KNOWN:
                    if cell != _KNOWN[key]:
                        raise ValueError(f"{where}: pinned {key} now reads {cell!r}")
                    vv[p] = None
                else:
                    vv[p] = cell
            clean.append((lab, vv))
        _check(role, clean, where)
        for lab, vals in clean:
            n = _norm(lab)
            growth = n.startswith("taux de croissance")
            pib = n.startswith(("pib", "produit interieur brut"))
            for p, cell in vals.items():
                out.append(dict(
                    approach="aggregate" if (pib or growth) else approach,
                    category=lab,
                    category_group=("Comptes nationaux, optique "
                                    + ("production" if role.startswith("PROD") else "emplois")
                                    + f" (Annuaire statistique {ed})"),
                    series_code=f"INSTAD-{role}", geography="National",
                    period=p, frequency="annual", price_basis=basis,
                    seasonal_adjustment="not_applicable",
                    measure="growth_yoy" if growth else "level",
                    value=None if cell is None else _num(cell),
                    unit="percent" if growth else "FDJ million",
                    base_period="Constant 2013 prices"
                    if (basis == "constant" and not growth) else "",
                    _edition=ed, _norm=n, _role=role))
    return out


def parse(pdf_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    files = [pdf_path, *(extras or [])]
    eds = sorted(((_edition_rows(f), f) for f in files),
                 key=lambda t: t[0][0]["_edition"], reverse=True)
    rows, seen, spelled = [], set(), {}
    for ed_rows, _ in eds:
        for r in ed_rows:
            role = r["_role"]
            names = spelled.setdefault(role, {})
            if r["_norm"] in names:
                canon = r["_norm"]
            else:
                # A typo ("tertaire"/"tertiaire") or a lengthened label
                # ("produit interieur brut pib" / "... au prix du marche").
                pre = [k for k in names if k.startswith(r["_norm"] + " ")
                       or r["_norm"].startswith(k + " ")]
                close = pre or difflib.get_close_matches(r["_norm"], list(names),
                                                         n=1, cutoff=0.88)
                canon = close[0] if close else r["_norm"]
                names.setdefault(canon, r["category"])
            k = (role, canon, r["period"])
            if k in seen:
                continue
            seen.add(k)
            if r["value"] is None:          # pinned: never back-filled
                continue
            r["category"] = names[canon]
            rows.append({c: r[c] for c in _OUT_COLS})
    df = pd.DataFrame(rows)[_OUT_COLS]
    key = ["approach", "category", "series_code", "period", "measure"]
    if df.duplicated(key).any():
        raise ValueError(f"INSTAD: duplicate keys\n{df[df.duplicated(key, keep=False)].head()}")
    return df
