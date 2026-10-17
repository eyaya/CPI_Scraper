"""Parser for the INSEED Chad quarterly national-accounts (CNT) PDF (French).

Francophone CEMAC note (like Cameroon). Each table lists GDP (PIB) by branch of
activity across the quarters ('Tn YYYY'), followed by a growth block we ignore:
  Tableau 1  Évolution du PIB trimestriel en volumes chaînés  -> production constant
  Tableau 3  Évolution du PIB trimestriel aux prix courants    -> production current
  Tableau 4  Déflateur du PIB trimestriel (base 100 = 2017)     -> deflator

Per row we read the label and every French number (comma decimal, optional space
thousands: '2341,7', '1 234,5'); the first len(periods) values are the quarterly
levels (or the deflator). Values are billion XAF (FCFA). Everything as published.

LAYOUT A (through the Q1 2026 note, June 2026): the above -- UNADJUSTED, 8
quarters + a T/T-4 growth block (ignored). Its Tableau 1 header says "en million
de FCFA", but the magnitudes are billions (quarterly PIB ~2 500 against INSEED's
own annual GDP of ~10 000 billion FCFA), and the later notes print "milliards";
the rows have always been filed as "XAF billion".

LAYOUT B (from the Q2 2026 note, September 2026): see `_parse_layout_b`.
SEASONALLY ADJUSTED ("Données CVS" on the cover), 5 quarters, milliards de FCFA,
production AND demand optiques, plus growth and contribution columns. Filed as
seasonal_adjustment "saa", so it never shares a merge key with layout A's
unadjusted rows.
"""
from __future__ import annotations
import re
import pdfplumber
import pandas as pd

_PERIOD_RE = re.compile(r"T([1-4])[ _]?(20\d\d)")
# space-grouped ('1 234,5') OR plain ('2341,7' / '246'); the space-group form is
# tried first so a '2 766,5' isn't split, but a spaceless '2766,5' still matches.
_FRNUM_RE = re.compile(r"-?\d{1,3}(?: \d{3})+(?:,\d+)?|-?\d+(?:,\d+)?")

_OUT_COLS = ["approach", "category", "category_group", "series_code", "geography",
             "period", "frequency", "price_basis", "seasonal_adjustment",
             "measure", "value", "unit", "base_period"]


def _spec(caption: str):
    c = caption.lower()
    if "contribution" in c:
        return None
    if "flateur" in c:                       # déflateur
        return ("deflator", "not_applicable", "index", "2017=100")
    if "prix courant" in c:
        return ("level", "current", "XAF billion", "")
    if "volume" in c or "chaîn" in c or "chain" in c:
        return ("level", "constant", "XAF billion", "chained volume, base 2017")
    return None


def _caption(page) -> str:
    for line in (page.extract_text() or "").split("\n"):
        if re.search(r"tableau\s*\d", line, re.I):
            return line
    return ""


def _frval(tok):
    return float(tok.replace(" ", "").replace(",", "."))


def _periods(tb):
    for row in tb[:4]:
        pers, seen = [], set()
        for c in row:
            m = _PERIOD_RE.search(re.sub(r"\s+", " ", str(c or "")))
            if m:
                p = f"{m.group(2)}-Q{m.group(1)}"
                if p not in seen:
                    seen.add(p); pers.append(p)
        if len(pers) >= 4:
            return pers
    return []


def _parse_table(tb, measure, basis, unit, base):
    periods = _periods(tb)
    if not periods:
        return []
    n = len(periods)
    rows = []
    for row in tb:
        joined = re.sub(r"\s+", " ", " ".join(str(c) for c in row if c)).strip()
        lm = re.match(r"^([^\d]+?)\s*(?=-?\d)", joined)
        if not lm:
            continue
        label = lm.group(1).strip(" .:-()%")
        low = label.lower()
        if (len(label) < 3 or len(label.split()) > 9 or _PERIOD_RE.search(label)
                or any(k in low for k in ("libell", "tableau", "source", "volumes",
                                          "prix courant", "flateur"))):
            continue
        nums = [_frval(t) for t in _FRNUM_RE.findall(joined)]
        if len(nums) < n:
            continue
        ap = "aggregate" if low == "pib" or "produit intérieur brut" in low else "production"
        for period, v in zip(periods, nums[0:n]):
            rows.append({
                "approach": ap, "category": label, "category_group": "",
                "series_code": "", "geography": "National", "period": period,
                "frequency": "quarterly", "price_basis": basis,
                "seasonal_adjustment": "nsa", "measure": measure,
                "value": v, "unit": unit, "base_period": base,
            })
    return rows


