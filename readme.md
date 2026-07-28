# gplaydl

Download APKs from Google Play right from your terminal. One command gets you the base APK, split APKs (App Bundles), OBB expansion files and Play Asset Delivery packs, and you never need a Google account.

- Anonymous authentication through a token dispenser
- Base APK, splits, OBB files and asset packs downloaded together by default
- 23 device profiles, rotated automatically so authentication keeps working
- Pure-Python protobuf decoding, no `gpapi` dependency
- Live progress bars, plus `search`, `info` and `list-splits` for browsing

## Help build the community pool

gplaydl has always borrowed anonymous tokens from Aurora Store's dispenser. That works, but it is not fair to lean on someone else's service forever, so gplaydl now runs [its own dispenser](https://dispenser.gplaydl.com) ([source](https://github.com/rehmatworks/gplaydl-dispenser)). It is stocked entirely with accounts that people have shared.

If you have a throwaway Google account to spare, you can help. It takes about two minutes:

1. Install the [gplaydl Authenticator](https://dispenser.gplaydl.com) app on any Android device ([source](https://github.com/rehmatworks/gplaydl-authenticator)).
2. Sign in with a spare Google account. Please do not use your personal one.
3. Choose "Share with community".

Your password and 2FA codes never leave your phone. The app uploads only the resulting Play token and the account's email address. If you change your mind, you can make an account private again or delete it from the app at any time.

Once the pool is big enough to depend on, gplaydl will use it by default and stop calling Aurora's. Until then Aurora stays the default and ours is opt-in:

```bash
gplaydl auth -d https://dispenser.gplaydl.com/api/auth
gplaydl download com.whatsapp -d https://dispenser.gplaydl.com/api/auth
```

Pass `-d` on whichever command you run, so token refreshes keep using the pool too. Any dispenser that speaks the same API works, including [one you host yourself](https://github.com/rehmatworks/gplaydl-dispenser). Every account shared brings the switch closer.

gplaydl mentions this once a week after a download. If you would rather it did not, set `GPLAYDL_NO_BANNER=1`.

## Installation

Requires Python 3.9 or newer.

```bash
pip install gplaydl
```

Or from source:

```bash
git clone https://github.com/rehmatworks/gplaydl.git && cd gplaydl
pip install .                             # or skip this and run it in place:
python -m gplaydl download com.whatsapp
```

## Quick start

```bash
gplaydl auth                    # get an anonymous token
gplaydl download com.whatsapp   # base APK + splits + OBB/asset packs
```

## Commands

Every command takes `-d/--dispenser` to pick a dispenser and `--arch` for the device architecture.

### `auth`

Gets an anonymous token and caches it.

```bash
gplaydl auth                              # default (arm64)
gplaydl auth --arch armv7                 # older 32-bit devices
gplaydl auth --clear                      # forget all cached tokens
```

Tokens live in `~/.config/gplaydl/auth-{arch}.json`. The other commands reuse them and refresh them automatically before they expire.

### `download`

Fetches the base APK, every split APK, and any extra files unless you opt out.

```bash
gplaydl download com.whatsapp                # everything
gplaydl download com.whatsapp -o ./apks      # custom output directory
gplaydl download com.whatsapp -a armv7       # ARMv7 build
gplaydl download com.whatsapp -v 231205015   # specific version code
gplaydl download com.whatsapp --no-splits    # skip split APKs
gplaydl download com.whatsapp --no-extras    # skip OBB / asset packs
```

| Type | Naming | Example |
|------|--------|---------|
| Base APK | `{package}-{vc}.apk` | `com.whatsapp-231205015.apk` |
| Split APK | `{package}-{vc}-{split}.apk` | `com.whatsapp-231205015-config.arm64_v8a.apk` |
| OBB (main/patch) | `{type}.{vc}.{package}.obb` | `main.20925.com.tencent.ig.obb` |
| Asset pack | `{package}-{vc}-asset.apk` | `com.tencent.ig-20925-asset.apk` |

Install a split build on a device with `adb install-multiple *.apk`.

### `info`, `search` and `list-splits`

```bash
gplaydl info com.whatsapp                 # version, developer, rating, downloads
gplaydl search "file manager" --limit 5   # find apps by name
gplaydl list-splits com.whatsapp          # see splits without downloading
```

## Architecture support

| Flag | ABI | Devices |
|------|-----|---------|
| `arm64` (default) | arm64-v8a | Modern phones (2017+) |
| `armv7` | armeabi-v7a | Older 32-bit phones |

## How it works

1. **Authenticate.** The dispenser hands back an anonymous Play token, trying device profiles in turn until one is accepted.
2. **Look up.** App metadata (version, size, split list) comes from Google Play's protobuf API.
3. **Purchase.** Free apps are "purchased" to authorise the download.
4. **Download.** Base APK, splits, OBB files and asset packs stream in parallel from Google's CDN.

## License

MIT. See [LICENSE](LICENSE).
