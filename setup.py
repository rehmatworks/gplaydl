from setuptools import setup

setup(name='gplaydl',
	version='1.3.5',
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
		'certifi==2020.4.5.1',
		'cffi==1.14.0',
		'chardet==3.0.4',
		'cryptography==2.9',
		'decorator==4.4.2',
		'gpapidl==1.0.2',
		'idna==2.9',
		'protobuf==3.14.0',
		'pycparser==2.20',
		'requests==2.23.0',
		'six==1.14.0',
		'termcolor==1.1.0',
		'urllib3==1.25.8',
		'validators==0.14.3'
	]
)
