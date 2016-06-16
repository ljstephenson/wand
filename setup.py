from setuptools import setup

scripts = [
    "pulsar_server=pulsar.server:main",
    "pulsar_client=pulsar.client:main",
]

setup(name='pulsar',
    version='0.1',
    packages=['pulsar',
              'pulsar.common',
              'pulsar.client',
              'pulsar.server',
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
