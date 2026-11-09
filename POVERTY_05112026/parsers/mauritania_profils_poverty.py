"""Mauritania -- ONS poverty profiles 2004 and 2008 (time depth for mauritania_*).

Both are ONS's own reports, on ANSADE's media library (admin.ansade.mr,
WordPress media API, plain requests). Their annex tables print, per row,
P0 P1 P2 C0 C1 C2 (C = contribution to the national index) -- six numbers, a
clean shape read here by one row reader per table block.

Profil de pauvreté 2004 (EPCV 2004; line 94 600 UM, extreme 71 550 UM per
person per year, both as printed in this report):
  A.1.1 wilaya, A.1.2 zone (rural fleuve / rural autre / Nouakchott / autres
  villes), A.1.3 milieu, A.1.4 extreme by zone and milieu, A.1.5 extreme by
  wilaya, A.1.6 education of the head, A.1.7 sex of the head, A.1.8 socio-
  economic group of the head; Tableau 12 relative poverty (line = mean
  spending of quintiles 2-3, 86 357 UM); A.2.15 and A.2.16: the EPCV 2000
  columns only -- P0 P1 P2 on both lines by wilaya / milieu, and by socio-
  economic group with C0. A.2.15's 2004 columns are NOT read: its 2004 urban
  and rural cells (13,3 / 37,8) contradict A.1.3 (28,9 / 59,0) -- a published
  defect. Its 2000 extreme national (34,1) differs from the prose (34,8); the
  table value is kept.
Profil de pauvreté 2008 (EPCV 2008; lines 129 600 / 96 400 UM):
  2.1.2 sex of the head at household AND person level; 2.1.10 wilaya; 2.1.11
  characteristics of the head (sex, milieu x sex -- P0 P1 P2 only, their C's
  are shares within the milieu --, education, household type, activity,
  institutional sector, socio-economic group, branch); 2.1.12 extreme by milieu
  and wilaya, households and persons; 2.1.16 / 2.1.17 the 53 moughataas,
  households and persons, overall and extreme; 2.1.8 relative poverty (2/3 of
  mean spending, 148 100 UM). 2.1.16 row 6 is printed "Moughataa" (2.1.17
  names it Timbédra): dropped, not renamed.
"""
from __future__ import annotations

import re

import pandas as pd

from . import _common as C

_BASE = dict(welfare_aggregate="consumption", frequency="ad_hoc", line_type="national")
LAYOUT = {"survey": "EPCV 2004 (Profil de pauvreté 2004)", **_BASE, "unit_of_analysis": "person",
          "line_level": "overall", "line_name": "Seuil de pauvreté (EPCV)", "period": "2004", "tables": []}
LAYOUT_2008 = {**LAYOUT, "survey": "EPCV 2008 (Profil de pauvreté 2008)", "period": "2008"}

_NUM = r"\d+(?:,\d+)?"
_MILIEU = {"rural": dict(topic="locality", characteristic="Rural", locality="rural", locality_label="Rural"),
           "urbain": dict(topic="locality", characteristic="Urbain", locality="urban", locality_label="Urbain")}
_ZONES = {"rural fleuve": "Rural fleuve", "rural autre": "Rural autre",
          "nouakchott": "Nouakchott", "autres villes": "Autres villes"}
_NAT = ("total", "ensemble", "national")
# Wilaya spellings vary between reports; normalised to the 2014 profile's
# (mauritania_2014), which every other Mauritania descriptor already uses.
_WILAYA = {"hodh el chargui": "Hodh Chargui", "hodh el charghi": "Hodh Chargui", "hodh charghi": "Hodh Chargui",
           "hodh charghy": "Hodh Chargui", "hodh chargui": "Hodh Chargui",
           "hodh el gharbi": "Hodh Gharbi", "hodh gharby": "Hodh Gharbi", "hodh gharbi": "Hodh Gharbi",
           "dakhlet nouadhibou": "Nouadhibou", "dakhlett nouadhibou": "Nouadhibou", "d.nouadhibou": "Nouadhibou",
           "dakhlett nouadibou": "Nouadhibou", "nouadhibou": "Nouadhibou", "tiris zemmour": "Tirs Zemmour",
           "tiris zemour": "Tirs Zemmour", "tiris-zemmour": "Tirs Zemmour", "tirs-ezemour": "Tirs Zemmour",
           "guidimakha": "Guidimagha", "hodh charghui": "Hodh Chargui", "d. nouadhibou": "Nouadhibou"}


