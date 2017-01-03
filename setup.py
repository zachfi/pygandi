from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='pygandi',
    version='0.1.0',
    description='A simple wrapper around some features of the Gandi API',
    long_description=long_description,
    license='BSD',
    packages=find_packages(exclude=['contrib']),
)
