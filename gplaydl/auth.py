"""Token dispenser authentication and Google Play header construction."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import cloudscraper
from rich.console import Console

from gplaydl.profiles import FALLBACK_PROFILE, get_priority_profiles

DEFAULT_DISPENSER_URL = "https://auroraoss.com/api/auth"

_CONFIG_DIR = Path.home() / ".config" / "gplaydl"

console = Console(stderr=True)


def _auth_path(arch: str) -> Path:
    return _CONFIG_DIR / f"auth-{arch}.json"


def save_auth(data: dict, arch: str = "arm64") -> Path:
    """Persist auth data to disk and return the file path."""
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
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
    if _CONFIG_DIR.exists():
        for f in _CONFIG_DIR.glob("auth-*.json"):
            f.unlink(missing_ok=True)


def fetch_token(
    dispenser_url: Optional[str] = None,
    arch: str = "arm64",
) -> Optional[dict]:
    """Obtain an anonymous auth token from the dispenser.

    Rotates through device profiles until one yields an authToken.
    Returns the full auth dict on success, None on failure.
    """
    url = dispenser_url or DEFAULT_DISPENSER_URL
    scraper = cloudscraper.create_scraper()
    headers = {
        "User-Agent": "com.aurora.store-4.6.1-70",
        "Content-Type": "application/json",
    }

    profiles = get_priority_profiles(arch)
    if not profiles:
        profiles = [("fallback", FALLBACK_PROFILE)]

    for profile_name, profile in profiles:
        device = profile.get("UserReadableName", profile_name)
        try:
            resp = scraper.post(url, json=profile, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("authToken"):
                    console.print(f"  Authenticated with profile: [bold]{device}[/bold]")
                    return data
        except Exception:
            continue

    return None


_MAX_TOKEN_AGE = 50 * 60  # 50 minutes — refresh before the ~1h Google expiry


def ensure_auth(
    arch: str = "arm64",
    dispenser_url: Optional[str] = None,
    force_refresh: bool = False,
) -> Optional[dict]:
    """Return cached auth or fetch a new token transparently.

    Proactively refreshes tokens older than 50 minutes.
    Pass *force_refresh=True* to ignore cache entirely (e.g. after a 401).
    """
    if not force_refresh:
        cached = load_cached_auth(arch)
        if cached and cached.get("authToken"):
            age = time.time() - cached.get("_cached_at", 0)
            if age < _MAX_TOKEN_AGE:
                return cached
            console.print("[dim]Token expired — refreshing...[/dim]")
    else:
        console.print("[dim]Refreshing token...[/dim]")

    data = fetch_token(dispenser_url=dispenser_url, arch=arch)
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
