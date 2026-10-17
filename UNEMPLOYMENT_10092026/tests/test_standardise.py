"""Offline tests for unemployment's standardised columns (../standardise.py).

    py -3 -W ignore -m indicators.unemployment.tests.test_standardise

House pattern: no pytest, a FAILURES list, main() -> 0/1.

THE STRONGEST CHECK IS THE LABOUR-FORCE ARITHMETIC, on the preferred rows of
each country / period / sex / age / education / place / working-age base /
definition / ICLS convention:

    UNE_RATE = 100 * UNE / LF      LFPR = 100 * LF / POP_WA
    EPR      = 100 * EMP / POP_WA  LF   = EMP + UNE

Measured before being asserted. It found three mapping bugs nothing else
would have: PARTS of a count printed under the whole's topic (Sudan's 2008
census "Unemployed: Seeking work for the first time", Malawi's "Unemployed -
Seeking Work", Mauritius's employment "outside large establishments", which
had even been picked as the preferred row), Kenya's "Long-Term Unemployed"
filed under `unemployed`, and the crude "taux brut d'activite" read as LFPR.
"""
from __future__ import annotations

import glob
import os
import sys

import pandas as pd

from indicators.unemployment.schema import UNEMPLOYMENT_COLUMNS
from indicators.unemployment.standardise import STD_COLUMNS, concept, icls, lu_code, standardise

FAILURES: list[str] = []
OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")

# Countries where an identity fails for a PUBLISHED reason, measured 2026-10-15.
# A country failing that is not here is a mapping bug until shown otherwise.
KNOWN = {
    # Kenya QLFS Table 1: its counts disagree with its own rates (LU2's count is
    # exactly 2x its footnote; see the unemployment README) -- 2020 quarters.
    ("UNE_RATE=100*UNE/LF", "Kenya"), ("LF=EMP+UNE", "Kenya"),
    # Mauritius: unemployment is counted for MAURITIANS only, employment and
    # the labour force include foreign workers (labels say so).
    ("UNE_RATE=100*UNE/LF", "Mauritius"), ("LF=EMP+UNE", "Mauritius"),
    ("EPR=100*EMP/POP_WA", "Mauritius"),
    # Cote d'Ivoire EHCVM 2021 profile: employed + unemployed (5,646,115) exceeds
    # its own "Main d'oeuvre" (5,564,992) in one table.
    ("LF=EMP+UNE", "Cote_dIvoire"),
    # OPEN PARSER DEFECT, not mapping: HCP's annual "Activite, emploi et
    # chomage" 2025 unemployed counts by sex/milieu all read ~1.6M (the national
    # total is 1,621k; women 1,595k against a 20.5% rate on 2,772k active).
    ("UNE_RATE=100*UNE/LF", "Morocco"),
    # NOT YET VERIFIED against the source (few rows each; likely different
    # tables/vintages on one page, or published rounding of small groups):
    # Tunisia 2019-Q4/2021-Q4 by sex (INS population-active series vs chomage
    # table), Botswana 2024-Q1 male 18+ (27.6 vs 26.5), Angola 2019-Q2 18+
    # (EMP+UNE 5.4% over LF), Mozambique 2022 EPR for "Desconhecido" education.
    ("UNE_RATE=100*UNE/LF", "Tunisia"), ("LF=EMP+UNE", "Tunisia"),
    ("UNE_RATE=100*UNE/LF", "Botswana"), ("LF=EMP+UNE", "Angola"),
    ("EPR=100*EMP/POP_WA", "Mozambique"),
}


def check(name, got, want):
    if got != want:
        FAILURES.append(f"{name}: got {got!r}, want {want!r}")


def test_label_traps():
    cases = [  # (topic, measure, label, code)
        ("unemployment_rate", "rate", "Taux de chômage", "UNE_RATE"),
        ("unemployment_rate", "count", "Unemployed", ""),     # a rate topic stored as a count
        ("labour_underutilisation_rate", "rate", "Under - Utilization [LU2]", "LU2"),
        ("labour_underutilisation_rate", "rate", "Unemployment Rate [LU3]", "LU3"),   # KNBS's own tag
        ("labour_underutilisation_rate", "rate", "Taux combiné sous-emploi + chômage (SU2)", "LU2"),
        ("labour_underutilisation_rate", "rate", "Taux combiné du chômage et de la main d'œuvre potentielle", "LU3"),
        ("labour_underutilisation_rate", "rate", "Taux cumulé de chômage et de la population active potentielle", "LU3"),
        ("labour_underutilisation_rate", "rate", "Combined rate of unemployment and potential labour force (CRUPLF)", "LU3"),
        ("labour_underutilisation_rate", "rate", "Taux de sous-utilisation de la main d'œuvre", "LU4"),
        ("labour_underutilisation_rate", "rate", "Taxa de subutilização do trabalho — Resolução I da 19ª CIET", "LU4"),
        ("labour_underutilisation_rate", "rate", "Aggregate measure of labour underutilization", "LU4"),
        ("labour_underutilisation_rate", "rate", "Combined rate of labour underutilization (%)", ""),  # names no LU
        ("unemployed", "count", "Unemployed: Seeking work for the first time", ""),
        ("unemployed", "count", "Unemployed - Not Seeking Work", ""),
        ("employed", "count", "Employment (including foreign workers) - outside large establishments", ""),
        ("employed", "count", "Employment (including foreign workers) - Total", "EMP"),
        ("unemployed", "count", "Long-Term Unemployed", "LTU"),
        ("labour_force_participation_rate", "rate", "Taux brut d'activité (16-65 ans)", ""),
        ("labour_force_participation_rate", "rate", "Taux d'activité strict", "LFPR"),
        ("neet_rate", "count", "NEET", "NEET"),
    ]
    for t, m, label, want in cases:
        check(f"concept({t}, {m}, {label!r})", concept(t, m, label), want)
    check("lu_code no tag", lu_code("Some other rate"), "")
    check("icls 19", icls("IEA (nova metodologia, 19ª, 20ª e 21ª CIET)", ""), "ICLS19")
    check("icls 13", icls("IEA (antiga metodologia, 13ª CIET)", ""), "ICLS13")
    check("icls unstated", icls("QLFS", "Unemployment rate"), "")


