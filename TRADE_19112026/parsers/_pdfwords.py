"""Word-position helpers for PDF tables whose ruling lines split one visual
table into several pdfplumber tables with different column grids (INS
Cameroun's annexes). A table is read from the page's WORDS instead:

  lines(page)          words grouped into visual lines (top within 3 pt)
  numbers(line_words)  numeric tokens re-joined across a thousands-separator
                       space ("8" "205" 2 pt apart -> "8 205"), each with its
                       x-centre; a column gap (>= ~6 pt) separates numbers
  nearest(x, centres)  index of the column whose centre is nearest x (within tol)

Nothing here converts or rescales a value: a token is returned as printed and
parsed by `_common.to_number`.
"""
from __future__ import annotations

import re

from ._common import to_number

_NUM = re.compile(r"^-?\d[\d  ]*(,\d+)?%?$")
_GROUP = re.compile(r"^\d{3}(,\d+)?%?$")


def lines(page, tol: float = 3.0, **kw):
    words = page.extract_words(x_tolerance=1.5, keep_blank_chars=False, use_text_flow=False, **kw)
    words.sort(key=lambda w: (round(w["top"]), w["x0"]))
    out: list[list[dict]] = []
    for w in words:
        if out and abs(out[-1][0]["top"] - w["top"]) <= tol:
            out[-1].append(w)
        else:
            out.append([w])
    for ln in out:
        ln.sort(key=lambda w: w["x0"])
    return out


def numbers(ws, max_gap: float = 3.6):
    """[(text, x0, x1)] numeric tokens of one line, thousands groups re-joined."""
    toks = []
    for w in ws:
        t = w["text"]
        if not _NUM.match(t):
            continue
        if (toks and _GROUP.match(t) and not toks[-1][0].endswith("%")
                and "," not in toks[-1][0] and w["x0"] - toks[-1][2] <= max_gap):
            toks[-1] = (toks[-1][0] + " " + t, toks[-1][1], w["x1"])
        else:
            toks.append((t, w["x0"], w["x1"]))
    return toks


def value(tok: str, decimal: str = ","):
    if tok.endswith("%"):
        return None
    return to_number(tok, decimal=decimal)


def nearest(x: float, centres: list[float], tol: float = 18.0):
    if not centres:
        return None
    i = min(range(len(centres)), key=lambda k: abs(centres[k] - x))
    return i if abs(centres[i] - x) <= tol else None


def text(ws) -> str:
    return " ".join(w["text"] for w in ws)
