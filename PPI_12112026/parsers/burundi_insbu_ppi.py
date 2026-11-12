"""Burundi -- INSBU "Indices des Prix à la Production Agricole au Burundi (IPPAB)".

Monthly release (insbu.bi, Laravel API /api/publications), base 2018 = 100
("IPPAB base 100 pour l'année 2018"), weights per mille from the 2014
national-accounts structure. The annex prints, for the last 6 months:
  Tableau 1 -- the 15 product classes and "Ensemble": weight, index per month,
               % change on 1 month and on the quarter;
  Tableau 2 -- the ~69 elementary products, same columns.
Collected: weight, index, and the 1-month change (inflation_mom), the last
checked against the two indices printed beside it (a row whose printed m/m
change disagrees with its own indices by > 0.15 pp is not given that change).
Not collected: the "1 Trim" column -- its definition is not stated and its
sign is printed on a line of its own in the text layer ("-" above
"Légumineuses ... 10,8" for -10,8), so it cannot be read safely.
index_variant 'agriculture' (a farm-gate PPI, not an industrial one).
Burundi publishes no industrial PPI (the IHPI is a production VOLUME index).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

INDEX_NAME = "Indice des Prix à la Production Agricole au Burundi (IPPAB)"
_MON = {"janv": 1, "jan": 1, "févr": 2, "fevr": 2, "fév": 2, "fev": 2, "mars": 3, "avr": 4, "mai": 5,
        "juin": 6, "juil": 7, "août": 8, "aout": 8, "sept": 9, "sep": 9, "oct": 10, "nov": 11,
        "déc": 12, "dec": 12}
_MTOK = re.compile(r"(?i)\b(janv|jan|févr|fevr|fév|fev|mars|avr|mai|juin|juil|août|aout|sept|sep|oct|nov|déc|dec)\.?-")
_NUM = r"-?\d[\d ]*,\d+|-?\d+"
_TAIL = re.compile(r"^(.*?)\s*((?:(?:" + _NUM + r")\s+)*(?:" + _NUM + r"))\s*$")


def _months(lines, i):
    """Periods of a header whose month line is lines[i] and whose 2-digit
    years are on the next line ("mars- avr- ... / 26 26 ...")."""
    mons = [_MON[m.lower()] for m in _MTOK.findall(lines[i])]
    for k in (i + 1, i + 2):
        if k < len(lines):
            yrs = re.findall(r"\b(\d{2})\b", lines[k])
            if len(yrs) >= len(mons):
                return [f"20{y}-{m:02d}" for m, y in zip(mons, yrs[:len(mons)])]
    return None


def _rows(lines, start, n):
    """(label, numbers) for each data row after a header, until the next
    'Tableau' or the end of the product list."""
    out, pending = [], []
    for ln in lines[start:]:
        s = ln.strip()
        if s.startswith("Tableau") and out:
            break
        if (not s or s.startswith(("INSBU", "Tél", "E-Mail", "Portail", "Devise", "Intitulé", "Nom de",
                                   "produits", "%sur", "sur:", "mois", "Mois")) or _MTOK.search(s)
                or re.fullmatch(r"[\d\s]+", s) or s == "-"):
            continue
        m = _TAIL.match(s)
        nums = m.group(2).split() if m and m.group(2) else []
        # Rejoin space-grouped thousands only inside one number ("1 014,3"
        # never occurs below 1000 with a space): numbers are split on spaces
        # and a lone 1-3 digit integer followed by a ",d" token is one value.
        vals, k = [], 0
        while k < len(nums):
            t = nums[k]
            if re.fullmatch(r"\d{1,3}", t) and k + 1 < len(nums) and re.fullmatch(r"\d{3},\d+", nums[k + 1]):
                vals.append(t + nums[k + 1]); k += 2
            else:
                vals.append(t); k += 1
        if len(vals) >= 1 + n:
            label = " ".join(pending + ([m.group(1)] if m.group(1) else []))
            pending = []
            out.append((re.sub(r"\s+", " ", label).strip(" -"), vals))
        elif out and s[:1].islower() and not pending:
            out[-1] = (out[-1][0] + " " + s, out[-1][1])
        else:
            pending.append(s)
    return out


# Tableau 1's 15 classes and their (fixed, base-2018) weights per mille. A row
# is filed under a class only when BOTH its label and its printed weight match:
# the text layer wraps long labels around the numbers ("Produits des plantes" /
# "oléagineuses 6,0 ..."), and a label read onto the wrong row would otherwise
# carry another class's values. Tableau 2's ~69 products are not collected for
# the same reason -- their wrapped labels cannot be tied to their rows this way.
_CLASSES = {"Céréales": 42.0, "Tubercules et racines": 416.0, "Légumineuses": 91.0,
            "Produits des plantes oléagineuses": 6.0, "Cultures industrielles/exportations": 51.0,
            "Légumes frais": 128.0, "Banane": 138.0, "Fruits frais": 17.0, "Bovins": 30.0,
            "Ovins caprins": 18.0, "Porcins": 9.0, "Autres produits élevages et volailles": 4.0,
            "Sous produits de l'élevage": 13.0,
            "Produits de la sylviculture et de l'exploitation forestière": 17.0,
            "Produits de la pêche (coutumière et artisanale)": 20.0, "Ensemble": 1000.0}


def _fold(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z]", "", t)


def _class(label, vals):
    w = C.to_number(vals[0], decimal=",") if vals else None
    f = _fold(label)
    for name, wt in _CLASSES.items():
        g = _fold(name)
        if f and (f == g or (len(f) >= 5 and (f in g or g in f))) and w == wt:
            return name
    return None


def parse(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        lines = [ln for pg in pdf.pages for ln in (pg.extract_text() or "").split("\n")]
    text = "\n".join(lines)
    if not re.search(r"base 100 pour l.ann[ée]e 2018|ann[ée]e de base est de 2018", text):
        raise ValueError(f"{path}: base 2018 not stated")
    base = "2018=100"
    out, seen = [], set()
    for i, ln in enumerate(lines):
        if not re.match(r"Tableau\s*[12]\b", ln.strip()):
            continue
        h = next((k for k in range(i + 1, min(i + 8, len(lines))) if len(_MTOK.findall(lines[k])) >= 3), None)
        if h is None:
            continue
        periods = _months(lines, h)
        if not periods:
            continue
        n = len(periods)
        for label, vals in _rows(lines, h + 2, n):
            cls = _class(label, vals)
            if cls is None or cls in seen:
                continue
            seen.add(cls)
            ind = cls
            nums = [C.to_number(v, decimal=",") for v in vals]
            # A row must print weight + one index per month + at most the two
            # changes; anything else (a missing cell shifts every later column)
            # is dropped rather than guessed. Indices are positive.
            if not (1 + n <= len(nums) <= 3 + n):
                continue
            w, idx, rest = nums[0], nums[1:1 + n], nums[1 + n:]
            if w is None or not (0 < w <= 1000) or any(v is None or v <= 0 for v in idx):
                continue
            for p, v in zip(periods, idx):
                if v is not None:
                    out.append(C.row(index_name=INDEX_NAME, index_variant="agriculture", industry=ind,
                                     period=p, frequency="monthly", measure="index", value=v,
                                     base_period=base))
            if w is not None:
                out.append(C.row(index_name=INDEX_NAME, index_variant="agriculture", industry=ind,
                                 period=periods[-1], frequency="monthly", measure="weight", value=w,
                                 unit="per_mille", base_period=base))
            if rest and rest[0] is not None and idx[-1] and idx[-2]:
                implied = (idx[-1] / idx[-2] - 1) * 100
                if abs(implied - rest[0]) <= 0.15:
                    out.append(C.row(index_name=INDEX_NAME, index_variant="agriculture", industry=ind,
                                     period=periods[-1], frequency="monthly", measure="inflation_mom",
                                     value=rest[0]))
    if len(out) < 30:
        raise ValueError(f"{path}: only {len(out)} values")
    return pd.DataFrame(out)


# A % change carries the base of its index (set from this output; see _base_carry).
from ._base_carry import carry_base  # noqa: E402
parse = carry_base(parse)
