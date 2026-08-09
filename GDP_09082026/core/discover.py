"""The 'discover' step: resolve the URL of the current data file.

Two methods, chosen per source by the descriptor's `discover.method`:

* page_scrape   - read a listing page and pick the anchor matching the
                  configured terms (the month is embedded in the filename, so
                  we never hardcode it). Good default for open NSO sites.
* probe_monthly - walk a URL template backward from the current month until a
                  file exists. Needed when the listing page is behind an
                  anti-bot WAF (Stats SA / Incapsula) but the file itself is
                  directly downloadable.
* catalog_latest- NADA catalog pages (Nigeria NBS): newest = largest download id.
* latest_dated  - listing pages of dated files (KNBS Kenya monthly PDFs): parse
                  the month+year out of each link and pick the newest.
"""
from __future__ import annotations
import re
from urllib.parse import urljoin, unquote
import requests
from bs4 import BeautifulSoup

from . import fetch
from .fetch import HEADERS, TIMEOUT


_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}
_DATE_RE = re.compile(
    r"(january|february|march|april|may|june|july|august|september|october|"
    r"november|december)[-_ ]+(\d{4})",
    re.IGNORECASE,
)


def latest_dated_link(
    page_url: str,
    link_contains: list[str],
    verify: bool = True,
) -> str:
    """For listing pages of month-dated files (KNBS Kenya). Collect links whose
    href/text contain all `link_contains` terms, parse '<Month> <Year>' from
    each, and return the newest by date. Robust to filename quirks like '_1'."""
    r = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT, verify=verify)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    terms = [t.lower() for t in link_contains]

    best = None  # ((year, month), href)
    for a in soup.find_all("a", href=True):
        hay = f"{a.get_text(' ', strip=True)} {a['href']}".lower()
        if not all(t in hay for t in terms):
            continue
        m = _DATE_RE.search(hay)
        if not m:
            continue
        key = (int(m.group(2)), _MONTHS[m.group(1).lower()])
        if best is None or key > best[0]:
            best = (key, a["href"])

    if best is None:
        raise LookupError(
            f"no dated link on {page_url} matching {link_contains}"
        )
    return urljoin(page_url, best[1])


def latest_dated_pdf(
    index_url: str,
    link_contains: list[str],
    pdf_contains: str | None = None,
    year: int | None = None,
    verify: bool = True,
) -> str:
    """Two-hop discovery (NISR Rwanda): the year index page lists monthly
    publication PAGES; each publication page hosts the PDF(s). Find the newest
    month's page, then the PDF on it. `index_url` may contain '{year}'.
    `pdf_contains` picks the right language edition (e.g. 'consumer price
    index' for the English PDF)."""
    if "{year}" in index_url:
        index_url = index_url.format(year=year)
    pub_page = latest_dated_link(index_url, link_contains, verify=verify)

    r = requests.get(pub_page, headers=HEADERS, timeout=TIMEOUT, verify=verify)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    pdfs = [a["href"] for a in soup.find_all("a", href=True)
            if a["href"].lower().endswith(".pdf")]
    if not pdfs:
        raise LookupError(f"no PDF on publication page {pub_page}")
    if pdf_contains:
        want = pdf_contains.lower()
        pref = [p for p in pdfs if want in unquote(p).lower()]
        pdfs = pref or pdfs
    return urljoin(pub_page, pdfs[0])


def latest_year_file(
    page_url: str,
    link_contains: list[str],
    verify: bool = True,
) -> str:
    """For homepages that link one file per YEAR (Stats SL GDP report, whose
    href embeds the year in the path/name, e.g. '.../gdp_2024/GDP-Report_2024
    _Final_Publish.pdf'). Collect links matching all `link_contains` terms,
    parse the largest 4-digit year (2000-2099) from href+text, return the
    newest."""
    r = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT, verify=verify)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    terms = [t.lower() for t in link_contains]
    year_re = re.compile(r"20\d\d")

    best = None  # (year, href)
    for a in soup.find_all("a", href=True):
        hay = f"{a.get_text(' ', strip=True)} {a['href']}".lower()
        if not all(t in hay for t in terms):
            continue
        years = [int(y) for y in year_re.findall(hay)]
        if not years:
            continue
        key = max(years)
        if best is None or key > best[0]:
            best = (key, a["href"])

    if best is None:
        raise LookupError(
            f"no year-stamped link on {page_url} matching {link_contains}"
        )
    return urljoin(page_url, best[1])


def catalog_latest(
    page_url: str,
    include_ext: list[str],
    exclude_contains: list[str] | None = None,
    base_url: str | None = None,
    verify: bool = True,
) -> str:
    """For NADA-style catalog pages (Nigeria NBS microdata) that list one
    download per month at '.../download/<id>/<filename>'. The <id> increases
    over time, so the newest publication is the matching link with the largest
    id. Returns its absolute URL.
    """
    r = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT, verify=verify)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    exclude_contains = [x.lower() for x in (exclude_contains or [])]
    id_re = re.compile(r"/download/(\d+)/([^/?#\s]+)")

    best = None  # (id, href)
    for a in soup.find_all("a", href=True):
        m = id_re.search(a["href"])
        if not m:
            continue
        fname = m.group(2).lower()
        if not any(fname.endswith(e.lower()) for e in include_ext):
            continue
        if any(x in fname for x in exclude_contains):
            continue
        i = int(m.group(1))
        if best is None or i > best[0]:
            best = (i, a["href"])

    if best is None:
        raise LookupError(
            f"no download link on {page_url} with ext {include_ext}"
        )
    return urljoin(page_url, best[1])


