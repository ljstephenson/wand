import numpy as np
import numpy.random as random

from wand.common import with_log

__all__ = [
    'FakeOSATask',
    'FakeWavemeterTask',
    'set_frequency',
]

_FREQUENCY = 10
def set_frequency(frequency):
    global _FREQUENCY
    _FREQUENCY = frequency


@with_log
class FakeTask(object):
    """Fake task that mimics data production but does not access hardware"""
    def __init__(self, loop, queue, channel):
        self._log.debug("Creating Task object for channel: {}".format(channel.name))
        self.loop = loop
        self.queue = queue
        self.channel = channel
        self._future = None
        self._active = False

    def _put_data(self):
        d = self._get_data()
        if not self.loop.is_closed():
            self.loop.create_task(self.queue.put(d))

        if self._active:
            self._future = self.loop.call_later(1.0/_FREQUENCY, self._put_data)

    def _get_data(self):
        raise NotImplementedError

    def StartTask(self):
        self._active = True
        self._future = self.loop.call_soon(self._put_data)

    def StopTask(self):
        self._active = False
        self.loop.call_soon_threadsafe(self._future.cancel)

    def ClearTask(self):
        pass


@with_log
class OSATask(FakeTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.samples = 16000
        self.dwnsmp = 10
        # Set up generating function
        random.seed(self.channel.number)
        width = random.randint(10, 100)
        spacing = random.randint(3000, 5000)
        n = int(self.samples/spacing - 0.5)
        centres = [(i+0.5)*spacing for i in range(n+1)]
        self._trace = self._get_trace(centres, width)
        random.seed()

    def _get_data(self):
        scale = 1e4
        dx = random.randint(-5, 5)
        data = np.arange(dx, self.samples+dx)
        data = np.asarray([self._trace(x) for x in data])
        data.shape = int(self.samples/self.dwnsmp), self.dwnsmp
        data = data.mean(axis=1)
        data = np.multiply(data, scale).astype(int)
        d = {'source':'osa', 'channel':self.channel.name, 'data':data.tolist(), 'scale':scale}
        return d

    def _get_trace(self, centres, w):
        lorentzians = [self._get_lorentzian(x0, w) for x0 in centres]
        def trace(x):
            return sum([f(x)+random.random()*0.02 for f in lorentzians])
        return trace

    def _get_lorentzian(self, x0, w):
        # x0: centre
        # w : half-width
        # height is 0.9
        def lorentzian(x):
            return 0.9*w**2/((x-x0)**2 + w**2)
        return lorentzian


@with_log
class WavemeterTask(FakeTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exposure = self.channel.exposure

        # Set up an approximate detuning Thz, consistent per channel
        random.seed(self.channel.number)
        self._detuning = (random.random()-0.5)*4e-3
        random.seed()

    def _get_data(self):
        if self.exposure != self.channel.exposure:
            self.setExposure()

        # set scale of wobble to be +/-1 MHz i.e. 1e-6THz
        wobble = (random.random()-0.5)*2e-6
        f = self.channel.reference + self._detuning + wobble
        # Occasionally send errors
        f = random.choice([f, -3, -4], p=[0.9, 0.05, 0.05])
        d = {'source':'wavemeter', 'channel':self.channel.name, 'data':f}
        return d

    def setExposure(self):
        self.exposure = self.channel.exposure
        self._log.debug("Changing exposure time")
