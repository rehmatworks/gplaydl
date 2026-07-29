"""Token dispenser authentication and Google Play header construction."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

import httpx
from rich.console import Console

from gplaydl.profiles import FALLBACK_PROFILE, get_priority_profiles

DEFAULT_DISPENSER = "https://dispenser.gplaydl.com"

CONFIG_DIR = Path.home() / ".config" / "gplaydl"

_LINK_PATH = CONFIG_DIR / "config.json"

console = Console(stderr=True)


class DispenserError(Exception):
    """The dispenser refused the request and said why."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        self.message = message
        super().__init__(message)


# --- The link between this machine and its dispenser -------------------------


def normalize_dispenser(url: str) -> str:
    """Reduce a dispenser URL to its base.

    Dispensers serve tokens at /api/auth, and people often pass the full
    endpoint to -d. The base and the full endpoint should mean the same server.
    """
    url = url.strip().rstrip("/")
    if url.endswith("/api/auth"):
        url = url[: -len("/api/auth")]
    return url


def load_link() -> dict:
    """Return {"dispenser": base, "api_key": key} or an empty dict."""
    try:
        data = json.loads(_LINK_PATH.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_link(dispenser: str, api_key: str) -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _LINK_PATH.write_text(json.dumps(
        {"dispenser": normalize_dispenser(dispenser), "api_key": api_key},
        indent=2,
    ))
    # The key lets anyone download as this device, so keep it to the owner.
    os.chmod(_LINK_PATH, 0o600)
    return _LINK_PATH


def dispenser_base(dispenser_url: Optional[str] = None) -> str:
    """The dispenser a command should talk to: -d wins, then the linked one."""
    if dispenser_url:
        return normalize_dispenser(dispenser_url)
    return load_link().get("dispenser") or DEFAULT_DISPENSER


def api_key_for(base: str) -> Optional[str]:
    """The key to present to *base*, if any.

    A key is a credential for one dispenser, so it is never sent anywhere but
    the server it was issued by. GPLAYDL_API_KEY overrides the config file,
    which is what CI jobs and containers want.
    """
    if env := os.environ.get("GPLAYDL_API_KEY"):
        return env
    link = load_link()
    if link.get("api_key") and link.get("dispenser") == base:
        return link["api_key"]
    return None


# --- Tokens -------------------------------------------------------------------


def _auth_path(arch: str) -> Path:
    return CONFIG_DIR / f"auth-{arch}.json"


def save_auth(data: dict, arch: str = "arm64") -> Path:
    """Persist auth data to disk and return the file path."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    data["_cached_at"] = time.time()
    path = _auth_path(arch)
    path.write_text(json.dumps(data, indent=2))
    return path


def load_cached_auth(arch: str = "arm64") -> Optional[dict]:
    """Return cached auth dict or None."""
    path = _auth_path(arch)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def clear_auth() -> None:
    """Remove all cached auth files."""
    if CONFIG_DIR.exists():
        for f in CONFIG_DIR.glob("auth-*.json"):
            f.unlink(missing_ok=True)


def _dispenser_request(
    dispenser_url: Optional[str],
    email: Optional[str],
) -> tuple[str, dict, Optional[dict]]:
    """Build (url, headers, params) for a dispenser token request."""
    base = dispenser_base(dispenser_url)
    url = base + "/api/auth"
    headers = {
        "User-Agent": "com.aurora.store-4.6.1-70",
        "Content-Type": "application/json",
    }
    if key := api_key_for(base):
        headers["X-Api-Key"] = key
    params = {"email": email} if email else None
    return url, headers, params


def _request_token(
    url: str, headers: dict, params: Optional[dict], profile: dict,
) -> Optional[dict]:
    """POST one device profile to the dispenser.

    Returns the auth dict, or None when this profile was not accepted.
    Refusals that no other profile can fix (bad key, no accounts, unknown
    email) raise DispenserError with the server's own explanation instead.
    """
    try:
        resp = httpx.post(url, json=profile, headers=headers,
                          params=params, timeout=30)
    except Exception:
        return None
    if resp.status_code == 200:
        data = resp.json()
        if data.get("authToken"):
            return data
        return None
    if resp.status_code in (401, 403, 404, 503):
        # Another device profile cannot change who we are or what we have
        # shared, so pass the dispenser's explanation straight up.
        raise DispenserError(resp.status_code, _server_message(resp))
    return None


def fetch_token(
    dispenser_url: Optional[str] = None,
    arch: str = "arm64",
    email: Optional[str] = None,
) -> Optional[dict]:
    """Obtain an auth token from the dispenser.

    Rotates through device profiles until one yields an authToken. Returns
    the full auth dict on success, None when every profile failed.
    """
    url, headers, params = _dispenser_request(dispenser_url, email)

    profiles = get_priority_profiles(arch)
    if not profiles:
        profiles = [("fallback", FALLBACK_PROFILE)]

    for profile_name, profile in profiles:
        data = _request_token(url, headers, params, profile)
        if data:
            device = profile.get("UserReadableName", profile_name)
            console.print(f"  Authenticated with profile: [bold]{device}[/bold]")
            return data

    return None


def fetch_token_for_profile(
    profile: dict,
    dispenser_url: Optional[str] = None,
    email: Optional[str] = None,
) -> Optional[dict]:
    """Obtain an auth token for one specific device profile.

    Used when a download needs a device Google considers compatible with a
    particular (usually old) app version. The token is not cached; it is
    minted for this one download.
    """
    url, headers, params = _dispenser_request(dispenser_url, email)
    return _request_token(url, headers, params, profile)


def _server_message(resp: httpx.Response) -> str:
    try:
        return resp.json().get("error") or f"dispenser returned HTTP {resp.status_code}"
    except json.JSONDecodeError:
        return f"dispenser returned HTTP {resp.status_code}"


_MAX_TOKEN_AGE = 50 * 60  # 50 minutes, so we refresh before the ~1h Google expiry


def ensure_auth(
    arch: str = "arm64",
    dispenser_url: Optional[str] = None,
    force_refresh: bool = False,
    email: Optional[str] = None,
) -> Optional[dict]:
    """Return cached auth or fetch a new token transparently.

    Proactively refreshes tokens older than 50 minutes. Pass
    *force_refresh=True* to ignore cache entirely (e.g. after a 401). Asking
    for a specific account with *email* always fetches fresh, since whatever
    is cached was minted for somebody else.
    """
    if not force_refresh and not email:
        cached = load_cached_auth(arch)
        if cached and cached.get("authToken"):
            age = time.time() - cached.get("_cached_at", 0)
            if age < _MAX_TOKEN_AGE:
                return cached
            console.print("[dim]Token expired, refreshing...[/dim]")
    elif force_refresh:
        console.print("[dim]Refreshing token...[/dim]")

    data = fetch_token(dispenser_url=dispenser_url, arch=arch, email=email)
    if data:
        save_auth(data, arch)
    return data


def build_headers(auth: dict) -> dict[str, str]:
    """Construct HTTP headers for Google Play FDFE requests."""
    device_info = auth.get("deviceInfoProvider", {})
    locale = "en_US"

    headers = {
        "Authorization": f"Bearer {auth['authToken']}",
        "User-Agent": device_info.get(
            "userAgentString",
            (
                "Android-Finsky/41.2.29-23 [0] [PR] 639844241 "
                "(api=3,versionCode=84122900,sdk=34,device=lynx,"
                "hardware=lynx,product=lynx,platformVersionRelease=14,"
                "model=Pixel%207a,buildId=UQ1A.231205.015,"
                "isWideScreen=0,supportedAbis=arm64-v8a;armeabi-v7a;armeabi)"
            ),
        ),
        "X-DFE-Device-Id": auth.get("gsfId", ""),
        "Accept-Language": "en-US",
        "X-DFE-Encoded-Targets": (
            "CAESN/qigQYC2AMBFfUbyA7SM5Ij/CvfBoIDgxXrBPsDlQUdMfOLAfoFrwEH"
            "gAcBrQYhoA0cGt4MKK0Y2gI"
        ),
        "X-DFE-Client-Id": "am-android-google",
        "X-DFE-Network-Type": "4",
        "X-DFE-Content-Filters": "",
        "X-Limit-Ad-Tracking-Enabled": "false",
        "X-Ad-Id": "",
        "X-DFE-UserLanguages": locale,
        "X-DFE-Request-Params": "timeoutMs=4000",
        "X-DFE-Cookie": auth.get("dfeCookie", ""),
        "X-DFE-No-Prefetch": "true",
    }

    if auth.get("deviceCheckInConsistencyToken"):
        headers["X-DFE-Device-Checkin-Consistency-Token"] = auth[
            "deviceCheckInConsistencyToken"
        ]
    if auth.get("deviceConfigToken"):
        headers["X-DFE-Device-Config-Token"] = auth["deviceConfigToken"]
    if device_info.get("mccMnc"):
        headers["X-DFE-MCCMNC"] = device_info["mccMnc"]

    return headers