def two_hop_scrape(
    index_url: str,
    page_link_contains: list[str],
    file_link_contains: list[str],
    base_url: str | None = None,
    verify: bool = True,
    impersonate=None,
) -> str:
    """Two-hop discovery where the file isn't linked from the listing directly.
    Pick the newest matching document page on an archive (first match = newest),
    then the file link on that page. Used by NSA Namibia: the CPI-bulletin
    category archive lists 'Excel Tables' *document pages*, each of which hosts
    the actual .xlsx. `impersonate` routes both fetches through a browser TLS
    fingerprint (UBOS's search index resets plain connections)."""
    page = find_download_link(index_url, page_link_contains, verify=verify,
                              impersonate=impersonate)
    return find_download_link(page, file_link_contains, base_url=base_url,
                              verify=verify, impersonate=impersonate)


def latest_quarter_link(
    page_url: str,
    link_contains: list[str],
    verify: bool = True,
) -> str:
    """Return the newest 'q<n>-<YYYY>' (or 'YYYY q<n>') link matching all
    `link_contains` terms — used when the download link itself carries the quarter
    (NBS Seychelles '…quarterly-national-accounts-q4-2025/download')."""
    r = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT, verify=verify)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    terms = [t.lower() for t in link_contains]
    q_re = re.compile(r"q([1-4])[-_ ](20\d\d)|(20\d\d)[-_ ]?q([1-4])", re.I)

    best = None  # ((year, quarter), url)
    for a in soup.find_all("a", href=True):
        hay = f"{a.get_text(' ', strip=True)} {a['href']}".lower()
        if not all(t in hay for t in terms):
            continue
        m = q_re.search(hay)
        if not m:
            continue
        key = (int(m.group(2)), int(m.group(1))) if m.group(1) \
            else (int(m.group(3)), int(m.group(4)))
        if best is None or key > best[0]:
            best = (key, urljoin(page_url, a["href"]))
    if best is None:
        raise LookupError(f"no quarter-stamped {link_contains} link at {page_url}")
    return best[1]


def latest_quarter_two_hop(
    index_url: str,
    page_link_contains: list[str],
    file_suffix: str = ".xlsx",
    verify: bool = True,
) -> str:
    """Two-hop discovery keyed on a 'q<N>-<YYYY>' quarter in the link (NISR Rwanda
    GDP). On a subject listing page, pick the newest publication page whose link
    matches all `page_link_contains` terms and carries a quarter stamp, then return
    the first `file_suffix` file on that page."""
    r = requests.get(index_url, headers=HEADERS, timeout=TIMEOUT, verify=verify)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    terms = [t.lower() for t in page_link_contains]
    q_re = re.compile(r"q([1-4])[-_ ](20\d\d)", re.I)

    best = None  # ((year, quarter), url)
    for a in soup.find_all("a", href=True):
        hay = f"{a.get_text(' ', strip=True)} {a['href']}".lower()
        if not all(t in hay for t in terms):
            continue
        m = q_re.search(a["href"])
        if not m:
            continue
        key = (int(m.group(2)), int(m.group(1)))
        if best is None or key > best[0]:
            best = (key, urljoin(index_url, a["href"]))
    if best is None:
        raise LookupError(f"no quarter-stamped '{page_link_contains}' page at {index_url}")

    r2 = requests.get(best[1], headers=HEADERS, timeout=TIMEOUT, verify=verify)
    r2.raise_for_status()
    soup2 = BeautifulSoup(r2.text, "html.parser")
    for a in soup2.find_all("a", href=True):
        if a["href"].lower().split("?")[0].endswith(file_suffix.lower()):
            return urljoin(best[1], a["href"])
    raise LookupError(f"no {file_suffix} on publication page {best[1]}")


def latest_quarter_file(
    page_url: str,
    link_contains: list[str],
    verify: bool = True,
) -> str:
    """Pick the newest file whose name carries a 'YYYYT<n>' or 'T<n> YYYY' quarter
    stamp (INSD Burkina 'Cnt2025T4.xlsx'). Among links matching all `link_contains`
    terms, parse the year+quarter and return the latest."""
    r = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT, verify=verify)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    terms = [t.lower() for t in link_contains]
    # 'YYYYT<n>' | 'T<n> YYYY' | compact '<n>t<yy>' (INSTAT Mali 'pibmali1t26')
    q_re = re.compile(
        r"(20\d\d)\s*T\s*([1-4])|T\s*([1-4])[-_ ]?(20\d\d)|([1-4])t(\d{2})(?=[_.])",
        re.I)

    best = None  # ((year, quarter), href)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not all(t in href.lower() for t in terms):
            continue
        m = q_re.search(href)
        if not m:
            continue
        if m.group(1):
            key = (int(m.group(1)), int(m.group(2)))
        elif m.group(3):
            key = (int(m.group(4)), int(m.group(3)))
        else:
            key = (2000 + int(m.group(6)), int(m.group(5)))
        if best is None or key > best[0]:
            best = (key, href)
    if best is None:
        raise LookupError(f"no quarter-stamped {link_contains} file at {page_url}")
    return urljoin(page_url, best[1])


