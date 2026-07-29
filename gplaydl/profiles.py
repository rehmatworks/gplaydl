"""Device profiles for Google Play API authentication.

Loads Aurora Store .properties files from the profiles/ directory.
Profiles are rotated during token acquisition for reliability.
"""

from pathlib import Path

PROFILES_DIR = Path(__file__).resolve().parent / "profiles"

FALLBACK_PROFILE = {
    "UserReadableName": "Generic ARM64 Device",
    "Build.HARDWARE": "qcom",
    "Build.RADIO": "unknown",
    "Build.BOOTLOADER": "unknown",
    "Build.FINGERPRINT": "google/sunfish/sunfish:13/TQ3A.230805.001/10316531:user/release-keys",
    "Build.BRAND": "google",
    "Build.DEVICE": "sunfish",
    "Build.VERSION.SDK_INT": "33",
    "Build.VERSION.RELEASE": "13",
    "Build.MODEL": "Pixel 4a",
    "Build.MANUFACTURER": "Google",
    "Build.PRODUCT": "sunfish",
    "Build.ID": "TQ3A.230805.001",
    "Build.TYPE": "user",
    "Build.TAGS": "release-keys",
    "Build.SUPPORTED_ABIS": "arm64-v8a,armeabi-v7a,armeabi",
    "Platforms": "arm64-v8a,armeabi-v7a,armeabi",
    "Screen.Density": "440",
    "Screen.Width": "1080",
    "Screen.Height": "2340",
    "Locales": "en-US",
    "SharedLibraries": (
        "android.ext.shared,android.test.base,android.test.mock,android.test.runner,"
        "com.android.future.usb.accessory,com.android.location.provider,"
        "com.android.media.remotedisplay,com.android.mediadrm.signer,"
        "com.android.nfc_extras,com.google.android.gms,com.google.android.maps,"
        "javax.obex,org.apache.http.legacy"
    ),
    "Features": (
        "android.hardware.audio.output,android.hardware.bluetooth,"
        "android.hardware.bluetooth_le,android.hardware.camera,"
        "android.hardware.camera.autofocus,android.hardware.camera.flash,"
        "android.hardware.camera.front,android.hardware.faketouch,"
        "android.hardware.fingerprint,android.hardware.location,"
        "android.hardware.location.gps,android.hardware.location.network,"
        "android.hardware.microphone,android.hardware.nfc,"
        "android.hardware.screen.landscape,android.hardware.screen.portrait,"
        "android.hardware.sensor.accelerometer,android.hardware.sensor.compass,"
        "android.hardware.sensor.gyroscope,android.hardware.sensor.light,"
        "android.hardware.sensor.proximity,android.hardware.telephony,"
        "android.hardware.touchscreen,android.hardware.touchscreen.multitouch,"
        "android.hardware.touchscreen.multitouch.distinct,"
        "android.hardware.touchscreen.multitouch.jazzhand,"
        "android.hardware.usb.accessory,android.hardware.usb.host,"
        "android.hardware.wifi,android.hardware.wifi.direct,"
        "android.software.app_widgets,android.software.backup,"
        "android.software.home_screen,android.software.input_methods,"
        "android.software.live_wallpaper,android.software.print,"
        "android.software.webview"
    ),
    "GSF.version": "223616055",
    "Vending.version": "82151710",
    "Vending.versionString": "21.5.17-21 [0] [PR] 326734551",
    "Roaming": "mobile-notroaming",
    "TimeZone": "America/New_York",
    "CellOperator": "310260",
    "SimOperator": "310260",
    "Client": "android-google",
    "GL.Version": "196610",
    "GL.Extensions": (
        "GL_OES_EGL_image,GL_OES_EGL_image_external,GL_OES_EGL_sync,"
        "GL_OES_vertex_half_float,GL_OES_framebuffer_object,"
        "GL_OES_rgb8_rgba8,GL_OES_compressed_ETC1_RGB8_texture,"
        "GL_EXT_texture_format_BGRA8888,GL_OES_texture_npot,"
        "GL_OES_packed_depth_stencil,GL_OES_depth24,"
        "GL_OES_depth_texture,GL_OES_texture_float,"
        "GL_OES_texture_half_float,GL_OES_element_index_uint,"
        "GL_OES_vertex_array_object"
    ),
}

# Tested priority order: profiles that dispensers accept most reliably, and
# that restricted apps (banking apps like Chase) tolerate. Pixel 9a first.
_PRIORITY_ARM64 = ["Pv", "D2", "eV", "iq", "Fj", "HE", "VP", "Hb", "p6", "B1"]
_PRIORITY_ARMV7 = ["XK", "Gj", "IV", "Gb"]
_PRIORITY_X86 = ["x8", "7M"]
_PRIORITY_TV = ["Gb"]

# ABI token to look for in a profile's Platforms list, per --arch value.
ABI_TOKENS = {
    "arm64": "arm64-v8a",
    "armv7": "armeabi-v7a",
    "x86": "x86",
    "x86_64": "x86_64",
}

