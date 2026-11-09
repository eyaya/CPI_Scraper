"""Tunisia -- monetary poverty (INS), two sources, one output file.

* `tunisia_poverty` -- "Enquête Nationale sur le Budget, la Consommation et
  le Niveau de vie des ménages 2021, Volume A" (in ARABIC), chapter 4:
    Tableau 12  poverty and extreme-poverty rates, urban / rural / national,
                2005 2010 2015 (2019) 2021  -- 2019 is the complementary
                survey, printed for the national poverty rate only
    Tableau 13  the same by the seven large regions, 2005-2021
    Tableau 14  P0, population weight, absolute and relative contribution by
                education of the household head (2021)
    Tableau 15  the same by socio-professional category of the head (2021)
  The Arabic text layer is NOT bidi-scrambled here (unlike INS's quarterly
  employment notes): read left to right, every row runs [extreme 2005..2021
  reversed] -- concretely "12,7 - 10.1 12.6 14.8 1,7 1.2 2.1 3.0" = poverty
  2021, 2019, 2015, 2010, 2005 then extreme 2021, 2015, 2010, 2005 -- and that
  order is CONFIRMED against INS's French web table (/statistiques/102: urban
  2015 10.1, 2010 12.6, 2005 14.8; extreme 1.2 / 2.1 / 3.0) and the prose
  (16,6% in 2021, 15,2% in 2015, 23,1% in 2005). Tableaux 14/15 run
  priority | relative contribution | absolute contribution | population |
  P0, confirmed by the identities abs = P0 x pop / 100 and rel = abs / 16,6.
  The volume mixes decimal commas and points ("10.1", "12,7").
  Category labels are printed only in Arabic; they are given in French with
  the Arabic original in brackets. The priority index (rel / pop) is derived
  and not collected; Gini (Tableaux 16-17) belongs to inequality.

* `tunisia_web_poverty` -- INS "Pauvreté" statistics page
  (www.ins.tn/statistiques/102), two server-rendered tables: poverty and
  extreme poverty by milieu, 2000 2005 2010 2015. Only 2000 is new; 2005-2015
  are identical to Volume A and share its merge keys.

INS's urban/rural is "milieu communal / non communal"; the French labels are
used for both sources so the two land on one key.

CROSS-CHECK (verbatim): P0 2021 16,6 (2019 13,8; 2015 15,2; 2010 20,5; 2005
23,1; 2000 25,4); extreme 2,9 / 2,9 / 6,0 / 7,4 / 7,7; urban 2021 12,7, rural
24,8; Centre Ouest 37,0, Grand Tunis 4,7; no education 23,5; unemployed head
41,3.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

_LINES = {"overall": "Seuil de pauvreté", "extreme": "Seuil de pauvreté extrême"}
_SURVEY = {"2000": "ENBCNV 2000", "2005": "ENBCNV 2005", "2010": "ENBCNV 2010",
           "2015": "ENBCNV 2015", "2019": "Enquête complémentaire 2019",
           "2021": "ENBCNV 2021"}
_REF = {"2021": "2021"}

LAYOUT = {"survey": "ENBCNV 2021", "welfare_aggregate": "consumption",
          "unit_of_analysis": "person", "frequency": "ad_hoc",
          "line_type": "national", "line_level": "overall",
          "line_name": _LINES["overall"], "period": "2021", "tables": []}
LAYOUT_WEB = dict(LAYOUT, survey="ENBCNV 2000-2015", period="2015")

_COMMUNAL = dict(topic="locality", locality="urban", locality_label="Milieu communal",
                 characteristic="Milieu communal")
_NONCOMMUNAL = dict(topic="locality", locality="rural", locality_label="Milieu non communal",
                    characteristic="Milieu non communal")

# Tableau 13 rows, in printed order, with a token of each (glyph-reversed)
# Arabic label as it comes out of the text layer -- the check that the order
# has not moved.
_REGIONS = [("Grand Tunis", "سنوت"), ("Nord Est", "يقرشلا لامشلا"),
            ("Nord Ouest", "يبرغلا لامشلا"), ("Centre Est", "يقرشلا طسولا"),
            ("Centre Ouest", "يبرغلا طسولا"), ("Sud Est", "يقرشلا بونجلا"),
            ("Sud Ouest", "يبرغلا بونجلا"), ("Total country", "عومجلا")]
_EDU = [("Aucun niveau [لا شيء]", None), ("Primaire et base 1er cycle [ابتدائي وأساسي مرحلة أولى]", "ىلوأ"),
        ("Secondaire et base 2e cycle [ثانوي وأساسي مرحلة ثانية]", "ةيناث"),
        ("Supérieur [عالي]", "يلاع"), (None, "ينطولا")]
_CSP = [("Cadres et professions libérales supérieurs [الإطارات والمهن الحرة العليا]", "ايلعلا"),
        ("Cadres et professions libérales moyens [الإطارات والمهن الحرة المتوسطة]", "ةطسوتملا"),
        ("Autres employés [أعوان آخرون]", "نورخآ ناوعأ"),
        ("Patrons de l'industrie, du commerce et des services [الأعراف في الصناعة والتجارة والخدمات]", "فارعلأا"),
        ("Indépendants de l'industrie, du commerce et des services [المستقلون في الصناعة والتجارة والخدمات]", "نولقتسملا"),
        ("Ouvriers non agricoles [العملة غير الفلاحيين]", "نيحلافلا ريغ"),
        ("Exploitants agricoles [الفلاحون]", "نوحلافلا"),
        ("Ouvriers agricoles [العملة الفلاحيين]", "نييحلافلا ةلمعلا"),
        ("Chômeurs [العاطلون عن العمل]", "لمعلا نع"),
        ("Retraités [المتقاعدون]", "نودعاقتملا"),
        ("Autres inactifs [غير نشيطين آخرون]", "نيطيشن ريغ"),
        (None, "ينطولا")]


def _num(tok: str):
    """One cell: '-' is an empty cell; comma and point are both decimal marks
    in this volume (no thousands appear in these tables)."""
    return None if tok in ("-", "–") else float(tok.replace(",", "."))


def _cells(line: str) -> list:
    return [_num(t) for t in re.findall(r"-?\d+(?:[.,]\d+)?|(?<=\s)-(?=\s)", " " + line + " ")]


def _row(metric, value, period, level="overall", **kw):
    return C.row(metric=metric, value=value, survey=_SURVEY[period],
                 welfare_aggregate="consumption", line_type="national", line_level=level,
                 line_name=_LINES[level], period=period,
                 reference_period=period, frequency="ad_hoc", **kw)


def _block(pages, caption, n):
    """The first `n` numeric lines after the line carrying `caption`."""
    for text in pages:
        lines = text.splitlines()
        for i, l in enumerate(lines):
            if caption in l:
                # The year header ("2021 2019 2015 ...") is a numeric line too.
                got = [x for x in lines[i + 1:] if re.match(r"^[-\d]", x.strip()) and len(_cells(x)) >= 4
                       and not all(v is not None and v.is_integer() and 1990 <= v <= 2030 for v in _cells(x))]
                if len(got) >= n:
                    return got[:n], lines[i + 1:]
    raise ValueError(f"table with caption {caption!r} not found")


def parse(path: str) -> pd.DataFrame:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        pages = [(p.crop((0, 0, p.width, p.height)).extract_text() or "") for p in pdf.pages]
    out = []

    # Tableau 12 -- 9 cells: P0 2021 2019 2015 2010 2005 | ext 2021 2015 2010 2005
    t12, _ = _block(pages, "12 لودجلا", 3)
    for line, attrs in zip(t12, (_COMMUNAL, _NONCOMMUNAL, {})):
        c = _cells(line)
        if len(c) != 9:
            raise ValueError(f"Tableau 12 row has {len(c)} cells: {line!r}")
        for v, y in zip(c[:5], ("2021", "2019", "2015", "2010", "2005")):
            if v is not None:
                out.append(_row("headcount", v, y, **attrs))
        for v, y in zip(c[5:], ("2021", "2015", "2010", "2005")):
            out.append(_row("headcount", v, y, "extreme", **attrs))
    if "ينطولا" not in t12[2]:
        raise ValueError(f"Tableau 12's third row is not the national row: {t12[2]!r}")

    # Tableau 13 -- 8 cells: P0 2021 2015 2010 2005 | ext 2021 2015 2010 2005
    t13, _ = _block(pages, "13 لودجلا", 8)
    for line, (geo, token) in zip(t13, _REGIONS):
        if token not in line:
            raise ValueError(f"Tableau 13 row order changed: expected {geo}, got {line!r}")
        c = _cells(line)
        if len(c) != 8:
            raise ValueError(f"Tableau 13 row has {len(c)} cells: {line!r}")
        if geo == "Total country":
            continue                     # repeats Tableau 12's national row
        for v, y in zip(c[:4], ("2021", "2015", "2010", "2005")):
            out.append(_row("headcount", v, y, geography=geo))
        for v, y in zip(c[4:], ("2021", "2015", "2010", "2005")):
            out.append(_row("headcount", v, y, "extreme", geography=geo))

    # Tableaux 14/15 -- priority | relative | absolute | population | P0 (2021)
    for caption, cats, topic in (("14 لودجلا", _EDU, "education_of_head"),
                                 ("15 لودجلا", _CSP, "employment_of_head")):
        rows, after = _block(pages, caption, len(cats))
        for k, (line, (label, token)) in enumerate(zip(rows, cats)):
            # Labels sit on the same line (15) or on the line below (14).
            here = line + " " + (after[after.index(line) + 1] if after.index(line) + 1 < len(after) else "")
            if token and token not in here:
                raise ValueError(f"{caption} row {k} is not {label or 'national'}: {line!r}")
            c = _cells(line)
            if len(c) != 5:
                raise ValueError(f"{caption} row has {len(c)} cells: {line!r}")
            prio, rel, ab, pop, p0 = c
            if abs(ab - p0 * pop / 100) > 0.15:
                raise ValueError(f"{caption} row {k}: absolute contribution {ab} != P0 x pop "
                                 f"({p0} x {pop} / 100) -- column order changed?")
            if label is None:            # the national row repeats Tableau 12
                continue
            kw = dict(topic=topic, characteristic=label)
            out += [_row("headcount", p0, "2021", **kw), _row("population_share", pop, "2021", **kw),
                    _row("absolute_contribution", ab, "2021", **kw), _row("poor_share", rel, "2021", **kw)]
    return pd.DataFrame(out)


def parse_web(path: str) -> pd.DataFrame:
    """INS /statistiques/102: two tables, poverty and extreme poverty, by
    milieu, years across the columns. Page furniture rows have no value."""
    import io
    tables = pd.read_html(io.StringIO(open(path, encoding="utf-8").read()))
    out = []
    for df in tables:
        title = " ".join(str(x) for x in df.iloc[:, 0].astype(str))
        level = "extreme" if "extrême" in title else "overall"
        years = [c for c in df.columns[1:] if re.fullmatch(r"(19|20)\d{2}", str(c))]
        for _, r in df.iterrows():
            lab = str(r.iloc[0]).strip()
            if all(pd.isna(r[y]) for y in years):
                continue
            attrs = (_COMMUNAL if lab == "Milieu communal" else _NONCOMMUNAL
                     if lab == "Milieu non communal" else {} if lab.startswith("Taux de pauvreté") else None)
            if attrs is None:
                raise ValueError(f"unexpected row label {lab!r} on the INS poverty page")
            for y in years:
                if not pd.isna(r[y]):
                    out.append(_row("headcount", float(r[y]), str(y), level, **attrs))
    if len(out) != 24:
        raise ValueError(f"expected 24 values (2 lines x 3 groups x 4 years), got {len(out)}")
    return pd.DataFrame(out)
