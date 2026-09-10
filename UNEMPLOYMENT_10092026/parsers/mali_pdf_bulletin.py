"""INSTAT Mali — Bulletin sur les indicateurs du marché du travail.

THIS PAGE IS AN INFOGRAPHIC, NOT A TABLE, and that is why the config-driven
layout could not read it. Extracted as text, the summary box interleaves labels
and values in an order that means nothing:

    Taux de
    Taux d'emploi Taux de chômage
    participation
    56.9% 2.4%
    58.3%
    Population en age de travailler
    11 851 516
    Main d'oeuvre Hors de la main d'oeuvre
    6 912 026
    4 939 489

Two labels share one line while their values sit on two later lines, and the
participation label is split around its neighbour. Any line-based reader either
finds nothing or pairs the wrong number with the wrong label -- and pairing
"Taux de chômage" with 58.3% would be a silently plausible answer.

So this reads the page GEOMETRICALLY: each caption is located by its words, and
its value is the numeric cluster sitting DIRECTLY BELOW IT in the same x-band.
That is the relationship the designer actually encoded, and it is stable in a
way the text order is not.

FRENCH SPACE THOUSANDS SEPARATORS: "11 851 516" arrives as three words, so
adjacent numeric words on the same baseline are joined before parsing.

THE REFERENCE PERIOD IS NOT THE TITLE YEAR. The cover reads "BULLETIN ... 2024"
but the box beneath says "Résumé du marché du travail pour le Mali 2021-2022",
and the body confirms the fieldwork was the 2022 labour-force survey. The
period is taken from that line, never from the title.

ARITHMETIC CHECK, and it is a real one: labour force = employed + unemployed,
working-age population = labour force + outside the labour force, and the
unemployment rate must equal unemployed / labour force to within rounding. All
three are asserted, so a mis-paired caption cannot ship.

CROSS-CHECK: participation 58.3%; employment rate 56.9%; unemployment 2.4%;
working-age population 11,851,516; labour force 6,912,026; employed 6,748,249;
unemployed 163,777; potential labour force 220,003; outside the labour force
4,939,489.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_SERIES = "ML_EMOP"
_BASE = "15+"
_SURVEY = "Enquête modulaire et permanente auprès des ménages (EMOP)"

# ANCHOR WORDS, not whole captions. Three of the nine captions are SPLIT
# ACROSS BASELINES with unrelated text between the halves --
#
#     Taux de            <- "Taux de participation", first half
#     Taux d'emploi  Taux de chômage
#     participation      <- ...second half, two lines later
#
# -- so matching a caption as a contiguous word sequence finds six of nine and
# silently drops the participation rate, the unemployed count and the potential
# labour force. What IS reliable is that the value sits directly below the
# caption's LAST word and shares its column, so that word is the anchor.
#
# `not_after` disambiguates a word that appears in more than one caption:
# "Chômage" is both the standalone box (163,777 unemployed) and the tail of
# "Taux de chômage" (2.4%). Without the guard the standalone box takes the
# rate's position and both end up wrong or missing.
_CAPTIONS = [
    {"anchor": "participation", "topic": "labour_force_participation_rate",
     "measure": "rate", "definition": "strict",
     "label": "Taux de participation"},
    {"anchor": "d'emploi", "topic": "employment_to_population_ratio",
     "measure": "rate", "definition": "not_applicable",
     "label": "Taux d'emploi"},
    {"anchor": "chômage", "line_has": "taux", "topic": "unemployment_rate",
     "measure": "rate", "definition": "strict", "label": "Taux de chômage"},
    {"anchor": "travailler", "topic": "working_age_population",
     "measure": "count", "definition": "not_applicable",
     "label": "Population en âge de travailler"},
    {"anchor": "potentielle", "topic": "potential_labour_force",
     "measure": "count", "definition": "not_applicable",
     "label": "Main-d'oeuvre potentielle"},
    {"anchor": "d'oeuvre", "line_has": "hors", "topic": "outside_labour_force",
     "measure": "count", "definition": "not_applicable",
     "label": "Hors de la main-d'oeuvre"},
    {"anchor": "d'oeuvre", "line_is": "main d'oeuvre", "topic": "labour_force",
     "measure": "count", "definition": "not_applicable",
     "label": "Main-d'oeuvre"},
    {"anchor": "emploi", "line_has": "en emploi", "topic": "employed",
     "measure": "count", "definition": "not_applicable", "label": "En emploi"},
    {"anchor": "chômage", "line_lacks": "taux", "topic": "unemployed",
     "measure": "count", "definition": "not_applicable", "label": "Chômage"},
]

_NUM = re.compile(r"^\d[\d\s]*(?:[.,]\d+)?%?$")
_Y_TOL = 3.0          # words within this many points share a baseline
_GAP = 12.0           # a wider gap than this ends a number


def _lines(words):
    """Words grouped into baselines, each sorted left to right."""
    out: list[list[dict]] = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if out and abs(w["top"] - out[-1][0]["top"]) <= _Y_TOL:
            out[-1].append(w)
        else:
            out.append([w])
    return [sorted(g, key=lambda w: w["x0"]) for g in out]


def _clusters(lines):
    """Numeric clusters, with their x-span and baseline.

    A French thousands separator is a space, so "11 851 516" arrives as three
    words. Adjacent numeric words closer than `_GAP` are one number.
    """
    out = []
    for g in lines:
        cur: list[dict] = []
        for w in g:
            if _NUM.match(w["text"]) and (
                    not cur or w["x0"] - cur[-1]["x1"] <= _GAP):
                cur.append(w)
                continue
            if cur:
                out.append(cur)
            cur = [w] if _NUM.match(w["text"]) else []
        if cur:
            out.append(cur)
    got = []
    for c in out:
        text = "".join(w["text"] for w in c)
        v = C.to_number(text.replace("%", ""))
        if v is None:
            continue
        got.append({"value": v, "x0": c[0]["x0"], "x1": c[-1]["x1"],
                    "top": c[0]["top"]})
    return got


def _flat(s: str) -> str:
    return C._deaccent(str(s)).lower().replace("\u2019", "'").strip()


_CAPTION_GAP = 20.0     # a wider gap than this starts a DIFFERENT caption


def _anchors(lines, spec) -> list[tuple[float, float, float]]:
    """Each match's (x0, x1, top), spanning that caption and nothing else.

    Two things have to be right here.

    THE VALUE IS CENTRED UNDER THE WHOLE CAPTION, not under its last word:
    "Population en age de travailler" runs x 252-413 and its 11,851,516 sits at
    x 303-362 -- inside the phrase, outside the anchor word "travailler"
    (x 366-413). So the anchor locates the caption and the span is then widened
    across its neighbouring words.

    BUT TWO CAPTIONS CAN SHARE A BASELINE. "Main d'oeuvre" (x 150-227) and
    "Hors de la main d'oeuvre" (x 379-511) print 2.2 points apart vertically,
    which is one line as far as any tolerance is concerned. Widening to the
    whole line therefore spans both captions, and the left one's value --
    6,912,026, the labour force -- gets read as the population OUTSIDE the
    labour force. The words of one caption sit ~3 points apart while the gap
    between captions is over 70, so expansion stops at `_CAPTION_GAP`.

    Guards are then applied to the SPAN's own text rather than the baseline's,
    for the same reason.
    """
    want = _flat(spec["anchor"])
    hits = []
    for g in lines:
        for i, w in enumerate(g):
            if _flat(w["text"]) != want:
                continue
            lo = hi = i
            while (lo > 0 and not _NUM.match(g[lo - 1]["text"])
                   and g[lo]["x0"] - g[lo - 1]["x1"] <= _CAPTION_GAP):
                lo -= 1
            while (hi + 1 < len(g) and not _NUM.match(g[hi + 1]["text"])
                   and g[hi + 1]["x0"] - g[hi]["x1"] <= _CAPTION_GAP):
                hi += 1
            span = g[lo:hi + 1]
            text = _flat(" ".join(x["text"] for x in span))
            if spec.get("line_is") and text != _flat(spec["line_is"]):
                continue
            if spec.get("line_has") and _flat(spec["line_has"]) not in text:
                continue
            if spec.get("line_lacks") and _flat(spec["line_lacks"]) in text:
                continue
            hits.append((min(x["x0"] for x in span),
                         max(x["x1"] for x in span),
                         max(x["top"] for x in span)))
    return hits


def parse(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[1] if len(pdf.pages) > 1 else pdf.pages[0]
        words = page.extract_words()
        text = page.extract_text() or ""
    lines = _lines(words)
    nums = _clusters(lines)

    m = re.search(r"(20\d{2})\s*[-–]\s*(20\d{2})", text)
    if not m:
        raise ValueError(
            f"{path}: no reference period on the summary page. The TITLE year "
            f"is the publication year, not the survey's -- refusing to date "
            f"the series from it.")
    period, reference = m.group(2), f"{m.group(1)}-{m.group(2)}"

    rows, used = [], set()
    for spec in _CAPTIONS:
        best = None
        for x0, x1, top in _anchors(lines, spec):
            for n in nums:
                if id(n) in used or n["top"] <= top:
                    continue
                centre = (n["x0"] + n["x1"]) / 2
                if not (x0 - 8 <= centre <= x1 + 8):
                    continue
                if best is None or n["top"] < best["top"]:
                    best = n
        if best is None:
            continue
        used.add(id(best))
        rows.append({
            "topic": spec["topic"], "definition": spec["definition"],
            "measure": spec["measure"], "value": best["value"],
            "unit": "percent" if spec["measure"] == "rate" else "persons",
            "sex": "total", "age_group": "Total", "education": "Total",
            "geography": "Total country", "locality": "all",
            "locality_label": "Total", "working_age_base": _BASE,
            "period": period, "reference_period": reference,
            "frequency": "ad_hoc", "survey": _SURVEY, "series_code": _SERIES,
            "series_label": spec["label"],
        })

    df = pd.DataFrame(rows)
    if df.empty:
        raise ValueError(f"{path}: the summary box yielded no indicator.")
    got = dict(zip(df["topic"], df["value"]))

    # The identities the box itself must satisfy. A caption paired with the
    # wrong number breaks at least one of them, which is the whole point of
    # checking rather than trusting the geometry.
    def near(a, b, tol):
        return abs(a - b) <= tol

    lf, emp, unemp = (got.get("labour_force"), got.get("employed"),
                      got.get("unemployed"))
    if None not in (lf, emp, unemp) and not near(lf, emp + unemp, 2):
        raise ValueError(
            f"Mali: labour force {lf:,.0f} != employed {emp:,.0f} + unemployed "
            f"{unemp:,.0f} -- a caption has been paired with the wrong value.")
    wap, out_lf = got.get("working_age_population"), got.get("outside_labour_force")
    if None not in (wap, lf, out_lf) and not near(wap, lf + out_lf, 2):
        raise ValueError(
            f"Mali: working-age population {wap:,.0f} != labour force "
            f"{lf:,.0f} + outside {out_lf:,.0f}.")
    rate = got.get("unemployment_rate")
    if None not in (rate, lf, unemp) and not near(rate, unemp / lf * 100, 0.15):
        raise ValueError(
            f"Mali: published unemployment rate {rate} does not match "
            f"{unemp:,.0f}/{lf:,.0f} = {unemp / lf * 100:.2f}.")
    return df
