from PyQt4 import QtGui, QtCore
import pyqtgraph as pg
import pyqtgraph.dockarea as dock
import numpy as np
import functools
import collections

from diagnostics.client.client import ClientBackend
from diagnostics.client.channel import ClientChannel

import time

class GUIChannel(ClientChannel):
    def __init__(self, *args, **kwargs):

        # GUI items must be initialised before values are set in super() call
        self._gui_init()
        super().__init__(*args, **kwargs)

        # This has to go after the name has been initialised for the dock title
        self._dock = dock.Dock(self.name)
        self._dock.addWidget(self._layout)

        self._connect_callbacks()

    def _gui_init(self):
        """All GUI inititialisation (except dock) goes here"""
        self._layout = pg.LayoutWidget()

        box_size = QtCore.QRect(0, 0, 100, 100)

        self._plot = pg.GraphicsLayoutWidget(border=(100, 100, 100))
        self._layout.addWidget(self._plot, colspan=3)

        self._detuning = pg.LabelItem("")
        self._detuning.setText("Detuning", size="64pt")
        self._frequency = pg.LabelItem("")
        self._frequency.setText("Frequency", size="8pt")
        self._name = pg.LabelItem("")
        self._name.setText("Name", size="32pt")

        self._osa = self._plot.addPlot(title="Spectrum Analyser")
        self._osa_curve = self._osa.plot(pen='y')

        self._plot.nextRow()
        self._plot.addItem(self._detuning)
        self._plot.nextRow()
        self._plot.addItem(self._frequency)
        self._plot.nextRow()
        self._plot.addItem(self._name)

        self._exposure = QtGui.QSpinBox()
        self._exposure.setRange(0, 100)
        self._exposure.setSuffix(" ms")
        self._exposure.setGeometry(box_size)

        self._reference = QtGui.QDoubleSpinBox()
        self._reference.setRange(0.0, 1000000.0)
        self._reference.setDecimals(5)
        self._reference.setSuffix(" THz")
        self._reference.setGeometry(box_size)

        self._lock = QtGui.QPushButton("Lock Switcher")
        self._lock.setCheckable(True)
        self._save = QtGui.QPushButton("Save Settings")

        self._layout.nextRow()
        self._layout.addWidget(self._lock)
        self._layout.addWidget(QtGui.QLabel("Reference Frequency"))
        self._layout.addWidget(QtGui.QLabel("Wavemeter Exposure"))

        self._layout.nextRow()
        self._layout.addWidget(self._save, col=0)
        self._layout.addWidget(self._reference, col=1)
        self._layout.addWidget(self._exposure, col=2)

    # -------------------------------------------------------------------------
    # Callbacks
    #
    def _connect_callbacks(self):
        self._lock.clicked.connect(self.toggle_lock)
        self._save.clicked.connect(self.save)
        self._reference.valueChanged.connect(self.ref)
        self._exposure.valueChanged.connect(self.exp)


    # Note that the value changed callbacks check that the new value is
    # different from the stored value - this mean that only user inputs
    # trigger communications with the server.
    # Previously whenever the server updated the client, the client
    # would trigger a new notification with the new value, which would loop
    def ref(self, val):
        if val != self._ref:
            self.client.request_configure_channel(self.name, cfg={'reference':val})
    def exp(self, val):
        if val != self._exp:
            self.client.request_configure_channel(self.name, cfg={'exposure':val})

    def save(self):
        self.client.request_save_channel_settings(self.name)

    def toggle_lock(self):
        if self._lock.isChecked():
            self.client.request_lock(self.name)
            self._lock.setText("Unlock Switcher")
        else:
            self.client.request_unlock(self.name)
            self._lock.setText("Lock Switcher")

    # -------------------------------------------------------------------------
    # Switcher locked/unlocked
    #
    def lock(self):
        """Called when channel is locked by another client"""
        if not self._lock.isChecked():
            self._lock.toggle()
            self._lock.setText("Unlock Switcher")

    def unlock(self):
        """Called when channel is unlocked by another client"""
        if self._lock.isChecked():
            self._lock.toggle()
            self._lock.setText("Lock Switcher")

    # -------------------------------------------------------------------------
    # Properties
    #
    @property
    def name(self):
        return self._n

    @name.setter
    def name(self, val):
        if val is None:
            val = ""
        self._n = val
        self._name.setText(val, color=self.color)
        try:
            self._name.setAttr('color', "5555ff")
        except Exception as e:
            print(e)

    @property
    def reference(self):
        return self._ref

    @reference.setter
    def reference(self, val):   
        if val is None:
            val = 0
        self._ref = val
        self._reference.setValue(val)

    @property
    def exposure(self):
        return self._exp

    @exposure.setter
    def exposure(self, val):
        if val is None:
            val = 0
        self._exp = val
        self._exposure.setValue(val)

    @property
    def osa(self):
        raise NotImplementedError

    @osa.setter
    def osa(self, val):
        self._osa_curve.setData(val)

    @property
    def frequency(self):
        return self._f

    @frequency.setter
    def frequency(self, val):
        error = None
        if val is None:
            val = 0
        elif val == -3:
            val = 0
            error = "Low Signal"
        elif val == -4:
            val = 0
            error = "Big Signal"
        elif val < 0:
            val = 0
            error = "Other Error"
        self._f = val
        self._frequency.setText("{:.7f}".format(val))

        if not error:
            # Detuning in MHz not THz
            self._detuning.setText("{:.1f}".format(self.detuning*1e6), color="ffffff")
        else:
            self._detuning.setText("{}".format(error), color="ff9900")

    @property
    def color(self):
        if not hasattr(self, "blue") or self.blue is None:
            color = "7c7c7c"
        elif self.blue:
            color = "5555ff"
        else:
            color = "ff5555"
        return color

    @property
    def blue(self):
        return self._blue

    @blue.setter
    def blue(self, val):
        self._blue = val
        self._name.setText(self.name, color=self.color)

    @property
    def dock(self):
        return self._dock


class ClientGUI(ClientBackend):
    # List of configurable attributes (maintains order when dumping config)
    # These will all be initialised during __init__ in the call to 
    # super.__init__ because JSONRPCPeer is a JSONConfigurable
    _attrs = collections.OrderedDict([
                ('name', None),
                ('servers', None),
                ('layout', None),
            ])
    def __init__(self, *args, **kwargs):
        self.win = QtGui.QMainWindow()
        self.area = dock.DockArea()
        self.win.setCentralWidget(self.area)

        super().__init__(GUIChannel, *args, **kwargs)

        for row in self.layout:
            prev = None
            pos = 'bottom'
            for channel in row:
                c = self.channels[channel]
                d = c.dock
                self.area.addDock(d, position=pos, relativeTo=prev)
                pos = 'right'
                prev = d

    def show(self):
        self.win.show()
