"""Shared orchestrator: discover -> download -> extract -> parse -> normalise ->
validate -> write tidy CSV, for one source descriptor.

This harness is indicator-agnostic. Each indicator supplies its own paths,
parser registry and schema through a `Pipeline` config and calls `run_cli`; see
`indicators/<indicator>/pipeline.py`, e.g.:

    python -m indicators.gdp.pipeline south_africa
    python -m indicators.cpi.pipeline --all
"""
from __future__ import annotations
import argparse
import dataclasses
import datetime as dt
import inspect
import os
import sys
import glob
from typing import Callable
from urllib.parse import unquote, urlparse
import yaml
import pandas as pd

from . import discover, fetch, pxweb


@dataclasses.dataclass
class Pipeline:
    """Everything indicator-specific the shared harness needs, injected by each
    indicator's `pipeline.py`."""
    sources_dir: str          # sources/*.yaml descriptors
    source_data_dir: str      # retained raw NSO files, one folder per country
    out_dir: str              # tidy <country>_<indicator>.csv outputs
    registry: dict            # parser id -> parse(local[, extras]) -> DataFrame
    columns: list             # the indicator schema's column order
    sort_cols: list           # columns to sort the output by
    validate: Callable        # (df, descriptor) -> validated df


_CFG: Pipeline | None = None   # set once per process by run_cli()/configure()


def configure(cfg: Pipeline) -> None:
    global _CFG
    _CFG = cfg