# ---------------------------------------------------------------- layout B --
# Layout B annex (Q2 2026 note): one table per caption, words read with a tight
# x-tolerance -- pdfplumber's table extractor splits '3,4' across cells and
# drops wrapped rows on these pages.
#   Tableau 1  PIB CVS en volumes chaînés      production  levels + T/T-4, T/T-1
#   Tableau 2  Contributions (production)       poids T-4, crois, contrib, poids T-1, crois, contrib
#   Tableau 3  PIB aux prix courants             production  levels
#   Tableau 4  Déflateurs (2017 = 100)           production  index + T/T-4, T/T-1
#   Tableau 5  Emplois CVS en volumes chaînés    expenditure levels + T/T-4, T/T-1
#   Tableau 6  Contributions des emplois         as Tableau 2
#   Tableau 7  Emplois aux prix courants         expenditure levels
# Tables 3, 4 and 7 do not repeat "CVS" in their captions, but the cover says
# the whole note is "Données CVS", and Tableau 4's deflators equal Tableau 3
# over Tableau 1 (checked below) -- so they are filed "saa" too.
_B_CAPTION_RE = re.compile(r"^Tableau\s*(\d+)\s*:")
_B_PERIOD_RE = re.compile(r"^(20\d\d)T([1-4])$")
_B_NUM_RE = re.compile(r"^-?\d+(?:,\d+)?$")
_B_DASHES = {"–", "—", "-"}
_B_VOL_BASE = "chained volume, base 2017"
_B_PIB = "PRODUIT INTÉRIEUR BRUT"
_B_PIB_D = "PRODUIT INTÉRIEUR BRUT (optique demande)"


def _b_caption_spec(caption: str):
    """(approach, kind, price_basis, unit, base) for a layout-B caption."""
    c = caption.lower()
    ap = "expenditure" if "emplois" in c else "production"
    if "contribution" in c:
        return ap, "contrib", "constant", None, ""
    if "flateur" in c:
        return ap, "level_growth", "not_applicable", "index", "2017=100"
    if "prix courant" in c:
        return ap, "level_growth", "current", "XAF billion", ""
    if "volume" in c:
        return ap, "level_growth", "constant", "XAF billion", _B_VOL_BASE
    return None


def _b_group(caption: str) -> str:
    """The caption as published, without 'Tableau n :' and the parentheses."""
    g = _B_CAPTION_RE.sub("", caption)
    g = re.sub(r"\s*\([^)]*\)", "", g)
    return re.sub(r"\s+", " ", g).strip()


def _b_lines(page):
    """Page words grouped into lines (top within 2.5 pt), left to right."""
    words = page.extract_words(x_tolerance=1.5, y_tolerance=2)
    lines = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if lines and abs(lines[-1][0] - w["top"]) <= 2.5:
            lines[-1][1].append(w)
        else:
            lines.append((w["top"], [w]))
    return [(top, [w["text"] for w in sorted(ws, key=lambda w: w["x0"])])
            for top, ws in lines]


def _b_split(tokens):
    """Split a line into (label, values); a value is a float, or None for a
    printed dash. Thousands come apart at this tolerance ('2', '389,4'), so a
    1-3 digit integer followed by a 3-digit group is rejoined."""
    i = len(tokens)
    while i > 0 and (_B_NUM_RE.match(tokens[i - 1]) or tokens[i - 1] in _B_DASHES):
        i -= 1
    label, num, vals, j = " ".join(tokens[:i]).strip(), tokens[i:], [], 0
    while j < len(num):
        t = num[j]
        if t in _B_DASHES:
            vals.append(None); j += 1; continue
        if (re.match(r"^-?\d{1,3}$", t) and j + 1 < len(num)
                and re.match(r"^\d{3}(?:,\d+)?$", num[j + 1])):
            t = t + num[j + 1]; j += 1
        vals.append(_frval(t)); j += 1
    return label, vals


