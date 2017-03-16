from setuptools import setup, find_packages

setup(
    name='amphitrite',
    version='0.1',
    packages=find_packages(),
    author='cosine',
    author_email='ksitht@gmail.com',
    url='https://github.com/cosine0/amphitrite',
    description='Symbolic binary debugging tool using Triton',
    install_requires=['sympy', 'psutil']
)
