from setuptools import setup

setup(name='gplaydl',
	version='1.0',
	description='Google Play APK downloader command line utility that utilizes gpapi to download APK files of free apps and games.',
	author="Rehmat",
	author_email="contact@rehmat.works",
	url="https://github.com/rehmatworks/gplaydl",
	license="MIT",
	entry_points={
		'console_scripts': [
			'gplaydl = gplaydl.gplaydl:main'
		],
	},
	packages=[
		'gplaydl'
	],
	install_requires=[
		'gpapi'
	]
)