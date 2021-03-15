import os
from setuptools import setup


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname),
                encoding='utf-8').read()


def strip_comments(string):
    return string.split('#', 1)[0].strip()


def reqs(*f):
    return list(filter(None, [strip_comments(string) for string in open(
        os.path.join(os.getcwd(), *f)).readlines()]))


setup(
    name="firestore_filling",
    version="0.0.1",
    author="Alexei Simacov",
    author_email="alexei.simacov@gmail.com",
    description=("An demonstration of how to fill cloud firebase collectons "
                 "with data from MS SQL Server"),
    license="MIT",
    keywords="cloud firestore, ms sql server",
    url="https://github.com/a-simacov/firestore_filling.git",
    long_description=read('readme.md'),
    install_requires=reqs('requirements.txt'),
    include_package_data=True
)
