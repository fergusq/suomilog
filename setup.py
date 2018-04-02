from setuptools import setup

setup(
	name='suomilog',
	version='0.2',
	description='Collection of natural language parsing utilities',
	url='http://github.com/fergusq/suomilog',
	author='Iikka Hauhio',
	author_email='iikka.hauhio@gmail.com',
	license='GPL',
	classifiers=[
		'Programming Language :: Python :: 3'
	],
	packages=['suomilog'],
	python_requires='>=3',
	install_requires=['voikko'],
)
