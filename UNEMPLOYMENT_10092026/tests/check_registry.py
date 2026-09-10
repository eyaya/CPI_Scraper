"""Registry sanity check: every descriptor must resolve, offline.

Run before any network run. It asserts, for every `sources/*.yaml`:

  * the required identity keys are present;
  * `parser:` exists in the parser REGISTRY;
  * the `discover.method` is one `core/run.py` actually dispatches on
    (an unknown method is a silent `ValueError` a whole run later);
  * an `api:` source carries an `api:` block and a `topic_map`/`topic` per table;
  * every topic named in a descriptor's `topic_map` is in `schema.TOPICS`.

    python -m indicators.unemployment.tests.check_registry
"""
from __future__ import annotations
import glob
import os
import re
import sys

import yaml

from indicators.unemployment import schema
from indicators.unemployment.parsers import REGISTRY

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCES = os.path.join(os.path.dirname(HERE), "sources")
# HERE = .../indicators/unemployment/tests -> repo root is three levels up.
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
RUN_PY = os.path.join(REPO, "core", "run.py")

REQUIRED = ("country", "iso3", "indicator", "tier", "source_type", "agency",
            "frequency", "parser")


def known_methods() -> set[str]:
    """The discovery methods core/run.py dispatches on, read from the source so
    this check cannot drift out of date."""
    with open(RUN_PY, encoding="utf-8") as f:
        src = f.read()
    return set(re.findall(r'method == "([a-z_]+)"', src)) | {"page_scrape"}


def main() -> int:
    methods = known_methods()
    problems: list[str] = []
    files = sorted(glob.glob(os.path.join(SOURCES, "*.yaml")))
    if not files:
        print(f"no descriptors found in {SOURCES}")
        return 1

    for path in files:
        name = os.path.basename(path)
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
            if not api:
                problems.append(f"{name}: source_type api with no `api:` block")
            for t in (api or {}).get("tables", []):
                if not (t.get("topic") or t.get("topic_map")):
                    problems.append(
                        f"{name}: api table {t.get('save_as')} declares neither "
                        f"`topic` nor `topic_map`")
                for topic in list((t.get("topic_map") or {}).values()) + \
                        ([t["topic"]] if t.get("topic") else []):
                    if topic not in schema.TOPICS:
                        problems.append(
                            f"{name}: unknown topic {topic!r} — add it to "
                            f"schema.TOPICS deliberately or fix the mapping")
        else:
            method = d.get("discover", {}).get("method", "page_scrape")
            if method not in methods:
                problems.append(
                    f"{name}: discover method {method!r} is not dispatched by "
                    f"core/run.py")

        print(f"  {name:22} tier {d.get('tier')}  {d.get('source_type'):6} "
              f"{d.get('parser')}")

    print()
    if problems:
        print(f"FAILED ({len(problems)}):")
        for p in problems:
            print("  -", p)
        return 1
    print(f"{len(files)} descriptor(s) OK — every parser resolves and every "
          f"discovery method is known")
    return 0


if __name__ == "__main__":
    sys.exit(main())
