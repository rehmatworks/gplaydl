# Command Line Utility to Download APK Files
Download APK files from Google Play Store to your PC directly.

## Usage:
```bash
-h, --help            show this help message and exit
-c, --configure       Create the configuration file by providing your Google
                     email and password (preferably app password).
-id PACKAGEID, --packageId PACKAGEID
                     Package ID of the app, i.e. com.whatsapp
-e EMAIL, --email EMAIL
                     Google username
-p PASSWORD, --password PASSWORD
                     Google password
-d STORAGEPATH, --directory STORAGEPATH
                     Path where to store downloaded files
-dc DEVICECODE, --deviceCode DEVICECODE
                     Device code name
-ex, --expansionfiles
                     Download expansion (OBB) data if available
```