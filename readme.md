# Command Line APK Downloader
Download APK & expansion (OBB) files from Google Play Store to your PC or server directly. A command line implementation of [NoMore201/googleplay-api](https://github.com/NoMore201/googleplay-api/).

## Installation
```bash
pip3 install gplaydl
```

or

```bash
git clone https://github.com/rehmatworks/gplaydl.git && \
cd gplaydl && \
python3 setup.py install
```
**Attention:** Only Python 3.2.x and up is supported. Please use PIP3, not PIP (if PIP is aliast to Python 2.x PIP)

## Configuration
Soon after the package is installed, type `gplaydl configure` and hit enter. You will be asked to provide the login info. Provided the following details:

* Email: Your Google account's email address
* Password: Your Google account's password (An app password is recommended)

## Downloading Apps
Download WhatsApp using the default device (bacon) and store the APK in the current directory:

```bash
gplaydl download --packageId com.whatsapp
```

Download WhatsApp using the default device (bacon) and store the APK in a custom path (i.e. ./apk-downloads/):

```bash
gplaydl download --packageId com.whatsapp --path ./apk-downloads/
```

Download WhatsApp using another device, i.e. `angler` ([Available Devices](https://github.com/NoMore201/googleplay-api/blob/master/gpapi/device.properties))

```bash
gplaydl download --packageId com.whatsapp --device angler
```

### Expansion Files:
Since version 1.2.0, expansion files are downloaded as well if they are available. If you don't want to download expansion files, set the flag to false:

```bash
gplaydl download --packageid com.rayark.Cytus.full --ex False
```

### Change Google Account:
Your Google login info is stored in a cache file and whenever the tokens expire, login info from the cached file is used to refresh the tokens. If your Google account password is changed, you will be prompted to provided new details whenever you will attempt to download an app.

But if you want to change your Google account for gplaydl, simply reconfigure it and your new account will be set in the cache:

```bash
gplaydl configure
```

## Features
* Shows download progress (since v.1.2.0)
* No need to provide device ID (Generated automatically))
* No need to provide auth token (Generated automatically)
* Re-uses auth token and refreshes it if expired

## Web-based APK Downloader
I've launched an awesome <a href="https://apkbucket.net/apk-downloader/">web-based APK downloader here</a> that you can use to download APK files to your PC directly from Google Play Store. It supports split APKs as well and the download links from Google servers are directly served to you.

### Credits:
[NoMore201/googleplay-api](https://github.com/NoMore201/googleplay-api/)