def wilaya(name: str) -> str:
    name = re.sub(r"^(?:Wilaya|Milieu)\s+", "", name.strip())   # 2.1.12: the column header joins the first row
    return _WILAYA.get(name.lower(), name)


def _row(**kw):
    return C.row(**{**_BASE, **kw})


def _lines(pdf, pages):
    out = []
    for p in pages:
        out += [l.strip() for l in (pdf.pages[p - 1].extract_text() or "").splitlines() if l.strip()]
    return out


def _table(lines, start, n, stop=None):
    """[(label, numbers)] for rows with exactly n numbers after `start`;
    a label wrapped onto the line above its numbers is re-joined."""
    i = next((k for k, l in enumerate(lines) if re.search(start, l)), None)
    if i is None:
        raise ValueError(f"table '{start}' not found")
    out, pend = [], ""
    for l in lines[i + 1:]:
        if stop and re.search(stop, l):
            break
        m = re.match(rf"^(.*?)\s*((?:{_NUM}\s+){{{n - 1}}}{_NUM})$", l)
        # The header's subscript line "0 1 2 0 1 2" (P0 P1 P2 C0 C1 C2) is not a row.
        if m and re.fullmatch(r"(?:[012]\s+){%d}[012]" % (n - 1), m.group(2)) and "," not in m.group(2):
            pend = ""
            continue
        if m and m.group(1) and not re.match(r"^[\d,\s]+$", m.group(1)):
            lab = (pend + " " + m.group(1)).strip() if pend else m.group(1).strip()
            out.append((lab, [float(x.replace(",", ".")) for x in m.group(2).split()]))
            pend = ""
        elif m and pend:
            out.append((pend, [float(x.replace(",", ".")) for x in m.group(2).split()]))
            pend = ""
        elif re.search(r"\d", l):
            pend = ""
        else:
            pend = l if len(l) < 45 else ""
        if out and re.match(r"(?i)^(total|ensemble|national)\b", out[-1][0]):
            break
    return out


def _fgt(out, vals, attrs, metrics=("headcount", "gap", "severity", "poor_share",
                                    "gap_contribution", "severity_contribution")):
    national = attrs.get("geography", "Total country") == "Total country" and attrs.get("topic", "total") == "total"
    for m, v in zip(metrics, vals):
        if national and m.endswith(("share", "contribution")):
            continue                  # a national row's contribution is 100 by definition
        if m:
            out.append(_row(metric=m, value=v, unit="percent", **attrs))


def _geo_attrs(label, kind):
    label = re.sub(r"^(?:Wilaya|Milieu)\s+", "", label.strip())
    low = label.lower().strip()
    if low.startswith(_NAT):
        return {}
    if low in _MILIEU:
        return dict(_MILIEU[low])
    if kind == "zone" and low in _ZONES:
        z = _ZONES[low]
        return dict(topic="locality", characteristic=z,
                    locality="rural" if z.startswith("Rural") else "urban", locality_label=z)
    return dict(geography=wilaya(label))


