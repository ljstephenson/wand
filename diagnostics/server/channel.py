"""
Server specific extension of channel class
"""
import diagnostics.common as common


class ServerChannel(common.Channel):
    """
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.clients = {}

    def add_client(self, client, conn):
        self.clients[client] = conn

    def remove_client(self, client):
        if client in self.clients:
            del self.clients[client]