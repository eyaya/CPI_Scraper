"""Togo -- monetary poverty (INSEED).

Two INSEED publications, both read here:

PRIMARY: "Note synthétique sur les résultats de pauvreté - EHCVM 2018-2019"
(Oct 2020, 5 pp). Fieldwork 25 Sep - 20 Dec 2018 and 5 Apr - 3 Jul 2019.
  Tableau 1  national P1, P2 and number of poor (P0 is read from Tableau 2)
  Tableau 2  P0 2006 / 2011 / 2015 / 2017 / 2018-2019 for Ensemble, Rural, Lomé
             urbain, Autres urbains -- only the 2017 and 2018-2019 columns are
             taken (2006-2015 come with P1/P2 from the profile below). The
             Urbain row prints two values for five years and the regions four,
             so which year each belongs to is not printed: those rows are
             skipped. The 2017 column names no survey ("Source : QUIBB
             2006-2011-2015, EHCVM 2018-2019").
  Tableau 3  P0 at the international US$1,9 and US$3,2 (PPP 2011) lines, and the
             urban P0 (26,5). Its rural P0 (58,7) and line (273 619) differ from
             Tableau 2 / Tableau 1 (58,8 / 273 628); Tableaux 1-2 are kept.
EXTRA: "Profil de pauvreté 2006-2011-2015" (QUIBB, Apr 2016), annexes 3.1-3.14:
  Pop. share, P0, P1, P2, P1/P0 (skipped, derived; in 2015 the report prints P1
  in that column), C0, C1, C2 by milieu, socio-economic group, sex, education,
  marital status and age of the head and household size, for 2006 / 2011 /
  2015, on the overall line (3.1-3.7) and the extreme / food line (3.8-3.14,
  several for 2015 only; 3.10's 2015 contributions are skipped -- they are a
cell-for-cell copy of 3.2's overall-line contributions). Ensemble rows are taken from 3.1 / 3.8 only (3.2's
  2015 Ensemble prints P1 22,0 against 22,1). The QUIBB welfare measure is
  consumption per ADULT EQUIVALENT; the EHCVM's is per person, and the note
  says the methodologies differ -- each round keeps its own survey and line.

CROSS-CHECK: 2018-19 P0 45,5 / P1 15,2 / P2 6,9, 3 476 705 poor, line 273 628;
rural 58,8, Lomé urbain 22,3; 2015 P0 55,1 / 22,1 / 11,7; 2006 61,7; extreme
2015 28,7; $1,9 PPP 23,1.
"""
from __future__ import annotations
import re

import pandas as pd

from . import _common as C

LAYOUT = {  # declarative defaults for check_registry; parsing is bespoke below
    "survey": "EHCVM 2018-2019", "welfare_aggregate": "consumption",
    "unit_of_analysis": "person", "line_type": "national", "line_level": "overall",
    "line_name": "Seuil de pauvreté (EHCVM)", "period": "2018", "tables": [],
}

_EH = dict(survey="EHCVM 2018-2019", welfare_aggregate="consumption",
           line_type="national", line_level="overall",
           line_name="Seuil de pauvreté (EHCVM)", line_value=273628,
           line_unit="XOF per person per year", period="2018",
           reference_period="2018-2019", frequency="ad_hoc")
_LOC = {"Ensemble": ("total", "all", "Total"), "Rural": ("locality", "rural", "Rural"),
        "Lomé urbain": ("locality", "other", "Lomé urbain"),
        "Autres urbains": ("locality", "other", "Autres urbains"),
        "Autre urbain": ("locality", "other", "Autres urbains"),  # 3.8 2006-11 spelling
        "Urbain": ("locality", "urban", "Urbain")}


def _text(path: str) -> list[str]:
    import pdfplumber
    with pdfplumber.open(path) as pdf:
        return [(p.crop((0, 0, p.width, p.height)).extract_text() or "") for p in pdf.pages]


def _loc_row(label, **kw):
    topic, loc, lab = _LOC[label]
    return C.row(topic=topic, locality=loc, locality_label=lab,
                 characteristic=lab if topic == "locality" else "Total", **kw)