def parse(path: str) -> pd.DataFrame:
    """Profil de pauvreté 2004."""
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        L = _lines(pdf, [44, 45, 49])
        T19 = _lines(pdf, [19])
    S = dict(survey=LAYOUT["survey"], period="2004", reference_period="2004", unit_of_analysis="person")
    OV = dict(line_level="overall", line_name="Seuil de pauvreté (EPCV)", line_value=94600,
              line_unit="MRO per person per year")
    EX = dict(line_level="extreme", line_name="Seuil d'extrême pauvreté (EPCV)", line_value=71550,
              line_unit="MRO per person per year")
    out = []
    for cap, kind, line in ((r"Tableau A\.1\.1", "wilaya", OV), (r"Tableau A\.1\.2", "zone", OV),
                            (r"Tableau A\.1\.3", "milieu", OV), (r"Tableau A\.1\.4", "zone", EX),
                            (r"Tableau A\.1\.5", "wilaya", EX)):
        for lab, v in _table(L, cap, 6):
            a = _geo_attrs(lab, kind)
            if not a:
                if kind != "wilaya":
                    continue          # the national row is A.1.1's
                _fgt(out, v[:3], {**S, **line})
                continue
            _fgt(out, v, {**S, **line, **a})
    for cap, topic in ((r"Tableau A\.1\.6", "education_of_head"), (r"Tableau A\.1\.7", "sex_of_head"),
                       (r"Tableau A\.1\.8", "employment_of_head")):
        for lab, v in _table(L, cap, 6):
            if lab.upper().startswith("TOTAL"):
                continue
            a = dict(topic=topic, characteristic=lab)
            if topic == "sex_of_head":
                a["sex"] = "male" if lab == "Homme" else "female"
            _fgt(out, v, {**S, **OV, **a})
    # Tableau 12 -- relative poverty
    rel = dict(line_type="relative", line_level="other", line_value=86357, line_unit="MRO per person per year",
               line_name="Pauvreté relative: moyenne des dépenses des 2e et 3e quintiles")
    i = next(k for k, l in enumerate(T19) if "Tableau 12" in l)
    for l in T19[i:i + 25]:
        m = re.search(rf"(Rural fleuve|Rural autre|Rural|Nouakchott|Autres villes|Urbain|National)\s+({_NUM})\s+({_NUM})\s+({_NUM})$", l)
        if m:
            lab = m.group(1)
            a = {} if lab == "National" else (_MILIEU.get(lab.lower()) or _geo_attrs(lab, "zone"))
            _fgt(out, [float(m.group(k).replace(",", ".")) for k in (2, 3, 4)], {**S, **rel, **a})
    # A.2.15 / A.2.16 -- the EPCV 2000 columns
    S0 = dict(survey="EPCV 2000 (Profil de pauvreté 2004)", period="2000", reference_period="2000",
              unit_of_analysis="person")
    OV0 = dict(line_level="overall", line_name="Seuil de pauvreté (EPCV)")
    EX0 = dict(line_level="extreme", line_name="Seuil d'extrême pauvreté (EPCV)")
    for lab, v in _table(L, r"Tableau A\.2\.15", 12, stop=r"Tableau A\.2\.16"):
        a = _geo_attrs(lab, "wilaya")
        _fgt(out, [v[0], v[2], v[4]], {**S0, **OV0, **a}, ("headcount", "gap", "severity"))
        _fgt(out, [v[6], v[8], v[10]], {**S0, **EX0, **a}, ("headcount", "gap", "severity"))
    i = next(k for k, l in enumerate(L) if "Tableau A.2.16" in l)
    joined, pend = [], ""
    for l in L[i + 1:]:
        m = re.match(rf"^(.*?)\s*((?:{_NUM}\s+){{8}}-?{_NUM})$", l)
        if m:
            joined.append(((pend + " " + m.group(1)).strip(), m.group(2).split()))
            pend = ""
        elif not re.search(r"\d", l) and not l.startswith(("Pauvreté", "contribution", "GSE")):
            pend = (pend + " " + l).strip()
    for lab, v in joined:
        if lab.upper().startswith("TOTAL"):
            continue
        a = dict(topic="employment_of_head", characteristic=lab[:1].upper() + lab[1:])
        vals = [float(x.replace(",", ".")) for x in v[4:8]]
        _fgt(out, vals, {**S0, **OV0, **a}, ("headcount", "gap", "severity", "poor_share"))
    df = pd.DataFrame(out)
    if len(df) < 300:
        raise ValueError(f"{path}: only {len(df)} values")
    return df


