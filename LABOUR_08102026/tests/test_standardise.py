"""Offline tests for labour's standardised columns (indicators/labour/standardise.py).

    py -3 -W ignore -m indicators.labour.tests.test_standardise

House pattern: no pytest, a FAILURES list, main() -> 0/1.

THE STRONGEST CHECK IS THE TABLES' OWN ARITHMETIC. Within one published table
(country, survey, topic, classification, series_code, sex, age, education,
geography, locality, working-age base, period, measure) the categories a code
family covers must add up to the table's own Total row:

  * NEVER MORE than the Total (+2%): two codes that overlap -- a section and
    its own sub-item, a broad sector beside the sections it contains -- would
    break this, mapped or not.
  * EQUAL to the Total (within 2%) wherever EVERY category in the table was
    coded.

Measured on the corpus before being asserted (2026-10-15): 3,184 of 3,188
fully-coded tables across 28 countries close within 2%. That check found
INS Cameroun's "Primaire / Industrie / BTP / Commerce / Services" -- where
"Industrie" excludes construction and "Services" excludes trade, so the broad
codes are wrong beside sections -- and the PUB-vs-GOV+SOE overlap.
"""
from __future__ import annotations

import glob
import os
import sys

import pandas as pd

from indicators.labour.schema import LABOUR_COLUMNS
from indicators.labour.standardise import _TABLE, STD_COLUMNS, code_for, standardise

FAILURES: list[str] = []
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")

# (country, topic, period, measure, sex) whose categories do not add to the
# table's Total for a reason that is not the mapping.
KNOWN_ARITHMETIC = {
    # Published (Arabic tables read from the rendered page): the 20 female
    # industry shares sum to 104.1, not 100.
    ("Libya", "industry", "2022", "share", "female"),
    ("Libya", "industry", "2022", "count", "female"),
    ("Libya", "industry", "2022", "share", "total"),
    ("Libya", "industry", "2022", "count", "total"),
    ("Libya", "industry", "2022", "share", "male"),
    ("Libya", "industry", "2022", "count", "male"),
    # Published: INE's 2014 occupation table sums to 130,424 against a Total of
    # 133,123 (armed forces and not-stated are not printed as rows).
    ("Cabo_Verde", "occupation", "2014", "count", "total"),
}


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


