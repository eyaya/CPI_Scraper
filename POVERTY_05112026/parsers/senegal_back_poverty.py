"""Senegal -- ANSD (ex-DPS) back-rounds.

parse (ESPS-II 2011) -- "Rapport ESPS-II 2011" (Rapport_ESPS-2011.pdf, ansd.sn).
    The ORIGINAL ESPS-II estimates (national 46,7), as against the EHCVM
    report's re-linked series (42,8) already collected as "ESPS-II 2011
    (raccordé EHCVM)". Lines are stratum-specific (Tableau 4.2: 1 053 / 798 /
    598 FCFA per adult-equivalent per day, Dakar / autre urbain / rural), so
    line_value is blank.
      Tableau 4.3 -- P0 P1 P2 by region for ESPS-I (2005/06) and ESPS-II. The
        header prints "ESPS-II -I | ESPS-II -II"; the first block is ESPS-I:
        its Ensemble is 48,3, the 2005-2006 rate the text gives, and the text
        compares Louga "entre l'ESPS-I et l'ESPS-II". Kaffrine, Kédougou and
        Sédhiou exist only in 2011 (created 2008).
      Tableaux 4.4-4.8 -- P0 P1 P2, contribution and number of poor by
        Dakar / Autres villes / Rural / Ensemble x sex, marital status, age,
        education and sector of the head. Only the Ensemble block's Total
        rows equal the national; the stratum Total rows are the strata.
parse_esam -- "La pauvreté au Sénégal : de la dévaluation de 1994 à 2001-2002"
    (Pauvrete_Senegal_1994_2002.pdf, Wayback `id_` copy of ansd.sn).
      Tableau 3 -- P0 P1 P2 for ESAM I (1994-95) and ESAM II (2001-02), each
        at HOUSEHOLD and at PERSON level, national / Dakar / autre urbain /
        rural. ("25,.3" in the text layer is 25,3.)
      Tableaux 4-9 -- HOUSEHOLD P0, number of poor households and contribution
        by milieu (both rounds), region, sex, age, marital status and
        education of the head (2001-02).

CROSS-CHECK (verbatim): ESPS-II 46,7 / 14,5 / 6,6; ESPS-I 48,3 / 15,4 / 7,0;
Kolda 2011 76,6; female head 2011 34,7; ESAM persons 67,9 (1994) / 57,1
(2001); households 61,4 / 48,5; 515 238 poor households in 2001.
"""
from __future__ import annotations
import re

import pandas as pd

from . import _common as C
from . import poverty_tables as T
from ._vocab import label_rows

_P = [{"metric": "headcount"}, {"metric": "gap"}, {"metric": "severity"}]
_PCN = _P + [{"metric": "poor_share"}, {"metric": "poor_count"}]
_ESPS1 = {"survey": "ESPS-I 2005/06 (rapport ESPS-II)", "period": "2005", "reference_period": "2005/06"}

LAYOUT = {
    "survey": "ESPS-II 2011", "welfare_aggregate": "consumption", "unit_of_analysis": "person",
    "frequency": "ad_hoc", "decimal": ",", "line_type": "national", "line_level": "overall",
    "line_name": "Seuils de pauvreté par strate (ESPS)", "period": "2011", "reference_period": "2011",  # fieldwork Aug - mid-Dec 2011 (report 1.2.3)
    "tables": [],
}
_REG = ["Dakar", "Ziguinchor", "Diourbel", "Saint-Louis", "Tambacounda", "Kaolack", "Thiès", "Louga",
        "Fatick", "Kolda", "Matam"]
_NEW = ["Kaffrine", "Kédougou", "Sédhiou"]
_BLOCKS = [("Dakar", dict(topic="locality", locality="other", locality_label="Dakar")),
           ("Autres? (?:V|v)illes|Autres urbain", dict(topic="locality", locality="other", locality_label="Autres villes")),
           ("Rural", dict(topic="locality", locality="rural", locality_label="Rural")),
           ("Ensemble", {})]


def _table(pages, caption):
    for i, t in enumerate(pages):
        if "...." in t:
            continue
        m = re.search(caption, t)
        if m:
            body = t[m.end():]
            if not re.search(r"^Source", body, re.M) and i + 1 < len(pages):
                body += "\n" + pages[i + 1]
            k = re.search(r"^(?:Source|Tableau ?\d|TABLEAU ?\d)", body, re.M)
            return body[:k.start()] if k else body
    raise ValueError(f"caption not found: {caption}")


def _r(metric, value, base, **kw):
    unit = "households" if metric == "poor_count" and base.get("unit_of_analysis") == "household" else None
    return C.row(metric=metric, value=value, unit=unit, welfare_aggregate="consumption", line_type="national",
                 line_level="overall", frequency="ad_hoc", **{**base, **kw})