def parse_2008(path: str) -> pd.DataFrame:
    """Profil de pauvreté 2008."""
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        L28 = _lines(pdf, [28])
        L39 = _lines(pdf, [39])
        LA = _lines(pdf, [115, 116, 117])
        LM = _lines(pdf, [118])
        LE = _lines(pdf, [119])
    S = dict(survey=LAYOUT_2008["survey"], period="2008", reference_period="2008")
    OV = dict(line_level="overall", line_name="Seuil de pauvreté (EPCV)", line_value=129600,
              line_unit="MRO per person per year")
    EX = dict(line_level="extreme", line_name="Seuil d'extrême pauvreté (EPCV)", line_value=96400,
              line_unit="MRO per person per year")
    HH, PP = dict(unit_of_analysis="household"), dict(unit_of_analysis="person")
    out = []
    # 2.1.2 -- sex of the head, households | persons
    for lab, v in _table(L28, r"Tableau 2\.1\.2", 12):
        a = {} if lab == "Ensemble" else dict(topic="sex_of_head", characteristic=lab,
                                              sex="male" if lab == "Homme" else "female")
        _fgt(out, v[:6], {**S, **OV, **HH, **a})
        _fgt(out, v[6:], {**S, **OV, **PP, **a})
    # 2.1.10 -- wilaya (persons; national = 2.1.2)
    for lab, v in _table(LA, r"Tableau 2\.1\.10", 6):
        if lab != "Ensemble":
            _fgt(out, v, {**S, **OV, **PP, "geography": wilaya(lab)})
    # 2.1.11 -- characteristics of the head (persons)
    i = next(k for k, l in enumerate(LA) if "Tableau 2.1.11" in l)
    block, milieu = None, None
    blocks = {"1. Sexe": "sex_of_head", "2. Milieu": "milieu", "3. Niveau": "education_of_head",
              "4. Typologie": "household_type", "5. Situation": "employment_of_head",
              "6. Secteur": "employment_of_head", "7. Groupes": "employment_of_head",
              "8. Branches": "employment_of_head"}
    prefix = {"5. Situation": "Activité: ", "6. Secteur": "Secteur institutionnel: ",
              "7. Groupes": "GSE: ", "8. Branches": "Branche: "}
    for l in LA[i + 1:]:
        hit = next((k for k in blocks if l.startswith(k)), None)
        if hit:
            block, pre = hit, prefix.get(hit, "")
            continue
        m = re.match(rf"^(.*?)\s*((?:{_NUM}\s+){{5}}{_NUM})$", l)
        if not m or block is None:
            continue
        lab, v = m.group(1).strip(), [float(x.replace(",", ".")) for x in m.group(2).split()]
        if lab == "Ensemble":
            break
        topic = blocks[block]
        if topic == "sex_of_head":
            continue                      # = 2.1.2 (persons)
        if topic == "milieu":
            if lab in ("Urbain", "Rural"):
                milieu = _MILIEU[lab.lower()]
                _fgt(out, v, {**S, **OV, **PP, **milieu})
            else:
                a = dict(topic="sex_of_head", characteristic=lab, sex="male" if lab == "Homme" else "female",
                         locality=milieu["locality"], locality_label=milieu["locality_label"])
                _fgt(out, v[:3], {**S, **OV, **PP, **a}, ("headcount", "gap", "severity"))
            continue
        _fgt(out, v, {**S, **OV, **PP, "topic": topic, "characteristic": pre + lab})
    # 2.1.12 -- extreme, milieu and wilaya, households | persons
    for lab, v in _table(LA, r"Tableau 2\.1\.12", 12, stop=r"Tableau 2\.13"):
        a = _geo_attrs(lab, "wilaya")
        _fgt(out, v[:6], {**S, **EX, **HH, **a})
        _fgt(out, v[6:], {**S, **EX, **PP, **a})
    # 2.1.16 / 2.1.17 -- moughataas
    for L, line in ((LM, OV), (LE, EX)):
        n = 0
        for l in L:
            m = re.match(rf"^(\d{{1,2}})\s+(\D+?)\s+((?:{_NUM}\s+){{11}}{_NUM})$", l)
            if not m:
                continue
            name = m.group(2).strip()
            if name == "Moughataa":
                continue                  # 2.1.16 row 6: label misprinted
            v = [float(x.replace(",", ".")) for x in m.group(3).split()]
            g = dict(geography=f"{name} (moughataa)")
            _fgt(out, v[:6], {**S, **line, **HH, **g})
            _fgt(out, v[6:], {**S, **line, **PP, **g})
            n += 1
        if n < 52:
            raise ValueError(f"{path}: only {n} moughataas read")
    # 2.1.8 -- relative poverty
    rel = dict(line_type="relative", line_level="other", line_value=148100, line_unit="MRO per person per year",
               line_name="Pauvreté relative: deux tiers de la dépense moyenne par tête")
    for l in L39:
        m = re.match(rf"^(Rural|Urbain|National)\s+({_NUM})\s+({_NUM})$", l)
        if m:
            a = {} if m.group(1) == "National" else _MILIEU[m.group(1).lower()]
            out.append(_row(metric="headcount", value=float(m.group(2).replace(",", ".")), unit="percent",
                            **S, **rel, **PP, **a))
            if a:
                out.append(_row(metric="poor_share", value=float(m.group(3).replace(",", ".")),
                                unit="percent", **S, **rel, **PP, **a))
    df = pd.DataFrame(out)
    if len(df) < 900:
        raise ValueError(f"{path}: only {len(df)} values")
    return df


