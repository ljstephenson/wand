"""
Interface to Leoni Fibre switcher
"""
import socket
import time

from wand.common import with_log

@with_log
class LeoniSwitcher(object):
    def __init__(self, host, port=10001):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect((host, port))
        self._log.info('Connected')

        self.nChannels = None
        self.getNumChannels()

    def _sendCommand(self, command):
        str = command+'\r\n'
        self._log.debug("Sending command: {}".format(command))
        self.s.sendall( str.encode() )

        if command.endswith('?'):
            resp = self.s.recv(1024).decode().strip()
            self._log.debug("Response: {}".format(resp))
            return resp
        else:
            return None

    def getNumChannels(self):
        if self.nChannels is None:
            # reply is "eol 1x16"
            self.nChannels = int( self._sendCommand('type?')[6:] )
            self._log.debug('nChannels = {}'.format(self.nChannels))
        return self.nChannels

    def firmware(self):
        """Get the firmware version"""
        return self._sendCommand('firmware?')

    def setChannel(self, channel):
        """Select the given channel number"""
        if channel < 0 or channel >= self.nChannels:
            raise ValueError('Channel out of bounds')
        self._sendCommand( 'ch{}'.format(channel) )
        time.sleep(2e-3)

    def getChannel(self):
        """Get the currently selected channel number"""
        return int(self._sendCommand('ch?'))