def _note(pages: list[str]) -> list[dict]:
    text = "\n".join(pages)
    out = []
    t1 = {}
    for key, pat in (("gap", r"^Profondeur de la pauvreté\s+([\d,]+)$"),
                     ("severity", r"^Sévérité de la pauvreté\s+([\d,]+)$"),
                     ("poor_count", r"^Effectif des pauvres\s+([\d ]+)$")):
        m = re.search(pat, text, re.M)
        if not m:
            raise ValueError(f"Togo note Tableau 1: {key} not found")
        t1[key] = C.to_number(m.group(1), decimal=",")
    for metric, v in t1.items():
        out.append(_loc_row("Ensemble", metric=metric, value=v, **_EH))
    # Tableau 2: the 2017 and 2018-2019 columns of the five-value rows.
    t2 = text[text.index("Tableau 2 : Chiffres de pauvreté"):]
    t2 = t2[:t2.index("Source : QUIBB")]
    m = re.search(r"INCIDENCE DE PAUVRETE\s*\n([\d,\s]+)\n", t2)
    rows = [("Ensemble", m.group(1))] if m else []
    for lab in ("Rural", "Lomé urbain", "Autres urbains"):
        mm = re.search(rf"^{lab}\s+([\d,\s]+)$", t2, re.M)
        rows.append((lab, mm.group(1) if mm else ""))
    for lab, nums in rows:
        vals = C.numbers_in(nums, decimal=",")
        if len(vals) != 5:
            raise ValueError(f"Togo note Tableau 2 {lab}: {vals}")
        out.append(_loc_row(lab, metric="headcount", value=vals[4], **_EH))
        out.append(_loc_row(lab, metric="headcount", value=vals[3],
                            **{**_EH, "survey": "Estimation 2017 (survey not named in Tableau 2)",
                               "line_name": "Seuil de pauvreté (Tableau 2, 2017)",
                               "line_value": 355638, "line_unit": "XOF per year (as printed)",
                               "period": "2017", "reference_period": "2017"}))
    # Tableau 3: international lines and the urban P0.
    for lab, metric_line in (("Seuil de \\$1,9 PPP 2011", "US$1,9 par jour (PPA 2011)"),
                             ("Seuil de \\$3,2 PPP 2011", "US$3,2 par jour (PPA 2011)")):
        mm = re.search(rf"^Incidence de la pauvreté-{lab}\s+([\d,]+)$", text, re.M)
        if not mm:
            raise ValueError(f"Togo note Tableau 3: {lab}")
        out.append(_loc_row("Ensemble", metric="headcount", value=C.to_number(mm.group(1), ","),
                            **{**_EH, "line_type": "international", "line_level": "other",
                               "line_name": metric_line, "line_value": "", "line_unit": ""}))
    mm = re.search(r"^Incidence de la pauvreté-Urbain\s+([\d,]+)$", text, re.M)
    out.append(_loc_row("Urbain", metric="headcount", value=C.to_number(mm.group(1), ","), **_EH))
    return out


# --- the QUIBB profile's annexes ---------------------------------------------
_ANNEX = {  # annex -> (topic, line level)
    1: ("locality", "overall"), 2: ("employment_of_head", "overall"),
    3: ("sex_of_head", "overall"), 4: ("education_of_head", "overall"),
    5: ("marital_status_of_head", "overall"), 6: ("age_of_head", "overall"),
    7: ("household_size", "overall"),
    8: ("locality", "extreme"), 9: ("sex_of_head", "extreme"),
    10: ("employment_of_head", "extreme"), 11: ("education_of_head", "extreme"),
    12: ("marital_status_of_head", "extreme"), 13: ("age_of_head", "extreme"),
    14: ("household_size", "extreme"),
}
_COLS = ["population_share", "headcount", "gap", "severity", None,
         "poor_share", "gap_contribution", "severity_contribution"]
_CONTRIB = {"poor_share", "gap_contribution", "severity_contribution"}
_LINE = {2006: 276400, 2011: 323388, 2015: 344408}
_HEADER = re.compile(r"^(?:Milieu|Groupe|Sexe|Scolarisation|Statut|Âge|Age|Taille)\b.*\bPop\.")


