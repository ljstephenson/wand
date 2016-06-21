"""
Server specific implementation of channel class
"""
import collections
import weakref

import wand.common as common

__all__ = [
    'Channel',
]


@common.with_log
class Channel(common.JSONConfigurable):
    """
    Stores information about a switcher channel.

    - name: name for the channel (must be unique over *all* labs)
    - reference: reference frequency value to use when calculating detuning
    - exposure: integer exposure time (ms) to use for wavemeter
    - number: physical channel number on switcher
    - array: ccd array to use on wavemeter
    - blue: true if blue laser - dictates inputs to use on DAQ card
    """
    _attrs = collections.OrderedDict([
                ('name', None),
                ('reference', None),
                ('exposure', None),
                ('number', None),
                ('array', None),
                ('blue', None),
            ])
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.clients = weakref.WeakValueDictionary()

    def add_client(self, client, conn):
        self._log.debug("{}: Adding client: {}".format(self.name, client))
        self.clients[client] = conn

    def remove_client(self, client):
        if client in self.clients:
            self._log.debug("{}: Removing client: {}".format(self.name, client))
            del self.clients[client]
