#!/usr/bin/env python
from setuptools import setup

setup(name = "tangods-logger",
      version = "1.0.2",
      description = "Logger device which logs stuff to Elasticsearch",
      packages = ['loggerds'],
      scripts = ['scripts/loggerds']
)
