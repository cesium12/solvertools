#!/usr/bin/env python
VERSION = "2017.0"

from setuptools import find_packages, setup

setup(
    name="solvertools",
    version=VERSION,
    packages=find_packages(),
    install_requires=[
        'nltk', 'whoosh', 'unidecode', 'natsort', 'flask', 'wordfreq'
    ],
)
