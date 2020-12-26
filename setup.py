from setuptools import setup

setup(name='gplaydl',
	version='1.3.4',
	description='Google Play APK downloader command line utility that utilizes gpapi to download APK files of free apps and games.',
	author="Rehmat Alam",
	author_email="contact@rehmat.works",
	url="https://github.com/rehmatworks/gplaydl",
	python_requires='>3.2.0',
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
		'gpapidl',
		'validators',
		'termcolor'
	]
)
