"""Parser for the Algeria ONS monthly IPC note PDF (Tier 3).

IMPORTANT — classification: ONS Algeria does NOT use the COICOP 12/13 divisions.
It reports a NATIONAL 8-group nomenclature (Transports & Communication combined;
Education-Culture-Loisirs combined; 'Divers (N.D.A.)' a catch-all). We capture it
EXACTLY as reported — native French labels, native grouping — and do NOT force it
onto COICOP. The `coicop_code` here is an Algeria-internal ordering (00 = Ensemble,
01..08 = the 8 groups), not a COICOP division code. Base 2001 = 100.

TWO INDICES, TWO GEOGRAPHIES (corrected 2026-10-14). The note carries the
Algiers-city index (page 2, 'ville d'Alger': Poids | Indice | MoM | YoY | 12-month)
and the NATIONAL index (page 7, 'EVOLUTION PAR GROUPE': Indice | MoM | YoY |
12-month, 17 towns). Until 2026-10-14 this parser read the Algiers table and
filed it as 'National' (2023-12: Algiers 275,17 vs national 287,68). Now:

  * geography 'National'      -- the national group table (index, MoM, YoY);
  * geography "Ville d'Alger" -- the Algiers group table, as before.

Page 7 also prints a 13-month history (m-12 .. m) of the national and Algiers
'Indice Général' and 'Alimentation' with their monthly variations, one decimal;
those months are emitted too, dated from the report month after checking that
the last column equals the group table's figure.

BACK SERIES (2026-10-14). `parse` reads the newest note plus `extra_urls`
through `ihpc_note_pdf.read_many`: the monthly notes ONS still links
(2023-10 on, found through its spip articles) and the yearbook 'Indice des prix
à la consommation 2014-2023' (Collections Statistiques n° 238, IPC2014_2023.pdf),
whose 'EVOLUTION MENSUELLE PAR GROUPE' pages give every month 2014-2023 for the
8 groups + Ensemble, Algiers and national, index and monthly variation. A month's
OWN note wins; history columns and the yearbook only fill months no own note
gives (their `_issue` sorts below every note's).

Report month: the note's own text ('EN JUIN 2026' in the doubled-letter page-7
title, else "mois d'<month> <year>"), then the filename.
"""
from __future__ import annotations
import os
import re
import unicodedata
import pdfplumber
import pandas as pd

_BASE_PERIOD = "2001 = 100"
_NATIONAL, _ALGER = "National", "Ville d'Alger"
_MONTHS = {"janvier": "01", "fevrier": "02", "mars": "03", "avril": "04",
           "mai": "05", "juin": "06", "juillet": "07", "aout": "08",
           "septembre": "09", "octobre": "10", "novembre": "11", "decembre": "12"}
# (code, native label as published, keyword on the normalised label) — first match wins
_GROUPS = [
    ("00", "Ensemble", "ensemble"),
    ("01", "Alimentation et boissons non alcoolisées", "alimentation"),
    ("02", "Habillement - Chaussures", "habillement"),
    ("03", "Logement - Charges", "logement"),
    ("04", "Meubles et Articles d'Ameublement", "meubles"),
    ("05", "Santé - Hygiène Corporelle", "sante"),
    ("06", "Transports et Communication", "transport"),
    ("07", "Education - Culture - Loisirs", "education"),
    ("08", "Divers (N.D.A.)", "divers"),
]
_LABEL = {c: lab for c, lab, _ in _GROUPS}
_IS_NUM = re.compile(r"-?\d[\d ]*,\d+%?$")
_NUM = re.compile(r"-?\d+,\d+")
_COLS = ["coicop_code", "coicop_label", "period", "measure", "value", "unit",
         "base_period", "geography"]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _val(t: str) -> float:
    return float(t.replace(" ", "").replace(",", ".").replace("%", ""))


def _code(label: str):
    n = _norm(label)
    for code, clabel, kw in _GROUPS:
        if kw in n:
            return code, clabel
    return None


def _back(period: str, n: int) -> str:
    y, m = int(period[:4]), int(period[5:]) - n
    while m <= 0:
        y, m = y - 1, m + 12
    return f"{y}-{m:02d}"