def _blocked(text, topic, labels, base, cols=("headcount", "gap", "severity", "poor_share", "poor_count")):
    """Rows of a table stacked in stratum blocks (Dakar / Autres villes /
    Rural / Ensemble), each block opened by its own heading line."""
    out, attrs = [], None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        hit = next((a for pat, a in _BLOCKS if re.fullmatch(pat, s)), None)
        if hit is not None:
            attrs = hit
            i += 1
            continue
        if attrs is None:
            i += 1
            continue
        lab = next((l for l in labels if s.startswith(l[0])), None)
        if lab:
            tail = s[len(lab[0]):]
            if not re.search(r"\d", tail) and i + 1 < len(lines):      # wrapped label
                i += 1
                tail = lines[i].strip()
                tail = tail[len(lab[2]):] if lab[2] and tail.startswith(lab[2]) else tail
            nums = C.numbers_in(tail, decimal=",")
            if len(nums) != len(cols):
                raise ValueError(f"{lab[1]} in {attrs or 'Ensemble'}: {nums}")
            for m, v in zip(cols, nums):
                if m == "poor_share" and not attrs and False:
                    continue
                out.append(_r(m, v, base, topic=topic, characteristic=lab[1], **{k: v2 for k, v2 in attrs.items()
                                                                               if k != "topic"},
                              **({"sex": lab[3]} if len(lab) > 3 else {})))
        i += 1
    return out


def parse(path: str) -> pd.DataFrame:
    pages = T._pages(path, halves=False)["full"]
    base = dict(survey=LAYOUT["survey"], line_name=LAYOUT["line_name"], period="2011",
                reference_period="2011", unit_of_analysis="person")
    rows = []
    t = _table(pages, r"Tableau 4\.3: Mesures de la pauvret. selon la r.gion")
    for ln in t.splitlines():
        s = ln.strip()
        lab = next((r for r in _REG + _NEW + ["Ensemble"] if re.match(re.escape(r) + r"\s", s)), None)
        if not lab:
            continue
        nums = C.numbers_in(s[len(lab):], decimal=",")
        geo = {} if lab == "Ensemble" else {"geography": lab}
        if len(nums) == 6:
            for m, v in zip(("headcount", "gap", "severity"), nums[:3]):
                rows.append(_r(m, v, {**base, **_ESPS1}, **geo))
            vals = nums[3:]
        elif len(nums) == 3 and lab in _NEW:
            vals = nums
        else:
            raise ValueError(f"Tableau 4.3 {lab}: {nums}")
        for m, v in zip(("headcount", "gap", "severity"), vals):
            rows.append(_r(m, v, base, **geo))
    specs = [
        (r"Tableau 4\.4: Mesures de la pauvret. selon le sexe", "sex_of_head",
         [("Masculin", "Masculin", "", "male"), ("Féminin", "Féminin", "", "female")]),
        (r"Tableau 4\.5: Mesures de la pauvret. selon la situation matrimoniale", "marital_status_of_head",
         [(l, l, "") for l in ("Marié monogame", "Marié polygame", "Célibataire", "Veuf", "Divorcé")]),
        (r"Tableau 4\.6: Mesures de la pauvret. selon l.âge", "age_of_head",
         [("< de 35 ans", "Moins de 35 ans", ""), ("35-59 ans", "35-59 ans", ""), ("60 ans et +", "60 ans et +", "")]),
        (r"Tableau 4\.7: Mesures de la pauvret. selon le niveau d.instruction", "education_of_head",
         [(l, l, "") for l in ("Sans instruction", "Primaire", "Secondaire 1", "Secondaire 2", "Supérieur")]),
        (r"Tableau 4\.8: Mesures de la pauvret. selon le secteur d.activit", "employment_of_head",
         [(l, "Secteur d'activité: " + l, "") for l in ("Secteur public", "Salarié privé", "Indépendant agricole",
                                                         "Indépendant non agri.")]
         + [("Autre dépendant (aide", "Secteur d'activité: Autre dépendant", "familial, apprenti…)"),
            ("Autre dépendant", "Secteur d'activité: Autre dépendant", ""),
            ("Sans emploi", "Secteur d'activité: Sans emploi", "")]),
    ]
    for cap, topic, labels in specs:
        rows += _blocked(_table(pages, cap), topic, labels, base)
    df = pd.DataFrame.from_records(rows)
    key = [c for c in df.columns if c != "value"]
    return df.drop_duplicates(key)


