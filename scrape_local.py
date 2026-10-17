#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Scrape CPI data from ALREADY-DOWNLOADED NSO files (PDF / Excel / CSV).

This skips the online steps (discover / download) of the main pipeline and runs
only the extraction: it hands your local file to the matching country parser,
attaches the identity/provenance columns, validates, and writes a tidy
`out/<country>_cpi.csv` (and/or `.xlsx`) — exactly the same output as
`python -m collector.run`, minus the network.

The parser and identity columns come from `sources/<country>.yaml`, so the file
you pass must be the source layout that country's parser understands.

USAGE
-----
Single file:
    py scrape_local.py <country> <path-to-file> [--format csv|xlsx|both] [--out DIR]
    py scrape_local.py libya  "C:\\downloads\\Consumer-Price-Index-...pdf"

Batch (a whole local folder):
    py scrape_local.py --dir <folder> [--format ...] [--out DIR]
    # Name each file after its country key, e.g.  libya.pdf, south_africa.xlsx,
    # kenya_june2026.pdf  (the country key just has to appear in the filename).

Batch (a folder inside a GitHub repo, no clone needed):
    py scrape_local.py --github OWNER/REPO/PATH            # public repo
    py scrape_local.py --github OWNER/REPO/PATH@BRANCH
    py scrape_local.py --github https://github.com/OWNER/REPO/tree/BRANCH/PATH
    py scrape_local.py --github OWNER/REPO/data --token <gh_token>   # private repo
    # (If your platform already CLONES the repo, just use --dir <checkout>/data.)

Notes
-----
* `<country>` is the descriptor stem, i.e. the name of the `sources/<country>.yaml`
  file (e.g. `south_africa`, `cote_divoire`, `drc`). List them with `--list`.
* API-only sources (e.g. Ghana) have no local file to scrape and are skipped.
* A few parsers optionally read secondary files via an `extras` argument (used by
  the online pipeline). Offline, only the single main file is parsed.
