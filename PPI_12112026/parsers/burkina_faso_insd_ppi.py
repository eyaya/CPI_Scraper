"""Burkina Faso -- INSD, Indice de Prix de Production de l'Industrie (IPPI), base 100 en 2015.

INSD's quarterly "IPI_IPPI Info" notes (insd.bf/sites/default/files/<yyyy-mm>/
IPI_IPPI...pdf) carry the renovated production index (IPI) and, in a second
part, the IPPI. The IPPI table:

  Tableau [1] : Indice de prix de production de l'industrie | dans l'industrie
                par [type de] produits
  Libellé  T<q>-<yy-1>  T<q-1>-<yy>  T<q>-<yy>   Variations (%) (T/T-1) (T/T-4)

i.e. the quarter, the previous quarter, the same quarter a year earlier, and
the % changes on the previous quarter (inflation_qoq) and a year earlier
(inflation_yoy). One row per product group (Ensemble, 3 types d'industrie,
divisions). The full series is the union of every issue (merge-on-write; the
newest issue wins where two print the same quarter). Comma decimals.

The IPI table that precedes it has the same shape and is NOT read: only the
caption naming "prix de production" opens a table.

A label wraps around its numbers ("Industries de production et de distribution
/ 100,0 ... / d'électricité, de gaz et d'eau"): a text line before a number line
opens the label, a lower-case line after it continues it.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

INDEX_NAME = "Indice de Prix de Production de l'Industrie (IPPI)"
_CAPTION = re.compile(r"Tableau\s*\d*\s*:\s*Indice de prix de production", re.I)
_PER = re.compile(r"\bT([1-4])-(\d{2})\b")
# Comma decimals, except the T3-2025 note ("155.2"); one or two decimals ("-1,48").
_NUM = re.compile(r"-?\d+[,.]\d{1,2}")


def parse(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        lines = [l.strip() for pg in pdf.pages for l in (pg.extract_text() or "").splitlines()]
    base_m = re.search(r"IPPI\s+base\s+100\s+en\s+(\d{4})", " ".join(lines))
    # The T3-2025 note (2026-02/IPI_IPPI Info.pdf) omits the methodology box
    # that states the base; it is the same base-2015 series -- its 2024-T3
    # Ensemble (155,2) and every overlapping cell equal the T4-2024 note's.
    base = f"{base_m.group(1)}=100" if base_m else "2015=100"
    out, seen = [], set()
    i = 0
    while i < len(lines):
        if not _CAPTION.search(lines[i]):
            i += 1
            continue
        j = i + 1
        while j < len(lines) and len(_PER.findall(lines[j])) < 3:
            j += 1
        quarters = [f"{2000 + int(y)}-Q{q}" for q, y in _PER.findall(lines[j])][:3]
        cols = [(p, "index") for p in quarters] + [(quarters[-1], "inflation_qoq"), (quarters[-1], "inflation_yoy")]
        rows, pending, k = [], [], j + 1
        while k < len(lines):
            ln = lines[k]
            k += 1
            if ln.startswith("Source") or _CAPTION.search(ln):
                break
            if re.fullmatch(r"\(?T/T-[14]\)?(?:\s+\(?T/T-[14]\)?)?|Variations \(%\)|\d+", ln):
                continue
            toks = ln.split()
            n = len(toks)
            while n > 0 and _NUM.fullmatch(toks[n - 1]):
                n -= 1
            nums = toks[n:]
            text = " ".join(toks[:n])
            if len(nums) == len(cols):
                rows.append([" ".join(pending + ([text] if text else [])), nums])
                pending = []
            elif nums:
                raise ValueError(f"{path}: {len(nums)} cells for {len(cols)} columns: {ln!r}")
            elif rows and not pending and text[:1].islower():
                rows[-1][0] += " " + text
            else:
                pending.append(text)
        for label, nums in rows:
            label = re.sub(r"\s+", " ", label).strip()
            for (p, meas), x in zip(cols, nums):
                v = C.to_number(x, decimal="," if "," in x else ".")
                key = (label, p, meas)
                if v is None or key in seen:
                    continue
                seen.add(key)
                out.append(C.row(index_name=INDEX_NAME, industry=label, period=p, frequency="quarterly",
                                 measure=meas, value=v, base_period=base if meas == "index" else ""))
        i = k
    if not out:
        raise ValueError(f"{path}: no IPPI table found")
    return pd.DataFrame(out)


# A % change carries the base of its index (set from this output; see _base_carry).
from ._base_carry import carry_base  # noqa: E402
parse = carry_base(parse)