# Registry: mauritania_profil2004_poverty -> parse, LAYOUT;
#           mauritania_profil2008_poverty -> parse_2008, LAYOUT_2008


# ------------------------------- Tendances de la pauvreté (EPCV 2019-2020) ---
LAYOUT_TENDANCES = {**LAYOUT, "survey": "EPCV 2019-2020", "period": "2019"}


def parse_tendances(path: str) -> pd.DataFrame:
    """ANSADE, 'Tendances de la pauvreté monétaire et des inégalités en
    Mauritanie, EPCV 2019-2020' (Sept 2021). Tableau 3 (milieu, P0 P1 P2 and
    C0 C1 C2), 4 (13 wilayas, P0 P1 P2), 6 (extreme line, wilaya and milieu),
    8 (sex of the person; children < 18 / adults, both lines) -- each for 2014
    and 2019 -- and 9 (age group x wilaya / milieu, 2019). The 2014 columns
    are the REVISED 2014 series (national 30,9, as in the Annuaire 2024), not
    the 2014 profile's 31,0, so they carry the survey 'EPCV 2014 (série
    révisée)'. 2019 line 19 100 MRU per person per year (Tableau 7's
    reference). Tableau 7 (P0 at +-5/10/15% of the line) is a sensitivity
    analysis and not collected; Gini and decompositions belong elsewhere."""
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        P = {i: [l.strip() for l in (pdf.pages[i - 1].extract_text() or "").splitlines() if l.strip()]
             for i in (20, 21, 27, 33)}
    Y = {"2014": dict(survey="EPCV 2014 (série révisée)", period="2014", reference_period="2014"),
         "2019": dict(survey="EPCV 2019-2020", period="2019", reference_period="2019-2020")}
    OV = dict(line_level="overall", line_name="Seuil de pauvreté", unit_of_analysis="person")
    EX = dict(line_level="extreme", line_name="Seuil d'extrême pauvreté", unit_of_analysis="person")
    out = []

    def put(metric, v, year, line, a):
        out.append(_row(metric=metric, value=v, unit="percent", **Y[year], **line, **a))

    def geo(lab):
        low = lab.lower().strip()
        if low in ("national", "total", "ensemble"):
            return {}
        if low in _MILIEU:
            return dict(_MILIEU[low])
        return dict(geography=wilaya(lab))

    def nums(s):
        return [float(x.replace(",", ".")) for x in s.split()]

    blk = None
    for l in P[20]:
        if l.startswith("Tableau 3"):
            blk = "idx"
        elif l.startswith("Contributions"):
            blk = "ctr"
        elif l.startswith("2.2.2"):
            break
        m = re.match(rf"^(Urbain|Rural|National|Total)\s+((?:{_NUM}\s+){{5}}{_NUM})$", l)
        if not (m and blk):
            continue
        v, a = nums(m.group(2)), geo(m.group(1))
        if blk == "ctr" and not a:
            continue
        mets = (("headcount", "gap", "severity") if blk == "idx"
                else ("poor_share", "gap_contribution", "severity_contribution"))
        for k, year in ((0, "2014"), (3, "2019")):
            for j, met in enumerate(mets):
                put(met, v[k + j], year, OV, a)
    for page, cap, line in ((21, "Tableau 4", OV), (27, "Tableau 6", EX)):
        on = False
        for l in P[page]:
            if l.startswith(cap):
                on = True
                continue
            m = re.match(rf"^(\D+?)\s+((?:{_NUM}\s+){{5}}{_NUM})$", l)
            if not (on and m):
                continue
            a = geo(m.group(1))
            if not a and page == 21:
                break                     # national = Tableau 3
            v = nums(m.group(2))
            for k, year in ((0, "2014"), (3, "2019")):
                for j, met in enumerate(("headcount", "gap", "severity")):
                    put(met, v[k + j], year, line, a)
            if not a:
                break
    for l in P[33]:
        m = re.match(rf"^(Masculin|Féminin|Enfants de moins de 18 ans|Adultes de 18 ans et plus)\s+((?:{_NUM}\s+){{3}}{_NUM})$", l)
        if not m:
            continue
        lab, v = m.group(1), nums(m.group(2))
        if lab in ("Masculin", "Féminin"):
            a = dict(topic="sex", characteristic=lab, sex="male" if lab == "Masculin" else "female")
        else:
            a = dict(topic="age", characteristic=lab,
                     age_group="0-17 ans" if lab.startswith("Enfants") else "18 ans et plus")
        put("headcount", v[0], "2014", OV, a)
        put("headcount", v[1], "2014", EX, a)
        put("headcount", v[2], "2019", OV, a)
        put("headcount", v[3], "2019", EX, a)
    on = False
    for l in P[33]:
        if l.startswith("Tableau 9"):
            on = True
            continue
        m = re.match(rf"^(\D+?)\s+({_NUM})\s+({_NUM})\s+({_NUM})$", l)
        if not (on and m):
            continue
        g = geo(m.group(1))
        if not g:
            break
        for k, (cl, ag) in ((2, ("Enfants de moins de 18 ans", "0-17 ans")),
                            (3, ("Adultes de 18 ans et plus", "18 ans et plus"))):
            a = {k2: v2 for k2, v2 in g.items() if k2 not in ("topic", "characteristic")}
            a.update(topic="age", characteristic=cl, age_group=ag)
            put("headcount", float(m.group(k).replace(",", ".")), "2019", OV, a)
    df = pd.DataFrame(out)
    if len(df) < 250:
        raise ValueError(f"{path}: only {len(df)} values")
    return df
