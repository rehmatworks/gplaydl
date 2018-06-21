# Command Line Utility to Download APK Files
Download APK files from Google Play Store to your PC directly.

## Installation
`pip3 install gplaydl`

## Usage:
```bash
-h, --help            show this help message and exit
-c, --configure       Create the configuration file by providing your Google
                     email and password (preferably app password).
-id, --packageId
                     Package ID of the app, i.e. com.whatsapp
-e, --email
                     Google username
-p, --password
                     Google password
-d, --directory
                     Path where to store downloaded files
-dc, --deviceCode
                     Device code name
-ex, --expansionfiles
                     Download expansion (OBB) data if available
```

### Examples
Save your email and password in config cache:
```
gplaydl --configure -e email@gmail.com -p passwordOrAppPassword
```
Download an APK file (i.e. WhatsApp):
```
gplaydl -id com.whatsapp
```

Use `gplaydl` without saving login info in cache:
```
gplaydl -id com.whatsapp -e email@gmail.com -p password
```

Store APK file in a custom directory:
```
gplaydl -id com.whatsapp -d folder-name-or-path
```

Download a game with expansion (OBB) files:
```
gplaydl -id com.rayark.Cytus.full
```

