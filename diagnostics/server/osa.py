"""
Optical Spectrum Analyser interface for data acquisition card.
"""
import numpy
import ctypes
import PyDAQmx

from PyDAQmx.DAQmxFunctions import DAQError

__all__ = ['OSATask',
           ]

# Value for choosing no options for DAQmx functions
NO_OPTIONS = 0

# Approx collection frequency
_FREQUENCY = 10

# Parameters for data acquisition
SAMPLES = 1600
RATE = 1.25e5
TIMEOUT = 0.1
MIN_V = -1.0
MAX_V = 1.0
AI_BLUE = b'/Dev1/ai0'
AI_RED = b'/Dev1/ai1'
TRIG_BLUE = b'/Dev1/PFI0'
TRIG_RED = b'/Dev1/PFI2'


class OSATask(PyDAQmx.Task):
    """
    """
    def __init__(self, loop, queue, channel):
        """
        Set up the Task in the DAQ card ready for use
        """
        super().__init__()

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
        data = numpy.zeros(SAMPLES)
        _read = numpy.int32()
        try:
            self.ReadAnalogF64(SAMPLES, TIMEOUT, PyDAQmx.DAQmx_Val_GroupByScanNumber, data,
                            SAMPLES, ctypes.byref(numpy.ctypeslib.as_ctypes(_read)), None)
        except Exception as e:
            print("DAQMX READ FAILED")
            print(e)

        data = numpy.around(data, decimals=4)
        d = {'source':'osa', 'channel':self.channel.name, 'data':data.tolist()}
    
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
        print("Status: {}".format(status))

        # Required
        return 0