# Registry: mauritania_tendances_poverty -> parse_tendances, LAYOUT_TENDANCES


# ------------------------------------------- Profils 2000 and 1996 (ONS) ---
# Both reports survive only as Wayback `id_` copies of ONS's own files
# (www.ons.mr/francais/...). Their text layers interleave each table with the
# prose beside it, so rows are matched by an EXPLICIT label + exactly three
# numbers at the END of the line, and a table is taken only where every
# expected row is found.
LAYOUT_2000 = {**LAYOUT, "survey": "EPCV 2000 (Profil de pauvreté 2000)", "period": "2000"}
LAYOUT_1996 = {**LAYOUT, "survey": "EPCV 1996 (Profil de pauvreté 1996)", "period": "1996"}
_W13 = ["Hodh El Charghi", "Hodh El Gharbi", "Assaba", "Gorgol", "Brakna", "Trarza", "Adrar",
        "D.Nouadhibou", "Tagant", "Guidimagha", "Tiris Zemmour", "Inchiri", "Nouakchott"]


def _end3(line, label):
    m = re.search(r"(?:^|\s)" + re.escape(label) + r"\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)\s+(\d+[.,]\d+)$", line.strip())
    return [float(x.replace(",", ".")) for x in m.groups()] if m else None


def parse_2000(path: str) -> pd.DataFrame:
    """Profil de la pauvreté en Mauritanie 2000 (ONS; line 67 316 UM, i.e.
    the 1996 line inflated -- NOT the revised line of the 2004 profile, whose
    EPCV 2000 estimate is 51,0 against 46,3 here). Tableau 1.6: P0 P1 P2 for
    the 13 wilayas + national; Tableau 1.8: wilaya contributions C0 C1 C2
    (columns in the printed wilaya order); p. 17: Nouakchott zone lotie / non
    lotie and the zones' contributions; Tableau 1.11: P0 P1 P2 by socio-
    economic group of the head. Not read: the GSE contribution blocks (their
    second row repeats the label 'Salariés du secteur public'), the extreme-
    poverty tables (cells missing from the text layer), relative poverty
    (Tableau 1.15 is one cell per line)."""
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        P = {i: (pdf.pages[i - 1].extract_text() or "").splitlines() for i in (17, 19, 20, 22)}
    S = dict(survey=LAYOUT_2000["survey"], period="2000", reference_period="2000", unit_of_analysis="person",
             line_level="overall", line_name="Seuil de pauvreté (EPCV)", line_value=67316,
             line_unit="MRO per person per year")
    out = []
    got = {}
    for l in P[19]:
        for w in _W13 + ["National"]:
            v = _end3(l, w)
            if v:
                got[w] = v
    if len(got) != 14:
        raise ValueError(f"{path}: Tableau 1.6 read {len(got)} of 14 rows: {sorted(got)}")
    for w, v in got.items():
        a = {} if w == "National" else dict(geography=wilaya(w))
        _fgt(out, v, {**S, **a}, ("headcount", "gap", "severity"))
    cs = [l for l in P[20] if re.match(r"^C\s+(?:\d+(?:\.\d+)?\s+){13}100$", l.strip())]
    if len(cs) != 3:
        raise ValueError(f"{path}: Tableau 1.8 has {len(cs)} contribution rows, expected 3")
    for met, l in zip(("poor_share", "gap_contribution", "severity_contribution"), cs):
        for w, v in zip(_W13, l.split()[1:14]):
            out.append(_row(metric=met, value=float(v), unit="percent", **S, geography=wilaya(w)))
    for lab in ("Lotie", "Non lotie"):
        v = next((_end3(l, lab) for l in P[17] if _end3(l, lab)), None)
        if v is None:
            raise ValueError(f"{path}: Nouakchott '{lab}' row missing")
        name = "Nouakchott, zone " + lab.lower()
        _fgt(out, v, {**S, "geography": "Nouakchott", "topic": "locality", "locality": "urban",
                      "characteristic": name, "locality_label": name}, ("headcount", "gap", "severity"))
    # the zones' contributions C0 C1 C2 (the index rows above them are on p. 16)
    zones = [("Nouakchott", "nouakchott"), ("Autres villes", "autres villes"), ("Urbain", None),
             ("Rural Fleuve", "rural fleuve"), ("Rural Autre", "rural autre"), ("Rural", None)]
    for l in P[17]:
        for lab, z in zones:
            v = _end3(l, lab)
            if not v:
                continue
            if lab == "Nouakchott" and v == [25.1, 6.1, 2.0]:
                continue                  # the Nouakchott INDEX row of the lotie table
            if lab == "Rural" and re.search(r"Rural (Fleuve|Autre)", l):
                continue
            a = _geo_attrs(z, "zone") if z else dict(_MILIEU[lab.lower()])
            _fgt(out, v, {**S, **a}, ("poor_share", "gap_contribution", "severity_contribution"))
    gse = ["Salariés du secteur public", "Salariés du secteur privé", "Indépendants agricoles",
           "Indépendants non agricoles", "occupés", "Chômeurs", "Inactifs"]
    i = next(k for k, l in enumerate(P[22]) if "Tableau 1.11" in l)
    seen = set()
    for l in P[22][i:]:
        for g in gse:
            v = _end3(l, g)
            if v and g not in seen:
                seen.add(g)
                lab = "Aides familiaux et autres occupés" if g == "occupés" else g
                _fgt(out, v, {**S, "topic": "employment_of_head", "characteristic": lab},
                     ("headcount", "gap", "severity"))
        if len(seen) == len(gse):
            break
    if len(seen) != len(gse):
        raise ValueError(f"{path}: Tableau 1.11 read {sorted(seen)}")
    return pd.DataFrame(out)


