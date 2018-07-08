import os
from setuptools import setup


# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


setup(
    name="optimHodgHux",
    version="0.0.1",
    author="Marc Javin",
    author_email="javin.marc@gmail.com",
    description=("Optimization suite for biological neural circuits"),
    long_description=read('README.rst'),
    license=read('LICENSE'),
    keywords="optimization neuron network machine learning neuroscience",
    url="https://gitlab.com/MarcusJP/opt_HH",
    packages=['opthh']
)
