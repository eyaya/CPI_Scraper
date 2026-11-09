"""Mali -- INSTAT's ANNUAL EMOP poverty series ("Résultats annuels de
l'EMOP-<year>", files ranuel<yy>_eq.pdf on instat-mali.org).

The Enquête Modulaire et Permanente auprès des Ménages is INSTAT's own yearly
consumption survey; each annual report carries a poverty chapter. One parser
serves every year: the report's OWN year is read from its tables' "Source :
EMOP-<year>" lines (the most frequent year) -- never from the URL.

Per report (own year only, survey "EMOP <year>"):
  * "Indices de pauvreté par région": P0/P1/P2 for each region and the
    nation. From 2022 the table also prints the 95% CI of P0 (and a CV, not
    taken). Regions change with the 2023 reform (Taoudenni, Ménaka, Nioro,
    Kita, Dioïla, Nara, Bougouni, Koutiala, San, Douentza, Bandiagara are
    added). Kidal* and Douentza* carry INSTAT's own caution (city only / CV
    > 15%), kept in the notes, not dropped.
  * "Indices de pauvreté selon le sexe du chef du ménage".
  * Tableau 8.7 (where printed): education of the head, household size,
    milieu (Bamako / Autres villes / Rural).
Each block is bounded by start/end: region names also open the "effort
d'investissement" table on the same page, whose "25 907 497 540 6,5 33 163"
reads as three numbers.

From the NEWEST report only (`trend=True`): Tableau 2.1 (national P0 and its
CI for every round EMEP 2001 .. EMOP 2024, each with that round's line) and
Tableau 3.2 (P0 for Bamako / Autres villes / Rural). These are the series AS
REPUBLISHED in that report -- revised against the rounds' own reports (2011:
45,4 in EMOP 2011's report, 45,6 here; the 2001 line 144 000 there, 136 000
here) -- so they carry survey "<round> (série républiée, EMOP <year>)". A CI
that does not bracket its estimate (EMOP 2019: 42,0 in [55,5; 60,5]) is a
published error and is not taken. The "sans les régions du Nord" column is a
subset and is not taken.

UNIT: "les principaux résultats relatifs aux indices de pauvreté se réfèrent
aux individus" -> person. Line in FCFA per person per year.
"""
from __future__ import annotations
import collections
import re

import pandas as pd

from . import _common as C
from . import poverty_tables as T
from ._vocab import label_rows

_REGIONS = ["Kayes", "Koulikoro", "Sikasso", "Ségou", "Mopti", "Tombouctou", "Gao", "Kidal",
            "Taoudenni", "Ménaka", "Nioro", "Kita", "Dioïla", "Nara", "Bougouni", "Koutiala",
            "San", "Douentza", "Bandiagara", "Bamako"]
_P = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"}]
_P_CI = [{"metric": "headcount"}, {"metric": "headcount_ci_low"}, {"metric": "headcount_ci_high"},
         {"skip": True}, {"metric": "gap"}, {"metric": "severity"}]

LAYOUT = {
    "survey": "EMOP (année du rapport)", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "frequency": "annual", "decimal": ",",
    "line_type": "national", "line_level": "overall",
    "line_name": "Seuil de pauvreté (EMOP)", "line_unit": "XOF per person per year",
    "period_patterns": [r"Source\s*:\s*EMOP[- ]?(20\d\d)"],
    "tables": [],
}


def _year(pages: list[str]) -> str:
    c = collections.Counter(y for t in pages for y in re.findall(r"Source\s*:\s*EMOP[- ]?(20\d\d)", t))
    if not c:
        raise ValueError("no 'Source : EMOP-<year>' line: cannot date this annual report")
    return c.most_common(1)[0][0]


def _region_rows(cols):
    # A name may carry INSTAT's caution star ("Kidal*") or a footnote number
    # glued to it ("Kidal12", EMOP 2022).
    rows = [{"match": rf"^{re.escape(r)}(?:\*|\d{{1,2}}(?=\s))?(?=\s+[\d,])", "geography": r,
             "columns": cols}
            for r in _REGIONS]
    rows.append({"match": r"^(?:Ensemble|Mali)(?=\s+[\d,])", "columns": cols})
    return rows