def _b_tables(pdf):
    """Yield (table number, caption, header tokens, [(label, values)])."""
    for page in pdf.pages:
        lines = _b_lines(page)
        k = 0
        while k < len(lines):
            m = _B_CAPTION_RE.match(" ".join(lines[k][1]))
            if not m:
                k += 1; continue
            caption, header, body, pending = " ".join(lines[k][1]), [], [], []
            k += 1
            while k < len(lines):
                top, toks = lines[k]
                t = " ".join(toks)
                if t.startswith("Source") or _B_CAPTION_RE.match(t):
                    break
                label, vals = _b_split(toks)
                if not vals:
                    if not body:
                        header.extend(toks)          # header (may wrap)
                    else:
                        pending.append((top, label))
                    k += 1; continue
                # A label wrapped round its figures: its words sit on text-only
                # lines just above and just below the figures' line.
                above = [l for tp, l in pending if tp > top - 8]
                if above:
                    label = " ".join(above + ([label] if label else []))
                    nxt = lines[k + 1] if k + 1 < len(lines) else None
                    if nxt and nxt[0] < top + 8 and not _b_split(nxt[1])[1]:
                        label = f"{label} {' '.join(nxt[1])}"; k += 1
                pending = []
                body.append((re.sub(r"\s+", " ", label).strip(" .:"), vals))
                k += 1
            yield int(m.group(1)), caption, header, body


def _b_period(tok):
    m = _B_PERIOD_RE.match(tok)
    return f"{m.group(1)}-Q{m.group(2)}"


def _b_shift(period: str, back: int) -> str:
    n = int(period[:4]) * 4 + int(period[-1]) - 1 - back
    return f"{n // 4}-Q{n % 4 + 1}"


def _parse_layout_b(pdf) -> list[dict]:
    rows, levels, growth, last = [], {}, {}, None

    def add(ap, cat, grp, period, basis, measure, v, unit, base):
        rows.append({
            "approach": ap, "category": cat, "category_group": grp,
            "series_code": "", "geography": "National", "period": period,
            "frequency": "quarterly", "price_basis": basis,
            "seasonal_adjustment": "saa", "measure": measure,
            "value": v, "unit": unit, "base_period": base,
        })

    for num, caption, header, body in _b_tables(pdf):
        spec = _b_caption_spec(caption)
        if not spec or not body:
            continue
        ap0, kind, basis, unit, base = spec
        grp = _b_group(caption)
        if kind == "level_growth":
            periods = [_b_period(t) for t in header if _B_PERIOD_RE.match(t)]
            gcols = [g for g in ("T/T-4", "T/T-1") if g in header]
            if len(periods) < 4:
                raise ValueError(f"INSEED Chad (layout B): no quarters in {caption!r}")
            last = periods[-1]
            measure = "deflator" if basis == "not_applicable" else "level"
            for label, vals in body:
                if len(vals) != len(periods) + len(gcols):
                    raise ValueError(f"INSEED Chad (layout B): {label!r} in table {num} "
                                     f"has {len(vals)} values, want "
                                     f"{len(periods) + len(gcols)}")
                ap = "aggregate" if label.startswith(_B_PIB) else ap0
                for period, v in zip(periods, vals):
                    if v is None:
                        raise ValueError(f"INSEED Chad (layout B): blank level {label!r}")
                    add(ap, label, grp, period, basis, measure, v, unit, base)
                    levels[(num, label, period)] = v
                for g, v in zip(gcols, vals[len(periods):]):
                    if v is None:      # '–': not meaningful (stocks, external balance)
                        continue
                    add(ap, label, grp, last, basis,
                        "growth_yoy" if g == "T/T-4" else "growth_qoq", v, "percent", "")
                    growth[(ap0, basis, label, g)] = v
        else:                                       # contributions
            if last is None:
                raise ValueError("INSEED Chad (layout B): contributions before levels")
            for label, vals in body:
                if len(vals) != 6:
                    raise ValueError(f"INSEED Chad (layout B): {label!r} in table {num} "
                                     f"has {len(vals)} values, want 6")
                ap = "aggregate" if label.startswith(_B_PIB) else ap0
                for (w, gr, c), g, back in ((vals[0:3], "T/T-4", 4),
                                            (vals[3:6], "T/T-1", 1)):
                    # 'Poids' = the item's share of real CVS GDP in the base
                    # quarter (T-4 or T-1), as published -- dated to that quarter.
                    if w is not None:
                        add(ap, label, f"{grp} - poids", _b_shift(last, back),
                            "constant", "share", w, "percent", "")
                    if c is not None:
                        add(ap, label, f"{grp} - {g}", last,
                            "constant", "contribution", c, "percentage points", "")
                    # The growth column repeats Tableau 1/5's; it must agree.
                    want = growth.get((ap0, "constant", label, g))
                    if gr is not None and want is not None and abs(gr - want) > 0.05:
                        raise ValueError(f"INSEED Chad (layout B): {label!r} {g} growth "
                                         f"{gr} in table {num} vs {want} in the level table")
    _b_checks(levels)
    return rows