# Features that mark a device profile as an Android TV.
_TV_FEATURES = ("android.hardware.type.television", "android.software.leanback")


def is_tv_profile(profile: dict) -> bool:
    features = profile.get("Features", "")
    return any(f in features for f in _TV_FEATURES)


def _load_properties(filepath: Path) -> dict:
    """Parse a Java-style .properties file into a dict."""
    profile: dict[str, str] = {}
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                profile[key] = val
    return profile


def load_all_profiles() -> dict:
    """Load every .properties file from the profiles directory."""
    profiles: dict[str, dict] = {}
    if not PROFILES_DIR.exists():
        return profiles
    for fp in sorted(PROFILES_DIR.glob("*.properties")):
        profile = _load_properties(fp)
        platforms = profile.get("Platforms", "")
        if "arm64-v8a" in platforms:
            arch = "arm64"
        elif "armeabi-v7a" in platforms:
            arch = "armv7"
        elif "x86" in platforms:
            arch = "x86"
        else:
            arch = "unknown"
        profiles[fp.stem] = {
            "name": profile.get("UserReadableName", fp.stem),
            "arch": arch,
            "profile": profile,
        }
    return profiles


_ALL = load_all_profiles()

ARM64_PROFILES: list[tuple[str, dict]] = [
    (k, d["profile"]) for k, d in _ALL.items() if d["arch"] == "arm64"
]
ARMV7_PROFILES: list[tuple[str, dict]] = [
    (k, d["profile"]) for k, d in _ALL.items() if d["arch"] == "armv7"
]
TV_PROFILES: list[tuple[str, dict]] = [
    (k, d["profile"]) for k, d in _ALL.items() if is_tv_profile(d["profile"])
]


def _profiles_supporting(abi_token: str) -> list[tuple[str, dict]]:
    """All profiles whose Platforms list contains *abi_token*."""
    return [
        (k, d["profile"]) for k, d in _ALL.items()
        if abi_token in d["profile"].get("Platforms", "")
    ]


def get_priority_profiles(arch: str = "arm64") -> list[tuple[str, dict]]:
    """Return profiles ordered by reliability (best first).

    *arch* is an ABI family, or "tv" for Android TV devices.
    """
    if arch == "armv7":
        priority, pool = _PRIORITY_ARMV7, ARMV7_PROFILES
    elif arch in ("x86", "x86_64"):
        priority, pool = _PRIORITY_X86, _profiles_supporting(ABI_TOKENS[arch])
    elif arch == "tv":
        priority, pool = _PRIORITY_TV, TV_PROFILES
    else:
        priority, pool = _PRIORITY_ARM64, ARM64_PROFILES

    seen: set[str] = set()
    result: list[tuple[str, dict]] = []

    for key in priority:
        for pkey, profile in pool:
            if pkey == key and pkey not in seen:
                result.append((pkey, profile))
                seen.add(pkey)
                break

    for pkey, profile in pool:
        if pkey not in seen:
            result.append((pkey, profile))
            seen.add(pkey)

    return result


def get_compat_profiles(arch: str = "arm64") -> list[tuple[str, dict]]:
    """Profiles most likely to be served old or unusual app versions.

    Google refuses delivery (status 2) when a version does not match the
    device: 2014-era APKs are often armeabi-v7a only, and Android 14+
    profiles are not served APKs targeting very old SDKs. So prefer low-SDK
    devices that support many ABIs.
    """
    if arch == "tv":
        pool = list(TV_PROFILES)
    else:
        pool = _profiles_supporting(ABI_TOKENS.get(arch, "arm64-v8a"))

    def sort_key(item: tuple[str, dict]) -> tuple[int, int]:
        profile = item[1]
        try:
            sdk = int(profile.get("Build.VERSION.SDK_INT", "99"))
        except ValueError:
            sdk = 99
        abi_count = len(profile.get("Platforms", "").split(","))
        return (sdk, -abi_count)

    return sorted(pool, key=sort_key)


def get_discovery_profiles(arch: str = "arm64") -> list[tuple[str, dict]]:
    """Profiles for apps that are invisible to the usual phone profiles.

    An app can be limited to a form factor (Android TV) or an ABI family
    (armv7-only, x86-only), so trying many similar phones does not help.
    Instead try one device of each kind: the most compatible device of the
    requested family, every TV, then the most compatible device of each
    other ABI family.
    """
    candidates: list[tuple[str, dict]] = []
    candidates += get_compat_profiles(arch)[:1]
    candidates += TV_PROFILES
    for other in ("armv7", "arm64", "x86_64"):
        if other != arch:
            candidates += get_compat_profiles(other)[:1]

    seen: set[str] = set()
    result: list[tuple[str, dict]] = []
    for key, profile in candidates:
        if key not in seen:
            seen.add(key)
            result.append((key, profile))
    return result
