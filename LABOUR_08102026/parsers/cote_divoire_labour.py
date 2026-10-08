"""Côte d'Ivoire — INS/ANStat, Profil de pauvreté de la Côte d'Ivoire 2021
(EHCVM 2021, Enquête Harmonisée sur les Conditions de Vie des Ménages),
chapter 4 "Emploi", Tableau 4-4 "Population en emploi selon le statut
d'occupation" -- formal / informal employment by sex, age, education and milieu.

REACHED THROUGH THE WAYBACK MACHINE. anstat.ci answers a Cloudflare interactive
challenge ("Just a moment...", HTTP 403) to every client -- plain requests and
curl_cffi chrome / safari / firefox fingerprints alike, rechecked 2026-10-01.
The Wayback Machine holds an unchanged capture of ANStat's OWN file
(/assets/projet/ehcvm2021.pdf, captured 2026-03-27), fetched in its `id_` form,
which returns the original bytes. It is an archive of the NSO's publication,
not an aggregator -- the DR Congo precedent.

A HOUSEHOLD survey (EHCVM, collected November 2021 - July 2022 in two waves),
on ICLS-19 definitions: the employed are persons aged 16+ (Côte d'Ivoire's
legal minimum working age, the report's own "population en âge de
travailler") who worked for pay or profit in the last 7 days.

EACH ROW IS A POPULATION GROUP and its two shares are that group's split of
employment between informal and formal (they sum to 100), with the counts
beside them: a composition of employment in this schema's sense, like Mali's
EMOP tables, with the group in sex / age_group / education / locality. The
universe was checked, not assumed: the Total row (9 199 529) is the report's
own "population en emploi" (Tableau 4-3), and each block's groups sum to it.

INFORMALITY AS THIS REPORT OPERATIONALISES IT: an employment is informal when
it carries no social protection, paid leave or sick leave (the report says the
questionnaire's limits forced that proxy for the ICLS-17 definition). That
definition travels in `survey`, since it is narrower than ANStat's ENE.

ABIDJAN / AUTRES VILLES / RURAL are the report's residence strata ->
locality urban (Abidjan, Autres villes) or rural, labelled as printed.

NOT COLLECTED: the "Effectif" of each group (employment levels --
`unemployment`'s territory); Tableau 4-3 (employment by age, a distribution
across ages -- `age_group` is a column here, not a topic); Tableau 4-5 (wage
employment rates); Graphique 4-1 (sector shares as chart labels interleaved
with the axis and a second chart in the text layer -- the values 38,4 / 15,3 /
24,1 / 22,1 cannot be tied to their bars without inference; the Senegal rule).
The RGPH 2014 report's tables 4.16-4.18 were also examined and refused: 4.16's
total (4 216 826) is not the 7 383 582 employed and its sex columns are shares
of the grand total; 4.17's total is the whole 15+ population with 43,5% "non
spécifié"; 4.18's employed-by-branch column sums to 99,5 with no stated base.

PERIOD 2022 (collection November 2021 - July 2022, dated to its final year as
Chad's ECOSIT4 is); reference "EHCVM 2021 (novembre 2021 - juillet 2022)".

PUBLISHED GAP KEPT: the education levels sum to 335 fewer employed than the
Total (`_KNOWN_GAP`).

CROSS-CHECK: informal employment 91,6% (8 427 186 of 9 199 529); women 94,3%;
Abidjan 81,9%; supérieur 39,2% informal (60,8% formal); 61 ans et plus 97,5%.
"""
from __future__ import annotations

import re

import pandas as pd
import pdfplumber

from . import _common as C

_SURVEY = ("Enquête Harmonisée sur les Conditions de Vie des Ménages (EHCVM) "
           "2021 -- informality = no social protection / paid or sick leave")
