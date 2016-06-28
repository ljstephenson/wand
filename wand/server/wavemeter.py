"""
Wavemeter interface
"""
import ctypes
import asyncio
import enum
from wand.common import with_log

__all__ = [
    'WavemeterError',
    'WavemeterTask',
    'init',
    'switch',
    'set_frequency'
]

# Approx collection frequency
_FREQUENCY = 10
def set_frequency(frequency):
    global _FREQUENCY
    _FREQUENCY = frequency

# -----------------------------------------------------------------------------
# Constants
#
# (Should be able to get these from the DLL, but had some difficulties)
@enum.unique
class WavemeterError(enum.Enum):
    """
    Values returned on error from GetFrequencyNum
    """
    NoValue = 0
    NoSignal = -1
    BadSignal = -2
    LowSignal = -3
    BigSignal = -4
    WlmMissing = -5
    NotAvailable = -6
    NothingChanged = -7
    NoPulse = -8

# Instantiating Constants for 'RFC' parameter
cInstNotification = 1

# Notification constants for 'Mode' parameter
cNotifyInstallCallback = 1
cNotifyRemoveCallback = 2

# Operation Mode Constants
cStop = ctypes.c_ushort(0)
cAdjustment = ctypes.c_ushort(1)
cMeasurement = ctypes.c_ushort(2)

# Measurement triggering action constants
cCtrlMeasurementTriggerSuccess = 3
# -----------------------------------------------------------------------------

def init():
    """
    Initialise the wavemeter
    """
    global lib

    # Open the DLL
    lib = ctypes.WinDLL('C:\Windows\system32\wlmData.dll')

    lib.GetFrequencyNum.restype = ctypes.c_double
    lib.Instantiate.restype = ctypes.c_long

    # Turn off auto-switcher mode
    lib.SetSwitcherMode( ctypes.c_long(0) )

    # Turn off auto exposure in all channels (1-8)
    for i in range(8):
        lib.SetExposureModeNum(i+1, 0)

    # Set to measuring normally
    lib.Operation(cMeasurement)


def switch(number=1):
    """
    Switch to the supplied channel number
    """
    lib.SetSwitcherChannel(number)

# Callback type to be defined. This must be in scope as long as the callback is
# in use, so just define it here
CALLBACK = ctypes.CFUNCTYPE(None, ctypes.c_long, ctypes.c_long, ctypes.c_double)
@with_log
class WavemeterTask(object):
    """
    Instantiate a new task every channel switch

    Notes:
        - The wavemeter can have a callback function registered that will fire
          whenever the wavemeter's state changes (channel switch, new
          measurement etc). This has not yet been implemented.
        - The current implementation polls the wavemeter, but is non-blocking
          thanks to the asyncio library
    """
    def __init__(self, loop, queue, channel):
        """initialise"""
        self._log.debug("Creating Task object for channel: {}".format(channel.name))
        self.loop = loop
        self.queue = queue
        self.channel = channel
        self._active = False
        self._future = None
        self._callback = None
        self._mode = "poll"

        lib.SetExposureNum(self.channel.number,
                           self.channel.array,
                           self.channel.exposure)

    def StartTask(self):
        """Start collections"""
        self._active = True

        if self._mode == "poll":
            # Schedule the first poll
            self._future = self.loop.create_task(self.measure())
        elif self._mode == "callback":
            # Register the callback function
            retval = lib.Instantiate(cInstNotification, cNotifyInstallCallback,
                                     self.get_cb(), 0)
            self._log.debug("Callback registering returned {}".format(retval))

    def StopTask(self):
        """Stop collections"""
        if self._mode == "poll":
            self.loop.call_soon_threadsafe(self._future.cancel)
            self._future = None
        elif self._mode == "callback":
            # Unregister the callback
            lib.Instantiate(cInstNotification, cNotifyRemoveCallback, 0, 0)

        self._active = False

    def ClearTask(self):
        """No-op so that wavemeter and OSA have identical APIs"""
        pass

    def setExposure(self):
        """Call after updating channel exposure"""
        self._log.debug("Changing exposure time")
        lib.SetExposureNum(self.channel.number,
                           self.channel.array,
                           self.channel.exposure)

    # -------------------------------------------------------------------------
    # Polling operation functions
    #
    async def measure(self):
        """Poll the wavemeter and reschedule the next poll"""
        lib.TriggerMeasurement(cCtrlMeasurementTriggerSuccess)
        await asyncio.sleep(1.0/_FREQUENCY)

        f = lib.GetFrequencyNum(self.channel.number, ctypes.c_double(0))
        d = {'source':'wavemeter', 'channel':self.channel.name, 'data':f}

        if not self.loop.is_closed():
            self.loop.create_task(self.queue.put(d))

        if self._active:
            self._future = self.loop.create_task(self.measure())

    # -------------------------------------------------------------------------
    # Callback operation functions
    #
    def get_cb(self):
        """
        Return the function to be used as a callback.

        The callback function must be a function with arguments defined by the
        wavemeter dll, so can't be a method (with the self argument). We can
        get around this by using a closure as below.
        """
        def func(mode, intval, dblval):
            self.callback(mode, intval, dblval)
        self._callback = CALLBACK(func)
        return self._callback

    def callback(self, mode, intval, dblval):
        """rocess the incoming callback from the wavemeter"""
        print("callback! {}, {}, {}".format(mode, intval, dblval))

