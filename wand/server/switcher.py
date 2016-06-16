"""
Interface to switcher
"""
class Switcher(object):
    def __init__(self):
        self.channel = None

    def switch(self, channel):
        """Perform switch and store new channel"""
        if channel != self.channel:
            self.channel = channel
