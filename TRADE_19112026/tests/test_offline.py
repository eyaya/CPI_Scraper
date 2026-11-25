"""Offline tests for the merchandise-trade package.

    py -3 -W ignore -m indicators.trade.tests.test_offline

House pattern: no pytest, a FAILURES list, main() -> 0/1.
"""
from __future__ import annotations

import glob
import os
import sys

import pandas as pd

from core.schema_base import ValidationError
from indicators.trade import schema
from indicators.trade.parsers import REGISTRY
from indicators.trade.parsers._common import row, scale_from_text
from indicators.trade.standardise import commodity_code, standardise

FAILURES: list[str] = []
HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)


def check(label, got, want):
    if got != want:
        FAILURES.append(f"{label}: got {got!r}, want {want!r}")


def _frame(rows, **meta):
    df = pd.DataFrame(rows)
    base = dict(country="Senegal", iso3="SEN", indicator="Trade", source_type="pdf", source_url="u",
                source_file="f", extracted_at="t")
    base.update(meta)
    for k, v in base.items():
        df[k] = v
    return df


def _headline(n=12, mult=1e6):
    out = []
    for i in range(n):
        p, e, m = f"2024-{i % 12 + 1:02d}", 100 + i, 150 + 2 * i
        out += [row(tradeflow="export", period=p, frequency="monthly", value=e, unit="XOF", unit_multiplier=mult,
                    price_basis="fob"),
                row(tradeflow="import", period=p, frequency="monthly", value=m, unit="XOF", unit_multiplier=mult,
                    price_basis="cif"),
                row(tradeflow="balance", period=p, frequency="monthly", value=e - m, unit="XOF", unit_multiplier=mult)]
    return out


def _fails(df) -> bool:
    try:
        schema.validate_trade(df)
        return False
    except ValidationError:
        return True


def test_identity_guard():
    good = _headline()
    check("consistent flows pass", _fails(_frame(good)), False)
    unsigned = [dict(r, value=abs(r["value"])) for r in good]           # deficit printed without its sign
    check("lost balance sign caught", _fails(_frame(unsigned)), True)
    shifted = [dict(r, period=f"2024-{int(r['period'][5:]) % 12 + 1:02d}") if r["tradeflow"] == "import" else r
               for r in good]                                          # imports filed a month late
    check("month-shifted imports caught", _fails(_frame(shifted)), True)
    rounded = [dict(r, value=r["value"] + (0.4 if r["tradeflow"] == "balance" else 0)) for r in good]
    check("rounding inside half a printed unit passes", _fails(_frame(rounded)), False)


def test_vocabulary_and_totals():
    bad_world = [dict(r, partner="World") for r in _headline(1)]          # world total must be "All partners"
    check("world spelled 'All partners'", _fails(_frame(bad_world)), True)
    neg = [dict(r, value=-5.0) if r["tradeflow"] == "export" else r for r in _headline(1)]
    check("negative export rejected", _fails(_frame(neg)), True)
    try:
        row(tradeflow="export", period="2024", frequency="annual", value=1, unit="XOF", unit_multiplier=500)
        check("odd multiplier rejected", False, True)
    except ValueError:
        pass
    try:
        row(tradeflow="export", period="2024", frequency="annual", value=1, unit="XOF", commodity="Cocoa")
        check("commodity without classification rejected", False, True)
    except ValueError:
        pass
    # one figure printed in millions and in billions of one file is one observation
    a = row(tradeflow="export", period="2024", frequency="annual", value=1234.0, unit="XOF", unit_multiplier=1e6)
    b = dict(a, value=1.234, unit_multiplier=1e9)
    check("same figure at two scales deduped", len(schema.validate_trade(_frame([a, b]))), 1)
    c = dict(a, value=1300.0)
    check("conflicting figure rejected", _fails(_frame([a, c])), True)


def test_row_split_guard():
    """Labels that swallowed table cells fail; nomenclature indents and one number pass."""
    def one(**kw):
        base = row(tradeflow="export", period="2024", frequency="annual", value=1, unit="XAF")
        return _frame([dict(base, **kw)], iso3="COG")
    for bad in ({"partner": "Chine 1 491 951", "partner_type": "country"},
                {"partner": "Angola - -", "partner_type": "country"},
                {"partner": "CEPGL (cid:3)", "partner_type": "group"},
                {"commodity": "0 Total 140 884,8 160 749,4", "commodity_classification": "sitc1"},
                {"commodity": "1 136 929", "commodity_classification": "national"}):
        check(f"row-split caught: {list(bad.values())[0]!r}", _fails(one(**bad)), True)
    for ok in ({"partner": "Former Soviet Union (93 - 94)", "partner_type": "group"},
               {"commodity": "- - Effets personnels", "commodity_classification": "national"},
               {"commodity": "Moteurs d'une puissance n'excédant pas 37,5 W", "commodity_classification": "hs4"}):
        check(f"legitimate label passes: {list(ok.values())[0]!r}", _fails(one(**ok)), False)


