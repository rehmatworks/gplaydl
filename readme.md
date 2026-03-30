# gplaydl

Download APKs from Google Play Store using anonymous authentication. Downloads base APKs, split APKs (App Bundles), OBB expansion files, and Play Asset Delivery packs — all by default.

> **v2.0 — Complete Rewrite.** Ground-up rewrite with a new CLI, pure-Python protobuf decoding (no `gpapi` dependency), and automatic token management. Looking for v1.x? See the [`master`](https://github.com/rehmatworks/gplaydl/tree/master) branch.

## Features

- Anonymous authentication via Aurora Store's token dispenser (no Google account needed)
- 23 device profiles with automatic rotation for reliable token acquisition
- Downloads base APK, split APKs, OBB files, and asset packs in one go
- Streaming gzip decompression for Play Asset Delivery packs
- Beautiful terminal UI with real-time download progress bars
- Architecture support: ARM64 (modern phones) and ARMv7 (older phones)
- Custom token dispenser URL support
- Search and browse app details from the command line

## Installation

**Requirements:** Python 3.9+

```bash
pip install gplaydl
```

### Install from source

```bash
git clone https://github.com/rehmatworks/gplaydl.git
cd gplaydl
pip install .
```

## Quick Start

```bash
# 1. Get an auth token (automatic, anonymous)
gplaydl auth

# 2. Download an app (base APK + splits + OBB/asset packs)
gplaydl download com.whatsapp
```

## Commands

### `auth` — Acquire an authentication token

```bash
gplaydl auth                          # Default (arm64)
gplaydl auth --arch armv7             # Token for older ARM devices
gplaydl auth -d https://my-server/api # Use a custom dispenser
gplaydl auth --clear                  # Remove all cached tokens
```

Tokens are cached at `~/.config/gplaydl/auth-{arch}.json` and reused automatically by other commands.

### `download` — Download APKs

By default, `download` fetches the base APK, all split APKs, and any additional files (OBB expansion files, Play Asset Delivery packs).

```bash
gplaydl download com.whatsapp                  # Everything (base + splits + extras)
gplaydl download com.whatsapp -o ./apks        # Custom output directory
gplaydl download com.whatsapp -a armv7          # ARMv7 build
gplaydl download com.whatsapp -v 231205015      # Specific version code
gplaydl download com.whatsapp --no-splits       # Skip split APKs
gplaydl download com.whatsapp --no-extras       # Skip OBB / asset packs
gplaydl download com.whatsapp -d https://...    # Use custom dispenser
```

**Output files:**

| Type | Naming | Example |
|------|--------|---------|
| Base APK | `{package}-{vc}.apk` | `com.whatsapp-231205015.apk` |
| Split APK | `{package}-{vc}-{split}.apk` | `com.whatsapp-231205015-config.arm64_v8a.apk` |
| OBB (main/patch) | `{type}.{vc}.{package}.obb` | `main.20925.com.tencent.ig.obb` |
| Asset pack | `{package}-{vc}-asset.apk` | `com.tencent.ig-20925-asset.apk` |

Split APKs can be installed to a device with:

```bash
adb install-multiple *.apk
```

### `info` — Show app details

```bash
gplaydl info com.whatsapp
```

Displays app name, version, developer, rating, download count, and Play Store URL.

### `search` — Search for apps

```bash
gplaydl search "whatsapp"
gplaydl search "file manager" --limit 5
```

### `list-splits` — List available split APKs

```bash
gplaydl list-splits com.whatsapp
```

Shows all split APK names (config splits, language splits, etc.) without downloading.

## Running without installing

```bash
python -m gplaydl auth
python -m gplaydl download com.whatsapp
```

## How It Works

1. **Authentication** — Gets an anonymous token from Aurora Store's dispenser, rotating through device profiles for reliability
2. **Details** — Fetches app metadata (version, size, splits) via Google Play's protobuf API
3. **Purchase** — "Purchases" the free app to get download authorization
4. **Delivery** — Gets download URLs for the base APK, split APKs, OBB files, and asset packs
5. **Download** — Streams all files in parallel from Google Play CDN with progress tracking

## Token Dispenser

The tool uses [Aurora Store's](https://auroraoss.com/) public token dispenser by default (`https://auroraoss.com/api/auth`). This service provides anonymous Google Play authentication tokens — no personal Google account required.

You can point to a custom/self-hosted dispenser with the `--dispenser` / `-d` flag on any command:

```bash
gplaydl auth -d https://my-dispenser.example.com/api/auth
gplaydl download com.whatsapp -d https://my-dispenser.example.com/api/auth
```

## Device Profiles

The tool includes 23 device profiles from Aurora Store, used to authenticate with Google Play's token dispenser. Profiles are rotated automatically during token acquisition to maximize compatibility.

Profiles are stored as `.properties` files in the `gplaydl/profiles/` directory.

## Architecture Support

| Flag | ABI | Devices |
|------|-----|---------|
| `arm64` (default) | arm64-v8a | Modern phones (2017+) |
| `armv7` | armeabi-v7a | Older 32-bit phones |

## License

MIT — see [LICENSE](LICENSE) for details.