def _annex_rows(block: list[str]) -> list[tuple[str, list[float]]]:
    """(label, 8 numbers) per row; re-joins labels wrapped around their numbers
    ("Secondaire" / "16,2 ..." / "partiel") or before them ("Apprentis, Aides
    familiaux," / "autres actif 6,7 ...")."""
    out, pending = [], ""
    i = 0
    while i < len(block):
        ln = block[i].strip()
        m = re.match(r"^(.*?)\s*((?:-?[\d,]+\s*){8})$", ln)
        if m:
            label = (pending + " " + m.group(1)).strip()
            pending = ""
            # Every cell is below 1 000, so each is ONE token: read generically,
            # "100 100 100" (2006/2011 Ensemble contributions) fuses into one
            # thousands group and the row is lost.
            nums = [C.to_number(t, decimal=",") for t in m.group(2).split()]
            nxt = block[i + 1].strip() if i + 1 < len(block) else ""
            if not m.group(1) and nxt and not re.search(r"\d", nxt) and len(nxt.split()) <= 2:
                label = f"{label} {nxt}"
                i += 1
            if len(nums) == 8 and None not in nums and label:
                out.append((label, nums))
        elif ln and not re.search(r"\d", ln):
            pending = (pending + " " + ln).strip()
        else:
            pending = ""
        i += 1
    return out


def _profile(pages: list[str]) -> list[dict]:
    text = "\n".join(pages)
    starts = [(int(m.group(1)), m.start()) for m in re.finditer(r"^Annexe 3\. (\d+) :", text, re.M)]
    starts = [s for s in starts if s[0] in _ANNEX]
    # the list of annexes (front matter) carries every caption with dot leaders
    starts = [s for s in starts if "......" not in text[s[1]:s[1] + 200]]
    out, seen = [], set()
    for k, (num, pos) in enumerate(starts):
        end = starts[k + 1][1] if k + 1 < len(starts) else text.find("Annexe 5. 1", pos)
        chunk = text[pos:end].splitlines()
        topic, level = _ANNEX[num]
        year, block = None, []
        blocks = []
        for ln in chunk:
            if re.fullmatch(r"(2006|2011|2015)", ln.strip()):
                if year:
                    blocks.append((year, block))
                year, block = int(ln.strip()), []
            elif year and not _HEADER.match(ln):
                block.append(ln)
        if year:
            blocks.append((year, block))
        for year, block in blocks:
            for label, nums in _annex_rows(block):
                if label == "Ensemble" and num not in (1, 8):
                    continue
                base = dict(survey=f"QUIBB {year}", welfare_aggregate="consumption",
                            line_type="national", line_level=level,
                            line_name=("Seuil de pauvreté monétaire (QUIBB)" if level == "overall"
                                       else "Seuil de pauvreté alimentaire (QUIBB)"),
                            line_value=_LINE[year] if level == "overall" else "",
                            line_unit="XOF per adult equivalent per year" if level == "overall" else "",
                            period=str(year), reference_period=str(year), frequency="ad_hoc")
                for metric, v in zip(_COLS, nums):
                    if metric is None:
                        continue
                    # PUBLISHED COPY: annex 3.10's 2015 C0/C1/C2 (extreme line)
                    # repeat annex 3.2's overall-line contributions cell for
                    # cell (3,0 2,8 2,6 / 15,4 14,6 13,7 ...) beside entirely
                    # different extreme rates -- not the extreme contributions.
                    if num == 10 and year == 2015 and metric in _CONTRIB:
                        continue
                    if topic == "locality":
                        out.append(_loc_row(label, metric=metric, value=v, **base))
                        continue
                    extra = {}
                    if topic == "sex_of_head":
                        extra["sex"] = {"Homme": "male", "Femme": "female"}[label]
                    out.append(C.row(metric=metric, value=v, topic=topic,
                                     characteristic=label, **extra, **base))
                seen.add(num)
    missing = set(_ANNEX) - seen
    if missing:
        raise ValueError(f"Togo profile: annexes {sorted(missing)} yielded no rows")
    return out


def parse(path: str, extras: list[str] | None = None) -> pd.DataFrame:
    rows = _note(_text(path))
    for ex in extras or []:
        if "profil_pauvrete_2016" in ex.replace("-", "_").lower():
            rows += _profile(_text(ex))
    return pd.DataFrame(rows)
