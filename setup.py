from setuptools import setup

setup(
    name='Rattle Snake',
    version='0.8',
    packages=[''],
    install_requires=["usb", "PyQt5", "glob", "json", "pyqtgraph"],
    url='https://pss-gitlab.math.univ-paris-diderot.fr/sainton/guipioneers',
    license='',
    author='Gregory Sainton',
    author_email='sainton@ipgp.fr',
    description='Program to control displacement of a motor measured by an interferometer'
)