def latest_dmy_file(
    page_url: str,
    link_contains: list[str],
    verify: bool = True,
) -> str:
    """Pick the newest file whose name carries a 'DD_MM_YYYY' (or DD-MM-YYYY) date
    (ZimStat 'Publish_Quarterly_GDP_2023-2025_ZWG_24_12_2025_Q3.xlsx'). Among links
    matching all `link_contains` terms, parse that date and take the latest."""
    r = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT, verify=verify)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    terms = [t.lower() for t in link_contains]
    dmy = re.compile(r"(\d{2})[_\-.](\d{2})[_\-.](20\d\d)")

    best = None  # ((year, month, day), href)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        low = unquote(href).lower()
        if not all(t in low for t in terms):
            continue
        m = dmy.search(unquote(href))
        if not m:
            continue
        dd, mm, yyyy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if mm > 12:
            dd, mm = mm, dd
        key = (yyyy, mm, dd)
        if best is None or key > best[0]:
            best = (key, href)
    if best is None:
        raise LookupError(f"no DD_MM_YYYY-dated {link_contains} file at {page_url}")
    return urljoin(page_url, best[1])


def latest_datestamp_file(
    page_url: str,
    link_contains: list[str],
    verify: bool = True,
) -> str:
    """Pick the newest file whose name ends in a '_DDMMYY' stamp (Statistics
    Mauritius: HS_QNA_1Qtr26_140726.xlsx). Among links matching all
    `link_contains` terms, parse the trailing 6-digit date and take the latest."""
    r = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT, verify=verify)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    terms = [t.lower() for t in link_contains]
    stamp = re.compile(r"_(\d{2})(\d{2})(\d{2})\.[a-z]+$", re.I)

    best = None  # ((yy, mm, dd), href)
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not all(t in href.lower() for t in terms):
            continue
        m = stamp.search(href)
        if not m:
            continue
        dd, mm, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        key = (yy, mm, dd)
        if best is None or key > best[0]:
            best = (key, href)
    if best is None:
        raise LookupError(f"no _DDMMYY-stamped {link_contains} file at {page_url}")
    return urljoin(page_url, best[1])


def gsheet_export_from_page(page_url: str, verify: bool = True) -> str:
    """Resolve a Google Sheets 'export' URL from a page that embeds the sheet
    (HCP Morocco links its IPC data this way). We take the sheet id and build a
    `format=xlsx` export so the WHOLE workbook (all tabs) is downloaded — a plain
    `?gid=` link would yield only one tab. Sheet ids are stable across HCP's
    monthly in-place updates, so the resulting URL persists."""
    r = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT, verify=verify)
    r.raise_for_status()
    m = re.search(r"spreadsheets/d/([A-Za-z0-9_-]{20,})", r.text)
    if not m:
        raise LookupError(f"no Google Sheet link found on {page_url}")
    return f"https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=xlsx"


def capmas_publication_file(
    api_base: str,
    publication_id: int,
    prefer: str = "excel",
    verify: bool = True,
) -> str:
    """Resolve the latest file URL for a CAPMAS publication (Egypt NSO).

    CAPMAS's site is a SPA backed by a JSON API; `GET <api_base>/api/Publication/
    <id>` returns the newest issue's `publicationDetail` with `excelUrl` /
    `pdfUrl` (GUID-named files served from the same host). We return the absolute
    URL of the preferred format, falling back to the other if it's absent.
    """
    api_base = api_base.rstrip("/")
    url = f"{api_base}/api/Publication/{publication_id}"
    r = requests.get(
        url, headers={**HEADERS, "Accept": "application/json", "locale": "en"},
        timeout=TIMEOUT, verify=verify,
    )
    r.raise_for_status()
    detail = (r.json().get("data") or {}).get("publicationDetail") or {}
    rel = detail.get("excelUrl") if prefer == "excel" else detail.get("pdfUrl")
    rel = rel or detail.get("pdfUrl") or detail.get("excelUrl")
    if not rel:
        raise LookupError(f"no file URL for CAPMAS publication {publication_id}")
    return api_base + rel


def _shift_month(year: int, month: int, back: int) -> tuple[int, int]:
    idx = (year * 12 + (month - 1)) - back
    return idx // 12, idx % 12 + 1


