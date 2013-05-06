#!/usr/bin/env python

from setuptools import setup

setup(name='imageproxy',
      version='1.0',
      description='Extremely Minimalist Image Processing Proxy',
      scripts=['scripts/imageproxy.py'],
      install_requires=['Pillow>=2.0.0', 'tornado>=3.0.1'],
     )
