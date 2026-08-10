"""Download + unzip helpers shared by all sources."""
from __future__ import annotations
import os
import zipfile
import requests
import urllib3

# Some NSO sites (e.g. KNBS Kenya) serve an incomplete TLS chain. Sources may
# opt out of verification via `verify=False`; suppress the resulting warning.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}
TIMEOUT = 60


def impersonating_get(url, impersonate, verify: bool = True,
                      headers: dict | None = None):
    """GET with a real browser's TLS fingerprint, via curl_cffi.

    For hosts that gate on the TLS handshake rather than the User-Agent. INEGE
    (Equatorial Guinea) sits behind Cloudflare: its HTML routes always answer 403,
    but the published files under /wp-content/uploads/ are served normally to a
    client whose fingerprint matches a real browser — `requests` is refused whatever
    User-Agent it sends, because OpenSSL's handshake gives it away.

    `impersonate` may be one profile or a list of them, tried in order until one
    isn't refused. Which profiles pass is not stable: Cloudflare scores per
    fingerprint, so a profile that works can start returning 403 while others still
    succeed. A list keeps the source collectable without a code change; a 403 means
    'this fingerprint is refused', NOT 'no such file' (that is a 404).

    Imported lazily so curl_cffi is only needed by the sources that ask for it.
    """
    from curl_cffi import requests as cffi_requests

    profiles = [impersonate] if isinstance(impersonate, str) else list(impersonate)
    resp = None
    for profile in profiles:
        resp = cffi_requests.get(url, impersonate=profile, timeout=TIMEOUT,
                                 verify=verify, headers=headers)
        if resp.status_code != 403:
            return resp
    return resp        # all refused — let the caller raise/skip on the 403


def download(url: str, dest_path: str, verify: bool = True,
             impersonate=None) -> str:
    """Stream a URL to disk. Returns the local path."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if impersonate:
        r = impersonating_get(url, impersonate, verify=verify)
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            f.write(r.content)
        return dest_path
    with requests.get(
        url, headers=HEADERS, timeout=TIMEOUT, stream=True, verify=verify
    ) as r:
        r.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1 << 16):
                f.write(chunk)
    return dest_path


def unzip_first(zip_path: str, dest_dir: str, suffix: str = ".xlsx") -> str:
    """Extract a zip and return the path to the first member ending in `suffix`."""
    os.makedirs(dest_dir, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        members = [m for m in z.namelist() if m.lower().endswith(suffix.lower())]
        if not members:
            raise FileNotFoundError(f"no {suffix} inside {zip_path}: {z.namelist()}")
        z.extractall(dest_dir)
    return os.path.join(dest_dir, members[0])