def probe_monthly_url(
    url_template: str,
    start_year: int,
    start_month: int,
    lookback_months: int = 6,
    tag_format: str = "%Y%m",
) -> str:
    """Return the newest existing URL from a monthly-tagged template.

    `url_template` must contain '{tag}', formatted from a date via `tag_format`
    (e.g. '%Y%m' -> '202605'). We check current month first, then older.
    """
    import datetime as _dt

    for back in range(lookback_months + 1):
        y, m = _shift_month(start_year, start_month, back)
        tag = _dt.date(y, m, 1).strftime(tag_format)
        url = url_template.format(tag=tag)
        try:
            r = requests.get(
                url, headers={**HEADERS, "Range": "bytes=0-0"},
                timeout=TIMEOUT, stream=True, allow_redirects=True,
            )
        except requests.RequestException:
            continue
        ok = r.status_code in (200, 206) and "zip" in r.headers.get(
            "content-type", ""
        ).lower()
        r.close()
        if ok:
            return url
    raise LookupError(
        f"no file found for {url_template} in last {lookback_months} months"
    )


_ES_MONTHS = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
              "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]


def inege_ipc_latest(
    url_template: str,
    impersonate=("chrome124", "firefox133", "safari17_0"),
    lookback_months: int = 6,
    publish_lag_months: tuple[int, ...] = (1, 2, 0),
    verify: bool = True,
) -> str:
    """Resolve the newest INEGE (Equatorial Guinea) monthly IPC report PDF.

    Discovery here is URL construction, not scraping, because inege.org's HTML is
    unreachable: Cloudflare answers 403 on every page route — '/', '?page_id=404',
    '/wp-json/', even '/robots.txt' — so there is no listing to read. The published
    PDFs under /wp-content/uploads/ ARE served, but only to a browser-like TLS
    fingerprint (see fetch.impersonating_get), so we walk back from the current
    month and probe the known filename pattern, newest first.

    WordPress files it under the upload month, which is normally the month AFTER
    the reference month, so each candidate month is tried at each `publish_lag_months`
    offset. `url_template` takes {pub_year}/{pub_month} (the uploads path) and
    {month}/{year} (the Spanish month name + year of the data itself).
    """
    import datetime as _dt

    today = _dt.date.today()
    for back in range(lookback_months + 1):
        ry, rm = _shift_month(today.year, today.month, back)
        for lag in publish_lag_months:
            py, pm = _shift_month(ry, rm, -lag)      # published after the data month
            url = url_template.format(
                pub_year=py, pub_month=f"{pm:02d}",
                month=_ES_MONTHS[rm - 1], year=ry,
            )
            try:
                r = fetch.impersonating_get(
                    url, impersonate, verify=verify,
                    headers={"Range": "bytes=0-15"},   # probe, don't pull megabytes
                )
            except Exception:
                continue
            if r.status_code in (200, 206) and r.content[:5] == b"%PDF-":
                return url
    raise LookupError(
        f"no INEGE IPC PDF found for {url_template} in the last {lookback_months} months"
    )


def find_download_link(
    page_url: str,
    link_contains: list[str],
    prefer_format: str | None = None,
    base_url: str | None = None,
    verify: bool = True,
    impersonate=None,
) -> str:
    """Return the absolute URL of the first link matching all `link_contains`
    terms (case-insensitive, matched against link text + href).

    `prefer_format` (e.g. 'Excel') further filters when a page offers the same
    file in multiple formats. `base_url` normalises the messy relative hrefs
    some NSO sites emit (Stats SA uses '/../timeseriesdata/...'). `impersonate`
    routes the page fetch through a browser TLS fingerprint (Stats SA's GDP
    listing sits behind the same Incapsula WAF as its CPI pages).
    """
    if impersonate:
        resp = fetch.impersonating_get(page_url, impersonate, verify=verify)
    else:
        resp = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT, verify=verify)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    terms = [t.lower() for t in link_contains]
    if prefer_format:
        terms_fmt = terms + [prefer_format.lower()]
    else:
        terms_fmt = terms

    def matches(hay: str, needles: list[str]) -> bool:
        hay = hay.lower()
        return all(n in hay for n in needles)

    candidates = []
    for a in soup.find_all("a", href=True):
        hay = f"{a.get_text(' ', strip=True)} {a['href']}"
        if matches(hay, terms_fmt):
            candidates.append(a["href"])
    # fall back to ignoring the format filter if nothing matched
    if not candidates:
        for a in soup.find_all("a", href=True):
            hay = f"{a.get_text(' ', strip=True)} {a['href']}"
            if matches(hay, terms):
                candidates.append(a["href"])

    if not candidates:
        raise LookupError(
            f"no link on {page_url} matching {link_contains} "
            f"(format={prefer_format})"
        )

    href = candidates[0].strip()
    # Stats SA emits 'https://host/../timeseriesdata/...' — collapse the '/..'
    if "/../" in href and base_url:
        href = base_url.rstrip("/") + "/" + href.split("/../", 1)[1]
    return urljoin(page_url, href)


_FR_SLUG_MONTHS = [
    ("janvier", "01"), ("fevrier", "02"), ("février", "02"), ("mars", "03"),
    ("avril", "04"), ("juillet", "07"), ("juin", "06"), ("mai", "05"),
    ("aout", "08"), ("août", "08"), ("septembre", "09"), ("octobre", "10"),
    ("novembre", "11"), ("decembre", "12"), ("décembre", "12"),
]


