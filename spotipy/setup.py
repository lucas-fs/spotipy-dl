from setuptools import setup

setup(
    name='spotipy',
    version='2.4.5',
    description='simple client for the Spotify Web API',
    author="@plamere, @lucas-fs",
    author_email="paul@echonest.com, lfereira@inf.ufsm.br",
    url='http://spotipy.readthedocs.org/',
    install_requires=[
        'requests>=2.3.0',
        'six>=1.10.0',
    ],
    license='LICENSE.txt',
    packages=['spotipy'])
