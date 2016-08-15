"""
Optical Spectrum Analyser interface for data acquisition card.
"""
import numpy as np
import ctypes
import PyDAQmx
from PyDAQmx.DAQmxFunctions import DAQError
from wand.common import with_log

__all__ = [
    'OSATask',
    'set_frequency',
    'channel_setup',
]

# Value for choosing no options for DAQmx functions
NO_OPTIONS = 0

# Approx collection frequency
_FREQUENCY = 10
def set_frequency(frequency):
    global _FREQUENCY
    _FREQUENCY = frequency

# Downsampling (reduces number of data points, not frequency)
DWNSMP = 10

# Parameters for data acquisition
SAMPLES = 16000
RATE = 1.25e6
TIMEOUT = 0.1
MIN_V = -1.0
MAX_V = 1.0

def channel_setup(config):
    """Set up the channels to be used in the DAQ card"""
    global AI_BLUE, AI_RED, TRIG_BLUE, TRIG_RED
    AI_BLUE = config['blue']['input'].encode()
    AI_RED = config['red']['input'].encode()
    TRIG_BLUE = config['blue']['trigger'].encode()
    TRIG_RED = config['red']['trigger'].encode()


@with_log
class OSATask(PyDAQmx.Task):
    """
    Task object for collecting data from the Optical Spectrum Analyser
    """
    def __init__(self, loop, queue, channel):
        """
        Set up the Task in the DAQ card ready for use
        """
        super().__init__()

        self._log.debug("Creating Task object for channel: {}".format(channel.name))
        self.loop = loop
        self.queue = queue
        self.channel = channel

        # Blue/Red lasers require using different etalons, so have different
        # analog inputs to the DAQ card
        if self.channel.blue:
            AI = AI_BLUE
            TRIG = TRIG_BLUE
        else:
            AI = AI_RED
            TRIG = TRIG_RED

        # We want to measure voltage in range MIN_V to MAX_V, with a finite
        # number of samples taken at RATE, triggering collection on the
        # falling edge of the trigger channel
        self.CreateAIVoltageChan(AI, '', PyDAQmx.DAQmx_Val_NRSE, MIN_V, MAX_V,
                                 PyDAQmx.DAQmx_Val_Volts, None)
        self.CfgSampClkTiming('', RATE, PyDAQmx.DAQmx_Val_Rising,
                              PyDAQmx.DAQmx_Val_FiniteSamps, SAMPLES)
        self.CfgDigEdgeStartTrig(TRIG, PyDAQmx.DAQmx_Val_Falling)

        # We have to manualy reset the trigger by restarting the task -
        # committing the task to the DAQ card minimises the time taken to
        # restart
        self.TaskControl(PyDAQmx.DAQmx_Val_Task_Commit)

        # Register callbacks
        self.AutoRegisterEveryNSamplesEvent(PyDAQmx.DAQmx_Val_Acquired_Into_Buffer,
                                            SAMPLES, NO_OPTIONS)
        self.AutoRegisterDoneEvent(NO_OPTIONS)

    def EveryNCallback(self):
        """
        Called when the DAQ has data, also resets the trigger
        """
        data = np.zeros(SAMPLES)
        _read = np.int32()
        try:
            self.ReadAnalogF64(SAMPLES, TIMEOUT, PyDAQmx.DAQmx_Val_GroupByScanNumber, data,
                               SAMPLES, ctypes.byref(np.ctypeslib.as_ctypes(_read)), None)
        except Exception as e:
            self._log.error("Read Error: {}".format(e))

        # Perform downsampling
        data.shape = int(SAMPLES/DWNSMP), DWNSMP
        data = data.mean(axis=1)

        # Multiply by 10000 and cast to int to truncate data
        scale = 1e4
        data = np.multiply(data, scale).astype(int)
        d = {'source':'osa', 'channel':self.channel.name, 'data':data.tolist(), 'scale':scale}

        if not self.loop.is_closed():
            self.loop.create_task(self.queue.put(d))

            # Restart task so that we have continuous acquisition
            self.RestartTask()

        # Required
        return 0

    def StopTask(self):
        """Wraps StopTask to catch exceptions that we don't care about"""
        try:
            super().StopTask()
        except DAQError:
            pass

    def RestartTask(self):
        self.StopTask()
        self.loop.call_later((1.0/_FREQUENCY), self._start)

    def _start(self):
        """Wraps to catch exceptions, but note that this isn't public"""
        try:
            self.StartTask()
        except DAQError:
            # Task specified is invalid i.e. we've switched away
            pass

    def DoneCallback(self, status):
        self._log.debug("Done: Status: {}".format(status))

        # Required
        return 0
