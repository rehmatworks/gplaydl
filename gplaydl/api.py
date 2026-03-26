"""Google Play Store FDFE API — details, purchase, delivery, search.

Uses a pure-Python protobuf decoder (no gpapi / protobuf library needed).
Field numbers are based on live probing from our research repo and
validated against gpapi's googleplay.proto definitions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

import cloudscraper
import httpx

from gplaydl.auth import build_headers
from gplaydl.protobuf import ProtoDecoder, extract_strings

FDFE_URL = "https://android.clients.google.com/fdfe"
DETAILS_URL = f"{FDFE_URL}/details"
PURCHASE_URL = f"{FDFE_URL}/purchase"
DELIVERY_URL = f"{FDFE_URL}/delivery"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class AppDetails:
    package: str
    title: str = ""
    developer: str = ""
    version_string: str = ""
    version_code: int = 0
    rating: Optional[str] = None
    downloads: Optional[str] = None
    play_url: str = ""


@dataclass
class SplitInfo:
    name: str
    url: str = ""
    size: int = 0


@dataclass
class ObbFile:
    file_type: int = 0  # 0 = main, 1 = patch
    version_code: int = 0
    size: int = 0
    url: str = ""
    cookies: list[dict] = field(default_factory=list)

    @property
    def type_label(self) -> str:
        return {0: "main", 1: "patch"}.get(self.file_type, "main")


@dataclass
class DeliveryResult:
    download_url: str = ""
    download_size: int = 0
    sha1: str = ""
    cookies: list[dict] = field(default_factory=list)
    splits: list[SplitInfo] = field(default_factory=list)
    obb_files: list[ObbFile] = field(default_factory=list)


class PlayAPIError(Exception):
    pass


class AuthExpiredError(PlayAPIError):
    """Raised when the API returns 401 — token needs refresh."""
    pass


# ---------------------------------------------------------------------------
# Protobuf helpers
# ---------------------------------------------------------------------------

def _first_bytes(fields: list[tuple[int, int, Any]], num: int) -> Optional[bytes]:
    """Return raw bytes of the first length-delimited field with number *num*."""
    for fn, wt, v in fields:
        if fn == num and wt == 2 and isinstance(v, (bytes, bytearray)):
            return bytes(v)
    return None


def _first_string(fields: list[tuple[int, int, Any]], num: int) -> str:
    for fn, wt, v in fields:
        if fn == num and wt == 2:
            return ProtoDecoder.decode_string(v)
    return ""


def _first_int(fields: list[tuple[int, int, Any]], num: int) -> Optional[int]:
    for fn, wt, v in fields:
        if fn == num and wt == 0:
            return int(v)
    return None


def _all_bytes(fields: list[tuple[int, int, Any]], num: int) -> list[bytes]:
    """Return all length-delimited occurrences of field *num*."""
    return [
        bytes(v) for fn, wt, v in fields
        if fn == num and wt == 2 and isinstance(v, (bytes, bytearray))
    ]


def _navigate(raw: bytes, *path: int) -> list[tuple[int, int, Any]]:
    """Walk a nested protobuf path, e.g. _navigate(raw, 1, 2, 4)."""
    data = raw
    for field_num in path:
        fields = ProtoDecoder(data).read_all_ordered()
        sub = _first_bytes(fields, field_num)
        if sub is None:
            return []
        data = sub
    return ProtoDecoder(data).read_all_ordered()


# ---------------------------------------------------------------------------
# Headers
# ---------------------------------------------------------------------------

def _proto_headers(auth: dict) -> dict:
    headers = build_headers(auth)
    headers["Content-Type"] = "application/x-protobuf"
    headers["Accept"] = "application/x-protobuf"
    return headers


# ---------------------------------------------------------------------------
# Details
# ---------------------------------------------------------------------------
# ResponseWrapper(1) -> Payload(2) -> DetailsResponse(4) -> DocV2
# DocV2: 1=docid, 5=title, 6=creator, 13=DocDetails
# DocDetails(1) -> AppDetails: 3=versionCode, 4=versionString

def _parse_details_proto(raw: bytes) -> tuple[str, str, int, str]:
    """Parse details response. Returns (docid, title, version_code, version_string)."""
    doc_fields = _navigate(raw, 1, 2, 4)
    if not doc_fields:
        return "", "", 0, ""

    docid = _first_string(doc_fields, 1)
    title = _first_string(doc_fields, 5)

    vc, vs = 0, ""
    doc_details_b = _first_bytes(doc_fields, 13)
    if doc_details_b:
        dd = ProtoDecoder(doc_details_b).read_all_ordered()
        app_details_b = _first_bytes(dd, 1)
        if app_details_b:
            ad = ProtoDecoder(app_details_b).read_all_ordered()
            vc = _first_int(ad, 3) or 0
            vs = _first_string(ad, 4)

    return docid, title, vc, vs


def get_details_proto(package: str, auth: dict) -> tuple[str, str, int, str]:
    """Fetch app details. Returns (docid, title, version_code, version_string)."""
    headers = _proto_headers(auth)
    resp = httpx.get(f"{DETAILS_URL}?doc={package}", headers=headers, timeout=30)
    if resp.status_code == 404:
        raise PlayAPIError(f"App not found: {package}")
    if resp.status_code == 401:
        raise AuthExpiredError("Auth token expired.")
    if resp.status_code != 200:
        raise PlayAPIError(f"Failed to fetch details (HTTP {resp.status_code}).")
    docid, title, vc, vs = _parse_details_proto(resp.content)
    if not docid:
        raise PlayAPIError("App not found or unavailable for this device profile.")
    return docid, title, vc, vs


def get_details(package: str, auth: dict) -> AppDetails:
    """Return structured app details."""
    docid, title, vc, vs = get_details_proto(package, auth)
    details = AppDetails(
        package=docid or package,
        title=title,
        version_string=vs,
        version_code=vc,
        play_url=f"https://play.google.com/store/apps/details?id={package}",
    )
    _enrich_from_html(details)
    return details


def _enrich_from_html(details: AppDetails) -> None:
    """Fill in rating / developer / downloads from the Play Store website."""
    try:
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(
            f"https://play.google.com/store/apps/details?id={details.package}&hl=en",
            timeout=15,
        )
        if resp.status_code != 200:
            return
        html = resp.text

        m = re.search(r'<a[^>]*href="/store/apps/developer[^"]*"[^>]*>([^<]+)</a>', html)
        if m:
            details.developer = m.group(1)

        m = re.search(r"(\d+\.\d+)\s*star", html, re.IGNORECASE)
        if m:
            details.rating = m.group(1)

        m = re.search(r">(\d[\d,KMB+]*)\s*[Dd]ownloads<", html)
        if m:
            details.downloads = m.group(1)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Purchase
# ---------------------------------------------------------------------------

def purchase(package: str, version_code: int, auth: dict) -> None:
    """Acquire a free app (equivalent of clicking 'Install')."""
    headers = build_headers(auth)
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    body = f"doc={package}&ot=1&vc={version_code}"
    resp = httpx.post(PURCHASE_URL, headers=headers, content=body, timeout=30)
    if resp.status_code not in (200, 204):
        pass  # non-fatal — may already be "purchased"


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------
# ResponseWrapper(1) -> Payload(21) -> DeliveryResponse(2) -> AppDeliveryData
# AppDeliveryData (field numbers from live probing):
#   1  = downloadSize         (varint, bytes)
#   2  = signature            (string)
#   3  = downloadUrl          (string)
#   4  = downloadAuthCookie   (repeated message: 1=name, 2=value)
#   15 = splitDeliveryData    (repeated message: 1=name, 2=size, 5=downloadUrl)
#   18 = additionalFile       (repeated message: 1=fileType, 2=size, 3=downloadUrl)
#   29 = versionCode          (varint)

def _parse_delivery(raw: bytes) -> DeliveryResult:
    """Parse a delivery response using ProtoDecoder."""
    # Primary path: Payload at field 21 (current API)
    for payload_fn in (21, 5, 4, 6):
        add_fields = _navigate(raw, 1, payload_fn, 2)
        if add_fields and _first_string(add_fields, 3):
            return _extract_delivery_from_fields(add_fields)

    # Last resort: tree walk for download URLs
    return _extract_delivery_from_tree(raw)


def _extract_delivery_from_fields(fields: list[tuple[int, int, Any]]) -> DeliveryResult:
    """Build DeliveryResult from parsed AppDeliveryData fields."""
    app_vc = _first_int(fields, 29) or 0

    result = DeliveryResult(
        download_url=_first_string(fields, 3),
        download_size=_first_int(fields, 1) or 0,
        sha1=_first_string(fields, 5),
    )

    # Cookies (field 4, repeated)
    for cookie_b in _all_bytes(fields, 4):
        cf = ProtoDecoder(cookie_b).read_all_ordered()
        name = _first_string(cf, 1)
        value = _first_string(cf, 2)
        if name:
            result.cookies.append({"name": name, "value": value})

    # Splits (field 15, repeated: 1=name, 2=size, 5=downloadUrl)
    for split_b in _all_bytes(fields, 15):
        sf = ProtoDecoder(split_b).read_all_ordered()
        name = _first_string(sf, 1)
        url = _first_string(sf, 5)
        if url:
            result.splits.append(SplitInfo(
                name=name or f"split{len(result.splits)}",
                url=url,
                size=_first_int(sf, 2) or 0,
            ))

    # OBB / additional files (field 18, repeated: 1=fileType, 2=size, 3=downloadUrl)
    # Field 18 is also used for encryptionParams (same shape but sub-field 3
    # contains a non-URL IV string), so we filter by checking the URL prefix.
    for af_b in _all_bytes(fields, 18):
        af = ProtoDecoder(af_b).read_all_ordered()
        url = _first_string(af, 3)
        if url and url.startswith("https://"):
            result.obb_files.append(ObbFile(
                file_type=_first_int(af, 1) or 0,
                version_code=app_vc,
                size=_first_int(af, 2) or 0,
                url=url,
            ))

    return result


def _extract_delivery_from_tree(raw: bytes) -> DeliveryResult:
    """Fallback: scan all strings in the protobuf for download URLs."""
    strings = extract_strings(raw)
    cdn_urls = [s for s in strings if s.startswith("https://") and "android.clients.google.com" in s]
    if not cdn_urls:
        cdn_urls = [s for s in strings if s.startswith("https://") and ("play" in s or "goog" in s)]

    result = DeliveryResult()
    if cdn_urls:
        result.download_url = cdn_urls[0]
    return result


def get_delivery(package: str, version_code: int, auth: dict) -> DeliveryResult:
    """Fetch download URLs for base APK, splits, and OBB files."""
    headers = _proto_headers(auth)
    url = f"{DELIVERY_URL}?doc={package}&ot=1&vc={version_code}"
    resp = httpx.get(url, headers=headers, timeout=30)
    if resp.status_code == 401:
        raise AuthExpiredError("Auth token expired.")
    if resp.status_code != 200:
        raise PlayAPIError(f"Delivery failed (HTTP {resp.status_code}).")

    result = _parse_delivery(resp.content)

    if not result.download_url:
        raise PlayAPIError(
            "No download URL returned. The app may require purchase or "
            "is unavailable for this device."
        )

    return result


# ---------------------------------------------------------------------------
# List splits (from details metadata)
# ---------------------------------------------------------------------------

def list_splits(package: str, auth: dict) -> list[str]:
    """Return split names from app details metadata."""
    headers = _proto_headers(auth)
    resp = httpx.get(f"{DETAILS_URL}?doc={package}", headers=headers, timeout=30)
    if resp.status_code == 401:
        raise AuthExpiredError("Auth token expired.")
    if resp.status_code != 200:
        raise PlayAPIError(f"Failed to fetch details (HTTP {resp.status_code})")

    # Navigate to AppDetails: 1 -> 2 -> 4 -> 13 -> 1
    doc_fields = _navigate(resp.content, 1, 2, 4)
    if not doc_fields:
        return []

    splits: set[str] = set()
    doc_details_b = _first_bytes(doc_fields, 13)
    if not doc_details_b:
        return []

    dd = ProtoDecoder(doc_details_b).read_all_ordered()
    app_details_b = _first_bytes(dd, 1)
    if not app_details_b:
        return []

    ad = ProtoDecoder(app_details_b).read_all_ordered()

    # file entries (field 17 in AppDetails, each with splitId at field 9)
    for file_b in _all_bytes(ad, 17):
        ff = ProtoDecoder(file_b).read_all_ordered()
        sid = _first_string(ff, 9)
        if sid:
            splits.add(sid)

    if not splits:
        split_pattern = re.compile(r"^config\.[a-z]")
        for s in extract_strings(app_details_b):
            if split_pattern.match(s):
                splits.add(s)

    return sorted(splits)


# ---------------------------------------------------------------------------
# Search (HTML scraping — no protobuf)
# ---------------------------------------------------------------------------

def search_apps(query: str, limit: int = 10) -> list[dict]:
    """Search Google Play via HTML scraping. Returns list of {package, title}."""
    scraper = cloudscraper.create_scraper()
    url = f"https://play.google.com/store/search?q={query}&c=apps"
    resp = scraper.get(url, timeout=30)
    if resp.status_code != 200:
        raise PlayAPIError(f"Search failed (HTTP {resp.status_code})")

    pattern = r'href="/store/apps/details\?id=([^"&]+)"[^>]*>([^<]*)</a>'
    matches = re.findall(pattern, resp.text)
    if not matches:
        alt = re.findall(r'data-docid="([^"]+)"', resp.text)
        matches = [(pkg, pkg) for pkg in set(alt)]

    seen: set[str] = set()
    results: list[dict] = []
    for pkg, title in matches:
        if pkg not in seen and len(results) < limit:
            seen.add(pkg)
            results.append({"package": pkg, "title": title.strip() or pkg})
    return results
