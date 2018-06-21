#!/usr/bin/python3
from gpapi.googleplay import GooglePlayAPI
import os
import sys
import argparse
import json
import pickle
from os.path import expanduser

ap = argparse.ArgumentParser(description='Command line APK downloader for Google Play Store.')
ap.add_argument('-c', '--configure', dest='configure', action='store_const', const=True, help='Create the configuration file by providing your Google email and password (preferably app password).', default=False)
ap.add_argument('-id', '--packageId', dest='packageId', help='Package ID of the app, i.e. com.whatsapp')
ap.add_argument('-e', '--email', dest='email', help='Google username', default=None)
ap.add_argument('-p', '--password', dest='password', help='Google password', default=None)
ap.add_argument('-d', '--directory', dest='storagepath', help='Path where to store downloaded files', default=False)
ap.add_argument('-dc', '--deviceCode', dest='deviceCode', help='Device code name', default='bacon')
ap.add_argument('-ex', '--expansionfiles', dest='expansionfiles', action='store_const', const=True, help='Download expansion (OBB) data if available', default=False)

args = ap.parse_args()

HOMEDIR = expanduser("~/.gplaydl/")
CACHEDIR = HOMEDIR+'cache/';
CACHEFILE = CACHEDIR + args.deviceCode + '.txt'
CONFIGDIR = HOMEDIR+'config/';
CONFIGFILE = CONFIGDIR + 'config.txt'

def write_cache(gsfId, token):
	if not os.path.exists(CACHEDIR):
		os.makedirs(os.path.dirname(CACHEDIR))
	info = {'gsfId': gsfId, 'token': token}
	pickle.dump(info, open(CACHEFILE, "wb"))

def read_cache():
	try:
		with open(CACHEFILE, "rb") as f:
			info = pickle.load(f)
	except:
		info = None
	return info

def refresh_cache(server, email, password):
	server.login(email, password, None, None)
	write_cache(server.gsfId, server.authSubToken)
	return server

def do_login(server, email, password):
	cacheinfo = read_cache()
	if cacheinfo:
		# Sign in using cached info
		try:
			server.login(None, None, cacheinfo['gsfId'], cacheinfo['token'])
		except:
			refresh_cache(email, password)
	else:
		# Re-authenticate using email and pass and save info to cache
		refresh_cache(server, email, password)
	return server

def main():  
	if args.email and args.password:
		email = args.email
		password = args.password
	else:
		email = None
		password = None

	if args.storagepath:
		storagepath = args.storagepath
	else:
		storagepath = './'

	if args.configure:
		if email is not None and password is not None:
			if not os.path.exists(CONFIGDIR):
				os.makedirs(os.path.dirname(CONFIGDIR))
			config = {'email': args.email, 'password': args.password}
			pickle.dump(config, open(CONFIGFILE, "wb"))
			print('Configuration file created successfully! Try downloading an APK file now.')
			sys.exit(1)
		else:
			print('Please provide email and password values.')
			sys.exit(1)

	if email is None and password is None:
		if os.path.exists(CONFIGFILE):
			with open(CONFIGFILE, "rb") as f:
				config = pickle.load(f)
				email = config['email']
				password = config['password']
		else:
			print('Please provide email and password or configure the credentials by running gplaydl --config')
			sys.exit(1)

	if args.packageId:
		server = GooglePlayAPI('en_US', 'America/New York', args.deviceCode)
		try:
			server = do_login(server, email, password)
		except:
			print('Login failed. Ensure that correct credentials are provided.')
			sys.exit(1)
		
		try:
			download = server.download(args.packageId, expansion_files=args.expansionfiles)
			apkpath = os.path.join(storagepath, download['docId'] + '.apk')
			if not os.path.isdir(storagepath):
				os.makedirs(storagepath)
			with open(apkpath, 'wb') as first:
				print('Downloading ' + download['docId'] + '.apk.....')
				for chunk in download.get('file').get('data'):
					first.write(chunk)
			print('APK downloaded and stored at ' + apkpath)

			if expansionfiles:
				for obb in download['additionalData']:
					name = obb['type'] + '.' + str(obb['versionCode']) + '.' + download['docId'] + '.obb'
					print('Downloading ' + name + '.....')
					obbpath = os.path.join(storagepath, download['docId'], name)
					if not os.path.isdir(os.path.join(storagepath, download['docId'])):
						os.makedirs(os.path.join(storagepath, download['docId']))
					with open(obbpath, 'wb') as second:
						for chunk in obb.get('file').get('data'):
							second.write(chunk)
					print('OBB file downloaded and stored at ' + obbpath)
			print('All done!')
		except:
			print('Download failed. gplaydl cannot download some apps that are paid or incompatible.')
	else:
		ap.print_help()