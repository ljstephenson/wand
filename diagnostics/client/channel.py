"""
Client specific extension of channel class
"""
import collections
from copy import copy

import diagnostics.common as common


class ClientChannel(common.Channel):
    """
    Client implementation of channel

    We expect the _attrs (except name) to be configured initially by the
    server. Some can be indirectly edited by a client - the client does not
    edit its instance of the channel, but instead communicates the change to
    the server, which echoes the change to all listening clients.
    """
    def __init__(self, client, *args, **kwargs):
        self.client = client
        super().__init__(*args, **kwargs)