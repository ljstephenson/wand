"""
Client specific representation of a server
"""
import collections

import wand.common as common
from wand.client.channel import Channel


class Server(common.JSONConfigurable):
    """
    Client implementation of server
    """
    _attrs = collections.OrderedDict([
        ('name', None),
        ('host', None),
        ('port', None),
        ('channels', Channel),
        ('all_channels', Channel),
        ('locked', None),
        ('pause', None),
        ('fast', None),
        ('uptime', None)
    ])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.connected = False
        self.client = None

    @property
    def addr(self):
        return (self.host, self.port)