def parse_1996(path: str) -> pd.DataFrame:
    """Profil de la pauvreté en Mauritanie 1996 (ONS, EIDSA / EPCV, May 1997,
    Volume 1). Tableau 8: P0 P1 P2 nationally and by zone (Nouakchott, autres
    villes, rural fleuve, rural autre) for 1990 AND 1996, on the line of
    53 841 UM in 1996 (32 800 UM in 1990), construction spending excluded
    from both rounds for comparability. Other tables are not read: their rows
    are printed beside prose in the text layer and several lose their year
    cell (Tableau 10's Rural Autre), and the report's own figures differ
    between tables (1996 national 50,0 in the text, 50,5 in Tableau 8)."""
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        L = [l.strip() for l in (pdf.pages[32].extract_text() or "").splitlines()]
    i = next(k for k, l in enumerate(L) if l.startswith("National 1990"))
    seq = [("National", "1990"), (None, "1996"), ("Nouakchott", "1990"), (None, "1996"),
           ("Autres villes", "1990"), (None, "1996"), ("Rural Fleuve", "1990"), (None, "1996"),
           ("Rural Autre", "1990"), (None, "1996")]
    out, cur, j = [], None, i
    for lab, year in seq:
        # rows are interleaved with prose lines: take the NEXT line, in order,
        # that starts with this row's label (or, for a 1996 row, its year)
        pat = (re.escape(lab) + r"\s+" if lab else "") + year + r"\s+(\d+,\d)\s+(\d+,\d)\s+(\d+,\d)"
        cur = lab or cur
        m = None
        while j < min(len(L), i + 30) and m is None:
            m = re.match("^" + pat, L[j])
            j += 1
        if not m:
            raise ValueError(f"{path}: Tableau 8 row {cur} {year} not found")
        v = [float(x.replace(",", ".")) for x in m.groups()]
        S = dict(survey=f"EPCV {year} (Profil de pauvreté 1996)", period=year, reference_period=year,
                 unit_of_analysis="person", line_level="overall", line_name="Seuil de pauvreté (EPCV)",
                 line_value=53841 if year == "1996" else 32800, line_unit="MRO per person per year")
        a = {} if cur == "National" else _geo_attrs(cur.lower(), "zone")
        _fgt(out, v, {**S, **a}, ("headcount", "gap", "severity"))
    return pd.DataFrame(out)
# Registry: mauritania_profil2000_poverty -> parse_2000, LAYOUT_2000;
#           mauritania_profil1996_poverty -> parse_1996, LAYOUT_1996