"""
from __future__ import annotations
import argparse
import datetime as dt
import glob
import os
import sys
import tempfile
import urllib.parse

import pandas as pd
import requests
import yaml

from indicators.cpi.pipeline import CONFIG as _CPI
from indicators.gdp.pipeline import CONFIG as _GDP

# The indicator whose sources/parsers/schema/out this run uses; set in main()
# from --indicator (default cpi). Same config object the online pipeline uses.
_PIPELINES = {"cpi": _CPI, "gdp": _GDP}
CFG = _CPI

# .json covers the sources whose published document IS a JSON payload rather than
# a file: a CMS record (Comoros/Strapi) or a retained API response (Ghana/PxWeb).
_EXTS = (".pdf", ".xls", ".xlsx", ".csv", ".json")

HERE = os.path.dirname(os.path.abspath(__file__))


def _descriptors() -> dict[str, dict]:
    """Return {country_key: descriptor} for every sources/*.yaml of this indicator."""
    out = {}
    for path in glob.glob(os.path.join(CFG.sources_dir, "*.yaml")):
        key = os.path.splitext(os.path.basename(path))[0]
        out[key] = yaml.safe_load(open(path, encoding="utf-8"))
    return out


def scrape_file(country: str, local_file: str, out_dir: str = None,
                fmt: str = "both") -> pd.DataFrame:
    """Parse one local file with the country's parser and write the output."""
    out_dir = out_dir or CFG.out_dir
    desc_path = os.path.join(CFG.sources_dir, f"{country}.yaml")
    if not os.path.exists(desc_path):
        raise FileNotFoundError(f"no descriptor {desc_path} "
                                f"(use --list to see valid country keys)")
    d = yaml.safe_load(open(desc_path, encoding="utf-8"))
    if d.get("parser") not in CFG.registry:
        raise KeyError(f"{country}: parser {d.get('parser')!r} not in the registry "
                       f"(is this an API-only source?)")
    if not os.path.exists(local_file):
        raise FileNotFoundError(f"file not found: {local_file}")

    # --- the extraction ---
    df = CFG.registry[d["parser"]](local_file)

    # --- identity / provenance columns (same as the online pipeline) ---
    df["country"] = d.get("country", country)
    df["iso3"] = d.get("iso3")
    df["indicator"] = d.get("indicator")
    df["source_type"] = d.get("source_type")
    df["source_url"] = "(local file)"
    df["source_file"] = os.path.basename(local_file)
    df["extracted_at"] = dt.datetime.now().isoformat(timespec="seconds")
    for col in CFG.columns:
        if col not in df.columns:
            df[col] = pd.NA

    # --- validate (fail loud on garbage) & order columns ---
    df = CFG.validate(df, d)
    df = df.sort_values(CFG.sort_cols).reset_index(drop=True)

    # --- write ---
    # Same merge semantics as the online pipeline: offline scraping a single
    # month must not discard the history already collected for that country
    # (see core.run._merge_with_existing).
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.join(out_dir, f"{country}_{d['indicator'].lower()}")
    csv_path = stem + ".csv"
    if CFG.merge_keys and os.path.exists(csv_path):
        import core.run as _run
        _run.configure(CFG)
        df = _run._merge_with_existing(df, csv_path, country)
        df = df.sort_values(CFG.sort_cols).reset_index(drop=True)
    # ...and the same standardised columns a pipeline run appends.
    if getattr(CFG, "standardise", None) is not None:
        df = CFG.standardise(df).sort_values(CFG.sort_cols).reset_index(drop=True)
    written = []
    if fmt in ("csv", "both"):
        df.to_csv(csv_path, index=False)
        written.append(csv_path)
    if fmt in ("xlsx", "both"):
        df.to_excel(stem + ".xlsx", index=False)
        written.append(stem + ".xlsx")
    print(f"[{country}] OK  {len(df):,} rows, {df['period'].nunique()} periods "
          f"({df['period'].min()}..{df['period'].max()}) -> "
          f"{', '.join(os.path.basename(w) for w in written)}")
    return df


def _match_country(filename: str, keys: list[str]) -> str | None:
    """Map a filename to a country key: exact stem, else longest key contained
    in the (normalised) stem."""
    stem = os.path.splitext(os.path.basename(filename))[0].lower().replace("-", "_")
    if stem in keys:
        return stem
    hits = [k for k in keys if k in stem]
    return max(hits, key=len) if hits else None


def _parse_github(spec: str):
    """Accept a GitHub folder — a web URL
    `https://github.com/OWNER/REPO/tree/BRANCH/PATH` or a shorthand
    `OWNER/REPO[/PATH][@BRANCH]` — and return (owner, repo, path, ref|None)."""
    if spec.startswith(("http://", "https://")):
        parts = urllib.parse.urlparse(spec).path.strip("/").split("/")
        owner, repo = parts[0], parts[1]
        ref, path = None, ""
        if len(parts) > 3 and parts[2] in ("tree", "blob"):
            ref, path = parts[3], "/".join(parts[4:])
        return owner, repo, path, ref
    ref = None
    if "@" in spec:
        spec, ref = spec.rsplit("@", 1)
    parts = spec.strip("/").split("/")
    return parts[0], parts[1], "/".join(parts[2:]), ref


def github_folder_to_tmp(spec: str, token: str | None = None) -> str:
    """Download every PDF/Excel/CSV in a GitHub repo folder to a temp dir and
    return that dir (works on public repos; private repos need a token)."""
    owner, repo, path, ref = _parse_github(spec)
    headers = {"Accept": "application/vnd.github+json"}
    token = token or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    api = f"https://api.github.com/repos/{owner}/{repo}/contents/{path}"
    r = requests.get(api, params={"ref": ref} if ref else {}, headers=headers, timeout=30)
    r.raise_for_status()
    items = r.json()
    items = items if isinstance(items, list) else [items]   # a single file -> dict
    tmp = tempfile.mkdtemp(prefix="nso_gh_")
    n = 0
    for it in items:
        if it.get("type") != "file" or not it.get("name", "").lower().endswith(_EXTS):
            continue
        dl = it.get("download_url")
        if not dl:
            continue
        with open(os.path.join(tmp, it["name"]), "wb") as fh:
            fh.write(requests.get(dl, headers=headers, timeout=90).content)
        n += 1
    where = f"{owner}/{repo}/{path or '.'}" + (f"@{ref}" if ref else "")
    print(f"fetched {n} file(s) from github {where} -> {tmp}")
    return tmp


def scrape_dir(folder: str, out_dir: str = None, fmt: str = "both") -> None:
    """Batch: scrape every file in `folder` whose name matches a country key."""
    keys = list(_descriptors())
    files = sorted(f for f in glob.glob(os.path.join(folder, "*"))
                   if f.lower().endswith(_EXTS))
    if not files:
        print(f"no PDF/Excel/CSV files found in {folder}")
        return
    ok, skipped, failed = 0, [], []
    for f in files:
        country = _match_country(f, keys)
        if not country:
            skipped.append(os.path.basename(f))
            continue
        try:
            scrape_file(country, f, out_dir=out_dir, fmt=fmt)
            ok += 1
        except Exception as e:            # fail-soft in batch
            failed.append(f"{os.path.basename(f)} ({type(e).__name__}: {e})")
    print(f"\n=== batch done: {ok} scraped, {len(skipped)} unmatched, "
          f"{len(failed)} failed ===")
    for s in skipped:
        print(f"  unmatched (rename to a country key): {s}")
    for fl in failed:
        print(f"  FAILED: {fl}")


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Scrape CPI from already-downloaded NSO files (no network).")
    ap.add_argument("country", nargs="?", help="country key (sources/<country>.yaml)")
    ap.add_argument("file", nargs="?", help="path to the local PDF/Excel/CSV")
    ap.add_argument("--dir", help="batch mode: scrape a whole local folder")
    ap.add_argument("--github", metavar="OWNER/REPO[/PATH][@BRANCH] | URL",
                    help="batch mode: scrape a folder in a GitHub repo (no clone needed)")
    ap.add_argument("--token", help="GitHub token for private repos (or set GITHUB_TOKEN)")
    ap.add_argument("--indicator", choices=["cpi", "gdp"], default="cpi",
                    help="which pipeline's sources/parsers/schema to use (default: cpi)")
    ap.add_argument("--out", default=None, help="output directory (default: the indicator's out/)")
    ap.add_argument("--format", choices=["csv", "xlsx", "both"], default="both",
                    help="output format (default: both)")
    ap.add_argument("--list", action="store_true", help="list valid country keys and exit")
    args = ap.parse_args(argv)

    global CFG
    CFG = _PIPELINES[args.indicator]

    if args.list:
        for k in sorted(_descriptors()):
            print(k)
        return 0
    if args.github:
        folder = github_folder_to_tmp(args.github, token=args.token)
        scrape_dir(folder, out_dir=args.out, fmt=args.format)
        return 0
    if args.dir:
        scrape_dir(args.dir, out_dir=args.out, fmt=args.format)
        return 0
    if args.country and args.file:
        scrape_file(args.country, args.file, out_dir=args.out, fmt=args.format)
        return 0
    ap.error("give either  <country> <file>  or  --dir <folder>  (or --list)")


if __name__ == "__main__":
    sys.exit(main())
