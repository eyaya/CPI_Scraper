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


def download(url: str, dest_path: str, verify: bool = True) -> str:
    """Stream a URL to disk. Returns the local path."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
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
