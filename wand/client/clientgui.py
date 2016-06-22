from . import QtGui
import pyqtgraph as pg
import pyqtgraph.dockarea as dock
import numpy as np
import functools
import collections

from wand.client.client import ClientBackend
from wand.client.channel import Channel

import time

class GUIChannel(Channel):
    def __init__(self, *args, **kwargs):

        # GUI items must be initialised before values are set in super() call
        self._gui_init()
        super().__init__(*args, **kwargs)

        # This has to go after the name has been initialised for the dock title
        self._dock = dock.Dock(self.name, autoOrientation=False)
        self._gui_layout()
        self._connect_callbacks()

    def _gui_init(self):
        """All GUI inititialisation (except dock) goes here"""
        self._plot = pg.GraphicsLayoutWidget(border=(80, 80, 80))

        self._detuning = pg.LabelItem("")
        self._detuning.setText("-", size="64pt")
        self._frequency = pg.LabelItem("")
        self._frequency.setText("-", size="12pt")
        self._short_name = pg.LabelItem("")
        self._short_name.setText("Name", size="32pt")

        self._osa = pg.PlotItem()
        self._osa.hideAxis('bottom')
        # NB: Can't have grid shown without axes...
        self._osa.showGrid(y=True)
        self._osa_curve = self._osa.plot(pen='y')

        self._exposure = QtGui.QSpinBox()
        self._exposure.setRange(0, 100)
        self._exposure.setSuffix(" ms")

        self._reference = QtGui.QDoubleSpinBox()
        self._reference.setRange(0.0, 1000000.0)
        self._reference.setDecimals(5)
        self._reference.setSuffix(" THz")

        self._lock = QtGui.QPushButton("View")
        self._lock.setCheckable(True)
        self._save = QtGui.QPushButton("Save Settings")

    def _gui_layout(self):
        """Place the initialised GUI items"""
        self._plot.addItem(self._osa, colspan=3)
        self._plot.nextRow()
        self._plot.addItem(self._detuning, colspan=3)
        self._plot.nextRow()
        self._plot.addItem(self._short_name)
        self._plot.addItem(self._frequency, colspan=2)

        self._dock.addWidget(self._plot, colspan=7)
        self._dock.addWidget(self._lock, row=1, col=1)
        self._dock.addWidget(QtGui.QLabel("Reference Frequency"), row=1, col=3)
        self._dock.addWidget(QtGui.QLabel("Wavemeter Exposure"), row=1, col=5)
        self._dock.addWidget(self._save, row=2, col=1)
        self._dock.addWidget(self._reference, row=2, col=3)
        self._dock.addWidget(self._exposure, row=2, col=5)

        # Sort the layout to make the most of available space
        self._plot.ci.setSpacing(2)
        self._plot.ci.setContentsMargins(2,2,2,2)
        self._dock.layout.setContentsMargins(0,0,0,4)
        for i in [0,2,4,6]:
            self._dock.layout.setColumnMinimumWidth(i, 4)
        for i in [1,3,5]:
            self._dock.layout.setColumnStretch(i,1)

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
        else:
            self.client.request_unlock(self.name)

    # -------------------------------------------------------------------------
    # Switcher locked/unlocked
    #
    def lock(self):
        """Called when channel is locked by another client"""
        if not self._lock.isChecked():
            self._lock.toggle()

    def unlock(self):
        """Called when channel is unlocked by another client"""
        if self._lock.isChecked():
            self._lock.toggle()

    # -------------------------------------------------------------------------
    # Properties
    #
    @property
    def short_name(self):
        return self._n

    @short_name.setter
    def short_name(self, val):
        if val is None:
            val = ""
        self._n = val
        self._short_name.setText(val, color=self.color)

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
            error = "Low"
        elif val == -4:
            error = "High"
        elif val < 0:
            error = "Error"
        else:
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
        self._short_name.setText(self.short_name, color=self.color)

    @property
    def dock(self):
        return self._dock


class GUIServer(QtGui.QToolBar):
    def __init__(self, client, server):
        self.name = server
        self.client = client

        super().__init__(server)
        self._create_widgets()
        self._add_all()
        self._connect_callbacks()

    def _create_widgets(self):
        self._echo = QtGui.QLineEdit()
        self._name = QtGui.QLabel(self.name)
        self._pause = QtGui.QPushButton("Pause")
        self._pause.setCheckable(True)
        self._fast = QtGui.QPushButton("Fast Update")
        self._fast.setCheckable(True)

    def _add_all(self):
        for widget in [self._name, self._echo, self._pause, self._fast]:
            self.addWidget(widget)

    def _connect_callbacks(self):
        self._echo.editingFinished.connect(self.echo)
        self._pause.clicked[bool].connect(self.pause)
        self._fast.clicked[bool].connect(self.fast)

    def echo(self):
        self.client.request_echo(self.name, self._echo.text())

    def pause(self, pause):
        print("{} setting {} pause to {}".format(self.client.name, self.name, pause))
        self.client.request_pause(self.name, pause)

    def fast(self, fast):
        self.client.request_fast(self.name, fast)

    def set_paused(self, paused):
        # paused and isChecked() *must* be proper booleans for XOR to work
        if self._pause.isChecked() ^ paused:
            print("{}: toggled pause to {}".format(self.name, paused))
            self._pause.toggle()
        else:
            print("{}: not toggled {}".format(self.name, paused))

    def set_fast(self, fast):
        if self._fast.isChecked() ^ fast:
            print("{}: toggled fast to {}".format(self.name, fast))
            self.fast.toggle()


class ClientGUI(ClientBackend):
    # List of configurable attributes (maintains order when dumping config)
    # These will all be initialised during __init__ in the call to 
    # super.__init__ because JSONRPCPeer is a JSONConfigurable
    _attrs = collections.OrderedDict([
                ('name', None),
                ('servers', None),
                ('short_names', None),
                ('layout', None),
            ])
    def __init__(self, *args, **kwargs):
        self.win = QtGui.QMainWindow()
        self.area = dock.DockArea()
        self.win.setCentralWidget(self.area)
        self.win.setWindowTitle("Super-duper Python Wavemeter Viewer!")

        super().__init__(GUIChannel, *args, **kwargs)

        self.place_channels()
        self.create_toolbars()
        self.place_toolbars()

    def show(self):
        self.win.show()

    def place_channels(self):
        """Place the channel docks into the dock area"""
        for row in self.layout:
            prev = None
            pos = 'bottom'
            for channel in row:
                c = self.get_channel_by_short_name(channel)
                d = c.dock
                self.area.addDock(d, position=pos, relativeTo=prev)
                pos = 'right'
                prev = d

    def create_toolbars(self):
        """Create and place server toolbars"""
        self.toolbars = collections.OrderedDict()
        for s in self.servers:  
            self.toolbars[s] = GUIServer(self, s)

    def place_toolbars(self):
        for t in self.toolbars.values():
            self.win.addToolBar(t)
