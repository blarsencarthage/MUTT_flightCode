from setuptools import setup

setup(
    name='Pilpxi',
    version='1.7',
    packages=['pilpxi'],
    url='https://downloads.pickeringtest.info/downloads/drivers/PXI_Drivers/',
    license='',
    author='Pickering Interfaces',
    author_email='support@pickeringtest.com',
    description='Python wrapper library for Pickering PXI Direct-IO driver',
    install_requires=['enum34']
)