def wpdm_latest(
    index_urls,
    slug_contains: str,
    base_url: str,
    verify: bool = True,
) -> str:
    """Resolve the newest WordPress 'Download Monitor' file (INS Congo INHPC).

    The download pages `<base>/download/<slug>/` are landing pages whose real
    file link carries a `?wpdmdl=<id>` token. We union the `/download/<slug>/`
    links across one or more listing pages, keep those matching `slug_contains`,
    parse a French month + 20xx year from each slug, take the newest, then fetch
    that landing page and return its `wpdmdl` download URL."""
    if isinstance(index_urls, str):
        index_urls = [index_urls]
    slugs = set()
    for u in index_urls:
        r = requests.get(u, headers=HEADERS, timeout=TIMEOUT, verify=verify)
        if r.ok:
            slugs.update(re.findall(rf"{re.escape(base_url.rstrip('/'))}/download/([a-z0-9\-]+)/?", r.text))

    best = None  # ((year, month), slug)
    for slug in slugs:
        if slug_contains not in slug:
            continue
        ym = re.search(r"(20\d\d)", slug)
        mo = next((mm for name, mm in _FR_SLUG_MONTHS if name in slug), None)
        if not (ym and mo):
            continue
        key = (int(ym.group(1)), int(mo))
        if best is None or key > best[0]:
            best = (key, slug)
    if not best:
        raise LookupError(f"no dated '{slug_contains}' download under {index_urls}")

    landing = f"{base_url.rstrip('/')}/download/{best[1]}/"
    r = requests.get(landing, headers=HEADERS, timeout=TIMEOUT, verify=verify)
    r.raise_for_status()
    m = re.search(r'https?://[^"\'\s]*/download/[^"\'\s]*wpdmdl=\d+[^"\'\s]*', r.text)
    if not m:
        raise LookupError(f"no wpdmdl link on landing page {landing}")
    return m.group(0).replace("&amp;", "&")


def latest_month_file(
    page_url: str,
    url_contains,
    verify: bool = True,
) -> str:
    """Return the newest `…_MM_YYYY.<ext>` file URL listed on a page.

    For sites that publish one dated file per month with a numeric `_MM_YYYY`
    stamp in the filename (ZimStat's 'CPI_Weighted_MM_YYYY.xls', served via the
    WordPress REST API). We collect every absolute URL containing all
    `url_contains` terms, parse (year, month) from the stamp, and return the newest
    (fixing the stray double slash some ZimStat links carry)."""
    if isinstance(url_contains, str):
        url_contains = [url_contains]
    terms = [t.lower() for t in url_contains]
    r = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT, verify=verify)
    r.raise_for_status()
    text = r.text.replace("\\/", "/")     # WP REST API JSON escapes forward slashes
    stamp = re.compile(r"_(\d{2})_(\d{4})\.")
    best = None  # ((year, month), url)
    for url in re.findall(r"https?://[^\"'\s<>\\]+", text):
        low = url.lower()
        if not all(t in low for t in terms):
            continue
        m = stamp.search(url)
        if not m:
            continue
        key = (int(m.group(2)), int(m.group(1)))
        if best is None or key > best[0]:
            best = (key, url)
    if not best:
        raise LookupError(f"no dated file matching {url_contains} on {page_url}")
    return best[1].replace("//wp-content", "/wp-content")


def latest_named_month_file(
    page_url: str,
    url_contains,
    lang: str = "fr",
    verify: bool = True,
) -> str:
    """Return the newest '<…><Month>_<Year><…>.<ext>' file URL listed on a page,
    where the month is a SPELLED-OUT name (French/English), not a numeric stamp.

    For NSOs that publish one dated file per month with the month spelled out in
    the filename (INS Niger's 'IHPCB2023_<Mois>_<Année>_VF.pdf', served from a
    stable /wp-content/uploads/ folder). We collect every absolute URL containing
    all `url_contains` terms, then parse the '<month>_<year>' pair out of the
    filename — matched as an ADJACENT unit so a base-year baked into the name
    (…B2023…) can't be mistaken for the data year — and return the newest."""
    if isinstance(url_contains, str):
        url_contains = [url_contains]
    terms = [t.lower() for t in url_contains]
    try:
        months = dict(_SLUG_MONTHS[lang])          # name -> "MM"
    except KeyError:
        raise ValueError(f"latest_named_month_file: unknown lang {lang!r}") from None
    # longest names first so 'juillet' wins over the 'jui' its start contains
    names = sorted(months, key=len, reverse=True)
    date_re = re.compile(
        r"(" + "|".join(re.escape(n) for n in names) + r")[-_ ]*(20\d\d)", re.I
    )

    r = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT, verify=verify)
    r.raise_for_status()
    text = r.text.replace("\\/", "/")     # some WP endpoints escape forward slashes
    best = None  # ((year, month), url)
    for url in re.findall(r"https?://[^\"'\s<>\\]+", text):
        low = url.lower()
        if not all(t in low for t in terms):
            continue
        fname = unquote(url.rsplit("/", 1)[-1]).lower()
        m = date_re.search(fname)
        if not m:
            continue
        key = (int(m.group(2)), int(months[m.group(1).lower()]))
        if best is None or key > best[0]:
            best = (key, url)
    if not best:
        raise LookupError(f"no dated file matching {url_contains} on {page_url}")
    return best[1]


