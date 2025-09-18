"""
Setup script for I2CTool.
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="i2ctool",
    version="0.1.0",
    author="Peter",
    description="I2C debugging tool with PySide6 GUI and hardware adapter support",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=[
        "PySide6>=6.5.0",
    ],
    extras_require={
        "dev": [
            "pytest",
            "pytest-qt",
        ],
    },
    entry_points={
        "console_scripts": [
            "i2ctool-gui=ui_pyside6.main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "configs": ["eeprom/*.json"],
    },
)