def _tables(year: str) -> list[dict]:
    sv = {"survey": f"EMOP {year}"}
    # Each spec reads ONE table's own text (see _virtual), so no page
    # selection is needed; `_caption` names which table.
    return [
        # 3 numbers (P0 P1 P2) or 6 (P0, CI low, CI high, CV, P1, P2); exact
        # counts keep each row on the right variant.
        {"_caption": "region", "exact_numbers": True, "defaults": sv, "columns": _P,
         "rows": _region_rows(_P)},
        {"_caption": "region", "exact_numbers": True, "defaults": sv, "columns": _P_CI,
         "rows": _region_rows(_P_CI)},
        {"_caption": "sex", "end": r"^(?:Ensemble|Mali)\b",
         "exact_numbers": True, "defaults": sv, "columns": _P,
         "rows": [{"match": r"^Masculin(?=\s)", "topic": "sex_of_head", "characteristic": "Masculin", "sex": "male"},
                  {"match": r"^Féminin(?=\s)", "topic": "sex_of_head", "characteristic": "Féminin", "sex": "female"}]},
        {"_caption": "t87", "start": r"^Niveau d.instruction du chef",
         "end": r"^Taille du m.nage", "exact_numbers": True, "defaults": sv, "columns": _P,
         "rows": label_rows("education_of_head", ["Sans instruction", "Aucun", "Primaire", "Secondaire",
                                                  "Supérieur"])},
        {"_caption": "t87", "start": r"^Taille du m.nage",
         "end": r"^Milieu", "exact_numbers": True, "defaults": sv, "columns": _P,
         "rows": [{"match": r"^" + re.escape(l).replace("–", "[–-]") + r"(?=\s+[\d,])",
                   "topic": "household_size", "characteristic": l}
                  for l in ["1 – 3 personnes", "4 – 7 personnes", "8 – 10 personnes",
                            "11 – 15 personnes", "Plus de 15 personnes"]]},
        {"_caption": "t87", "start": r"^Milieu\s*$",
         "end": r"^(?:Ensemble|Mali)\b", "exact_numbers": True, "defaults": sv, "columns": _P,
         "rows": [{"match": r"^Bamako(?=\s)", "topic": "locality", "locality": "other", "locality_label": "Bamako"},
                  {"match": r"^Autres villes(?=\s)", "topic": "locality", "locality": "other",
                   "locality_label": "Autres villes"},
                  {"match": r"^Rural(?=\s)", "topic": "locality", "locality": "rural", "locality_label": "Rural"}]},
    ]


_TREND_ROW = re.compile(r"^(EMEP|ELIM|EMOP)\s+(20\d\d)(?:-(\d\d))?\s+(.*)$")


def _trend(pages: list[str], year: str, lines_by_year: dict) -> list[dict]:
    """Tableau 2.1 and 3.2 of the newest report: the republished series."""
    rows: list[dict] = []
    tag = f" (série républiée, EMOP {year})"
    names: dict[str, str] = {}
    page = next((t for t in pages if re.search(r"Evolution des seuils et incidences de pauvret", t)
                 and "...." not in t and re.search(r"^(?:EMEP|ELIM|EMOP)\s+20\d\d", t, re.M)), None)
    if page:
        for ln in page.splitlines():
            m = _TREND_ROW.match(ln.strip())
            if not m:
                continue
            per = m.group(2)
            nm = f"{m.group(1)} {per}" + (f"-{m.group(3)}" if m.group(3) else "")
            if m.group(1) == "ELIM" and m.group(3):
                nm = "MICS/ELIM " + nm[5:]
            names[per] = nm
            nums = C.numbers_in(m.group(4), decimal=",")
            if per == year or len(nums) != 5:
                continue
            line, p0, lo, hi, _north = nums
            lines_by_year[per] = line
            base = dict(survey=nm + tag, period=per, reference_period=nm.split(" ", 1)[1],
                        line_value=line)
            rows.append(base | {"metric": "headcount", "value": p0})
            if lo <= p0 <= hi:
                rows += [base | {"metric": "headcount_ci_low", "value": lo},
                         base | {"metric": "headcount_ci_high", "value": hi}]
    page = next((t for t in pages if re.search(r"Evolution de l.incidence de la pauvret. selon le milieu", t)
                 and "...." not in t), None)
    if page:
        on = False
        for ln in page.splitlines():
            s = ln.strip()
            if re.match(r"^Enqu.te\s+Bamako", s):
                on = True
                continue
            if on and s.startswith("Source"):
                break
            m = re.match(r"^(20\d\d)\s+(.*)$", s) if on else None
            if not m or m.group(1) == year or m.group(1) not in names:
                continue
            nums = C.numbers_in(m.group(2), decimal=",")
            if len(nums) != 4:
                continue
            nm = names[m.group(1)]
            for (loc, lab), v in zip((("other", "Bamako"), ("other", "Autres villes"), ("rural", "Rural")), nums[:3]):
                rows.append(dict(survey=nm + tag, period=m.group(1), reference_period=nm.split(" ", 1)[1],
                                 line_value=lines_by_year.get(m.group(1), ""), metric="headcount", value=v,
                                 topic="locality", locality=loc, locality_label=lab,
                                 characteristic=lab))
    out = []
    for r in rows:
        out.append(C.row(
            metric=r["metric"], value=r["value"], survey=r["survey"], welfare_aggregate="consumption",
            line_type="national", line_level="overall", line_name=LAYOUT["line_name"],
            line_value=r["line_value"], line_unit=LAYOUT["line_unit"], period=r["period"],
            reference_period=r["reference_period"], frequency="annual",
            topic=r.get("topic", "total"), characteristic=r.get("characteristic", "Total"),
            locality=r.get("locality", "all"), locality_label=r.get("locality_label", "Total")))
    return out