def _undouble(line: str) -> str:
    """'EENN JJUUIINN 22002266' -> 'EN JUIN 2026' (ONS's bold titles extract doubled)."""
    out = []
    for tok in line.split():
        out.append(tok[0::2] if len(tok) % 2 == 0 and tok[0::2] == tok[1::2] else tok)
    return " ".join(out)


def _month(text: str, pat: str) -> str | None:
    for mm, yy in re.findall(pat, text, re.IGNORECASE):
        if _norm(mm) in _MONTHS:
            return f"{yy}-{_MONTHS[_norm(mm)]}"
    return None


# ---------------------------------------------------------------- monthly note

def _alger_table(page) -> dict:
    """The Algiers group table (word coordinates; the 'Alimentation' label wraps)."""
    rows = {}
    for w in page.extract_words():
        rows.setdefault(round(w["top"]), []).append(w)
    merged = []
    for k in sorted(rows):
        if merged and k - merged[-1][0] <= 3:
            merged[-1][1].extend(rows[k])
        else:
            merged.append([k, list(rows[k])])
    picked, pending = {}, ""
    for _, ws in merged:
        ws = sorted(ws, key=lambda w: w["x0"])
        nums = [w["text"] for w in ws if _IS_NUM.match(w["text"])]
        labs = " ".join(w["text"] for w in ws if not _IS_NUM.match(w["text"])).strip()
        if len(nums) >= 4:
            hit = _code(labs or pending)
            pending = ""
            if hit and hit[0] not in picked:
                picked[hit[0]] = (_val(nums[1]), _val(nums[2]), _val(nums[3]))
        elif labs:
            pending = (pending + " " + labs).strip() if pending else labs
    return picked


def _national_table(text: str) -> dict:
    """The national group table: '<label> <indice> <MoM> <YoY> <12 mois>'."""
    picked = {}
    for ln in text.splitlines():
        if "EVOLUTION COMPAREE" in _undouble(ln):
            break
        nums = _NUM.findall(ln)
        if len(nums) != 4:
            continue
        hit = _code(ln[:ln.find(nums[0])])
        if hit and hit[0] not in picked:
            picked[hit[0]] = tuple(_val(x) for x in nums[:3])
    return picked


def _history(text: str, period: str, tables: dict) -> list:
    """13-month 'Indice Général' / 'Alimentation' lines for ALGER and NATIONAL."""
    lines = [ln for ln in text.splitlines()
             if re.search(r"\b(ALGER|NATIONAL)\b", ln) and len(_NUM.findall(ln)) == 13]
    if len(lines) != 8:
        return []
    months = [_back(period, k) for k in range(12, -1, -1)]
    recs = []
    for i, ln in enumerate(lines):
        code = "00" if i < 4 else "01"
        geo = _ALGER if "ALGER" in ln else _NATIONAL
        vals = [_val(x) for x in _NUM.findall(ln)]
        is_index = (i % 4) < 2
        own = tables[geo].get(code)
        # the last column is the report month: it must equal the group table
        if not own or abs(vals[-1] - (own[0] if is_index else own[1])) > 0.051:
            return []
        for per, v in zip(months[:-1], vals[:-1]):
            recs.append((code, _LABEL[code], per, "index" if is_index else "inflation_mom",
                         v, "Index" if is_index else "percent",
                         _BASE_PERIOD if is_index else "", geo))
    return recs