def test_partner_filing_and_codes():
    from indicators.trade.parsers._common import classify_partner
    from indicators.trade.standardise import partner_code
    check("world total under another name", classify_partner("TOTAL WORLD NEW", "country"), (None, "world"))
    check("aggregate re-filed", classify_partner("Various Countries", "country")[1], "group")
    check("continent only as the whole label", [classify_partner(x, "country")[1] for x in
                                                 ("Afrique", "South Africa", "Central African Rep")],
          ["group", "country", "country"])
    check("partner codes", [partner_code(x, "country") for x in
                            ("Cote dIvoire", "CÔTE D'IVOIRE", "AT:AUSTRIA", "UG", "Chypre(pays)", "ZAIRE",
                             "Yugoslavia", "UK")],
          ["CIV", "CIV", "AUT", "UGA", "CYP", "COD", "", "GBR"])
    check("world partner code", partner_code("All partners", "world"), "_W")


def test_scale_and_codes():
    check("FCFA millions, WAEMU", scale_from_text("Valeurs en millions de FCFA", "SEN"), (1e6, "XOF"))
    check("FCFA billions, CEMAC", scale_from_text("en milliards de F CFA", "CMR"), (1e9, "XAF"))
    check("USD thousands", scale_from_text("in thousands of US dollars"), (1e3, "USD"))
    check("no scale stated", scale_from_text("Exports by destination", "KEN"), (None, None))
    check("codes", [commodity_code("27 - Mineral fuels", "hs2"), commodity_code("Live animals", "hs2", "1"),
                    commodity_code("Food", "sitc1", "0"), commodity_code("Cocoa", "national", "18"),
                    commodity_code("All products", "")],
          ["HS2_27", "HS2_01", "SITC1_0", "", "_T"])


def test_standardise_ids_and_preference():
    s = standardise(schema.validate_trade(_frame(_headline())))
    check("ids", sorted(s["series_id"].unique()),
          ["TRADE_BALANCE_T_W_XOF_M", "TRADE_EXPORT_T_W_XOF_FOB_M", "TRADE_IMPORT_T_W_XOF_CIF_M"])
    check("value_std applies the multiplier", float(s["value_std"].iloc[0]), 100e6)
    # A provisional figure in an old bulletin vs the revised one in a newer
    # bulletin (whose window ends later), even if the newer was extracted first.
    old = _frame(_headline(3), source_file="note_2024-03.pdf", extracted_at="z")
    new = _frame([dict(r, value=r["value"] + (1 if r["tradeflow"] == "export" else 0)) for r in _headline(6)],
                 source_file="note_2024-06.pdf", extracted_at="a")
    new.loc[new["tradeflow"] == "balance", "value"] += 1
    s = standardise(pd.concat([old, new], ignore_index=True))
    pref = s[s["is_preferred"] & (s["period"] == "2024-01") & (s["tradeflow"] == "export")]
    check("newest bulletin preferred", pref["source_file"].tolist(), ["note_2024-06.pdf"])


def test_ghana_replay():
    """The StatsBank tables on disk reproduce the published Ghana rows exactly."""
    import yaml
    d = yaml.safe_load(open(os.path.join(PKG, "sources", "ghana.yaml"), encoding="utf-8"))
    tables = [{**t, "path": os.path.join(PKG, "source_data", "Ghana", t["save_as"])} for t in d["api"]["tables"]]
    if not all(os.path.exists(t["path"]) for t in tables):
        FAILURES.append("ghana replay: saved StatsBank tables missing")
        return
    df = schema.validate_trade(_frame(REGISTRY["ghana_pxweb_trade"](tables)))
    out = pd.read_csv(os.path.join(PKG, "out", "ghana_trade.csv"), dtype=str, keep_default_na=False)
    out = out[out["source_url"].str.contains("statsbank", na=False)]
    k = [c for c in schema.KEY]
    a = df.assign(v=df["value"].astype(float)).set_index(k)["v"]
    b = out.assign(v=out["value"].astype(float)).set_index(k)["v"]
    j = pd.concat([a, b], axis=1, keys=["replay", "out"])
    check("ghana replay: same keys", (int(j["replay"].isna().sum()), int(j["out"].isna().sum())), (0, 0))
    check("ghana replay: same values", bool((j["replay"] - j["out"]).abs().max() == 0), True)


def test_outputs_valid():
    """Every written country file still validates on the published columns."""
    for f in sorted(glob.glob(os.path.join(PKG, "out", "*_trade.csv"))):
        d = pd.read_csv(f, dtype=str, keep_default_na=False)
        try:
            schema.validate_trade(d[schema.TRADE_COLUMNS])
        except ValidationError as e:
            FAILURES.append(f"{os.path.basename(f)}: {e}")


def main() -> int:
    for t in (test_identity_guard, test_vocabulary_and_totals, test_row_split_guard,
              test_partner_filing_and_codes, test_scale_and_codes,
              test_standardise_ids_and_preference, test_ghana_replay, test_outputs_valid):
        try:
            t()
        except Exception as e:  # noqa: BLE001
            FAILURES.append(f"{t.__name__}: {type(e).__name__}: {e}")
    if FAILURES:
        print(f"FAILED ({len(FAILURES)}):")
        for f in FAILURES:
            print("  -", f)
        return 1
    print("trade offline tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
