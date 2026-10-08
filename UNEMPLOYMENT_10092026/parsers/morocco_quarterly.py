"""Morocco — HCP annual ENE report, Tableau 11 "Indicateurs trimestriels
d'activité, d'emploi et de chômage par milieu de résidence": the FOUR
QUARTERS of the year, for National, Urbain and Rural.

`morocco_unemployment` reads Tableaux 2/3 for the ANNUAL figures. Tableau 11
prints the same indicators quarter by quarter; only the four quarterly columns
are read here -- its "Année" column repeats the annual figures already
collected and is checked equal to Tableau 11's own quarters' neighbour rather
than emitted.

Rows read (the series labels are Tableau 11's own, so they never collide with
Tableaux 2/3's): taux d'activité (total, by sex, by age band, by diploma),
taux d'emploi, taux de sous-emploi, taux de chômage (total, by sex, by age
band, by diploma), and the levels population active / active occupée / en
chômage / en sous-emploi (thousands). Feminisation rates and the shares of
paid employment are not topics here.

Each block's column header must name the four quarters and the year; the
quarter columns are dated YYYY-Qn from it. A block that does not parse as 5
values per row raises.

CROSS-CHECK (2025, National): chômage 13,3 / 12,8 / 13,1 / 12,9; 15-24 ans
37,7 / 35,8 / 38,4 / 37,2; Urbain 16,6 / 16,4 / 16,3 / 16,5; Rural activité
45,6 / 46,4 / 45,2 / 47,0.
"""
from __future__ import annotations

import re

import pdfplumber

_SURVEY = "Activité, emploi et chômage (résultats annuels)"
_MILIEU = {"NATIONAL": ("all", "Total"), "URBAIN": ("urban", "Urbain"),
           "RURAL": ("rural", "Rural")}
_NUM = r"\d{1,3}(?: \d{3})*(?:,\d+)?"
# The value run: digits, spaces and decimal commas to the end of the line.
_ROW = re.compile(r"^-?\s*(.*?)\s*((?:\d[\d,]*\s+){4,9}\d[\d,]*)$")


def _values(run: str) -> list[float]:
    """"12 249 12 458 ..." and "662 635 651 ..." both read right: every
    level here is under 100 000 thousand, so a thousands group always
    starts with ONE OR TWO digits followed by exactly three."""
    toks, out, i = run.split(), [], 0
    while i < len(toks):
        t = toks[i]
        if (len(t) <= 2 and t.isdigit() and i + 1 < len(toks)
                and len(toks[i + 1]) == 3 and toks[i + 1].isdigit()):
            t, i = t + toks[i + 1], i + 1
        out.append(_num(t))
        i += 1
    return out
# label -> (topic, measure, unit, definition)
_LEVELS = {
    "Population active (en milliers)": ("labour_force", "not_applicable"),
    "Population active occupée (en milliers)": ("employed", "not_applicable"),
    "Population active en chômage (en milliers)": ("unemployed", "not_applicable"),
}
_RATES = {
    "Taux d'activité (%)": ("labour_force_participation_rate", "strict"),
    "Taux d'emploi (%)": ("employment_to_population_ratio", "not_applicable"),
    "Taux de sous-emploi (%)": ("underemployment_rate", "not_applicable"),
    "Taux de chômage (%)": ("unemployment_rate", "strict"),
}


def _num(v: str) -> float:
    return float(v.replace(" ", "").replace(",", "."))


def parse_quarters(path: str) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        pages = [p.extract_text() or "" for p in pdf.pages]
    out = []
    blocks = 0
    for text in pages:
        if not re.search(r"^Tableau 11 : Indicateurs trimestriels", text, re.M):
            continue
        lines = [ln.strip() for ln in text.splitlines()]
        milieu = next((m for m in _MILIEU if m in lines), None)
        year = next((ln for ln in lines if re.fullmatch(r"20\d\d", ln)), None)
        hdr = " ".join(lines[:12])
        if not milieu or not year or not re.search(
                r"1er\s+2ème\s+3ème\s+4ème\s+Année", hdr):
            raise ValueError(f"HCP T11: unreadable block header {hdr[:120]!r}")
        loc, loc_label = _MILIEU[milieu]
        topic, definition, dim = None, None, None
        pending = ""
        for ln in lines:
            if ln.startswith("• Selon le sexe"):
                dim = "sex"; continue
            if ln.startswith("• Selon l'âge"):
                dim = "age"; continue
            if ln.startswith("• Selon le diplôme"):
                dim = "edu"; continue
            m = _ROW.match(ln)
            if not m:
                pending = ln if not re.search(r"\d", ln) else ""
                continue
            label = re.sub(r"^-\s*", "", (m.group(1) or pending)).strip()
            label = re.sub(r"^-", "", label).strip()
            pending = ""
            vals = _values(m.group(2))
            if len(vals) != 5:
                raise ValueError(f"HCP T11 {milieu}: {ln!r}")
            ctx = {}
            if label in _RATES:
                topic, definition = _RATES[label]
                dim, slabel = None, label
                meas, unit = "rate", "percent"
            elif label in _LEVELS:
                (topic, definition), dim = _LEVELS[label], None
                slabel, meas, unit = label, "count", "thousand_persons"
            elif dim and topic in ("labour_force_participation_rate",
                                   "unemployment_rate"):
                slabel, meas, unit = f"{_base(topic)} - {label}", "rate", "percent"
                if dim == "sex":
                    ctx["sex"] = {"Hommes": "male", "Femmes": "female"}[label]
                elif dim == "age":
                    ctx["age_group"] = label.replace(" ans", "").replace(
                        " et plus", "+")
                else:
                    ctx["education"] = label
            else:
                continue            # feminisation, paid-employment shares
            t = topic
            if t == "unemployment_rate" and ctx.get("age_group") == "15-24":
                t = "youth_unemployment_rate"
            for q, v in enumerate(vals[:4], start=1):
                out.append({
                    "topic": t, "definition": definition, "series_label": slabel,
                    "sex": ctx.get("sex", "total"),
                    "age_group": ctx.get("age_group", "Total"),
                    "education": ctx.get("education", "Total"),
                    "geography": "Total country", "locality": loc,
                    "locality_label": loc_label, "working_age_base": "15+",
                    "period": f"{year}-Q{q}",
                    "reference_period": f"{q}{'er' if q == 1 else 'ème'} "
                                        f"trimestre {year}",
                    "frequency": "quarterly", "measure": meas, "value": v,
                    "unit": unit, "survey": _SURVEY,
                    "series_code": "HCP ENE T11"})
            if label in _LEVELS or label in _RATES:
                pass
        blocks += 1
    if blocks != 3:
        raise ValueError(f"HCP T11: {blocks} milieu blocks, expected 3")
    return out


def _base(topic: str) -> str:
    return {"labour_force_participation_rate": "Taux d'activité (%)",
            "unemployment_rate": "Taux de chômage (%)"}[topic]