_FR_TITLE_MONTHS = [
    ("janvier", "01"), ("fevrier", "02"), ("février", "02"), ("mars", "03"),
    ("avril", "04"), ("juillet", "07"), ("juin", "06"), ("mai", "05"),
    ("aout", "08"), ("août", "08"), ("septembre", "09"), ("octobre", "10"),
    ("novembre", "11"), ("decembre", "12"), ("décembre", "12"),
]


def anstat_ci_ihpc(
    search_url: str,
    file_base: str,
    title_contains: str = "INDICE HARMONISE DES PRIX",
    verify: bool = True,
) -> str:
    """Resolve the newest ANStat Côte d'Ivoire IHPC bulletin PDF.

    anstat.ci is a SPA; its `searchPublicationByCritere` endpoint (POST) returns a
    JSON `{view: <html cards>}`. Each card has a thumbnail
    `Imageval_indicateur<ID>.png` and a title, and the PDF lives at the parallel
    path `<file_base>/File_val_indicateur<ID>.pdf`. We pick the newest IHPC card by
    the French month+year in its title and build that deterministic PDF URL — no
    need for the ephemeral per-request detail hash."""
    r = requests.post(search_url, data={"critere": "", "page": 0},
                      headers={**HEADERS, "X-Requested-With": "XMLHttpRequest"},
                      timeout=TIMEOUT, verify=verify)
    view = (r.json() or {}).get("view", "")
    cards = re.findall(
        r"Imageval_indicateur(\d+)\.png.*?ft_rapport[^>]*>\s*([^<]+?)\s*</div>",
        view, re.S)

    best = None  # ((year, month), image_id)
    for img_id, title in cards:
        low = title.lower()
        if title_contains.lower() not in low:
            continue
        ym = re.search(r"(20\d\d)", title)
        mo = next((mm for name, mm in _FR_TITLE_MONTHS if name in low), None)
        if not (ym and mo):
            continue
        key = (int(ym.group(1)), int(mo))
        if best is None or key > best[0]:
            best = (key, img_id)
    if not best:
        raise LookupError(f"no '{title_contains}' card at {search_url}")
    return f"{file_base.rstrip('/')}/File_val_indicateur{best[1]}.pdf"


def anstat_ci_publication(
    search_url: str,
    file_base: str,
    title_contains: str,
    verify: bool = True,
) -> str:
    """Resolve the newest ANStat Côte d'Ivoire publication PDF whose title matches
    `title_contains`, that is ACTUALLY available. anstat.ci is a SPA; its
    searchPublicationByCritere endpoint returns cards with an
    Imageval_indicateur<ID>.png thumbnail (ID increases over time) and the PDF at
    the parallel <file_base>/File_val_indicateur<ID>.pdf. The very newest card is
    often listed before its file is uploaded (404), so we walk the matching cards
    newest-first and return the first whose file really serves a PDF."""
    r = requests.post(search_url, data={"critere": title_contains, "page": 0},
                      headers={**HEADERS, "X-Requested-With": "XMLHttpRequest"},
                      timeout=TIMEOUT, verify=verify)
    view = (r.json() or {}).get("view", "")
    cards = re.findall(r'Imageval_indicateur(\d+)\.png"\s*alt="([^"]+)"', view)
    ids = sorted({cid for cid, t in cards if title_contains.lower() in t.lower()},
                 key=int, reverse=True)
    if not ids:
        raise LookupError(f"no '{title_contains}' card at {search_url}")
    for cid in ids:
        url = f"{file_base.rstrip('/')}/File_val_indicateur{cid}.pdf"
        try:
            probe = requests.get(url, headers={**HEADERS, "Range": "bytes=0-3"},
                                 timeout=TIMEOUT, verify=verify)
        except requests.RequestException:
            continue
        if probe.status_code in (200, 206) and probe.content[:4] == b"%PDF":
            return url
    raise LookupError(f"no available '{title_contains}' PDF among {len(ids)} cards")


def insbu_latest(
    api_url: str,
    title_contains: str,
    verify: bool = True,
) -> str:
    """Resolve the newest INSBU (Burundi) publication PDF whose title matches.

    insbu.bi is a SPA over a Laravel API at `<host>/api/publications` (paginated,
    newest first). Each item has `title` and `document_url`. We take the newest
    item whose title contains `title_contains` and return its document URL."""
    r = requests.get(api_url, headers={**HEADERS, "Accept": "application/json"},
                     timeout=TIMEOUT, verify=verify)
    data = (r.json() or {}).get("data") or []
    matches = [p for p in data if title_contains.lower() in str(p.get("title", "")).lower()]
    if not matches:
        raise LookupError(f"no '{title_contains}' publication at {api_url}")
    matches.sort(key=lambda p: p.get("date") or p.get("publication_date") or "", reverse=True)
    best = matches[0]
    url = best.get("document_url") or best.get("document") or ""
    return url


