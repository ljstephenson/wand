from setuptools import setup, find_packages
import sys

scripts = [
    "wand_server=wand.server.main:main",
    "wand_client=wand.client.main:main",
]

requirements=['json-rpc>=1.10']
if '--conda' not in sys.argv:
   requirements += ['influxdb>=2', 'PyDAQmx>=1']
else:
    index = sys.argv.index('--conda')
    sys.argv.pop(index)  # Removes the '--conda'

setup(
    name='wand',
    version='2.1.4',
    url='https://github.com/ljstephenson/wand',
    author='Laurent Stephenson',
    packages=find_packages(),
    entry_points={
        "console_scripts": scripts,
    },
    install_requires=requirements,
    package_data={'wand': ['resources/*.svg', 'resources/*.json']},
    include_package_data=True
)
