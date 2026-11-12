"""Chad -- INSEED "Indice de prix de production de l'industrie (IPPI)", quarterly
note, base 2022 = 100, NAEMA rév.1 (extraction, manufacturing, electricity /
water, waste water), 54 enterprises.

"Tableau 1 : Indice des prix de production de l'industrie par branche
d'activités" -- rows: Ensemble, Ensemble hors pétrole, sections and branches;
columns: the quarters (7-10, "T1-24" ...) then two "Variations (%)": on the
previous quarter, on the same quarter a year earlier.

One descriptor reads every retained note; per branch x quarter x measure the
NEWEST note wins (INSEED revises: produits alimentaires T1-24 is 100,4 in
the T3-2025 note, 90,5 from the T4-2025 note on).

WRAPPED LABELS. A two-line label is printed with its numbers on a line of
their own, between the label's two lines ("TRAVAIL DU BOIS ... EN" /
numbers / "BOIS HORS MEUBLES"): a text-only line within 7 pt below a
numbers-only line belongs to that row.

CHANGES are kept per column only where Ensemble's arithmetic proves it (the
T2-2026 note's y/y for Ensemble prints 29,0 where its indices give 30,3: that
column is not taken from that note).
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

INDEX_NAME = "Indice de prix de production de l'industrie (IPPI)"
BASE = "2022=100"
_Q = re.compile(r"^T([1-4])-(\d\d)$")
_NUM = re.compile(r"^-?\d+(?:,\d+)?$")


def _lines(words):
    out = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if out and w["top"] - out[-1][0]["top"] <= 2.5:
            out[-1].append(w)
        else:
            out.append([w])
    return [sorted(l, key=lambda w: w["x0"]) for l in out]


def _qi(lab: str) -> int:
    m = _Q.match(lab)
    return (2000 + int(m.group(2))) * 4 + int(m.group(1)) - 1


def _qp(i: int) -> str:
    return f"{i // 4}-Q{i % 4 + 1}"


def parse_note(path: str):
    with pdfplumber.open(path) as pdf:
        page = next((p for p in pdf.pages if "Tableau 1" in (p.extract_text() or "")
                     and "branche d" in (p.extract_text() or "")), None)
        if page is None:
            return None
        words = page.extract_words()
    lines = _lines(words)
    hi = next(i for i, l in enumerate(lines) if l[0]["text"] == "Libellé")
    labels = [w["text"] for w in lines[hi] if _Q.match(w["text"])]
    body = []
    # The change header ("T2-26/ T1-26 T2-26 / T2-25") sits between "Libellé" and the data.
    start = next(i for i in range(hi + 1, len(lines)) if lines[i][0]["text"] == "Ensemble")
    for l in lines[start:]:
        if l[0]["text"].startswith("Source") or l[0]["text"].startswith("Institut"):
            break
        body.append(l)
    ncol = max(sum(1 for w in l if _NUM.match(w["text"])) for l in body)
    nq = ncol - 2
    quarters = [_qi(x) for x in labels[:nq]]
    if len(quarters) != nq or quarters != list(range(quarters[0], quarters[0] + nq)):
        raise ValueError(f"{path}: quarter labels {labels} for {nq} columns")
    rows, text = [], []
    last_numbers_only_top = None
    for l in body:
        nums = [w for w in l if _NUM.match(w["text"])]
        txt = [w["text"] for w in l if not _NUM.match(w["text"])]
        if not nums:
            if rows and last_numbers_only_top is not None and l[0]["top"] - last_numbers_only_top <= 7:
                rows[-1][0] += " " + " ".join(txt)          # second line of a wrapped label
                last_numbers_only_top = None
            else:
                text += txt
            continue
        if any(len(w["text"]) == 2 and w["text"].isdigit() for w in nums) and not txt and len(nums) != ncol:
            continue                                        # a stray axis line
        if len(nums) != ncol:
            raise ValueError(f"{path}: line {' '.join(w['text'] for w in l)!r} has {len(nums)} numbers, expected {ncol}")
        label = " ".join(text + txt).strip()
        last_numbers_only_top = l[0]["top"] if not txt else None
        rows.append([label, [C.to_number(w["text"], decimal=",") for w in nums]])
        text = []
    rows = [(re.sub(r"\s+", " ", lab).strip(), v) for lab, v in rows]
    ens = dict(rows).get("Ensemble")
    if ens is None:
        raise ValueError(f"{path}: no Ensemble row")
    ref = quarters[-1]
    keep = {}
    for j, (meas, lag) in enumerate((("inflation_qoq", 1), ("inflation_yoy", 4))):
        if ref - lag in quarters:
            implied = (ens[nq - 1] / ens[quarters.index(ref - lag)] - 1) * 100
            if abs(implied - ens[nq + j]) <= 0.15:
                keep[nq + j] = meas
    recs = []
    for lab, vals in rows:
        for j, q in enumerate(quarters):
            if vals[j] is not None:
                recs.append(C.row(index_name=INDEX_NAME, industry=lab, period=_qp(q), frequency="quarterly",
                                  measure="index", value=vals[j], base_period=BASE))
        for j, meas in keep.items():
            if vals[j] is not None:
                recs.append(C.row(index_name=INDEX_NAME, industry=lab, period=_qp(ref), frequency="quarterly",
                                  measure=meas, value=vals[j]))
    return ref, recs


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    best = {}
    for f in [path] + list(extras or []):
        got = parse_note(f)
        if not got:
            continue
        ref, recs = got
        for r in recs:
            key = (r["industry"], r["period"], r["measure"])
            if key not in best or ref > best[key][0]:
                best[key] = (ref, r)
    if not best:
        raise ValueError("no IPPI table read")
    return pd.DataFrame([r for _, r in best.values()])


# A % change carries the base of its index (set from this output; see _base_carry).
from ._base_carry import carry_base  # noqa: E402
parse = carry_base(parse)
