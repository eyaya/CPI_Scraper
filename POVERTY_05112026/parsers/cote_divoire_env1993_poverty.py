"""Côte d'Ivoire -- INS "Profil de pauvreté" from ENV 1993 and ENV 1995
(ENV1993-1995.pdf; Wayback `id_` copy of ins.ci/ENV/).

The ORIGINAL 1993 and 1995 estimates (national P0 0,313 and 0,339), as
against the re-estimates the ENV 2002 / 2008 reports republish (32,3 and
36,8, already collected as "ENV 1993 (série ENV 2002)" ...). P0, P1, P2 are
printed as FRACTIONS ("0,313"), so they carry unit "index", kept as printed;
contributions are printed as percentages (100,000) and carry unit percent.
Persons (the tables count "EFFECTIF INDIVIDUS"). Overall line 75 000 FCFA of
1985 carried forward: 101 340 (1993), 144 800 (1995); extreme line ("les 10%
les plus pauvres") 64 465 (1993), 94 600 (1995). Box-drawn tables: every
cell is delimited by "│", and a label longer than its cell wraps onto the
row above with empty number cells.

    2.1.1  P0 by stratum, 1985 -- only 1985 is read (1993 is 2.2's, 1995 the
           2.5.1.2 totals', both with more measures).
    2.1.3  P0 (PERCENT) by stratum 1985-1995 -- only 1986, 1987 and 1988 are
           read, the years no other table has.
    2.2    1993: P0, P1, contribution by stratum; 1995: the contribution only.
    2.1.2  extreme, 1993: P0, P1, contribution by stratum.
    2.4.1a / 2.4.2a  overall / extreme by socio-economic group, 1993 only
           (their ENSEMBLE rows repeat 2.2 / 2.1.2 and are skipped).
    2.4.1b / 2.4.2b  the same for 1995: P0, P1, P2 with contributions.
    2.5.1.1  1993 by stratum x sex of head: overall P0, contribution, P1;
             extreme P0, contribution. Contributions are WITHIN the stratum.
    2.5.1.2 / 2.5.1.3  1995 by stratum x sex of head, overall / extreme: P0,
             P1, P2 with their (within-stratum) contributions; the TOTAL rows
             give the stratum and national P0 / P1 / P2.
NOT COLLECTED: 2.1.0 (extreme P0 1995 against a 92 340 FCFA line that no
other table or the text uses -- its values differ from 2.1.2's at 94 600);
2.1.2's 1995 contribution column (sums to 100 but matches neither the P0 nor
the P1 shares the stratum rates imply); the P1/P0 ratios ("étendue"); sample
and weighted counts; Tableau 3 (by nationality of the head: no topic in the
schema); Tableau 4 (housing). One cell of 2.5.1.1 prints "3.O1O" (letters O)
and is dropped.

CROSS-CHECK (verbatim): 1993 P0 0,313 / P1 0,087; 1995 0,3391 / 0,0837 /
0,0315; extreme 1995 0,0993; Forêt Ouest 1995 0,4714; 1986 national 6,9;
female heads 1995 0,2674; vivriers 1995 0,542.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

LINE = "Seuil de pauvreté relatif (75 000 FCFA de 1985, actualisé)"
LINE_EXT = "Seuil d'extrême pauvreté (ENV)"
_LV = {("overall", "1985"): 75000, ("overall", "1993"): 101340, ("overall", "1995"): 144800,
       ("extreme", "1993"): 64465, ("extreme", "1995"): 94600}
_SURVEY = {"1993": "ENV 1993", "1995": "ENV 1995"}

_STRATA = {"ABIDJAN": "Abidjan", "AUTRES VILLES": "Urbain hors Abidjan",
           "FORET RURALE EST": "Forêt rurale Est", "FORET EST": "Forêt rurale Est",
           "FORET RURALE OUEST": "Forêt rurale Ouest", "FORET OUEST": "Forêt rurale Ouest",
           "SAVANE RURALE": "Savane rurale", "SAVANE": "Savane rurale",
           "Abidjan": "Abidjan", "Autres villes": "Urbain hors Abidjan", "Forêt Est": "Forêt rurale Est",
           "Forêt Ouest": "Forêt rurale Ouest", "Savane": "Savane rurale"}
_NATIONAL = {"ENSEMBLE", "ENSEMBLE C.I.", "Côte d'Ivoire", "Ensemble C.I."}
_GSE = {"AGRICULTEUR D'EXPORTATION": "Agriculteur d'exportation",
        "AGRICULTEUR DE VIVRIERS": "Agriculteur de vivriers",
        "EMPLOYE AGRICOLE": "Employé agricole",
        "EMPLOYE DU SECTEUR PUBLIC": "Employé du secteur public",
        "EMPLOYE DU SECTEUR PRIVE MODERNE": "Employé du secteur privé moderne",
        "TRAVAILLEUR DU SECTEUR INFORMEL": "Travailleur du secteur informel",
        "EMPLOYE DU SECTEUR INFORMEL": "Employé du secteur informel",
        "INDEPENDANT DU SECTEUR INFORMEL": "Indépendant du secteur informel",
        "CHOMEUR": "Chômeur", "INACTIF": "Inactif"}
_SEX = {"HOMME": "male", "FEMME": "female"}


def _num(cell: str):
    s = cell.strip()
    if not re.fullmatch(r"\d+(?:[.,]\d+)?", s):
        return None   # "." (no case), "3.O1O" (letters in the text layer)
    return float(s.replace(",", "."))


def _section(text: str, start: str, end: str | None) -> str:
    i = text.index(start)
    j = text.index(end, i + len(start)) if end else len(text)
    return text[i:j]


def _rows(block: str):
    """Data rows of a box table as (label, cells): the wrapped label lines
    above a row (all number cells empty) are joined onto it."""
    pending = []
    for ln in block.split("\n"):
        if not ln.startswith("│"):
            continue
        cells = [c.strip() for c in ln.strip().strip("│┤").split("│")]
        nums = cells[1:]
        if not any(nums):
            if cells[0]:
                pending.append(cells[0])
            continue
        label = " ".join(pending + ([cells[0]] if cells[0] else []))
        pending = []
        yield re.sub(r"\s+", " ", label).strip(), cells


def _base(period: str, level: str, survey: str | None = None, **kw) -> dict:
    lv = _LV.get((level, period), "")
    return dict(survey=survey or _SURVEY[period], welfare_aggregate="consumption",
                line_type="national", line_level=level, line_name=LINE if level == "overall" else LINE_EXT,
                line_value=lv, line_unit="XOF per person per year" if lv != "" else "",
                period=period, reference_period=period, frequency="ad_hoc", **kw)


def _stratum(label: str) -> dict:
    if label in _NATIONAL:
        return {}
    lab = _STRATA[label]
    return dict(topic="locality", characteristic=lab, locality="other", locality_label=lab)


def _put(out, metric, value, base, attrs):
    if value is None:
        return
    unit = "percent" if metric in ("poor_share", "gap_contribution", "severity_contribution") else "index"
    out.append(C.row(metric=metric, value=value, unit=unit, **base, **attrs))


def parse(path: str) -> pd.DataFrame:
    with pdfplumber.open(path) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    out: list[dict] = []

    # 2.1.1 -- 1985 only: cells [effectif, P0] x 1985 / 1993 / 1995.
    for label, c in _rows(_section(text, "TABLEAU 2.1.1:", "Par rapport aux")):
        if label in _STRATA or label in _NATIONAL:
            _put(out, "headcount", _num(c[2]), _base("1985", "overall", "ENV 1985 (série ENV 1993-95)"),
                 _stratum(label))

    # 2.1.3 -- percent, 1986-1988 only.
    blk = _section(text, "Tableau 2.1.3 : Incidence", "Note : Il n'y a pas")
    n13 = 0
    for ln in blk.split("\n"):
        m = re.match(r"^(Abidjan|Autres villes|Forêt Est|Forêt Ouest|Savane|Côte d'Ivoire)\s+(.*)$", ln.strip())
        if not m:
            continue
        vals = m.group(2).split()
        if len(vals) != 6:
            raise ValueError(f"2.1.3 {ln!r}")
        for yr, v in zip(["1986", "1987", "1988"], vals[1:4]):
            out.append(C.row(metric="headcount", value=C.to_number(v, ","), unit="percent",
                             **_base(yr, "overall", f"ENV {yr} (série ENV 1993-95)"), **_stratum(m.group(1))))
        n13 += 1
    if n13 != 6:
        raise ValueError(f"2.1.3: {n13} rows")

    # 2.2 (overall) and 2.1.2 (extreme): [eff93, P0 93, P1 93, P1/P0, contrib 93,
    # eff95, P0 95, P1 95, contrib 95, P1/P0].
    for cap, end, level in (("TABLEAU 2.2:", "2.3. L'étendue", "overall"),
                            ("TABLEAU 2.1.2:", "2.1.3. Incidence", "extreme")):
        for label, c in _rows(_section(text, cap, end)):
            if not (label in _STRATA or label in _NATIONAL):
                continue
            a = _stratum(label)
            b = _base("1993", level)
            _put(out, "headcount", _num(c[2]), b, a)
            _put(out, "gap", _num(c[3]), b, a)
            _put(out, "poor_share", _num(c[5]), b, a)
            if level == "overall":
                _put(out, "poor_share", _num(c[9]), _base("1995", level), a)

    # 2.4.1a / 2.4.2a -- 1993 by GSE: [eff, eff pauvres, P0, contrib, P1, P1/P0, ...]
    # 2.4.1b / 2.4.2b -- 1995: [eff, eff pauvres, P0, c, P1, c, P2, c, P1/P0]
    for cap, end, level, yr in (("TABLEAU 2.4.1a:", "TABLEAU 2.4.1b:", "overall", "1993"),
                                ("TABLEAU 2.4.1b:", "TABLEAU 2.4.2a:", "overall", "1995"),
                                ("TABLEAU 2.4.2a:", "TABLEAU 2.4.2b:", "extreme", "1993"),
                                ("TABLEAU 2.4.2b:", "2.5. Distribution", "extreme", "1995")):
        seen = 0
        for label, c in _rows(_section(text, cap, end)):
            # The ENSEMBLE rows repeat 2.2 / 2.1.2 (1993) and the 2.5.1.x
            # totals (1995, there with four decimals): not read twice.
            if label in _GSE:
                a = dict(topic="employment_of_head", characteristic=_GSE[label])
            else:
                continue
            seen += 1
            b = _base(yr, level)
            if yr == "1993":
                for metric, k in (("headcount", 3), ("poor_share", 4), ("gap", 5)):
                    _put(out, metric, _num(c[k]), b, a)
            else:
                for metric, k in (("headcount", 3), ("poor_share", 4), ("gap", 5), ("gap_contribution", 6),
                                  ("severity", 7), ("severity_contribution", 8)):
                    _put(out, metric, _num(c[k]), b, a)
        if seen < 8:
            raise ValueError(f"{cap}: {seen} rows")

    # 2.5.1.1 -- 1993 x sex: [stratum, sex, eff, P0, c, P1, P1/P0, P0x, cx, P1/P0x]
    stratum = None
    for ln in _section(text, "TABLEAU 2.5.1.1:", "En 1995, le constat").split("\n"):
        if not ln.startswith("│"):
            continue
        cells = [x.strip() for x in ln.strip().strip("│").split("│")]
        if cells[0]:
            stratum = cells[0]
        if cells[1] not in _SEX:
            continue
        sx = _SEX[cells[1]]
        a = dict(_stratum(stratum), topic="sex_of_head", sex=sx,
                 characteristic={"male": "Homme", "female": "Femme"}[sx])
        a.setdefault("locality", "all")
        _put(out, "headcount", _num(cells[3]), _base("1993", "overall"), a)
        _put(out, "poor_share", _num(cells[4]), _base("1993", "overall"), a)
        _put(out, "gap", _num(cells[5]), _base("1993", "overall"), a)
        _put(out, "headcount", _num(cells[7]), _base("1993", "extreme"), a)
        _put(out, "poor_share", _num(cells[8]), _base("1993", "extreme"), a)

    # 2.5.1.2 / 2.5.1.3 -- 1995 x sex, sub-tables a..f / a'..f':
    # [sex, eff enq, eff pond, eff pauvres, P0, c, P1, c, P2, c, P1/P0]
    _SUB = {"Abidjan": "Abidjan", "Autres villes": "Autres villes", "Forêt Est": "Forêt Est",
            "Forêt Ouest": "Forêt Ouest", "Savane": "Savane", "Ensemble C.I.": "Ensemble C.I."}
    for cap, end, level in (("TABLEAU 2.5.1.2: INDICES DE PAUVRETE DE CI-1995 PAR SEXE DU CHEF DE\nMENAGE",
                             "TABLEAU 2.5.1.3:", "overall"),
                            ("TABLEAU 2.5.1.3:", "3. PAUVRETE ET NATIONALITE", "extreme")):
        sub, n = None, 0
        for ln in _section(text, cap, end).split("\n"):
            m = re.match(r"^[a-f]'? ?- ?(.+?)\s*$", ln)
            if m and m.group(1) in _SUB:
                sub = m.group(1)
                continue
            if not ln.startswith("│"):
                continue
            cells = [x.strip() for x in ln.strip().strip("│┤").split("│")]
            if cells[0] not in ("HOMME", "FEMME", "TOTAL"):
                continue
            geo = _stratum("Côte d'Ivoire" if sub == "Ensemble C.I." else sub)
            b = _base("1995", level)
            if cells[0] == "TOTAL":
                for metric, k in (("headcount", 4), ("gap", 6), ("severity", 8)):
                    _put(out, metric, _num(cells[k]), b, geo)
            else:
                sx = _SEX[cells[0]]
                a = dict(geo, topic="sex_of_head", sex=sx, characteristic={"male": "Homme", "female": "Femme"}[sx])
                for metric, k in (("headcount", 4), ("poor_share", 5), ("gap", 6), ("gap_contribution", 7),
                                  ("severity", 8), ("severity_contribution", 9)):
                    _put(out, metric, _num(cells[k]), b, a)
            n += 1
        if n != 18:
            raise ValueError(f"{cap[:16]}: {n} rows")
    return pd.DataFrame(out)


LAYOUT = {"survey": "ENV 1995", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
          "line_type": "national", "line_level": "overall", "line_name": LINE,
          "period": "1995", "frequency": "ad_hoc", "decimal": ",", "tables": []}
