"""INS Congo -- Annuaire statistique du Congo, population chapter, four
editions giving 2007-2018. A SECOND Congo descriptor (congo_annuaire.yaml)
beside congo.yaml (the 2023 RGPH-5 census).

EDITIONS AND THE YEARS EACH SUPPLIES (the newest printing of a year wins):
* 2018 (édition 2020), Chapitre 6 -- 2014-2018. Tableau 6.1 "Estimation de la
  population résidante du Congo par département de 2014 à 2018", Tableau 6.4
  "... par âge de 2014 à 2018". Each year prints "Ens." and "dont F" only --
  MALES ARE NOT PRINTED and are not derived. Projected from the 2007 RGPH
  (intermediate hypothesis); series_type estimate.
* 2014 -- 2010-2013, Tableaux 2.1.1 (departments) and 2.1.3 (five-year age
  bands), "Ens. / H / F". Also 2014 MALES by department (its 2014 total and
  female figures must equal the 2018 edition's, and do). Its 2014 AGE rows are
  not read: they disagree with the 2018 edition's (5-9 ans: 611 299 vs
  577 261) and the newer printing wins.
* 2012 -- 2008-2009, same tables.
* 2010 -- 2007, same tables; source "CNSEE (RGPH-07)", the census year, so
  series_type census (2008-2010 there are "données corrigées").

NOT READ: the commune tables (6.2/6.3, 2.1.2) -- communes share names with
departments (Pointe-Noire, Brazzaville) but print different figures, and the
schema has no geography-level column.

LAYOUT. The 2018 chapter uses a space as thousands separator, values
RIGHT-ALIGNED under their header: each digit group is assigned to the column
whose header ends at or right of it. The 2010-2014 editions print plain
integers, read as a token stream: label, then 3 x years numbers.

PUBLISHED INCONSISTENCIES, kept and pinned (_GAPS; a change means the parse
or the file changed):
* 2018 ed., 6.1, 2014 both sexes: departments sum to 4 665 779 against Total
  Congo 4 666 379 -- because it prints Cuvette 196 330 where the 2014 edition
  prints 196 930 (= its H 96 703 + F 100 226, +1). Filed as the 2018 edition
  prints it, so Cuvette 2014's filed male (2014 ed.) + female (2018 ed.)
  exceeds its total by 599.
* 2018 ed., national female 2014: 6.1 prints 2 360 183 (= its departments),
  6.4 2 367 754. National totals are filed from 6.1; 6.4 gives age bands.
* 2014 ed., Tableau 2.1.3, 2011: M + F misses Ens. for five age bands (5-9
  ans by 1 000, 30-34 by 500, 50-54 by 500, 55-59 by 20, 60-64 by 50), and
  the bands miss the Total (Ens. by 480, H by 1 187, F by 363).
* gaps of 1-2 persons (independent rounding) are tolerated, not listed.
"""
from __future__ import annotations

import re

import fitz
import pandas as pd

_DEPTS = {"Total Congo": "Total country", "Total": "Total country",
          "Kouilou": "Kouilou", "Niari": "Niari", "Lékoumou": "Lekoumou",
          "Lekoumou": "Lekoumou", "Bouenza": "Bouenza", "Pool": "Pool",
          "Plateaux": "Plateaux", "Cuvette": "Cuvette",
          "Cuvette- Ouest": "Cuvette-ouest", "Cuvette-Ouest": "Cuvette-ouest",
          "Cuvette-ouest": "Cuvette-ouest", "Sangha": "Sangha",
          "Likouala": "Likouala", "Brazzaville": "Brazzaville",
          "Pointe- Noire": "Pointe-Noire", "Pointe-Noire": "Pointe-Noire"}

# edition -> {years read from it: what}
_PLAN = {"2018": {"years": ["2014", "2015", "2016", "2017", "2018"]},
         "2014": {"years": ["2010", "2011", "2012", "2013"]},
         "2012": {"years": ["2008", "2009"]},
         "2010": {"years": ["2007"]}}
