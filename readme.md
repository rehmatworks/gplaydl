# gplaydl

Download APKs from Google Play right from your terminal. One command gets you the base APK, split APKs (App Bundles), OBB expansion files and Play Asset Delivery packs.

gplaydl downloads through a Google account you add yourself in the Authenticator app. Your account stays private to you, and setup takes about two minutes.

- Base APK, splits, OBB files and asset packs downloaded together by default
- Signs in with your own account, kept private to you and never shared
- 23 device profiles, rotated automatically so authentication keeps working
- Pure-Python protobuf decoding, no `gpapi` dependency
- Live progress bars, plus `search`, `info` and `list-splits` for browsing

## Installation

Requires Python 3.9 or newer.

```bash
pip install gplaydl
```

Or from source:

```bash
git clone https://github.com/rehmatworks/gplaydl.git && cd gplaydl
pip install .
```

## First-time setup

You will need any Android phone for a couple of minutes, and a spare Google account to add.

1. Install the [gplaydl Authenticator](https://dispenser.gplaydl.com) app ([source](https://github.com/rehmatworks/gplaydl-authenticator)) on the phone. It is not on Google Play, so Android will ask you to allow the install.
2. Sign in with a spare Google account. Prefer a throwaway over your main one: Google sometimes restricts accounts it sees on unofficial clients. The account stays private to you and is never shared with anyone.
3. Open **Link gplaydl** in the app, then run this on your computer and type in the code it shows:

```bash
gplaydl link
```

Done. Every download now goes through your own account:

```bash
gplaydl download com.whatsapp
```

Your Google password and 2FA codes never leave the phone; the app uploads only the resulting Play token. You can remove an account in the app whenever you like, and if you skip `gplaydl link`, the first command that needs it will walk you through the same steps.

## Quick start

```bash
gplaydl link                    # once, with the code from the app
gplaydl download com.whatsapp   # base APK + splits + OBB/asset packs
```

## Commands

Every command takes `-d/--dispenser` to pick a dispenser and `--arch` for the device architecture.

### `link`

Pairs this machine with the dispenser. Run it once, or again to re-link.

```bash
gplaydl link                              # asks for the code interactively
gplaydl link --code ABCD-EFGH             # or pass it directly
gplaydl link -d https://your.dispenser    # link to a self-hosted dispenser
```

The key lands in `~/.config/gplaydl/config.json`. For containers and CI, set `GPLAYDL_API_KEY` instead of linking interactively.

If you added more than one account in the app, pass `--email you@gmail.com` on `auth` or `download` to use a specific one. Without it, gplaydl rotates through the accounts you added.

### `auth`

Gets a Play token and caches it. You rarely need to run this yourself; the other commands fetch and refresh tokens on their own.

```bash
gplaydl auth                              # default (arm64)
gplaydl auth --arch armv7                 # older 32-bit devices
gplaydl auth --clear                      # forget all cached tokens
```

Tokens live in `~/.config/gplaydl/auth-{arch}.json` and refresh automatically before they expire.

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

## Multiple accounts and purchased apps

You can add several accounts in the app. By default gplaydl rotates through them; pass `--email` to pick one, which is also how you download apps tied to a specific account:

```bash
gplaydl download com.example.paid --email you@gmail.com
```

A word of caution before adding an account you care about: Google can rate-limit, lock, or restrict accounts it sees on unofficial clients. It is uncommon, but it happens, which is why a throwaway account is the safer choice.

## Self-hosting

The dispenser is open source and runs anywhere Go and Postgres do. Host your own for a team or just for yourself:

1. Follow the [dispenser deployment guide](https://github.com/rehmatworks/gplaydl-dispenser).
2. In the Authenticator app, point **Settings → Server** at your instance and add accounts.
3. Link gplaydl against it: `gplaydl link -d https://your.dispenser`

## Architecture support

| Flag | ABI | Devices |
|------|-----|---------|
| `arm64` (default) | arm64-v8a | Modern phones (2017+) |
| `armv7` | armeabi-v7a | Older 32-bit phones |

## How it works

1. **Authenticate.** The dispenser mints a Play token from one of your own accounts and hands it back, trying device profiles in turn until one is accepted.
2. **Look up.** App metadata (version, size, split list) comes from Google Play's protobuf API.
3. **Purchase.** Free apps are "purchased" to authorise the download.
4. **Download.** Base APK, splits, OBB files and asset packs stream in parallel from Google's CDN.

## Upgrading from 3.x

gplaydl 4 drops the shared community pool: downloads now go through a Google account you add yourself, kept private to you. Add an account in the Authenticator app and run `gplaydl link` once after upgrading. (Older 2.x releases borrowed anonymous tokens from Aurora Store; that path is gone.)

## License

MIT. See [LICENSE](LICENSE).
