#!/usr/bin/env python

import sys
from setuptools import setup

REQ_PYTHON = (3,3)
assert sys.version_info >= REQ_PYTHON, \
    "python >= {} is required".format(".".join(map(str, REQ_PYTHON)))

setup(name='imageproxy',
      version='1.0',
      description='Extremely Minimalist Image Processing Proxy',
      scripts=['scripts/imageproxy.py'],
      install_requires=['Pillow>=2.0.0', 'tornado>=3.0.1'],
     )