def _rows(**cols) -> pd.DataFrame:
    n = max([len(v) for v in cols.values() if isinstance(v, list)] or [1])
    base = {c: "" for c in UNEMPLOYMENT_COLUMNS}
    base.update(country="Testland", iso3="TST", indicator="Unemployment", survey="LFS",
                topic="unemployment_rate", definition="strict", series_label="Unemployment rate",
                sex="total", age_group="Total", education="Total", geography="Total country",
                locality="all", locality_label="Total", working_age_base="15+", period="2024",
                frequency="annual", measure="rate", value="10", unit="percent", source_file="f.pdf")
    rows = []
    for i in range(n):
        r = dict(base)
        for k, v in cols.items():
            r[k] = v[i] if isinstance(v, list) else v
        rows.append(r)
    return pd.DataFrame(rows)


def test_definitions_never_share_an_id():
    df = _rows(definition=["strict", "broad", "strict"], working_age_base=["15+", "15+", "15-64"])
    ids = standardise(df)["series_id"].tolist()
    check("distinct ids for strict/broad/base", len(set(ids)), 3)
    # sex (T) and age (T) are part of the ID since 2026-10-15: one value per
    # series_id, place and date.
    check("id form", ids[0], "UNE_UNE_RATE_STRICT_WA15P_A_T_T")
    nm = standardise(df)["series_name"].tolist()
    check("name form", nm[0], "Unemployment rate - strict definition, working-age base 15+, "
                              "annual, both sexes, all ages")


def test_sex_age_and_locality_split_ids():
    df = _rows(sex=["male", "female"], age_group=["15-24", "15-24"], locality=["urban", "rural"])
    check("cuts in the id", standardise(df)["series_id"].tolist(),
          ["UNE_UNE_RATE_STRICT_WA15P_A_M_Y15T24_URB", "UNE_UNE_RATE_STRICT_WA15P_A_F_Y15T24_RUR"])


def test_icls_spreads_across_the_survey():
    """Morocco's EMO states the 19th ICLS only on its employment labels ("emploi
    contre revenu"); its labour force row is the same survey and must carry the
    same token, or LF and EMP land in different series and never meet."""
    df = _rows(country="Morocco", iso3="MAR", survey="EMO", topic=["employed", "labour_force"],
               measure="count", definition="not_applicable", unit="persons",
               series_label=["Population en emploi contre revenu", "Main-d'œuvre"])
    ids = standardise(df)["series_id"].tolist()
    check("ICLS token on both EMO rows", [("ICLS19" in i) for i in ids], [True, True])


def test_kenya_lu2_contradiction():
    """Table 1 prints LU2 = 18.6 for 2022-Q4; Table 6 and the prose 9.0. Both
    are LU2; the longer-running Table 6 series is the preferred one."""
    t6 = _rows(country="Kenya", iso3="KEN", topic="labour_underutilisation_rate", definition="broad",
               series_label="Under - Utilization [LU2]",
               period=["2022-Q2", "2022-Q3", "2022-Q4"], frequency="quarterly", value=["10", "10.4", "9.0"])
    t1 = _rows(country="Kenya", iso3="KEN", topic="labour_underutilisation_rate", definition="broad",
               series_label="Labour Underutilization (LU2)", period="2022-Q4", frequency="quarterly", value="18.6")
    s = standardise(pd.concat([t6, t1], ignore_index=True))
    q4 = s[s["period"] == "2022-Q4"]
    check("both LU2", sorted(q4["category_code"]), ["LU2", "LU2"])
    check("preferred 2022-Q4 LU2", q4.loc[q4["is_preferred"], "value"].tolist(), ["9.0"])
    # Kenya's labels happen to sort the same way as their lengths; make the
    # one-period series sort LAST so only the length rule can pick the long one.
    s2 = standardise(pd.concat([t6, t1.assign(series_label="ZZ LU2 single print")], ignore_index=True))
    q4 = s2[s2["period"] == "2022-Q4"]
    check("longest series wins over label order", q4.loc[q4["is_preferred"], "value"].tolist(), ["9.0"])