def test_label_traps():
    cases = [
        # (topic, label, classification, code) -- "" = deliberately NOT mapped
        ("industry", "Agriculture, forestry and fishing", "ISIC Rev.4", "A"),
        ("industry", "Agricultura, Produção Animal, Caça, Floresta e Pesca", "National", "A"),
        ("industry", "A. Agriculture, forestry, fishing", "ISIC Rev.4", "A"),     # letter prefix
        ("industry", "X - Not elsewhere classified", "ISIC Rev.4", "_X"),
        ("industry", "Arts,entertainment and recreation", "National", "R"),       # Sudan, no space
        ("industry", "Electricity, gas and water", "National", "DE"),
        ("industry", "Eletricidade, Gás, Vapor, Água quente e fria e ar frio", "National", "D"),
        ("industry", "Transport, storage & communication", "National", "HJ"),
        ("industry", "Trade", "National", "GI"),                 # Stats SA QLFS: trade incl. hotels
        ("industry", "الأنشطة المالية وانشطة التأمين", "National", "K"),        # hamza folding
        ("industry", "Transport", "National", ""),               # H in Madagascar, H+J in QLFS
        ("industry", "Finance", "National", ""),                 # K-N in QLFS
        ("industry", "Other services", "National", ""),          # residual
        ("industry", "Mines et énergie", "National", ""),        # B+D mixture
        ("industry", "Agriculture, forestry, fishing and mining", "National", ""),
        ("industry", "Manufacturing - Sugar", "National", ""),   # sub-item
        ("industry", "Wholesale & retail trade - Retail", "National", ""),  # sub-item behind an open rule
        ("industry", "Les industries non manufacturières", "National", ""),
        ("occupation", "Service/Sales Workers", "National", "ISCO_5"),
        ("occupation", "Legislators, senior officials and managers", "National", "ISCO_1"),
        ("occupation", "الفنيون ومساعدو الأخصائيين", "National", "ISCO_3"),
        ("occupation", "Managers, Professionals, Technicians (ISCO 1,2,3)", "ISCO-08", "ISCO_1_2_3"),
        ("occupation", "Technicians and assoc", "National", ""),  # truncated by SNBS: never completed
        ("occupation", "Cadres moyens", "National", ""),          # Morocco's national scheme, not ISCO
        ("occupation", "Technicians and associate professionals (including police and armed forces)",
         "National", ""),
        ("employment_status", "Self-employed with employees", "ICSE-93", "EMP"),
        ("employment_status", "Self-Employed", "National", ""),   # scope varies by office
        ("employment_status", "Apprenti, aide familiale", "National", ""),
        ("employment_status", "Agric contributing family worker", "National", ""),  # sub-item
        ("employment_status", "Salarié public", "National", ""),
        ("employment_status", "Workers not classifiable by status", "ICSE-93", "_X"),
        ("sector", "Entreprises publiques et semi- publiques", "National", "SOE"),
        ("sector", "Central Government", "National", ""),          # a component of GOV
        ("formality", "Informal employment (excluding agriculture)", "National", ""),
        ("formality", "Informal", "National", ""),                 # jobs or units? not said
        ("hours", "De 1 hora a menos de 15 horas", "Not applicable", "H1T14"),
        ("hours", "99 and Above", "Not applicable", "H_GE99"),
        ("activity_status", "Economically inactive", "Not applicable", "OLF"),
    ]
    for topic, label, cls, want in cases:
        check(f"code_for({topic}, {label!r})", code_for(topic, label, cls), want)


def _rows(**cols) -> pd.DataFrame:
    n = max([len(v) for v in cols.values() if isinstance(v, list)] or [1])
    base = {c: "" for c in LABOUR_COLUMNS}
    base.update(country="Testland", iso3="TST", indicator="Labour", survey="LFS 2024",
                topic="industry", classification="National", sex="total", age_group="Total",
                education="Total", geography="Total country", locality="all",
                locality_label="Total", working_age_base="15+", period="2024",
                frequency="annual", measure="share", value="10", unit="percent",
                source_file="f.pdf")
    rows = []
    for i in range(n):
        r = dict(base)
        for k, v in cols.items():
            r[k] = v[i] if isinstance(v, list) else v
        rows.append(r)
    return pd.DataFrame(rows)


def test_context_rules():
    # broad words are broad only in a table of broad sectors (INS Cameroun)
    cm = _rows(characteristic=["Primaire", "Industrie", "BTP", "Commerce", "Services", "Total"],
               value=["40", "10", "5", "20", "25", "100"])
    check("broad beside sections", standardise(cm)["category_code"].tolist(),
          ["", "", "F", "G", "", "_T"])
    gh = _rows(characteristic=["Agriculture", "Industry", "Services", "Total"],
               value=["40", "20", "40", "100"])
    check("broad-only table", standardise(gh)["category_code"].tolist(),
          ["BROAD_AGR", "BROAD_IND", "BROAD_SER", "_T"])
    # bare Agriculture beside its own parts is a part, not the sector
    ml = _rows(characteristic=["Agriculture", "Elevage", "Pêche", "Total"], value=["30", "5", "5", "40"])
    check("agriculture beside its parts", standardise(ml)["category_code"].tolist()[0], "")
    # Stats SA's Elementary excludes the domestic workers listed beside it
    za = _rows(country="South_Africa", iso3="ZAF", topic="occupation",
               characteristic=["Elementary", "Domestic worker"])
    check("ZA elementary", standardise(za)["category_code"].tolist(), ["", ""])


