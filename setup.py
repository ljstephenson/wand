from setuptools import setup

scripts = [
    "wand_server=wand.server:main",
    "wand_client=wand.client:main",
]

setup(name='wand',
    version='0.1',
    packages=['wand',
              'wand.common',
              'wand.client',
              'wand.server',
             ],
    entry_points={
        "console_scripts": scripts,
    },
    install_requires=[
        'influxdb>=2',
        'jsonrpc',
        'numpy>=1',
        'PyDAQmx>=1',
        'pyqt>=4',
        'pyqtgraph',
        'quamash'
    ],
    dependency_links=[
        'https://github.com/pavlov99/json-rpc/zipball/master'
    ]
)
