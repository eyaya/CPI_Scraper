"""Parser registry for unemployment / labour-force sources.

Four kinds of parser sit behind these ids:

* **`ghana_pxweb_unemployment`** -- a hand-written Tier-1 PxWeb reader. Ghana is
  the only NSO in Africa exposing its labour tables through a machine-readable
  API, so it earns bespoke code.
* **PDF layouts** -- ONE MODULE PER COUNTRY, `<country>_unemployment.py`, each
  holding a declarative layout read by `pdf_key_indicators.make_parser`. These
  were a single 1,900-line `layouts.py`; they are split so that a country's
  layout sits beside its own descriptor and its own notes, which is the shape
  every other indicator in this repo uses. Shared column vocabularies live in
  `_vocab.py`.
* **Structured workbooks** -- `excel_wide_series` over `excel_layouts.py` for
  the period-across-the-columns shape, plus two readers of their own where that
  model does not fit: Mauritius (periods run DOWN the rows) and Egypt (a
  single-quarter release with sex across the columns).
* **Server-rendered HTML** -- `html_wide_series` over `html_layouts.py`, for
  INS Tunisie, whose PDF is bidi-scrambled and unusable.

Mali is the exception to all of it: its bulletin is an INFOGRAPHIC, so
`mali_pdf_bulletin` reads it by glyph position rather than by line.

Adding a country is: write `<country>_unemployment.py`, add it below, write
`sources/<country>.yaml`. A country whose report has no parseable table (chart
labels or an image only) is NOT given an entry -- see PENDING.md for why, and
do not invent one to fill the gap.
"""
from . import ghana_pxweb_unemployment
from . import pdf_key_indicators  # noqa: F401  -- re-exported for the tests
from . import excel_wide_series
from . import html_wide_series
from . import mauritius_excel_cmphs
from . import egypt_excel_lfs
from . import mali_pdf_bulletin
from .excel_layouts import EXCEL_LAYOUTS
from .html_layouts import HTML_LAYOUTS

from . import angola_unemployment
from . import benin_unemployment
from . import botswana_unemployment
from . import burkina_faso_unemployment
from . import cameroon_unemployment
from . import egypt_unemployment
from . import eswatini_unemployment
from . import ethiopia_unemployment
from . import guinea_bissau_unemployment
from . import kenya_unemployment
from . import liberia_unemployment
from . import morocco_unemployment
from . import namibia_unemployment
from . import niger_unemployment
from . import nigeria_unemployment
from . import rwanda_unemployment
from . import seychelles_unemployment
from . import sierra_leone_unemployment
from . import somalia_unemployment
from . import tanzania_unemployment
from . import uganda_unemployment
from . import zambia_unemployment
from . import zimbabwe_unemployment

REGISTRY = {
    # --- Tier 1: API ------------------------------------------------------
    "ghana_pxweb_unemployment": ghana_pxweb_unemployment.parse,

    # --- Tier 3: report PDF, one module per country -----------------------
    "angola_pdf": angola_unemployment.parse,
    "benin_pdf": benin_unemployment.parse,
    "botswana_pdf": botswana_unemployment.parse,
    "burkina_faso_pdf": burkina_faso_unemployment.parse,
    "cameroon_pdf": cameroon_unemployment.parse,
    "egypt_pdf": egypt_unemployment.parse,
    "eswatini_pdf": eswatini_unemployment.parse,
    "ethiopia_pdf": ethiopia_unemployment.parse,
    "guinea_bissau_pdf": guinea_bissau_unemployment.parse,
    "kenya_pdf": kenya_unemployment.parse,
    "liberia_pdf": liberia_unemployment.parse,
    "morocco_pdf": morocco_unemployment.parse,
    "namibia_pdf": namibia_unemployment.parse,
    "niger_pdf": niger_unemployment.parse,
    "nigeria_pdf": nigeria_unemployment.parse,
    "rwanda_pdf": rwanda_unemployment.parse,
    "seychelles_pdf": seychelles_unemployment.parse,
    "sierra_leone_pdf": sierra_leone_unemployment.parse,
    "somalia_pdf": somalia_unemployment.parse,
    "tanzania_pdf": tanzania_unemployment.parse,
    "uganda_pdf": uganda_unemployment.parse,
    "zambia_pdf": zambia_unemployment.parse,
    "zimbabwe_pdf": zimbabwe_unemployment.parse,

    # --- Read by position, not by line ------------------------------------
    "mali_pdf": mali_pdf_bulletin.parse,

    # --- Tier 2: structured workbook --------------------------------------
    # Mauritius is TRANSPOSED relative to `excel_wide_series` (periods down
    # column A) and Egypt is a single-quarter release with no period column at
    # all. Both reported "no period header row" on every sheet -- one wrong
    # model, not thirty-six changed layouts -- so each has its own reader.
    "mauritius_excel": mauritius_excel_cmphs.parse,
    "egypt_excel": egypt_excel_lfs.parse,
}

# --- Tier 2: structured workbook (period-across-the-columns) --------------
for _name, _cfg in EXCEL_LAYOUTS.items():
    REGISTRY.setdefault(f"{_name}_excel", excel_wide_series.make_parser(_cfg))

# --- Tier 2: server-rendered HTML table ----------------------------------
for _name, _cfg in HTML_LAYOUTS.items():
    REGISTRY[f"{_name}_html"] = html_wide_series.make_parser(_cfg)

# The offline tests reach for a country's layout by name; keep that working
# now that each lives in its own module.
LAYOUTS = {}
for _mod in list(globals().values()):
    _L = getattr(_mod, "LAYOUTS", None)
    name = getattr(_mod, "__name__", "")
    if (isinstance(_L, dict) and name.endswith("_unemployment")
            and not name.endswith("ghana_pxweb_unemployment")):
        LAYOUTS.update(_L)

del _name, _cfg, _mod, _L