_CAPTION = re.compile(r"Tableau 4-4 : Population en emploi selon le statut d.occupation")
_COUNT = r"\d{1,3}(?: \d{3})*"
_PCT = r"\d{1,3},\d"
# The page is set in two columns and pdfplumber interleaves them, so each
# table row is found by its label and the exact six-cell shape at the END of
# a line: informal count, %, formal count, %, 100,0%, total.
_ROW = re.compile(rf"(?:^|\s)(Masculin|Féminin|16-24|25-34|35-44|45-54|55-60|"
                  rf"61 et plus|Aucun|Primaire|Secondaire|Supérieur|Abidjan|"
                  rf"(?:Autres )?villes|Rural|Total)\s+({_COUNT}) ({_PCT})% "
                  rf"({_COUNT}) ({_PCT})% 100,0% ({_COUNT})$")
_GROUPS = {
    "sex": ["Masculin", "Féminin"],
    "age_group": ["16-24", "25-34", "35-44", "45-54", "55-60", "61 et plus"],
    "education": ["Aucun", "Primaire", "Secondaire", "Supérieur"],
    "locality": ["Abidjan", "Autres villes", "Rural"],
}


# A PUBLISHED GAP, KEPT: the four education levels sum to 9 199 194 employed,
# 335 short of the Total (9 199 529) -- persons whose level was not recorded,
# presumably; sex, age and milieu reconcile to within rounding. Pinned so that
# any other gap, or a correction, raises.
_KNOWN_GAP = {"education": 335}


def _num(s: str) -> float:
    return float(s.replace(" ", "").replace(",", "."))


def _rows(path: str) -> dict:
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[70:100]:
            text = page.extract_text() or ""
            if not _CAPTION.search(text):
                continue
            got = {}
            for ln in text.splitlines():
                m = _ROW.search(ln.strip())
                if m:
                    # "Autres" sits on the line above "villes" in the left
                    # column's flow; the stratum is "Autres villes".
                    lab = "Autres villes" if m.group(1).endswith("villes") else m.group(1)
                    if lab in got:
                        raise ValueError(f"EHCVM T4-4: {lab!r} read twice")
                    got[lab] = [_num(m.group(i)) for i in range(2, 7)]
            return got
    raise ValueError("EHCVM T4-4: caption not found")


def parse(path: str) -> pd.DataFrame:
    rows = _rows(path)
    want = [g for gs in _GROUPS.values() for g in gs] + ["Total"]
    if sorted(rows) != sorted(want):
        raise ValueError(f"EHCVM T4-4: rows {sorted(rows)}")
    for lab, (n_inf, p_inf, n_for, p_for, n_tot) in rows.items():
        if abs(n_inf + n_for - n_tot) > 2 or abs(p_inf + p_for - 100) > 0.15:
            raise ValueError(f"EHCVM T4-4 {lab}: parts do not add up")
    total = rows["Total"][4]
    for dim, labs in _GROUPS.items():
        s = sum(rows[l][4] for l in labs)
        if abs(total - s - _KNOWN_GAP.get(dim, 0)) > 5:
            raise ValueError(f"EHCVM T4-4: {dim} groups sum to {s}, Total {total}")

    out = []
    for lab, (n_inf, p_inf, n_for, p_for, _) in rows.items():
        ctx = {}
        if lab in _GROUPS["sex"]:
            ctx["sex"] = C.normalise_sex(lab)
        elif lab in _GROUPS["age_group"]:
            ctx["age_group"] = lab
        elif lab in _GROUPS["education"]:
            ctx["education"] = lab
        elif lab in _GROUPS["locality"]:
            ctx["locality"] = "rural" if lab == "Rural" else "urban"
            ctx["locality_label"] = lab
        for cat, n, p in (("Emploi informel", n_inf, p_inf),
                          ("Emploi formel", n_for, p_for)):
            for val, meas, unit in ((n, "count", "persons"), (p, "share", "percent")):
                out.append(C.row(topic="formality", characteristic=cat,
                                 classification="Not applicable", value=val,
                                 survey=_SURVEY, period="2022",
                                 reference_period="EHCVM 2021 (novembre 2021 - juillet 2022)",
                                 frequency="ad_hoc", measure=meas, unit=unit,
                                 working_age_base="16+",
                                 series_code="EHCVM2021 T4-4", **ctx))
    return pd.DataFrame(out)