def _parse_note(pdf) -> pd.DataFrame:
    texts = [p.extract_text() or "" for p in pdf.pages]
    full = " ".join(texts)
    nat_i = next((i for i, t in enumerate(texts)
                  if "NATIONAL" in t and "EVOLUTION PAR GROUPE" in
                  "\n".join(_undouble(ln) for ln in t.splitlines())), None)
    alg_i = next((i for i, t in enumerate(texts)
                  if all(k in t for k in ("ENSEMBLE", "Divers", "Habillement"))), None)
    title = "\n".join(_undouble(ln) for ln in texts[nat_i].splitlines()) if nat_i is not None else ""
    period = (_month(title, r"\bEN\s+([A-ZÉÛ]+)\s+(20\d\d)")
              or _month(full, r"mois\s+d[e'’]?\s*([a-zûéèêàâäîïôùç]+)\s+(20\d\d)"))
    if not period or nat_i is None:
        raise ValueError("Algeria IPC: report month or national table not found")

    tables = {_NATIONAL: _national_table(texts[nat_i]),
              _ALGER: _alger_table(pdf.pages[alg_i]) if alg_i is not None else {}}
    missing = [c for c, _, _ in _GROUPS if c not in tables[_NATIONAL]]
    if missing:
        raise ValueError(f"Algeria IPC national groups incomplete: missing {missing}")
    if tables[_ALGER] and len(tables[_ALGER]) != len(_GROUPS):
        print(f"  [algeria_ons] {period}: Algiers table incomplete -- not emitted")
        tables[_ALGER] = {}

    own = []
    for geo, picked in tables.items():
        for code, (idx, mom, yoy) in picked.items():
            own.append((code, _LABEL[code], period, "index", idx, "Index", _BASE_PERIOD, geo))
            own.append((code, _LABEL[code], period, "inflation_mom", mom, "percent", "", geo))
            own.append((code, _LABEL[code], period, "inflation_yoy", yoy, "percent", "", geo))
    hist = _history(texts[nat_i], period, tables)
    a = pd.DataFrame.from_records(own, columns=_COLS).assign(_issue=period)
    b = pd.DataFrame.from_records(hist, columns=_COLS).assign(_issue=f"0000-{period}")
    return pd.concat([a, b], ignore_index=True)


# ------------------------------------------------------- 2014-2023 yearbook

def _parse_yearbook(pdf) -> pd.DataFrame:
    """'EVOLUTION MENSUELLE PAR GROUPE - ALGER ET NATIONAL - ANNEE <yyyy>' pages:
    per group an ALGER and a NAT index line, then their monthly variations, each
    12 months + the annual figure (not emitted)."""
    recs = []
    for page in pdf.pages:
        t = page.extract_text() or ""
        if "EVOLUTION MENSUELLE PAR GROUPE" not in t or "INDICES MENSUELS" not in t:
            continue
        m = re.search(r"D[ée]c\.\s+(20\d\d)", t)
        if not m:
            continue
        year = m.group(1)
        rows = [ln for ln in t.splitlines()
                if re.search(r"\b(ALGER|NAT)\b", ln) and len(_NUM.findall(ln)) == 13]
        order = ["01", "02", "03", "04", "05", "06", "07", "08", "00"]
        if len(rows) != 4 * len(order):
            raise ValueError(f"Algeria yearbook {year}: {len(rows)} region rows, expected 36")
        # the groups must appear in the expected order
        pos = [_norm(t).find(k) for k in ("1. alimentation", "2. habillement", "3. logement",
                                         "4. meubles", "5. sant", "6. transport",
                                         "7. education", "8. divers", "ensemble")]
        if -1 in pos or pos != sorted(pos):
            raise ValueError(f"Algeria yearbook {year}: groups not in the expected order")
        for gi, code in enumerate(order):
            block = rows[4 * gi: 4 * gi + 4]           # ALGER idx, NAT idx, ALGER var, NAT var
            for k, ln in enumerate(block):
                geo = _ALGER if re.search(r"\bALGER\b", ln) else _NATIONAL
                is_index = k < 2
                vals = [_val(x) for x in _NUM.findall(ln)][:12]
                for mi, v in enumerate(vals):
                    recs.append((code, _LABEL[code], f"{year}-{mi + 1:02d}",
                                 "index" if is_index else "inflation_mom", v,
                                 "Index" if is_index else "percent",
                                 _BASE_PERIOD if is_index else "", geo))
    if not recs:
        raise ValueError("Algeria yearbook: no monthly group pages found")
    return pd.DataFrame.from_records(recs, columns=_COLS).assign(_issue="0000")


# ------------------------------------------------------------------- entry

def _parse_issue(pdf_path: str) -> pd.DataFrame:
    with pdfplumber.open(pdf_path) as pdf:
        first = (pdf.pages[0].extract_text() or "") if pdf.pages else ""
        if "Collections Statistiques" in first:
            out = _parse_yearbook(pdf)
        else:
            out = _parse_note(pdf)
    out["frequency"] = "monthly"
    return out


def parse(pdf_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    from .ihpc_note_pdf import read_many
    return read_many([pdf_path, *(extras or [])], _parse_issue, "algeria_ons")
