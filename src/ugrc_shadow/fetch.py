"""Live HTTP fetch helpers.

Every call here hits the network. Nothing UGRC or Protomaps publishes is ever cached to disk
as an input to the build - the whole point of this tool is that its connection to both sources
stays live and explicit on every run.
"""
from __future__ import annotations

import requests

_TIMEOUT = 30
_HEADERS = {"User-Agent": "ugrc-shadow (+https://github.com/)"}


def fetch_json(url: str) -> dict:
    """GET a URL as JSON. Appends Esri's required f=json param if this looks like an Esri URL
    that doesn't already specify a format."""
    if "arcgis" in url and "f=" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}f=json"
    resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def fetch_bytes(url: str) -> bytes:
    resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.content


def fetch_text(url: str) -> str:
    resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.text