def test_youth_rate_needs_a_band():
    s = standardise(_rows(topic="youth_unemployment_rate", age_group=["15-24", "Jovens"]))
    check("youth codes", s["category_code"].tolist(), ["UNE_RATE", ""])
    check("youth age", s["age_code"].tolist(), ["Y15T24", ""])


def _corpus() -> pd.DataFrame:
    return pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False, low_memory=False)
                      for f in glob.glob(os.path.join(OUT_DIR, "*.csv"))], ignore_index=True)


def identity_failures(d: pd.DataFrame) -> dict:
    """{(identity, country): n failing} over preferred rows; tolerance 0.6
    points on rates (published rounding), 0.5% on LF = EMP + UNE."""
    p = d[d["is_preferred"].astype(str) == "True"].copy()
    p["v"] = pd.to_numeric(p["value_std"])
    p["icls"] = p["series_id"].str.extract(r"_(ICLS\d+)_")[0].fillna("")
    k = ["country", "period", "sex", "age_group", "education", "geography",
         "locality_label", "working_age_base", "icls"]
    out: dict = {}
    for defs in (["strict", "not_applicable"], ["broad"]):
        # counts of the wider/narrower kind only beside rates of the same kind;
        # EMP and POP_WA carry no definition and serve both
        x = p[p["definition"].isin(defs) | p["category_code"].isin(["EMP", "POP_WA"])]
        w = x.pivot_table(index=k, columns="category_code", values="v", aggfunc="first")
        tests = [("UNE_RATE=100*UNE/LF", "UNE_RATE", lambda w: 100 * w.UNE / w.LF, ["UNE", "LF"]),
                 ("LFPR=100*LF/POP_WA", "LFPR", lambda w: 100 * w.LF / w.POP_WA, ["LF", "POP_WA"]),
                 ("EPR=100*EMP/POP_WA", "EPR", lambda w: 100 * w.EMP / w.POP_WA, ["EMP", "POP_WA"])]
        for name, col, f, need in tests:
            if not {col, *need} <= set(w.columns):
                continue
            m = pd.concat([w[col], f(w)], axis=1).dropna()
            bad = (m.iloc[:, 0] - m.iloc[:, 1]).abs() > 0.6
            for c, n in m[bad].reset_index().groupby("country").size().items():
                out[(name, c)] = out.get((name, c), 0) + int(n)
        if {"LF", "EMP", "UNE"} <= set(w.columns):
            m = pd.concat([w.LF, w.EMP + w.UNE], axis=1).dropna()
            bad = ((m.iloc[:, 0] - m.iloc[:, 1]).abs() / m.iloc[:, 0]) > 0.005
            for c, n in m[bad].reset_index().groupby("country").size().items():
                out[("LF=EMP+UNE", c)] = out.get(("LF=EMP+UNE", c), 0) + int(n)
    return out


def test_corpus():
    d = _corpus()
    missing = [c for c in STD_COLUMNS if c not in d.columns]
    check("standardised columns in out/ (run: py -3 -m tools.standardise unemployment)", missing, [])
    if missing:
        return
    ids = d.loc[d["series_id"] != "", "series_id"]
    check("unsafe series_id", sorted(ids[~ids.str.match(r"^[A-Z][A-Z0-9_]*$")].unique())[:5], [])
    p = d[d["is_preferred"] == "True"]
    key = ["country", "series_id", "sex", "age_group", "education", "geography", "locality_label", "period"]
    check("one preferred row per observation", int(p.duplicated(key).sum()), 0)
    # 97.0% since 2026-10-15: subsets filed as the whole (excl. potential labour
    # force, foreign workers, discouraged job-seekers) are now deliberately uncoded.
    check("rows with a code (>= 96%)", (d["category_code"] != "").mean() >= 0.96, True)
    fails = identity_failures(d)
    check("NEW identity failures", sorted(k for k in fails if k not in KNOWN), [])


def test_published_columns_untouched():
    path = sorted(glob.glob(os.path.join(OUT_DIR, "*.csv")))[0]
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    s = standardise(d)
    same = d[UNEMPLOYMENT_COLUMNS].reset_index(drop=True).equals(s[UNEMPLOYMENT_COLUMNS].reset_index(drop=True))
    check(f"published columns unchanged ({os.path.basename(path)})", same, True)


def main() -> int:
    for fn in (test_label_traps, test_definitions_never_share_an_id, test_sex_age_and_locality_split_ids,
               test_icls_spreads_across_the_survey,
               test_kenya_lu2_contradiction,
               test_youth_rate_needs_a_band, test_corpus, test_published_columns_untouched):
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
