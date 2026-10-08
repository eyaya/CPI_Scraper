"""Registry sanity check for the MPI package: every descriptor must resolve,
offline, before anyone spends a network run on it.

It asserts, for every `sources/*.yaml`:

  * the required identity keys are present;
  * `parser:` exists in the parser REGISTRY;
  * the `discover.method` is one `core/run.py` actually dispatches on
    (an unknown method is a silent `ValueError` a whole run later);
  * an `api:` source carries an `api:` block and a `topic` per table;
  * every topic named is in `schema.TOPICS`.

And — specific to MPI, because these are the fields that make a published
index interpretable rather than just a number — it asserts the METHODOLOGY:

  * `mpi_type` is national or global;
  * `k_cutoff`, `n_dimensions` and `n_indicators` are declared and numeric,
    on the layout for a PDF source or on every table of an API source;
  * `k_cutoff` is expressed in PERCENT (a k of 0.333 is a units bug, not a
    33.3% cutoff, and would sail through the row validator);
  * a `global` measure has exactly 3 dimensions and 10 indicators — that is
    what "the global MPI" means, and anything else is a national measure
    mislabelled.

    python -m indicators.mpi.tests.check_registry
"""
from __future__ import annotations
import glob
import os
import re
import sys

import yaml

from indicators.mpi import schema
from indicators.mpi.parsers import REGISTRY
from indicators.mpi.parsers import LAYOUTS

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.path.join(os.path.dirname(HERE), "sources")
# HERE = .../indicators/mpi/tests -> the repo root is three levels up.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
RUN_PY = os.path.join(REPO, "core", "run.py")

REQUIRED = ("country", "iso3", "indicator", "tier", "source_type", "agency",
            "frequency", "parser")

METHODOLOGY = ("k_cutoff", "n_dimensions", "n_indicators")


def known_methods() -> set[str]:
    """The discovery methods core/run.py dispatches on, read from the source so
    this check cannot drift out of date."""
    with open(RUN_PY, encoding="utf-8") as f:
        src = f.read()
    return set(re.findall(r'method == "([a-z_]+)"', src)) | {"page_scrape"}


def check_methodology(where: str, m: dict, problems: list[str]) -> None:
    """`m` is a layout or an API table spec — either way it must carry the rule
    that produced the numbers."""
    for key in METHODOLOGY:
        v = m.get(key)
        if v is None:
            problems.append(f"{where}: missing {key} — an MPI value cannot be "
                            f"interpreted without the rule that produced it")
        elif not isinstance(v, (int, float)):
            problems.append(f"{where}: {key} is {v!r}, not a number")

    k = m.get("k_cutoff")
    if isinstance(k, (int, float)) and not (1 <= k <= 100):
        problems.append(
            f"{where}: k_cutoff {k} is out of range. It must be in PERCENT "
            f"(33.3, not 0.333) — a fractional k passes the row validator and "
            f"then silently mislabels every cutoff in the file.")

    t = m.get("mpi_type", "national")
    if t not in schema.MPI_TYPES:
        problems.append(f"{where}: unknown mpi_type {t!r}")
    elif t == "global":
        if (m.get("n_dimensions"), m.get("n_indicators")) != (3, 10):
            problems.append(
                f"{where}: declared mpi_type 'global' with "
                f"{m.get('n_dimensions')} dimensions / "
                f"{m.get('n_indicators')} indicators. The global MPI is 3 and "
                f"10 by definition; this is a NATIONAL measure mislabelled.")


def main() -> int:
    methods = known_methods()
    problems: list[str] = []
    files = sorted(glob.glob(os.path.join(SOURCES, "*.yaml")))
    if not files:
        print(f"no descriptors found in {SOURCES}")
        return 1

    kinds: dict[str, int] = {}
    for path in files:
        name = os.path.basename(path)
        stem = name[:-5]
        with open(path, encoding="utf-8") as f:
            d = yaml.safe_load(f)

        for key in REQUIRED:
            if key not in d:
                problems.append(f"{name}: missing required key {key!r}")

        parser = d.get("parser")
        if parser not in REGISTRY:
            problems.append(
                f"{name}: parser {parser!r} is not in the REGISTRY "
                f"({sorted(REGISTRY)})")

        if d.get("source_type") == "api":
            api = d.get("api")
            # A plain JSON endpoint fetched through `discover:` is also an
            # `api` source (see core/run.py); only neither is an error.
            if not api and not d.get("discover"):
                problems.append(f"{name}: source_type api with neither an `api:` nor a `discover:` block")
            for t in (api or {}).get("tables", []):
                label = f"{name}:{t.get('save_as')}"
                if not t.get("topic"):
                    problems.append(f"{label}: no `topic`")
                elif t["topic"] not in schema.TOPICS:
                    problems.append(
                        f"{label}: unknown topic {t['topic']!r} — add it to "
                        f"schema.TOPICS deliberately or fix the mapping")
                check_methodology(label, t, problems)
            kind = (api or {}).get("tables", [{}])[0].get("mpi_type", "national")
        else:
            method = d.get("discover", {}).get("method", "page_scrape")
            if method not in methods:
                problems.append(
                    f"{name}: discover method {method!r} is not dispatched by "
                    f"core/run.py")
            layout = LAYOUTS.get(stem)
            if layout is None:
                problems.append(
                    f"{name}: no LAYOUT named {stem!r} in parsers/{stem}_mpi.py "
                    f"(the descriptor and its layout must share a stem)")
                kind = "?"
            else:
                check_methodology(f"layouts[{stem}]", layout, problems)
                kind = layout.get("mpi_type", "national")

        # A layout may ALSO carry global-MPI cells inside an otherwise
        # national measure -- Botswana's Appendix 5 republishes the global MPI
        # alongside its own. Report that, or the summary line would say the
        # package holds no global series when it holds twenty-seven rows of one.
        nested_global = False
        layout = LAYOUTS.get(stem, {})
        for tbl in layout.get("tables", []):
            for col in tbl.get("columns", []):
                if isinstance(col, dict) and col.get("mpi_type") == "global":
                    nested_global = True
                    check_methodology(f"layouts[{stem}].global column", col,
                                      problems)
        if nested_global:
            kinds["global (within a national report)"] = \
                kinds.get("global (within a national report)", 0) + 1

        kinds[kind] = kinds.get(kind, 0) + 1
        print(f"  {name:22} tier {d.get('tier')}  {d.get('source_type'):6} "
              f"{kind:8} {d.get('parser')}"
              + ("  + global MPI" if nested_global else ""))

    print()
    if problems:
        print(f"FAILED ({len(problems)}):")
        for p in problems:
            print("  -", p)
        return 1
    print(f"{len(files)} descriptor(s) OK — every parser resolves, every "
          f"discovery method is known, and every measure declares its "
          f"methodology.")
    print("  by mpi_type: " + ", ".join(f"{k} {v}" for k, v in sorted(kinds.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
