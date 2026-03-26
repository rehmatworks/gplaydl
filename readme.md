# gplaydl

Download APKs from Google Play Store using anonymous authentication. Supports single APKs, split APKs (App Bundles), and OBB expansion files.

> **v2.0 — Complete Rewrite.** This is a ground-up rewrite with a new CLI, pure-Python protobuf decoding (no `gpapi` dependency), and automatic token management. Looking for v1.x? See the [`master`](https://github.com/rehmatworks/gplaydl/tree/master) branch.

## Features

- Anonymous authentication via Aurora Store's token dispenser (no Google account needed)
- 23 device profiles with automatic rotation for reliable token acquisition
- Download base APKs, split APKs, and OBB expansion files
- Beautiful terminal UI with real-time download progress bars
- Architecture support: ARM64 (modern phones) and ARMv7 (older phones)
- Custom token dispenser URL support
- Search and browse app details from the command line

## Installation

**Requirements:** Python 3.9+

```bash
# Clone the repo
git clone https://github.com/rehmatworks/gplaydl.git
cd gplaydl

# Install in editable mode
pip install -e .
```

Or install dependencies directly:

```bash
pip install -r requirements.txt
```

## Quick Start

```bash
# 1. Get an auth token (automatic, anonymous)
gplaydl auth

# 2. Download an app
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

```bash
gplaydl download com.whatsapp                  # Base APK + splits
gplaydl download com.whatsapp -o ./apks        # Custom output directory
gplaydl download com.whatsapp -a armv7          # ARMv7 build
gplaydl download com.whatsapp -v 231205015      # Specific version code
gplaydl download com.whatsapp --no-splits       # Base APK only, skip splits
gplaydl download com.some.game --obb            # Include OBB expansion files
gplaydl download com.whatsapp -d https://...    # Use custom dispenser
```

Split APKs are saved as individual files. Install them to a device with:

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
4. **Delivery** — Gets download URLs for the base APK, split APKs, and OBB files
5. **Download** — Streams files from Google Play CDN with progress tracking

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