def test_ids_and_scale():
    df = _rows(characteristic=["Construction", "Construction"], education=["Total", "Primary"],
               measure="count", unit="thousand_persons", value="12.5", age_group="15 à 24 ans")
    s = standardise(df)
    check("series_id", s["series_id"].tolist(), ["LAB_IND_F_COUNT_T_Y15T24_W15_GE", ""])
    check("value_std", s["value_std"].tolist(), [12500.0, 12500.0])
    check("age_code", s["age_code"].tolist(), ["Y15T24", "Y15T24"])


def _corpus() -> pd.DataFrame:
    return pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, low_memory=False)
                      for f in glob.glob(os.path.join(OUT_DIR, "*.csv"))], ignore_index=True)


def _family(topic: str, code: str) -> str:
    if code in ("", "_T", "_U", "_X"):
        return ""
    if topic == "industry":
        if code in ("PRIMARY", "SECONDARY", "TERTIARY"):
            return "p3"
        return "ais" if code.startswith("BROAD") else "sec"
    if topic == "formality":
        return "jobs" if code in ("INFEMP", "FORMEMP") else "units"
    if topic == "activity_status":
        return "lf" if code == "LF" else "act"
    return topic


def test_corpus():
    d = _corpus()
    missing = [c for c in STD_COLUMNS if c not in d.columns]
    check("standardised columns present (run: py -3 -m tools.standardise labour)", missing, [])
    if missing:
        return
    ids = d.loc[d["series_id"] != "", "series_id"]
    check("unsafe series_id", sorted(ids[~ids.str.match(r"^[A-Z][A-Z0-9_]*$")].unique())[:5], [])
    p = d[d["is_preferred"] == "True"]
    k = ["country", "series_id", "geography", "locality", "locality_label", "period"]
    check("one preferred row per observation", int(p.duplicated(k).sum()), 0)
    check("preferred rows all carry a series_id", int((p["series_id"] == "").sum()), 0)

    d = d.assign(v=pd.to_numeric(d["value"]),
                 fam=[_family(t, c) for t, c in zip(d["topic"], d["category_code"])])
    over, off, complete = set(), set(), 0
    for key, g in d.groupby(_TABLE, sort=False):
        tot = g.loc[g["category_code"] == "_T", "v"]
        if len(tot) != 1 or tot.iloc[0] <= 0:
            continue
        T = tot.iloc[0]
        unk = g[g["category_code"].isin(["_U", "_X"])]
        blanks = int((g["category_code"] == "").sum())
        kk = dict(zip(_TABLE, key))
        tag = (kk["country"], kk["topic"], kk["period"], kk["measure"], kk["sex"])
        for fam, h in g[g["fam"] != ""].groupby("fam"):
            if fam == "sec" and (h["category_code"] == "A").any():
                h = h[~h["category_code"].isin(["A02", "A03"])]
            if fam == "sector" and h["category_code"].isin(["GOV", "SOE"]).any():
                h = h[h["category_code"] != "PUB"]
            r = (h["v"].sum() + unk["v"].sum()) / T
            if r > 1.02 + 0.5 / T:
                over.add(tag)
            if blanks == 0 and fam not in ("lf",):
                complete += 1
                if abs(r - 1) > 0.02:
                    off.add(tag)
    check("NEW tables where coded categories exceed the Total", sorted(over - KNOWN_ARITHMETIC), [])
    check("NEW fully-coded tables not adding to their Total", sorted(off - KNOWN_ARITHMETIC), [])
    check("fully-coded tables checked (>= 3000)", complete >= 3000, True)


def test_published_columns_untouched():
    path = sorted(glob.glob(os.path.join(OUT_DIR, "*.csv")))[0]
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    s = standardise(d)
    same = d[LABOUR_COLUMNS].reset_index(drop=True).equals(s[LABOUR_COLUMNS].reset_index(drop=True))
    check(f"published columns unchanged ({os.path.basename(path)})", same, True)


def main() -> int:
    for fn in (test_label_traps, test_context_rules, test_ids_and_scale, test_corpus,
               test_published_columns_untouched):
        try:
            fn()
        except Exception as e:
            FAILURES.append(f"{fn.__name__} raised {type(e).__name__}: {e}")
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}):")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("all standardise checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
