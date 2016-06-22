"""
Client specific extension of channel class
"""
import collections

import wand.common as common


class Channel(common.JSONConfigurable):
    """
    Client implementation of channel

    We expect the _attrs (except name) to be configured initially by the
    server. Some can be indirectly edited by a client - the client does not
    edit its instance of the channel, but instead communicates the change to
    the server, which echoes the change to all listening clients.
    """
    _attrs = collections.OrderedDict([
                ('name', None),
                ('short_name', None),
                ('reference', None),
                ('exposure', None),
                ('number', None),
                ('array', None),
                ('blue', None),
            ])
    def __init__(self, client, *args, **kwargs):
        self.client = client
        super().__init__(*args, **kwargs)

    @property
    def detuning(self):
        return (self.frequency - self.reference)

    def lock(self):
        pass

    def unlock(self):
        pass
