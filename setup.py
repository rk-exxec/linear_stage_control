from setuptools import setup, find_packages


with open('README.md') as f:
    readme = f.read()

with open('LICENSE') as f:
    license = f.read()

with open('reqirements.txt') as f:
    requires = f.readlines()

setup(
    name='Linear Stage Control',
    version='0.1.0',
    description='Linear Stage Control is a program to control a single linear table via SMCI33-1',
    long_description=readme,
    author='Raphael Kriegl',
    author_email='40037381+rk-exxec@users.noreply.github.com',
    url='https://github.com/rk-exxec/linear_stage_control',
    license=license,
    packages=find_packages(),
    requires=requires
)