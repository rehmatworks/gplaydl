# Command Line APK Downloader
Download APK, split APKs, and expansion (OBB) files from Google Play Store to your personal computer or server directly with minimum effort.

## Brief Instructions
```bash
# Install the package
pip3 install --upgrade --force-reinstall gplaydl

# Configure auth
gplaydl configure

# Let's try downloading an app
gplaydl download --packageId com.whatsapp
```

## Detailed Instructions
So the brief instructions didn't get you going? Here is a detailed guide for you. Let's begin with installing the package using PIP3.

```bash
pip3 install --upgrade --force-reinstall gplaydl
```

If `gplaydl` is already installed on your system, it will be upgraded to the latest version as we are forcing PIP to install from the latest release.

or

```bash
git clone https://github.com/rehmatworks/gplaydl.git && \
cd gplaydl && \
python3 setup.py install
```
**Attention:** Only Python 3.2.x and up is supported. Please use PIP3, not PIP (if PIP is aliased to Python 2.x PIP)

## Configuration
Soon after the package is installed, type the following and hit enter:

```bash
gplaydl configure
```

You will be asked to provide the login info. Provided the following details:

* Email: Your Google account's email address
* Password: Your Google account's password (An app password is recommended)

## Downloading Apps
Download WhatsApp using the default device **Nexus 6 (api27) [shamu]** and store the APK in the current directory:

```bash
gplaydl download --packageId com.whatsapp
```

Download WhatsApp using the default device **Nexus 6 (api27) [shamu]** and store the APK in a custom path (i.e. ./apk-downloads/):

```bash
gplaydl download --packageId com.whatsapp --path ./apk-downloads/
```

Download WhatsApp using another device, i.e. `angler` ([Available Devices](https://github.com/NoMore201/googleplay-api/blob/master/gpapi/device.properties))

```bash
gplaydl download --packageId com.whatsapp --device angler
```

### Expansion Files:
Since version 1.2.0, expansion files are downloaded as well if available. If you don't want to download those files, set the flag to `n`:

```bash
gplaydl download --packageid com.rayark.Cytus.full --ex n
```

### Split APKs:
Since version 1.3.0, split APK files are downloaded as well if available. If you don't want to download split APKs, set the flag to `n`:

```bash
gplaydl download --packageid com.twitter.android --splits n
```

### Change Google Account:
Your Google login info is stored in a cache file and whenever the tokens expire, login info from the cached file is used to refresh the tokens. If your Google account password is changed, you will be prompted to provided new details whenever you will attempt to download an app.

But if you want to change your Google account for gplaydl, simply reconfigure it and your new account will be set in the cache:

```bash
gplaydl configure
```

## Features
* Full support for split APKs (since v.1.3.0)
* Full support for OBB aka. expansion files (since v.1.3.0)
* Supports download of (your purchased) paid apps (since v.1.3.0)
* Shows download progress (since v.1.2.0)
* No need to provide device ID (Generated automatically))
* No need to provide auth token (Generated automatically)
* Re-uses auth token and refreshes it if expired

## Web-based APK Downloader
Aren't comfortable using CLI tools? Use my <a href="https://apkbucket.net/apk-downloader/">web-based APK downloader here</a>.

### Credits:
[NoMore201/googleplay-api](https://github.com/NoMore201/googleplay-api/)
