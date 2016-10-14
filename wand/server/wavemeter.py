"""
Wavemeter interface
"""
import asyncio
import ctypes
from wand.common import with_log
from wand.server.wlmconstants import (
    cMeasurement, cInstNotification, cCtrlMeasurementTriggerSuccess,
    cNotifyInstallCallback, cNotifyRemoveCallback, cExpoMin, cExpoMax
)

__all__ = [
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


def init(as_switcher):
    """
    Initialise the wavemeter
    """
    global lib

    # Boolean telling us whether the wlm is being used as a switcher as well
    global _SWITCHER
    _SWITCHER = as_switcher

    # Open the DLL
    lib = ctypes.WinDLL('C:\Windows\system32\wlmData.dll')

    lib.GetFrequencyNum.restype = ctypes.c_double
    lib.Instantiate.restype = ctypes.c_long
    lib.GetExposureRange.restype = ctypes.c_long

    # Turn off auto-switcher mode
    lib.SetSwitcherMode(ctypes.c_long(0))

    if _SWITCHER:
        # Turn off auto exposure in all channels (1-8)
        for i in range(8):
            lib.SetExposureModeNum(i+1, 0)
    else:
        lib.SetExposureModeNum(1, 0)

    # Set to measuring normally
    lib.Operation(cMeasurement)

    global EXP_MAX, EXP_MIN
    EXP_MIN = lib.GetExposureRange(ctypes.c_long(cExpoMin))
    EXP_MAX = lib.GetExposureRange(ctypes.c_long(cExpoMax))


def switch(number=1):
    """
    Switch to the supplied channel number
    """
    if not _SWITCHER:
        raise Exception("Wavemeter is not the currently active fibre switcher")
    lib.SetSwitcherChannel(number)


# Callback type to be defined. This must be in scope as long as the callback is
# in use, so just define it here
CALLBACK = ctypes.CFUNCTYPE(
    None, ctypes.c_long, ctypes.c_long, ctypes.c_double)


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
        self._log.debug(
            "Creating Task object for channel: {}".format(channel.name))
        self.loop = loop
        self.queue = queue
        self.channel = channel
        self._active = False
        self._future = None
        self._callback = None
        self._mode = "poll"
        # If the wavemeter is not the switcher then the first result will be
        # garbage and must be discarded
        self._first = not _SWITCHER

        self.setExposure()

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
        self._log.debug("Setting wavemeter exposure")
        self.exposure = self.channel.exposure
        lib.SetExposureNum(self.channel.number if _SWITCHER else 1,
                           self.channel.array,
                           self.channel.exposure)

    # -------------------------------------------------------------------------
    # Polling operation functions
    #
    async def measure(self):
        """Poll the wavemeter and reschedule the next poll"""
        # Check exposure hasn't changed
        if self.exposure != self.channel.exposure:
            self.setExposure()
        lib.TriggerMeasurement(cCtrlMeasurementTriggerSuccess)
        await asyncio.sleep(1.0/_FREQUENCY)

        f = lib.GetFrequencyNum(self.channel.number if _SWITCHER else 1,
                                ctypes.c_double(0))
        d = {'source': 'wavemeter', 'channel': self.channel.name, 'data': f}

        if not self.loop.is_closed() and not self._first:
            self.loop.create_task(self.queue.put(d))
        self._first = False

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