_EDITION_YEARS = {"2014": ["2010", "2011", "2012", "2013", "2014"],
                  "2012": ["2008", "2009", "2010", "2011", "2012"],
                  "2010": ["2007", "2008", "2009", "2010"]}

# (edition, table, year, row, check) -> published difference. check "sexes":
# M + F - Ens.; "parts": sum of rows - Total, per sex column.
# Differences of 1-2 persons (independent rounding) are not recorded.
_GAPS: dict = {
    ("2018", "6.1", "2014", "Total country", "parts:total"): -600.0,
    # 2014 ed., Tableau 2.1.3, 2011: e.g. 5-9 ans Ens. 518 370, H 258 880 +
    # F 258 490 = 517 370.
    ("2014", "2.1.3", "2011", "5-9", "sexes"): -1000.0,
    ("2014", "2.1.3", "2011", "30-34", "sexes"): -500.0,
    ("2014", "2.1.3", "2011", "50-54", "sexes"): 500.0,
    ("2014", "2.1.3", "2011", "55-59", "sexes"): -20.0,
    ("2014", "2.1.3", "2011", "60-64", "sexes"): -50.0,
    ("2014", "2.1.3", "2011", "Total", "parts:total"): -480.0,
    ("2014", "2.1.3", "2011", "Total", "parts:male"): -1187.0,
    ("2014", "2.1.3", "2011", "Total", "parts:female"): -363.0,
}
_T61_VS_T64 = {("2014", "female"): (2360183.0, 2367754.0)}
# 2014 printed by both editions: (geography, sex) -> (2014 ed., 2018 ed.).
# Cuvette's 600 is the 2018 edition's department-sum gap above: the 2014
# edition's 196 930 = H 96 703 + F 100 226 (+1), so 196 330 is a misprint in
# the newer edition. Filed as the 2018 edition prints it.
_ED2014_VS_ED2018 = {("Cuvette", "total"): (196930.0, 196330.0)}


# --------------------------------------------------------------------- 2018
def _cells_2018(page, number: str) -> list[dict]:
    """Rows of {label, values} of Tableau <number> -- the band from its title
    to its own "Source" line (one page can hold two tables)."""
    years = _PLAN["2018"]["years"]
    W = page.get_text("words")
    top = next(w[1] for i, w in enumerate(W)
               if w[4] == "Tableau" and i + 1 < len(W) and W[i + 1][4] == number)
    bottom = min((w[1] for w in W if w[4].startswith("Source") and w[1] > top), default=1e9)
    W = [w for w in W if top <= w[1] < bottom]
    heads = sorted((w for w in W if w[4] in ("Ens.", "F")), key=lambda w: w[2])
    if len(heads) != 10:
        raise ValueError(f"INS Congo: {len(heads)} column headers on page {page.number + 1}")
    rights = [h[2] for h in heads]                     # right edges, in order
    cols = [(y, s) for y in years for s in ("total", "female")]
    head_y = max(h[3] for h in heads)
    lab_x = rights[0] - 75
    body = [w for w in W if w[3] > head_y + 3]
    labels = [w for w in body if w[0] < lab_x]
    nums = [w for w in body if w[0] >= lab_x and re.fullmatch(r"\d+", w[4])]

    lines: list[list] = []
    for w in sorted(nums, key=lambda w: w[3]):
        if lines and abs(w[3] - lines[-1][0][3]) <= 3:
            lines[-1].append(w)
        else:
            lines.append([w])
    rows: list[dict] = []
    for ln in lines:
        y = sum(w[3] for w in ln) / len(ln)
        groups: dict[int, list] = {}
        for w in ln:
            k = next(i for i, r in enumerate(rights) if w[2] <= r + 1.5)
            groups.setdefault(k, []).append(w)
        vals = {cols[k]: float("".join(t[4] for t in sorted(g)))
                for k, g in groups.items()}
        lab = " ".join(w[4] for w in sorted(
            (w for w in labels if abs(w[3] - y) <= 7.5), key=lambda w: (round(w[3]), w[0])))
        # a row whose cells sit a point apart can come out as two lines
        if rows and rows[-1]["label"] == lab and not set(rows[-1]["values"]) & set(vals):
            rows[-1]["values"].update(vals)
        else:
            rows.append({"label": lab, "values": vals})
    return rows


