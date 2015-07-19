# Based on setup.py from https://github.com/pypa/sampleproject

from setuptools import setup, find_packages

setup(
    name="krill",

    version="0.1.0",

    description="Read and filter web feeds",
    long_description="For a detailed description, see https://github.com/p-e-w/krill.",

    url="https://github.com/p-e-w/krill",

    author="Philipp Emanuel Weidmann",
    author_email="pew@worldwidemann.com",

    license="GPLv3",

    classifiers=[
        "Development Status :: 3 - Alpha",

        "Intended Audience :: End Users/Desktop",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content :: News/Diary",

        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",

        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
        "Programming Language :: Python :: 3.4",
    ],

    keywords="news feed rss atom twitter",

    packages=find_packages(),

    install_requires=[
        "beautifulsoup4",
        "feedparser",
        "blessings",
    ],

    entry_points={
        "console_scripts": [
            "krill = krill.krill:main",
        ],
    },
)