def inseed_tchad_quarterly(
    api_base: str,
    title_contains: str,
    verify: bool = True,
) -> str:
    """Resolve the newest INSEED Chad publication whose title matches and carries a
    '<n>e/er/ème Trimestre <YYYY>' quarter stamp. inseed.ssn-tchad.td is a Node API
    (`<api_base>/api/publications`, paginated) with `titre` and `fichier.url`."""
    api_base = api_base.rstrip("/")
    q_re = re.compile(r"(\d)\s*(?:er|ème|eme|e)?\s*trimestre\s*(20\d\d)", re.I)
    best = None  # ((year, quarter), file_url)
    for pg in range(1, 30):
        r = requests.get(f"{api_base}/api/publications?page={pg}&limit=100",
                         headers={**HEADERS, "Accept": "application/json"},
                         timeout=TIMEOUT, verify=verify)
        data = (r.json() or {}).get("data") or []
        if not data:
            break
        for d in data:
            title = str(d.get("titre", ""))
            if title_contains.lower() not in title.lower():
                continue
            m = q_re.search(title)
            url = (d.get("fichier") or {}).get("url")
            if not (m and url):
                continue
            key = (int(m.group(2)), int(m.group(1)))
            if best is None or key > best[0]:
                best = (key, api_base + url if url.startswith("/") else url)
    if not best:
        raise LookupError(f"no quarterly '{title_contains}' at {api_base}")
    return best[1]


def inseed_tchad_latest(
    api_base: str,
    title_contains: str,
    verify: bool = True,
) -> str:
    """Resolve the newest INSEED Chad publication whose title matches.

    inseed.td is a SPA over a Node API at `<api_base>/api/publications` (paginated).
    Each item has `titre` and `fichier.url`. We page through, keep titles containing
    `title_contains` with a trailing `MM-YYYY`, take the newest, and return the file
    URL on the API host."""
    api_base = api_base.rstrip("/")
    best = None  # ((year, month), file_url)
    for pg in range(1, 30):
        r = requests.get(f"{api_base}/api/publications?page={pg}&limit=100",
                         headers={**HEADERS, "Accept": "application/json"},
                         timeout=TIMEOUT, verify=verify)
        data = (r.json() or {}).get("data") or []
        if not data:
            break
        for d in data:
            title = d.get("titre", "")
            if title_contains.lower() not in title.lower():
                continue
            m = re.search(r"(\d{2})[-_ ](\d{4})", title)
            url = (d.get("fichier") or {}).get("url")
            if not (m and url):
                continue
            key = (int(m.group(2)), int(m.group(1)))
            if best is None or key > best[0]:
                best = (key, url)
    if not best:
        raise LookupError(f"no '{title_contains}' publication at {api_base}")
    return api_base + best[1] if best[1].startswith("/") else best[1]


# Longest name first so 'july' wins over the 'jul' prefix it contains.
_EN_SLUG_MONTHS = [
    ("january", "01"), ("february", "02"), ("march", "03"), ("april", "04"),
    ("june", "06"), ("july", "07"), ("august", "08"), ("september", "09"),
    ("october", "10"), ("november", "11"), ("december", "12"),
    ("jan", "01"), ("feb", "02"), ("mar", "03"), ("apr", "04"), ("may", "05"),
    ("jun", "06"), ("jul", "07"), ("aug", "08"), ("sep", "09"), ("oct", "10"),
    ("nov", "11"), ("dec", "12"),
]
_SLUG_MONTHS = {"fr": _FR_SLUG_MONTHS, "en": _EN_SLUG_MONTHS}


def wp_media_latest(
    api_url: str,
    name_contains: str,
    lang: str = "fr",
    verify: bool = True,
) -> str:
    """Resolve the newest PDF from a WordPress media (wp/v2/media) search result.

    ANSADE Mauritania is a SPA over a WordPress backend; its monthly INPC note is
    a media item whose `source_url` filename carries a French month + year. We keep
    those matching `name_contains`, parse the date from the filename, and return
    the newest (the media endpoint may answer 406 but still returns valid JSON).

    `lang` selects the month names to look for in the filename — SNBS Somalia
    publishes the same shape in English ('May-CPI-Report-2026.pdf'), with the
    month spelled out or abbreviated and the word order varying between issues.

    Everything is matched against the FILENAME, never the whole URL: these files
    sit under '/wp-content/uploads/<year>/<month>/', so a note published late (a
    December issue uploaded in January) would otherwise take its year from the
    upload path and be dated twelve months out."""
    try:
        months = _SLUG_MONTHS[lang]
    except KeyError:
        raise ValueError(f"wp_media_latest: unknown lang {lang!r}") from None
    r = requests.get(api_url, headers={**HEADERS, "Accept": "application/json"},
                     timeout=TIMEOUT, verify=verify)
    items = r.json()
    best = None  # ((year, month), url)
    for it in (items if isinstance(items, list) else []):
        url = (it.get("source_url") or "")
        low = unquote(url.rsplit("/", 1)[-1]).lower()
        if name_contains.lower() not in low or not low.endswith(".pdf"):
            continue
        ym = re.search(r"(20\d\d)", low)
        mo = next((mm for name, mm in months if name in low), None)
        if not (ym and mo):
            continue
        key = (int(ym.group(1)), int(mo))
        if best is None or key > best[0]:
            best = (key, url)
    if not best:
        raise LookupError(f"no dated PDF matching {name_contains!r} at {api_url}")
    return best[1]


