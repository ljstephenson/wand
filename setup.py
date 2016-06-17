from setuptools import setup

scripts = [
    "wand_server=wand.server.main:main",
    "wand_client=wand.client.main:main",
]

setup(name='wand',
    version='0.1.0',
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
        'json-rpc>=1.10',
        'PyDAQmx>=1',
        'quamash',
    ]
)
