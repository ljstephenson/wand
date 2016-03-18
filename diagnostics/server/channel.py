"""
Server specific extension of channel class
"""
import weakref

import diagnostics.common as common


class ServerChannel(common.Channel):
    """
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.clients = weakref.WeakValueDictionary()

    def add_client(self, client, conn):
        self.clients[client] = conn

    def remove_client(self, client):
        if client in self.clients:
            del self.clients[client]