def _b_checks(levels):
    """Cross-table identities of the layout-B note. Raises on a break."""
    lv = levels.get
    for (num, label, p), v in levels.items():
        if num != 4:
            continue
        cur, vol = lv((3, label, p)), lv((1, label, p))
        # Deflator = current / chained volume x 100, within what the printed
        # one-decimal rounding of both levels allows (wide for tiny branches:
        # 1,3 / 1,8 bounds the ratio between 67.6 and 77.1).
        if cur is None or not vol or vol <= 0.05:
            continue
        lo = (cur - 0.05) / (vol + 0.05) * 100 - 0.05
        hi = (cur + 0.05) / (vol - 0.05) * 100 + 0.05
        if not lo <= v <= hi:
            raise ValueError(f"INSEED Chad (layout B): deflator {label} {p} = {v}, "
                             f"current/volume = {cur / vol * 100:.1f}")
    for p in {k[2] for k in levels}:
        # The two optiques print the same GDP.
        for a, b in ((1, 5), (3, 7)):
            x, y = lv((a, _B_PIB, p)), lv((b, _B_PIB_D, p))
            if x is not None and y is not None and abs(x - y) > 0.05:
                raise ValueError(f"INSEED Chad (layout B): PIB {p} {x} (table {a}) "
                                 f"vs {y} (table {b})")
        # Current prices are additive: VAB + taxes = PIB; DIT + X - M = PIB.
        vab, tax, pib = (lv((3, "Valeur ajoutée brute totale (VAB)", p)),
                         lv((3, "Impôts nets sur les produits", p)), lv((3, _B_PIB, p)))
        if None not in (vab, tax, pib) and abs(vab + tax - pib) > 0.15:
            raise ValueError(f"INSEED Chad (layout B): VAB + taxes != PIB at {p}")
        dit, x, m, pd_ = (lv((7, "Demande intérieure totale", p)),
                          lv((7, "Exportations de biens et services", p)),
                          lv((7, "Importations de biens et services", p)),
                          lv((7, _B_PIB_D, p)))
        if None not in (dit, x, m, pd_) and abs(dit + x - m - pd_) > 0.15:
            raise ValueError(f"INSEED Chad (layout B): DIT + X - M != PIB at {p}")


def _is_layout_b(pdf) -> bool:
    for page in pdf.pages:
        for line in (page.extract_text() or "").split("\n"):
            if _B_CAPTION_RE.match(line) and "CVS" in line:
                return True
    return False


def parse(pdf_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = []
    with pdfplumber.open(pdf_path) as pdf:
        if _is_layout_b(pdf):
            rows.extend(_parse_layout_b(pdf))
        for page in ([] if rows else pdf.pages):
            spec = _spec(_caption(page))
            if not spec:
                continue
            for tb in page.extract_tables():
                if len(tb) >= 8:
                    rows.extend(_parse_table(tb, *spec))
    if not rows:
        raise ValueError("no GDP rows parsed from INSEED Chad note")
    # ANNUAL back series (extras): INSEED's annual accounts reports, each its
    # own vintage -- see chad_inseed_annual.
    from .chad_inseed_annual import parse_annual
    for ex in extras or []:
        rows.extend(parse_annual(ex))
    return pd.DataFrame.from_records(rows)[_OUT_COLS].drop_duplicates(
        ["approach", "category", "category_group", "period", "frequency",
         "measure", "price_basis", "seasonal_adjustment"])