def parse_esam(path: str) -> pd.DataFrame:
    pages = [t.replace("25,.3", "25,3") for t in T._pages(path, halves=False)["full"]]
    rows = []
    rounds = {"1994-95": dict(survey="ESAM I 1994/95", period="1994", reference_period="1994-95"),
              "2001-02": dict(survey="ESAM II 2001/02", period="2001", reference_period="2001-02")}
    line = dict(line_name="Seuil de pauvreté (ESAM, méthode harmonisée 1994-2002)")
    t3 = _table(pages, r"TABLEAU 3: MESURES DE LA PAUVRETE")
    cur = None
    places = [({}, "household"), (dict(topic="locality", locality="other", locality_label="Dakar"), "household"),
              (dict(topic="locality", locality="other", locality_label="Autre urbain"), "household"),
              (dict(topic="locality", locality="rural", locality_label="Rural"), "household"),
              ({}, "person"), (dict(topic="locality", locality="other", locality_label="Dakar"), "person"),
              (dict(topic="locality", locality="other", locality_label="Autre urbain"), "person"),
              (dict(topic="locality", locality="rural", locality_label="Rural"), "person")]
    for ln in t3.splitlines():
        s = ln.strip()
        if s in rounds:
            cur = rounds[s]
            continue
        m = re.match(r"^(Incidence de la pauvreté|Ecart de pauvreté|Sévérité de la pauvreté) \(%\) (.*)$", s)
        if m and cur:
            metric = {"I": "headcount", "E": "gap", "S": "severity"}[m.group(1)[0]]
            nums = C.numbers_in(m.group(2), decimal=",")
            if len(nums) != 8:
                raise ValueError(f"ESAM Tableau 3 {s!r}")
            for (attrs, unit), v in zip(places, nums):
                ch = {"characteristic": attrs["locality_label"]} if attrs else {}
                rows.append(_r(metric, v, {**cur, **line, "unit_of_analysis": unit}, **attrs, **ch))
    hh = {**rounds["2001-02"], **line, "unit_of_analysis": "household"}
    # Tableau 4: milieu x (poor households, rate, contribution), 2001 and 1994
    t4 = _table(pages, r"TABLEAU 4 : M.NAGES PAUVRES ET INCIDENCE DE PAUVRETE SELON LE MILIEU")
    for yr, key in (("2001", "2001-02"), ("1994", "1994-95")):
        m = re.search(rf"^{yr} (.*)$", t4, re.M)
        nums = C.numbers_in(m.group(1), decimal=",") if m else []
        if len(nums) != 11:
            raise ValueError(f"ESAM Tableau 4 {yr}: {nums}")
        b = {**rounds[key], **line, "unit_of_analysis": "household"}
        for k, (attrs, _unit) in enumerate(places[1:4]):
            att = {**attrs, "characteristic": attrs["locality_label"]}
            rows += [_r("poor_count", nums[3 * k], b, **att), _r("poor_share", nums[3 * k + 2], b, **att)]
        rows.append(_r("poor_count", nums[9], b))
    specs = [
        (r"TABLEAU 5: M.NAGES PAUVRES ET INCIDENCE DE PAUVRETE SELON LA", None,
         [("Dakar", "Dakar"), ("Ziguinchor", "Ziguinchor"), ("Diourbel", "Diourbel"), ("Saint Louis", "Saint-Louis"),
          ("Tambacounda", "Tambacounda"), ("Kaolack", "Kaolack"), ("Thiès", "Thiès"), ("Louga", "Louga"),
          ("Fatick", "Fatick"), ("Kolda", "Kolda")]),
        (r"TABLEAU 6: M.NAGES PAUVRES ET INCIDENCE DE PAUVRETE SELON LE SEXE", "sex_of_head",
         [("Homme", "Homme"), ("Femme", "Femme")]),
        (r"TABLEAU 7 : M.NAGES PAUVRES ET INCIDENCE DE PAUVRETE SELON L.AGE", "age_of_head",
         [(l, l) for l in ("15 - 24 ans", "25 - 34 ans", "35 - 44 ans", "45 - 54 ans", "55 - 64 ans",
                           "65 ans et plus")]),
        (r"TABLEAU 8: M.NAGES PAUVRES ET INCIDENCE DE PAUVRETE SELON LE STATUT", "marital_status_of_head",
         [(l, l) for l in ("Monogame", "Polygame", "Célibataire", "Veuf/ve", "Divorcé(e)")]),
        (r"TABLEAU 9: M.NAGES PAUVRES ET INCIDENCE DE PAUVRETE SELON LE NIVEAU", "education_of_head",
         [(l, l) for l in ("Aucun", "Primaire", "Secondaire", "Technique et professionnel", "Supérieur général",
                           "Autre")]),
    ]
    for cap, topic, labels in specs:
        t = _table(pages, cap)
        for raw, char in labels:
            m = re.search(rf"^{re.escape(raw)} (\d[\d ]*) (\d+,\d) (\d+,\d)$", t, re.M)
            if not m:
                raise ValueError(f"{cap[:30]} {raw!r} not found")
            cnt, p0, ctr = C.to_number(m.group(1)), C.to_number(m.group(2), ","), C.to_number(m.group(3), ",")
            att = {"geography": char} if topic is None else {"topic": topic, "characteristic": char}
            if topic == "sex_of_head":
                att["sex"] = "male" if char == "Homme" else "female"
            rows += [_r("headcount", p0, hh, **att), _r("poor_count", cnt, hh, **att),
                     _r("poor_share", ctr, hh, **att)]
    df = pd.DataFrame.from_records(rows)
    key = [c for c in df.columns if c != "value"]
    return df.drop_duplicates(key)


LAYOUT_ESAM = dict(LAYOUT, survey="ESAM II 2001/02", period="2001",
                   line_name="Seuil de pauvreté (ESAM, méthode harmonisée 1994-2002)")