# ---------------------------------------------------------------- 2010-2014
_ROW = r"(80 ans et plus|\d+-\d+ ans|[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'\-]*(?: [A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'\-]*)*)"


def _cells_old(page, number: str, years: list[str]) -> list[dict]:
    text = " ".join(page.get_text().split())
    m = re.search(rf"Tableau {re.escape(number)} :.*?Source", text)
    if not m:
        raise ValueError(f"INS Congo: Tableau {number} not on page {page.number + 1}")
    block = m.group(0)
    head = re.search(r"(?:Ens\. H F ?){%d}" % len(years), block)
    if not head:
        raise ValueError(f"INS Congo Tableau {number}: header not found")
    body = block[head.end():]
    n = 3 * len(years)
    cols = [(y, s) for y in years for s in ("total", "male", "female")]
    rows = []
    for r in re.finditer(_ROW + r" ((?:\d+ ){%d}\d+)" % (n - 1), body):
        nums = [float(x) for x in r.group(2).split()]
        rows.append({"label": r.group(1), "values": dict(zip(cols, nums))})
    # every label in the body must have been read
    labels = re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'\-]+", body)
    read = " ".join(r["label"] for r in rows)
    lost = [w for w in labels if w not in read and w not in ("Source",)]
    if lost:
        raise ValueError(f"INS Congo Tableau {number}: rows not read: {lost}")
    return rows


# ------------------------------------------------------------------- common
def _age(label: str) -> str:
    s = label.replace(" ", "").replace("ans", "")
    if s in ("TotalCongo", "Total"):
        return "Total"
    if re.fullmatch(r"75(ou\+|et\+|\+|etplus)?", s):
        return "75+"
    if s == "80etplus":
        return "80+"
    if re.fullmatch(r"\d+(-\d+)?", s):
        return s
    raise ValueError(f"INS Congo: age label {label!r}")


def _find(doc, pattern: str):
    for page in doc:
        if re.search(pattern, " ".join(page.get_text().split())):
            return page
    raise ValueError(f"INS Congo: {pattern!r} not found")


def _edition(doc) -> str:
    for page in list(doc)[:60]:
        t = " ".join(page.get_text().split())
        m = re.search(r"ANNUAIRE STATISTIQUE DU CONGO (\d{4})", t, re.I)
        if m and m.group(1) in _PLAN:
            return m.group(1)
    raise ValueError("INS Congo: edition not recognised")


def _gaps(ed, table, rows: dict, total_key: str, sexes) -> dict:
    out = {}
    for geo, v in rows.items():
        for y in {k[0] for k in v}:
            if "male" in sexes:
                d = v[(y, "male")] + v[(y, "female")] - v[(y, "total")]
                if abs(d) > 2:
                    out[(ed, table, y, geo, "sexes")] = d
    for y in {k[0] for v in rows.values() for k in v}:
        for s in sexes:
            d = sum(v[(y, s)] for g, v in rows.items() if g != total_key) - rows[total_key][(y, s)]
            if abs(d) > 2:
                out[(ed, table, y, total_key, f"parts:{s}")] = d
    return out


