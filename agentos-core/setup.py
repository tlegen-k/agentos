from setuptools import setup, find_packages

version = '0.0.1'

setup(
    name='agentos-core',
    author='Andy Konwinski',
    version=version,
    #packages=find_packages(),
    install_requires=[
            'click>=7.0',
    ],
    entry_points='''
        [console_scripts]
        agentos-core=cli:agentos_cmd
    ''',
    license='Apache License 2.0',
)
