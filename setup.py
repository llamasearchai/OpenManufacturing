#!/usr/bin/env python3
"""
OpenManufacturing platform setup script.

This module contains the package metadata and installation configuration.
"""

from setuptools import find_packages, setup

with open("README.md", "r") as readme_file:
    long_description = readme_file.read()

with open("requirements.txt", "r") as req_file:
    requirements = req_file.read().splitlines()

setup(
    name="openmanufacturing",
    version="1.0.0",
    author="OpenManufacturing Team",
    author_email="info@openmanufacturing.org",
    description="Advanced optical packaging and assembly platform for manufacturing automation",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/llamasearchai/OpenManufacturing",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=requirements,
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Manufacturing",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Electronic Design Automation (EDA)",
    ],
    entry_points={
        "console_scripts": [
            "openmanufacturing=openmanufacturing.cli:main",
        ],
    },
)