def parse(local_path: str, extras: list[str] | None = None) -> pd.DataFrame:
    tables: dict[str, dict] = {}
    for path in [local_path] + list(extras or []):
        with fitz.open(path) as doc:
            ed = _edition(doc)
            if ed in tables:
                raise ValueError(f"INS Congo: edition {ed} given twice")
            if ed == "2018":
                d = _cells_2018(_find(doc, r"Tableau 6\.1 : Estimation de la population r.sidante du Congo par d.partement"), "6.1")
                a = _cells_2018(_find(doc, r"Tableau 6\.4 : Evolution de la population r.sidante par .ge"), "6.4")
                sexes, years = ("total", "female"), _PLAN["2018"]["years"]
            else:
                years = _EDITION_YEARS[ed]
                d = _cells_old(_find(doc, r"Tableau 2\.1\.1 : (Estimations|Evolution) des effectifs de la population r.sidante"), "2.1.1", years)
                a = _cells_old(_find(doc, r"Tableau 2\.1\.3 : (Estimations|Evolution) (de la population|des effectifs de la population) r.sidante"), "2.1.3", years)
                sexes = ("total", "male", "female")
        full = {(y, s) for y in years for s in sexes}
        depts, ages = {}, {}
        for r in d:
            geo = _DEPTS.get(r["label"])
            if geo is None or geo in depts or set(r["values"]) != full:
                raise ValueError(f"INS Congo {ed} departments: row {r['label']!r} {sorted(r['values'])[:3]}")
            depts[geo] = r["values"]
        if set(depts) != set(_DEPTS.values()):
            raise ValueError(f"INS Congo {ed} departments: {sorted(depts)}")
        for r in a:
            g = _age(r["label"])
            if g in ages or set(r["values"]) != full:
                raise ValueError(f"INS Congo {ed} ages: row {r['label']!r}")
            ages[g] = r["values"]
        tables[ed] = {"depts": depts, "ages": ages, "sexes": sexes,
                      "dt": "6.1" if ed == "2018" else "2.1.1",
                      "at": "6.4" if ed == "2018" else "2.1.3"}
    if set(tables) != set(_PLAN):
        raise ValueError(f"INS Congo: editions {sorted(tables)}, want {sorted(_PLAN)}")

    # checks over the years filed, every gap pinned
    gaps: dict = {}
    for ed, t in tables.items():
        keep = set(_PLAN[ed]["years"])
        dd = {g: {k: v for k, v in vals.items() if k[0] in keep} for g, vals in t["depts"].items()}
        aa = {g: {k: v for k, v in vals.items() if k[0] in keep} for g, vals in t["ages"].items()}
        gaps.update(_gaps(ed, t["dt"], dd, "Total country", t["sexes"]))
        gaps.update(_gaps(ed, t["at"], aa, "Total", t["sexes"]))
        for k in t["ages"]["Total"]:
            if k[0] in keep and t["ages"]["Total"][k] != t["depts"]["Total country"][k]:
                if not (ed == "2018" and _T61_VS_T64.get(k) == (t["depts"]["Total country"][k], t["ages"]["Total"][k])):
                    raise ValueError(f"INS Congo {ed} {k}: department total "
                                     f"{t['depts']['Total country'][k]} vs age total {t['ages']['Total'][k]}")
    if gaps != _GAPS:
        raise ValueError(f"INS Congo: published gaps changed: {gaps}")
    # 2014 males come from the 2014 edition: its 2014 Ens. and F must be the 2018 edition's
    for geo, v in tables["2014"]["depts"].items():
        for s in ("total", "female"):
            pair = (v[("2014", s)], tables["2018"]["depts"][geo][("2014", s)])
            if pair[0] != pair[1] and _ED2014_VS_ED2018.get((geo, s)) != pair:
                raise ValueError(f"INS Congo 2014 {geo} {s}: 2014 ed. {v[('2014', s)]} "
                                 f"vs 2018 ed. {tables['2018']['depts'][geo][('2014', s)]}")

    out = []

    def rec(sex, age, geo, year, value, code):
        st = "census" if year == "2007" else "estimate"
        out.append({"series_type": st, "sex": sex, "age_group": age,
                    "geography": geo, "period": year, "frequency": "annual",
                    "measure": "count", "value": value, "unit": "persons",
                    "series_code": code})

    for ed, t in tables.items():
        keep = set(_PLAN[ed]["years"])
        for geo, vals in t["depts"].items():
            for (y, s), v in vals.items():
                if y in keep or (ed == "2014" and y == "2014" and s == "male"):
                    rec(s, "Total", geo, y, v, f"CG_ASN{ed}_T{t['dt']}")
        for g, vals in t["ages"].items():
            if g == "Total":
                continue
            for (y, s), v in vals.items():
                if y in keep:
                    rec(s, g, "Total country", y, v, f"CG_ASN{ed}_T{t['at']}")
    return pd.DataFrame(out)