def regex_on_page(
    page_url: str,
    pattern: str,
    base_url: str | None = None,
    verify: bool = True,
) -> str:
    """Return the first URL matching `pattern` in a page's raw source.

    For sites that embed the data-file path in inline/obfuscated JavaScript rather
    than an <a href> (INE Angola builds its 'Download Excel' from a path baked into
    a script). We regex the raw HTML and resolve the match against `base_url`."""
    r = requests.get(page_url, headers=HEADERS, timeout=TIMEOUT, verify=verify)
    r.raise_for_status()
    m = re.search(pattern, r.text)
    if not m:
        raise LookupError(f"pattern {pattern!r} not found on {page_url}")
    return urljoin(base_url or page_url, m.group(0))


def edocman_latest(
    index_url: str,
    slug_contains: str,
    base_url: str,
    verify: bool = True,
) -> str:
    """Resolve the newest Joomla 'Edocman' document (ICASEES / CAR IHPC bulletins).

    Document links look like `/index.php/component/edocman/<slug>/download`; the
    slug carries a French month + 20xx year (the `N°` in the slug resets each year,
    so we sort by parsed date, not by number). We pick the newest matching slug and
    build its `/download?Itemid=0` URL, which serves the file directly."""
    r = requests.get(index_url, headers=HEADERS, timeout=TIMEOUT, verify=verify)
    r.raise_for_status()
    slugs = set(re.findall(r"edocman/([a-z0-9\-]+)", r.text, re.I))

    best = None  # ((year, month), slug)
    for slug in slugs:
        if slug_contains not in slug:
            continue
        ym = re.search(r"(20\d\d)", slug)
        mo = next((mm for name, mm in _FR_SLUG_MONTHS if name in slug), None)
        if not (ym and mo):
            continue
        key = (int(ym.group(1)), int(mo))
        if best is None or key > best[0]:
            best = (key, slug)
    if not best:
        raise LookupError(f"no dated '{slug_contains}' edocman doc at {index_url}")
    return f"{base_url.rstrip('/')}/index.php/component/edocman/{best[1]}/download?Itemid=0"


def nso_malawi_publication(
    api_base: str,
    title_contains: str,
    verify: bool = True,
) -> str:
    """Resolve the download URL of a Malawi NSO publication whose title matches.

    nsomalawi.mw is a Nuxt SPA over a Laravel CMS; `<api_base>/api/web/publications`
    is paginated and each item carries a `document` field with the file's download
    URL. We page through and return the first match's document."""
    api_base = api_base.rstrip("/")
    for pg in range(1, 15):
        r = requests.get(f"{api_base}/api/web/publications?page={pg}",
                         headers={**HEADERS, "Accept": "application/json"},
                         timeout=TIMEOUT, verify=verify)
        pubs = (r.json() or {}).get("publications") or {}
        data = pubs.get("data") or []
        if not data:
            break
        for p in data:
            if title_contains.lower() in str(p.get("title", "")).lower():
                doc = p.get("document")
                if doc:
                    return doc
        if pg >= (pubs.get("last_page") or 1):
            break
    raise LookupError(f"no '{title_contains}' publication at {api_base}")


def malawi_cms_cpi(
    api_base: str,
    slug_prefix: str = "consumer-price-index",
    file_regex: str = r"cpi.*\.xlsx$",
    exclude_regex: str = r"yoy",
    verify: bool = True,
) -> str:
    """Resolve the latest Malawi NSO CPI 'Stats Flash' file via the headless CMS.

    nsomalawi.mw is a Nuxt SPA over a Laravel CMS whose public JSON lives under
    `<api_base>/api/web`. `GET .../news` lists posts newest-first; we take the
    latest whose slug starts with `slug_prefix`, then `GET .../news/<slug>` and
    return the attachment whose filename matches `file_regex` but not
    `exclude_regex` (the index workbook, not the year-on-year one)."""
    api_base = api_base.rstrip("/")
    lst = requests.get(f"{api_base}/api/web/news", headers=HEADERS,
                       timeout=TIMEOUT, verify=verify)
    lst.raise_for_status()
    posts = (lst.json().get("data") or {})
    posts = posts.get("data") if isinstance(posts, dict) and "data" in posts else posts
    cands = [p for p in posts if str(p.get("slug", "")).startswith(slug_prefix)]
    if not cands:
        raise LookupError(f"no Malawi CPI posts under slug '{slug_prefix}'")
    cands.sort(key=lambda p: p.get("published_at") or p.get("created_at") or "", reverse=True)
    slug = cands[0]["slug"]

    det = requests.get(f"{api_base}/api/web/news/{slug}", headers=HEADERS,
                       timeout=TIMEOUT, verify=verify)
    det.raise_for_status()
    atts = (det.json().get("data") or {}).get("attachments") or []
    frx, xrx = re.compile(file_regex, re.I), re.compile(exclude_regex, re.I)
    for a in atts:
        url = a.get("url") or ""
        name = unquote(url.rsplit("/", 1)[-1])
        if frx.search(name) and not xrx.search(name):
            return url
    raise LookupError(f"no CPI workbook attachment for Malawi post '{slug}'")
