"""Google Play Store FDFE API: details, purchase, delivery, search.

Uses a pure-Python protobuf decoder (no gpapi / protobuf library needed).
Field numbers are based on live probing from our research repo and
validated against gpapi's googleplay.proto definitions.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from gplaydl.auth import build_headers
from gplaydl.protobuf import ProtoDecoder, extract_strings

SEARCH_URL = f"https://android.clients.google.com/fdfe/search"

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
    gzipped_url: str = ""
    gzipped_size: int = 0


@dataclass
class AdditionalFile:
    file_type: int = 0  # 0 = main OBB, 1 = patch OBB, 2 = asset pack APK
    version_code: int = 0
    size: int = 0
    url: str = ""
    gzipped: bool = False
    cookies: list[dict] = field(default_factory=list)

    @property
    def is_asset_pack(self) -> bool:
        return self.file_type == 2

    @property
    def extension(self) -> str:
        return ".apk" if self.is_asset_pack else ".obb"

    @property
    def type_label(self) -> str:
        return {0: "main", 1: "patch", 2: "asset"}.get(self.file_type, "main")


@dataclass
class DeliveryResult:
    download_url: str = ""
    download_size: int = 0
    gzipped_url: str = ""
    gzipped_size: int = 0
    sha1: str = ""
    sha256: str = ""
    cookies: list[dict] = field(default_factory=list)
    splits: list[SplitInfo] = field(default_factory=list)
    additional_files: list[AdditionalFile] = field(default_factory=list)


class PlayAPIError(Exception):
    pass


class AuthExpiredError(PlayAPIError):
    """Raised when the API returns 401 and the token needs a refresh."""
    pass


class AppNotSupportedError(PlayAPIError):
    """Delivery status 2: this version is not served to the current device profile."""
    pass


class AppNotAvailableError(PlayAPIError):
    """The app is invisible to the current device profile (e.g. an Android
    TV exclusive looked up as a phone), or does not exist at all."""
    pass


class AppNotPurchasedError(PlayAPIError):
    """Delivery status 3: the account has not acquired this app."""
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

def _first_float(fields: list[tuple[int, int, Any]], num: int) -> Optional[float]:
    for fn, wt, v in fields:
        if fn == num and wt == 5:
            return struct.unpack("<f", struct.pack("<I", v))[0]
    return None


@dataclass
class _ParsedDetails:
    docid: str = ""
    title: str = ""
    creator: str = ""
    version_code: int = 0
    version_string: str = ""
    rating: Optional[str] = None
    downloads: Optional[str] = None


def _parse_details_proto(raw: bytes) -> _ParsedDetails:
    """Parse details protobuf response into structured fields."""
    result = _ParsedDetails()
    doc_fields = _navigate(raw, 1, 2, 4)
    if not doc_fields:
        return result

    result.docid = _first_string(doc_fields, 1)
    result.title = _first_string(doc_fields, 5)
    result.creator = _first_string(doc_fields, 6)

    # AggregateRating (DocV2 field 14): sub 17 = display string, sub 2 = float
    rating_b = _first_bytes(doc_fields, 14)
    if rating_b:
        rf = ProtoDecoder(rating_b).read_all_ordered()
        result.rating = _first_string(rf, 17) or None
        if not result.rating:
            star = _first_float(rf, 2)
            if star and star > 0:
                result.rating = f"{star:.1f}"

    # DocDetails(13) -> AppDetails(1)
    doc_details_b = _first_bytes(doc_fields, 13)
    if doc_details_b:
        dd = ProtoDecoder(doc_details_b).read_all_ordered()
        app_details_b = _first_bytes(dd, 1)
        if app_details_b:
            ad = ProtoDecoder(app_details_b).read_all_ordered()
            result.version_code = _first_int(ad, 3) or 0
            result.version_string = _first_string(ad, 4)
            # Downloads: field 61 = short display (e.g. "10B+")
            result.downloads = _first_string(ad, 61) or None

    return result


def _fetch_details_raw(package: str, auth: dict) -> bytes:
    """Fetch raw protobuf details response."""
    headers = _proto_headers(auth)
    resp = httpx.get(f"{DETAILS_URL}?doc={package}", headers=headers, timeout=30)
    if resp.status_code == 404:
        raise PlayAPIError(f"App not found: {package}")
    if resp.status_code == 401:
        raise AuthExpiredError("Auth token expired.")
    if resp.status_code != 200:
        raise PlayAPIError(f"Failed to fetch details (HTTP {resp.status_code}).")
    return resp.content


def get_details_proto(package: str, auth: dict) -> tuple[str, str, int, str]:
    """Fetch app details. Returns (docid, title, version_code, version_string)."""
    parsed = _parse_details_proto(_fetch_details_raw(package, auth))
    if not parsed.docid:
        raise AppNotAvailableError("App not found or unavailable for this device profile.")
    return parsed.docid, parsed.title, parsed.version_code, parsed.version_string


def get_details(package: str, auth: dict) -> AppDetails:
    """Return structured app details."""
    parsed = _parse_details_proto(_fetch_details_raw(package, auth))
    if not parsed.docid:
        raise AppNotAvailableError("App not found or unavailable for this device profile.")
    return AppDetails(
        package=parsed.docid or package,
        title=parsed.title,
        developer=parsed.creator,
        version_string=parsed.version_string,
        version_code=parsed.version_code,
        rating=parsed.rating,
        downloads=parsed.downloads,
        play_url=f"https://play.google.com/store/apps/details?id={package}",
    )


# ---------------------------------------------------------------------------
# Purchase
# ---------------------------------------------------------------------------
# ResponseWrapper(1) -> Payload(4) -> BuyResponse
# BuyResponse field 55 = encodedDeliveryToken, passed to delivery as "dtok".

def purchase(package: str, version_code: int, auth: dict) -> str:
    """Acquire a free app (equivalent of clicking 'Install').

    Returns the delivery token Play hands back, or "" when there is none.
    """
    headers = build_headers(auth)
    headers["Content-Type"] = "application/x-www-form-urlencoded"
    body = f"doc={package}&ot=1&vc={version_code}"
    resp = httpx.post(PURCHASE_URL, headers=headers, content=body, timeout=30)
    if resp.status_code == 401:
        raise AuthExpiredError("Auth token expired.")
    if resp.status_code not in (200, 204):
        return ""  # non-fatal; may already be "purchased"
    buy_fields = _navigate(resp.content, 1, 4)
    if not buy_fields:
        return ""
    return _first_string(buy_fields, 55)


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------
# ResponseWrapper(1) -> Payload(21) -> DeliveryResponse
# DeliveryResponse: 1 = status (1=OK, 2=not compatible with device,
#                   3=not purchased), 2 = AppDeliveryData
# AppDeliveryData (field numbers from live probing):
#   1  = downloadSize         (varint)
#   2  = sha1                 (string)
#   3  = downloadUrl          (string)
#   4  = downloadAuthCookie / OBB metadata (repeated, see below)
#   5  = downloadAuthCookie   (repeated message: 1=name, 2=value)
#   13 = downloadUrlGzipped   (string)
#   14 = downloadSizeGzipped  (varint)
#   15 = splitDeliveryData    (repeated message: 1=name, 2=size,
#          3=gzippedSize, 5=downloadUrl, 6=gzippedUrl,
#          8=compressed variant {1=type, 2=size, 3=url})
#   18 = compressedAppData    (message: 1=type(2=gzip), 2=size, 3=url)
#          -> the BASE APK again, gzip-compressed. Not a separate file!
#   19 = sha256               (string)
#   29 = latest versionCode   (varint)

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
        gzipped_url=_first_string(fields, 13),
        gzipped_size=_first_int(fields, 14) or 0,
        sha1=_first_string(fields, 2),
        sha256=_first_string(fields, 19),
    )

    # Field 18: compressedAppData {1=type, 2=size, 3=url}. This is the base
    # APK again, gzip-compressed -- it used to be downloaded as a bogus
    # "-asset.apk" that was byte-identical to the base APK. Use it only as a
    # fallback source for the gzipped base URL.
    if not result.gzipped_url:
        for c_b in _all_bytes(fields, 18):
            cf = ProtoDecoder(c_b).read_all_ordered()
            url = _first_string(cf, 3)
            if url.startswith("https://") and (_first_int(cf, 1) or 0) == 2:
                result.gzipped_url = url
                result.gzipped_size = _first_int(cf, 2) or 0
                break

    # Cookies (field 5, repeated: 1=name, 2=value).
    for c_b in _all_bytes(fields, 5):
        cf = ProtoDecoder(c_b).read_all_ordered()
        f1_wt = next((wt for fn, wt, _ in cf if fn == 1), None)
        if f1_wt == 2:
            name = _first_string(cf, 1)
            if name:
                result.cookies.append({"name": name, "value": _first_string(cf, 2)})

    # Field 4 (repeated) has carried BOTH cookies and OBB file metadata.
    # Cookies have f1=string(name), f2=string(value).
    # OBB entries have f1=varint(fileType), f2=varint(versionCode),
    # f3=varint(size), f4=string(downloadUrl), f7=string(compressedUrl).
    for f4_b in _all_bytes(fields, 4):
        cf = ProtoDecoder(f4_b).read_all_ordered()
        f1_wt = next((wt for fn, wt, _ in cf if fn == 1), None)
        if f1_wt == 2:
            name = _first_string(cf, 1)
            value = _first_string(cf, 2)
            if name:
                result.cookies.append({"name": name, "value": value})
        elif f1_wt == 0:
            url = _first_string(cf, 4)
            if url and url.startswith("https://"):
                ft = _first_int(cf, 1) or 0
                result.additional_files.append(AdditionalFile(
                    file_type=ft,
                    version_code=_first_int(cf, 2) or app_vc,
                    size=_first_int(cf, 3) or 0,
                    url=url,
                    gzipped=False,
                ))

    # Splits (field 15, repeated).
    for split_b in _all_bytes(fields, 15):
        sf = ProtoDecoder(split_b).read_all_ordered()
        name = _first_string(sf, 1)
        url = _first_string(sf, 5)
        if not url:
            continue
        gz_url = _first_string(sf, 6)
        gz_size = _first_int(sf, 3) or 0
        if not gz_url:
            g_b = _first_bytes(sf, 8)
            if g_b:
                gf = ProtoDecoder(g_b).read_all_ordered()
                if (_first_int(gf, 1) or 0) == 2:
                    gz_url = _first_string(gf, 3)
                    gz_size = _first_int(gf, 2) or 0
        result.splits.append(SplitInfo(
            name=name or f"split{len(result.splits)}",
            url=url,
            size=_first_int(sf, 2) or 0,
            gzipped_url=gz_url,
            gzipped_size=gz_size,
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


def get_delivery(
    package: str,
    version_code: int,
    auth: dict,
    delivery_token: str = "",
) -> DeliveryResult:
    """Fetch download URLs for base APK, splits, and OBB files.

    *delivery_token* is the token the purchase endpoint hands back; passing
    it along matches what the Play client does.
    """
    headers = _proto_headers(auth)
    url = f"{DELIVERY_URL}?doc={package}&ot=1&vc={version_code}"
    if delivery_token:
        url += f"&dtok={delivery_token}"
    resp = httpx.get(url, headers=headers, timeout=30)
    if resp.status_code == 401:
        raise AuthExpiredError("Auth token expired.")
    if resp.status_code != 200:
        raise PlayAPIError(f"Delivery failed (HTTP {resp.status_code}).")

    result = _parse_delivery(resp.content)

    if not result.download_url:
        status = _first_int(_navigate(resp.content, 1, 21), 1)
        if status == 2:
            raise AppNotSupportedError(
                f"Google Play does not serve version {version_code} of "
                f"{package} to the current device profile."
            )
        if status == 3:
            raise AppNotPurchasedError(
                f"The account has not acquired {package}; it may be a paid "
                "app or unavailable in the account's region."
            )
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
# Search (FDFE protobuf API)
# ---------------------------------------------------------------------------

def _find_docv2(data: bytes, depth: int = 0, max_depth: int = 10) -> list[dict]:
    """Recursively find DocV2 entries (docid at f1, title at f5) in protobuf."""
    results: list[dict] = []
    if depth > max_depth:
        return results
    try:
        fields = ProtoDecoder(data).read_all_ordered()
    except Exception:
        return results

    f1_str = _first_string(fields, 1)
    f5_str = _first_string(fields, 5)
    if f1_str and "." in f1_str and " " not in f1_str and f5_str:
        return [{"package": f1_str, "title": f5_str, "creator": _first_string(fields, 6)}]

    for _fn, wt, v in fields:
        if wt == 2 and isinstance(v, (bytes, bytearray)) and len(v) > 20:
            results.extend(_find_docv2(bytes(v), depth + 1, max_depth))
    return results


def search_apps(query: str, auth: dict, limit: int = 10) -> list[dict]:
    """Search Google Play via FDFE protobuf API. Returns list of {package, title, creator}."""
    headers = _proto_headers(auth)
    resp = httpx.get(f"{SEARCH_URL}?q={query}&c=3", headers=headers, timeout=30)
    if resp.status_code == 401:
        raise AuthExpiredError("Auth token expired.")
    if resp.status_code != 200:
        raise PlayAPIError(f"Search failed (HTTP {resp.status_code})")

    docs = _find_docv2(resp.content)

    seen: set[str] = set()
    results: list[dict] = []
    for doc in docs:
        pkg = doc["package"]
        if pkg not in seen and len(results) < limit:
            seen.add(pkg)
            results.append(doc)
    return results
