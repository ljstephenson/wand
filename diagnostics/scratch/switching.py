"""
switcher switches
"""

INTERVAL=1

class Switcher(object):
    """
    Global state of the switcher

    :attr channel:
        number of current channel selected

    :attr locked:
        None if unlocked, else channel number of channel locked to

    :attr lock_time:
        time lock was requested, to allow timeout

    :attr channels:
        channels configured for this switcher

    :attr clients:
        clients to send information to

    :meth switch:
        switch to a channel
    """
    def __init__(self):
        self.channel = None
        self.locked = False
        self.channels = {}
        self.clients = {}

    def run(self):
        """
        normal operation mode, switch between channels periodically
        """

    def switch(self, channel):
        # Act only if on wrong channel
        if self.channel != channel:
            # Stop current collections

            # Interface with the switcher

            # Change stored number
            self.channel = channel

            # Restart collections

    def lock(self, channel):
        """
        lock to a channel
        """
        self.locked = True