_CAPTIONS = {
    "region": r"Indices de pauvret. par r.gion",
    "sex": r"Indices de pauvret. selon le sexe du chef",
    "t87": r"Indicateurs de pauvret. selon le sexe du CM",
}


def _virtual(pages: list[str], caption: str) -> list[str]:
    """One table's own text, from its caption down to its "Source" line.

    The annual reports run a table over a page break with no repeated caption
    (EMOP 2014's and 2021's regions continue overleaf) and put other tables on
    the same page whose block headings repeat ("Taille du ménage" in Tableau
    8.6 above 8.7, EMOP 2015). Reading from the caption down -- onto the next
    page when no Source line closes it -- reads exactly one table."""
    for i, t in enumerate(pages):
        if "...." in t:
            continue
        m = re.search(caption, t)
        if not m:
            continue
        body = t[m.start():]
        if not re.search(r"^Source", body, re.M) and i + 1 < len(pages):
            body += "\n" + pages[i + 1]
        k = re.search(r"^Source", body, re.M)
        return [body[:k.start()] if k else body]
    return []


def parse(path: str, trend: bool = False) -> pd.DataFrame:
    pages = T._pages(path, halves=False)
    year = _year(pages["full"])
    cfg = dict(LAYOUT, period=year, reference_period=year, survey=f"EMOP {year}")
    rows: list[dict] = []
    for tbl in _tables(year):
        cap = _CAPTIONS[tbl.pop("_caption")]
        got, _ = T._parse_table({"full": _virtual(pages["full"], cap)}, cfg, tbl, year, year)
        rows.extend(got)
    if not rows:
        raise ValueError(f"{path}: no EMOP poverty table matched")
    df = pd.DataFrame.from_records(rows)
    # A NEGATIVE INDEX IS A BROKEN ROW, not a value: EMOP 2022's Tableau 8.7
    # prints "Supérieur 14,7 -1,0 1,7". The whole row (P0 included) is dropped,
    # since a cell that cannot be right says the row was mis-set.
    grp = ["topic", "characteristic", "geography", "locality_label", "period"]
    bad = df.loc[pd.to_numeric(df["value"]) < 0, grp].drop_duplicates()
    if len(bad):
        print(f"[mali_emop] {path}: dropped {len(bad)} row(s) printing a negative index: "
              f"{bad.to_dict('records')}")
        df = df.merge(bad.assign(_bad=1), on=grp, how="left")
        df = df[df["_bad"].isna()].drop(columns="_bad")
    if trend:
        lines: dict = {}
        tr = pd.DataFrame.from_records(_trend(pages["full"], year, lines))
        df = pd.concat([df, tr], ignore_index=True)
    # The own year's line, as printed in its own Tableau 2-1 row/column.
    own = _own_line(pages["full"], year)
    if own:
        df.loc[df["period"] == year, "line_value"] = own
    return df


def _own_line(pages: list[str], year: str):
    for t in pages:
        if not re.search(r"Evolution des seuils (?:et incidences )?de pauvret", t) or "...." in t:
            continue
        m = re.search(rf"^EMOP\s+{year}\s+(\d{{3}}\s?\d{{3}})\s", t, re.M)
        if m:
            return C.to_number(m.group(1), decimal=",")
    return None


def parse_latest(path: str) -> pd.DataFrame:
    """The newest annual report: own-year tables + the republished trend."""
    return parse(path, trend=True)
