#!/usr/bin/env python
from setuptools import setup

setup(name = "python-loggerds",
      version = "0.1.0",
      description = "Logger device which logs stuff to Elasticsearch",
      packages = ['loggerds'],
      scripts = ['scripts/loggerds']
)
