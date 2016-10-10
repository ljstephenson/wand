"""
Wavemeter interface
"""
import asyncio
from ctypes import (
    c_bool, c_long, c_ushort, c_double, c_ssize_t, WinDLL
)
import time
from wand.common import with_log
from wand.server.wlmconstants import (
    cMeasurement, cCtrlMeasurementTriggerSuccess, cInstCheckForWLM,
    cCtrlWLMShow, cCtrlWLMWait
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
    lib = WinDLL('C:\Windows\system32\wlmData.dll')

    setup_functions()
    startup()


def setup_functions():
    prototypes = {
        # General access functions
        "Instantiate": (c_long, None),
        "ControlWLMEx": (c_long, [c_long, c_long, c_long, c_long, c_long]),
        "GetWLMVersion": (c_long, [c_long]),
        "GetWLMCount": (c_long, [c_long]),
        "GetChannelsCount": (c_long, [c_long]),
        # Measurement result access functions
        "GetFrequencyNum": (c_double, [c_long, c_double]),
        "GetCalWavelength": (c_double, [c_long, c_double]),
        "GetPowerNum": (c_double, [c_long, c_double]),
        # Operation related functions
        "GetOperationState": (c_ushort, [c_ushort]),
        "Operation": (c_long, [c_ushort]),
        "Calibration": (c_long, [c_long, c_long, c_double, c_long]),
        "TriggerMeasurement": (c_long, [c_long]),
        # State and parameter functions
        "setExposureNum": (c_long, [c_long, c_long, c_long]),
        "SetExposureModeNum": (c_long, [c_long, c_bool]),
        # Switch functions
        "SetSwitcherMode": (c_long, [c_long]),
        "SetSwitcherChannel": (c_long, [c_long]),
    }
    # General setup with no error checking
    for name, types in prototypes.items():
        fn = getattr(lib, name)
        fn.restype = types(0)
        if types(1) is not None:
            fn.argtypes = types(1)


def startup():
    """Start the wavemeter"""
    # Wavemeter can take a ~long~ time to start
    startup_timeout_msecs = 20000
    running = lib.Instantiate(c_long(cInstCheckForWLM),
                              c_long(0), c_ssize_t(0), c_long(0))
    if not running:
        started = lib.ControlWLMEx(cCtrlWLMShow | cCtrlWLMWait,
                                   0, 0, startup_timeout_msecs, 1)
        if started == 0:
            raise Exception("Timed out waiting for WLM application to start.")

    # Turn off auto switching
    lib.SetSwitcherMode(False)

    # Set auto exposure off
    if _SWITCHER:
        for i in range(1, 9):
            lib.SetExposureModeNum(i, False)
    else:
        lib.SetExposureModeNum(1, False)

    # Set to measuring normally
    lib.Operation(cMeasurement)


def switch(number=1):
    """
    Switch to the supplied channel number
    """
    if not _SWITCHER:
        raise Exception("Wavemeter is not the currently active fibre switcher")
    lib.SetSwitcherChannel(number)


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
        # If the wavemeter is not the switcher then the first result will be
        # garbage and must be discarded
        self._first = not _SWITCHER

    def StartTask(self):
        """Start collections"""
        self._active = True
        self._task_helper()

    def SingleShot(self):
        """Do a single collection asynchronously"""
        self._active = False
        self._task_helper()

    def _task_helper(self):
        # If wavemeter is not switcher, measurements are not synchronised
        # with switcher so the first measurement (or two) are garbage
        if self._first:
            # Set to minimimum exposure and discard measurement
            lib.SetExposureNum(self.channel.number if _SWITCHER else 1, 1, 2)
            lib.TriggerMeasurement(cCtrlMeasurementTriggerSuccess)
            _ = lib.GetFrequencyNum(self.channel.number if _SWITCHER else 1, 0)

        self.setExposure()
        self._future = self.loop.create_task(self.measure())

    def StopTask(self):
        """Stop collections"""
        self.loop.call_soon_threadsafe(self._future.cancel)
        self._future = None
        self._active = False

    def ClearTask(self):
        """No-op so that wavemeter and OSA have identical APIs"""
        pass

    def MeasureOnce(self):
        """Synchronously retrieve wavelength"""
        if self._first:
            # Set to minimimum exposure and discard measurement
            lib.SetExposureNum(self.channel.number if _SWITCHER else 1, 1, 2)
            lib.TriggerMeasurement(cCtrlMeasurementTriggerSuccess)
            time.sleep(5e-3)
            _ = lib.GetFrequencyNum(self.channel.number if _SWITCHER else 1, 0)

        self.setExposure()
        lib.TriggerMeasurement(cCtrlMeasurementTriggerSuccess)
        time.sleep(self.channel.exposure*1e-3)
        return lib.GetFrequencyNum(self.channel.number if _SWITCHER else 1, 0)

    def setExposure(self):
        """Call after updating channel exposure"""
        self.exposure = self.channel.exposure
        lib.SetExposureNum(self.channel.number if _SWITCHER else 1, 1,
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

        f = lib.GetFrequencyNum(self.channel.number if _SWITCHER else 1, 0)
        d = {'source': 'wavemeter', 'channel': self.channel.name, 'data': f}

        if not self.loop.is_closed():
            self.loop.create_task(self.queue.put(d))

        if self._active:
            self._future = self.loop.create_task(self.measure())