def load_descriptor(name: str) -> dict:
    path = os.path.join(_CFG.sources_dir, f"{name}.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def collect(name: str) -> str:
    """Collect one source. If it fails and the descriptor defines a `fallback`
    (an alternative source keyed the same way — discover/parser/source_type/…),
    retry with the fallback merged over the primary (e.g. Kenya: KNBS PDF ->
    CBK headline inflation when KNBS is down)."""
    d = load_descriptor(name)
    try:
        return _run(d)
    except Exception as e:
        fb = d.get("fallback")
        if not fb:
            raise
        print(f"[{d['country']}] primary failed: {type(e).__name__}: {e} "
              f"-> trying fallback", file=sys.stderr)
        merged = {k: v for k, v in d.items() if k != "fallback"}
        merged.update(fb)
        return _run(merged)


def _run(d: dict) -> str:
    country = d["country"]
    print(f"[{country}] tier {d['tier']} / {d['source_type']}")

    verify = d.get("verify_ssl", True)
    country_dir = os.path.join(_CFG.source_data_dir, country)

    # Tier-1 API sources fetch data directly (no file to discover/download);
    # the raw JSON response is retained as the source document.
    if d["source_type"] == "api":
        api = d["api"]
        os.makedirs(country_dir, exist_ok=True)
        # Multi-table API (e.g. GDP split across production/expenditure x
        # annual/quarterly PxWeb tables): fetch each, retain each raw json, and
        # hand the parser the list of {path, approach, ...} table descriptors.
        if api.get("tables"):
            saved = []
            for t in api["tables"]:
                raw = pxweb.fetch(t["table_url"], t["dimensions"], verify=verify)
                local = os.path.join(country_dir, t["save_as"])
                with open(local, "wb") as fh:
                    fh.write(raw)
                print(f"[{country}] source saved: source_data/{country}/"
                      f"{t['save_as']} ({len(raw):,} bytes)")
                saved.append({**t, "path": local})
            df = _CFG.registry[d["parser"]](saved)
            return _write_output(d, country, saved[0]["table_url"],
                                 saved[0]["path"], df)
        url = api["table_url"]
        print(f"[{country}] api: {url}")
        raw = pxweb.fetch(url, api["dimensions"], verify=verify)
        local = os.path.join(
            country_dir, api.get("save_as", f"{country}_{d['indicator']}_api.json")
        )
        with open(local, "wb") as fh:
            fh.write(raw)
        print(
            f"[{country}] source saved: source_data/{country}/"
            f"{os.path.basename(local)} ({len(raw):,} bytes)"
        )
        return _finish(d, country, url, local)

    # 1. discover
    disc = d["discover"]
    method = disc.get("method", "page_scrape")
    if method == "probe_monthly":
        today = dt.date.today()
        url = discover.probe_monthly_url(
            url_template=disc["url_template"],
            start_year=today.year,
            start_month=today.month,
            lookback_months=disc.get("lookback_months", 6),
            tag_format=disc.get("tag_format", "%Y%m"),
        )
    elif method == "page_scrape":
        url = discover.find_download_link(
            page_url=disc["page_url"],
            link_contains=disc["link_contains"],
            prefer_format=disc.get("prefer_format"),
            base_url=disc.get("base_url"),
            verify=verify,
            impersonate=disc.get("impersonate"),
        )
    elif method == "latest_dated":
        url = discover.latest_dated_link(
            page_url=disc["page_url"],
            link_contains=disc["link_contains"],
            verify=verify,
        )
    elif method == "latest_dated_pdf":
        url = discover.latest_dated_pdf(
            index_url=disc["index_url"],
            link_contains=disc["link_contains"],
            pdf_contains=disc.get("pdf_contains"),
            year=dt.date.today().year,
            verify=verify,
        )
    elif method == "latest_year_file":
        url = discover.latest_year_file(
            page_url=disc["page_url"],
            link_contains=disc["link_contains"],
            verify=verify,
        )
    elif method == "static_url":
        url = disc["url"]          # a stable page/file URL (e.g. an HTML data table)
    elif method == "inege_ipc_latest":
        url = discover.inege_ipc_latest(
            url_template=disc["url_template"],
            impersonate=disc.get("impersonate", "chrome124"),
            lookback_months=disc.get("lookback_months", 6),
            verify=verify,
        )
    elif method == "gsheet_from_page":
        url = discover.gsheet_export_from_page(disc["page_url"], verify=verify)
    elif method == "latest_dmy_file":
        url = discover.latest_dmy_file(
            page_url=disc["page_url"],
            link_contains=disc["link_contains"],
            verify=verify,
        )
    elif method == "latest_quarter_file":
        url = discover.latest_quarter_file(
            page_url=disc["page_url"],
            link_contains=disc["link_contains"],
            verify=verify,
        )
    elif method == "latest_datestamp_file":
        url = discover.latest_datestamp_file(
            page_url=disc["page_url"],
            link_contains=disc["link_contains"],
            verify=verify,
        )
    elif method == "latest_quarter_link":
        url = discover.latest_quarter_link(
            page_url=disc["page_url"],
            link_contains=disc["link_contains"],
            verify=verify,
        )
    elif method == "latest_quarter_two_hop":
        url = discover.latest_quarter_two_hop(
            index_url=disc["index_url"],
            page_link_contains=disc["page_link_contains"],
            file_suffix=disc.get("file_suffix", ".xlsx"),
            verify=verify,
        )
    elif method == "two_hop_scrape":
        url = discover.two_hop_scrape(
            index_url=disc["index_url"],
            page_link_contains=disc["page_link_contains"],
            file_link_contains=disc["file_link_contains"],
            base_url=disc.get("base_url"),
            verify=verify,
            impersonate=disc.get("impersonate"),
        )
    elif method == "anstat_ci_ihpc":
        url = discover.anstat_ci_ihpc(
            search_url=disc["search_url"],
            file_base=disc["file_base"],
            title_contains=disc.get("title_contains", "INDICE HARMONISE DES PRIX"),
            verify=verify,
        )
    elif method == "anstat_ci_publication":
        url = discover.anstat_ci_publication(
            search_url=disc["search_url"],
            file_base=disc["file_base"],
            title_contains=disc["title_contains"],
            verify=verify,
        )
    elif method == "insbu_latest":
        url = discover.insbu_latest(
            api_url=disc["api_url"],
            title_contains=disc["title_contains"],
            verify=verify,
        )
    elif method == "inseed_tchad_quarterly":
        url = discover.inseed_tchad_quarterly(
            api_base=disc["api_base"],
            title_contains=disc["title_contains"],
            verify=verify,
        )
    elif method == "inseed_tchad_latest":
        url = discover.inseed_tchad_latest(
            api_base=disc["api_base"],
            title_contains=disc["title_contains"],
            verify=verify,
        )
    elif method == "wp_media_latest":
        url = discover.wp_media_latest(
            api_url=disc["api_url"],
            name_contains=disc["name_contains"],
            lang=disc.get("lang", "fr"),
            verify=verify,
        )
    elif method == "latest_month_file":
        url = discover.latest_month_file(
            page_url=disc["page_url"],
            url_contains=disc["url_contains"],
            verify=verify,
        )
    elif method == "latest_named_month_file":
        url = discover.latest_named_month_file(
            page_url=disc["page_url"],
            url_contains=disc["url_contains"],
            lang=disc.get("lang", "fr"),
            verify=verify,
        )
    elif method == "regex_on_page":
        url = discover.regex_on_page(
            page_url=disc["page_url"],
            pattern=disc["pattern"],
            base_url=disc.get("base_url"),
            verify=verify,
        )
    elif method == "edocman_latest":
        url = discover.edocman_latest(
            index_url=disc["index_url"],
            slug_contains=disc["slug_contains"],
            base_url=disc["base_url"],
            verify=verify,
        )
    elif method == "wpdm_latest":
        url = discover.wpdm_latest(
            index_urls=disc["index_urls"],
            slug_contains=disc["slug_contains"],
            base_url=disc["base_url"],
            verify=verify,
        )
    elif method == "nso_malawi_publication":
        url = discover.nso_malawi_publication(
            api_base=disc["api_base"],
            title_contains=disc["title_contains"],
            verify=verify,
        )
    elif method == "malawi_cms_cpi":
        url = discover.malawi_cms_cpi(
            api_base=disc["api_base"],
            slug_prefix=disc.get("slug_prefix", "consumer-price-index"),
            file_regex=disc.get("file_regex", r"cpi.*\.xlsx$"),
            exclude_regex=disc.get("exclude_regex", r"yoy"),
            verify=verify,
        )
    elif method == "capmas_publication":
        url = discover.capmas_publication_file(
            api_base=disc["api_base"],
            publication_id=disc["publication_id"],
            prefer=disc.get("prefer", "excel"),
            verify=verify,
        )
    elif method == "catalog_latest":
        url = discover.catalog_latest(
            page_url=disc["page_url"],
            include_ext=disc["include_ext"],
            exclude_contains=disc.get("exclude_contains"),
            base_url=disc.get("base_url"),
            verify=verify,
        )
    else:
        raise ValueError(f"unknown discover method: {method}")
    print(f"[{country}] discovered: {url}")

    # 2. download the actual source file, keeping its original published name
    #    (or `save_as` when the URL carries none, e.g. a Google Sheets export),
    #    into source_data/<Country>/ so the primary document is retained.
    orig_name = disc.get("save_as") or unquote(os.path.basename(urlparse(url).path))
    if not orig_name:
        stamp = dt.date.today().strftime("%Y%m")
        orig_name = f"{country}_{d['indicator']}_{stamp}"
    src_path = os.path.join(country_dir, orig_name)
    # `impersonate` opts a source into a browser TLS fingerprint (see fetch);
    # needed where the host refuses `requests` outright (INEGE Equatorial Guinea).
    fetch.download(url, src_path, verify=verify,
                   impersonate=disc.get("impersonate"))
    print(
        f"[{country}] source saved: source_data/{country}/{orig_name} "
        f"({os.path.getsize(src_path):,} bytes)"
    )

    # 3. extract the usable file (unzip if needed); the extracted file is kept
    #    alongside the original archive in the same country folder.
    if src_path.lower().endswith(".zip"):
        local = fetch.unzip_first(
            src_path, country_dir, suffix=disc.get("inner_suffix", ".xlsx")
        )
    else:
        local = src_path

    # Some indicators are split across more than one published file (e.g. HCP
    # Morocco keeps the general index and the by-division indices in separate
    # Google Sheets). `extra_urls` are downloaded, retained, and handed to the
    # parser (if it accepts an `extras=` argument) alongside the primary file.
    extras = _download_extras(d, country, country_dir, verify)

    return _finish(d, country, url, local, extras)


def _download_extras(d: dict, country: str, country_dir: str, verify: bool) -> list[str]:
    extras = []
    for i, ex in enumerate(d.get("extra_urls", []) or []):
        ex_url = ex["url"] if isinstance(ex, dict) else ex
        ex_name = (ex.get("save_as") if isinstance(ex, dict) else None) \
            or unquote(os.path.basename(urlparse(ex_url).path)) \
            or f"{country}_{d['indicator']}_extra{i}"
        ex_path = os.path.join(country_dir, ex_name)
        fetch.download(ex_url, ex_path, verify=verify)
        print(
            f"[{country}] extra source saved: source_data/{country}/{ex_name} "
            f"({os.path.getsize(ex_path):,} bytes)"
        )
        extras.append(ex_path)
    return extras


def _finish(d: dict, country: str, url: str, local: str,
            extras: list[str] | None = None) -> str:
    """Shared tail for every source: parse -> normalise -> validate -> write."""
    # 4. parse (pass extras only to parsers that opt in via an `extras` param)
    parse = _CFG.registry[d["parser"]]
    if extras and "extras" in inspect.signature(parse).parameters:
        df = parse(local, extras=extras)
    else:
        df = parse(local)
    return _write_output(d, country, url, local, df)


def _write_output(d: dict, country: str, url: str, local: str,
                  df: pd.DataFrame) -> str:
    """Normalise -> validate -> write, given an already-parsed frame. Split out
    so multi-table API sources (which parse several files at once) share it."""
    # 5. normalise: attach the descriptor's constant identity columns
    df["country"] = country
    df["iso3"] = d["iso3"]
    df["indicator"] = d["indicator"]
    df["source_type"] = d["source_type"]
    df["source_url"] = url
    df["source_file"] = os.path.basename(local)
    df["extracted_at"] = dt.datetime.now().isoformat(timespec="seconds")

    # 6. validate against the indicator's schema (supplied by the pipeline config)
    for col in _CFG.columns:
        if col not in df.columns:
            df[col] = pd.NA
    df = _CFG.validate(df, d)

    # 7. write
    os.makedirs(_CFG.out_dir, exist_ok=True)
    out_path = os.path.join(_CFG.out_dir, f"{country.lower()}_{d['indicator'].lower()}.csv")
    df.sort_values(_CFG.sort_cols).to_csv(out_path, index=False)
    periods = df["period"].nunique()
    print(
        f"[{country}] OK -> {out_path}  "
        f"({len(df):,} rows, {periods} periods, "
        f"{df['period'].min()}..{df['period'].max()})"
    )
    return out_path


def run_cli(cfg: Pipeline, argv=None) -> int:
    """CLI entry point invoked by each indicator's pipeline.py."""
    configure(cfg)
    ap = argparse.ArgumentParser()
    ap.add_argument("source", nargs="?", help="descriptor name, e.g. south_africa")
    ap.add_argument("--all", action="store_true", help="run every descriptor")
    args = ap.parse_args(argv)

    if args.all:
        names = [
            os.path.splitext(os.path.basename(p))[0]
            for p in glob.glob(os.path.join(cfg.sources_dir, "*.yaml"))
        ]
    elif args.source:
        names = [args.source]
    else:
        ap.error("give a source name or --all")

    failures = 0
    for n in names:
        try:
            collect(n)
        except Exception as e:  # isolate one country's failure from the rest
            failures += 1
            print(f"[{n}] FAILED: {type(e).__name__}: {e}", file=sys.stderr)
    return 1 if failures else 0
