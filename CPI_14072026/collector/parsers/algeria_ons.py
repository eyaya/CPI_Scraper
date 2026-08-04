"""Parser for the Algeria ONS monthly IPC note PDF (Tier 3).

IMPORTANT — classification: ONS Algeria does NOT use the COICOP 12/13 divisions.
It reports a NATIONAL 8-group nomenclature (Transports & Communication combined;
Education-Culture-Loisirs combined; 'Divers (N.D.A.)' a catch-all). We capture it
EXACTLY as reported — native French labels, native grouping — and do NOT force it
onto COICOP. The `coicop_code` here is an Algeria-internal ordering (00 = Ensemble,
01..08 = the 8 groups), not a COICOP division code.

The note's headline table gives, per group: Poids | Indice <month> | MoM % |
YoY % | annual %. The 'Alimentation' label wraps across lines, so we reconstruct
rows from word coordinates (carry a wrapped label to its number row). We emit the
index + MoM + YoY for the report month (base 2001 = 100). One PDF = one month.
"""
from __future__ import annotations
import os
import re
import unicodedata
import pdfplumber
import pandas as pd

_BASE_PERIOD = "2001 = 100"
_MONTHS = {"janvier": "01", "fevrier": "02", "mars": "03", "avril": "04",
           "mai": "05", "juin": "06", "juillet": "07", "aout": "08",
           "septembre": "09", "octobre": "10", "novembre": "11", "decembre": "12"}
# (code, native label as published, keyword on the normalised label) — first match wins
_GROUPS = [
    ("00", "Ensemble", "ensemble"),
    ("01", "Alimentation et boissons non alcoolisées", "alimentation"),
    ("02", "Habillement - Chaussures", "habillement"),
    ("03", "Logement - Charges", "logement"),
    ("04", "Meubles et Articles d'Ameublement", "meubles"),
    ("05", "Santé - Hygiène Corporelle", "sante"),
    ("06", "Transports et Communication", "transport"),
    ("07", "Education - Culture - Loisirs", "education"),
    ("08", "Divers (N.D.A.)", "divers"),
]
_IS_NUM = re.compile(r"-?\d[\d ]*,\d+%?$")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    return "".join(c for c in s if not unicodedata.combining(c)).lower()


def _val(t: str) -> float:
    return float(t.replace(" ", "").replace(",", ".").replace("%", ""))


def _code(label: str):
    n = _norm(label)
    for code, clabel, kw in _GROUPS:
        if kw in n:
            return code, clabel
    return None


def parse(pdf_path: str) -> pd.DataFrame:
    def _month(text, pat):
        for mm, yy in re.findall(pat, text, re.IGNORECASE):
            if _norm(mm) in _MONTHS:
                return f"{yy}-{_MONTHS[_norm(mm)]}"
        return None

    with pdfplumber.open(pdf_path) as pdf:
        full = " ".join(p.extract_text() or "" for p in pdf.pages)
        # report month: prefer the filename (IPC_<Month><Year>), else "mois d'<month> <year>"
        period = (_month(os.path.basename(pdf_path), r"([A-Za-zûéèêàâäîïôùç]+?)_?\s*(20\d\d)")
                  or _month(full, r"mois\s+d[e'’]?\s*([a-zûéèêàâäîïôùç]+)\s+(20\d\d)"))
        page = next((p for p in pdf.pages
                     if all(k in (p.extract_text() or "") for k in ("ENSEMBLE", "Divers", "Habillement"))), None)
        words = page.extract_words() if page else []
    if not period or not words:
        raise ValueError("Algeria IPC: report month or group table not found")

    rows = {}
    for w in words:
        rows.setdefault(round(w["top"]), []).append(w)
    merged = []
    for k in sorted(rows):
        if merged and k - merged[-1][0] <= 3:
            merged[-1][1].extend(rows[k])
        else:
            merged.append([k, list(rows[k])])

    picked, pending = {}, ""
    for _, ws in merged:
        ws = sorted(ws, key=lambda w: w["x0"])
        nums = [w["text"] for w in ws if _IS_NUM.match(w["text"])]
        labs = " ".join(w["text"] for w in ws if not _IS_NUM.match(w["text"])).strip()
        if len(nums) >= 4:
            hit = _code(labs or pending)
            pending = ""
            if hit and hit[0] not in picked:
                picked[hit[0]] = (hit[1], _val(nums[1]), _val(nums[2]), _val(nums[3]))
        elif labs:
            pending = (pending + " " + labs).strip() if pending else labs

    missing = [c for c, _, _ in _GROUPS if c not in picked]
    if missing:
        raise ValueError(f"Algeria IPC groups incomplete: missing {missing}")

    records = []
    for code, (label, idx, mom, yoy) in picked.items():
        records.append((code, label, period, "index", idx, "Index", _BASE_PERIOD))
        records.append((code, label, period, "inflation_mom", mom, "percent", ""))
        records.append((code, label, period, "inflation_yoy", yoy, "percent", ""))
    out = pd.DataFrame.from_records(
        records, columns=["coicop_code", "coicop_label", "period", "measure",
                          "value", "unit", "base_period"])
    out["geography"] = "National"
    out["frequency"] = "monthly"
    return out
