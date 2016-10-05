import collections
import pyqtgraph as pg
import pyqtgraph.dockarea as dock

from . import QtGui, QtCore

from wand.client.client import ClientBackend
from wand.client.channel import Channel
from wand.client.server import Server
from wand.common import with_log


@with_log
class GUIChannel(Channel):
    def __init__(self, *args, **kwargs):
        # GUI items must be initialised before values are set in super() call
        self._gui_init()
        super().__init__(*args, **kwargs)

        # This has to go after the name has been initialised for the dock title
        self._dock = dock.Dock(self.name, autoOrientation=False)
        self._build_menu()
        self._gui_layout()
        self._connect_callbacks()
        self._enable_all(False)

        for label in [self._detuning, self._alias, self._frequency]:
            label.contextMenuEvent = lambda ev: self.menu.popup(QtGui.QCursor.pos())
            label.mousePressEvent = lambda ev: None
            label.mouseReleaseEvent = lambda ev: self.lockSlot()

    def _gui_init(self):
        """All GUI inititialisation (except dock) goes here"""
        self._plot = pg.GraphicsLayoutWidget(border=(80, 80, 80))

        self._detuning = pg.LabelItem("")
        self._detuning.setText("-", size="64pt")
        self._frequency = pg.LabelItem("")
        self._frequency.setText("-", size="12pt")
        self._alias = pg.LabelItem("")
        self._alias.setText("-", size="32pt")

        self._osa = pg.PlotItem()
        self._osa.hideAxis('bottom')
        # NB: Can't have grid shown without axes...
        self._osa.showGrid(y=True)
        self._osa_curve = self._osa.plot(pen='y')

        self._queued = QtGui.QCheckBox("Queue")

        self._exposure = QtGui.QSpinBox()
        self._exposure.setRange(0, 100)
        self._exposure.setSuffix(" ms")

        self._reference = QtGui.QDoubleSpinBox()
        self._reference.setRange(0.0, 1000000.0)
        self._reference.setDecimals(5)
        self._reference.setSuffix(" THz")

    def _gui_layout(self):
        """Place the initialised GUI items"""
        self._plot.addItem(self._osa, colspan=2)
        self._plot.nextRow()
        self._plot.addItem(self._detuning, colspan=2)
        self._plot.nextRow()
        self._plot.addItem(self._alias)
        self._plot.addItem(self._frequency)

        self._dock.addWidget(self._plot, colspan=7)
        self._dock.addWidget(self._queued, row=1, col=1)
        self._dock.addWidget(QtGui.QLabel("Reference Frequency"), row=1, col=3)
        self._dock.addWidget(QtGui.QLabel("Wavemeter Exposure"), row=1, col=5)
        self._dock.addWidget(self._reference, row=2, col=3)
        self._dock.addWidget(self._exposure, row=2, col=5)

        # Sort the layout to make the most of available space
        self._plot.ci.setSpacing(2)
        self._plot.ci.setContentsMargins(2, 2, 2, 2)
        self._dock.layout.setContentsMargins(0, 0, 0, 4)
        for i in [0, 2, 4, 6]:
            self._dock.layout.setColumnMinimumWidth(i, 4)
        for i in [1, 3, 5]:
            self._dock.layout.setColumnStretch(i, 1)

    def _enable_all(self, enable):
        """Enable or disable all editable boxes"""
        for widget in [self._reference, self._exposure, self._queued]:
            widget.setEnabled(enable)

    def _build_menu(self):
        self.menu = QtGui.QMenu()
        self.zeroAction = QtGui.QAction("Set reference to current", self._dock)
        self.saveAction = QtGui.QAction("Save Settings", self._dock)

        self.menu.addAction(self.zeroAction)
        self.menu.addAction(self.saveAction)

    # -------------------------------------------------------------------------
    # Callbacks
    #
    def _connect_callbacks(self):
        self._reference.valueChanged.connect(self.referenceSlot)
        self._exposure.valueChanged.connect(self.exposureSlot)
        self._queued.clicked.connect(self.queueSlot)
        self.zeroAction.triggered.connect(self.zeroSlot)
        self.saveAction.triggered.connect(self.saveSlot)

    # Note that the value changed callbacks check that the new value is
    # different from the stored value - this mean that only user inputs
    # trigger communications with the server.
    # Previously whenever the server updated the client, the client
    # would trigger a new notification with the new value, which would loop
    def referenceSlot(self, val):
        if val != self._ref:
            self.client.request_configure_channel(self.name,
                                                  cfg={'reference': val})

    def exposureSlot(self, val):
        if val != self._exp:
            self.client.request_configure_channel(self.name,
                                                  cfg={'exposure': val})

    def saveSlot(self):
        self.client.request_save_channel_settings(self.name)

    def lockSlot(self):
        # if NOT locked, request the lock and let the server handle it
        if not self.locked:
            self.client.request_lock(self.name)
        else:
            self.client.request_unlock(self.name)

    def zeroSlot(self):
        """Set the current value as reference (zeros the detuning)"""
        if self.frequency:
            self.referenceSlot(self.frequency)

    def queueSlot(self):
        """Add/remove the channel from server queue cycle"""
        self.client.request_queue(self.name, self.queued)

    # -------------------------------------------------------------------------
    # Properties
    #
    @property
    def alias(self):
        return self._n

    @alias.setter
    def alias(self, val):
        if val is None:
            val = ""
        self._n = val
        self._alias.setText(val, color=self.color)

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
            self._f = None
        elif val == -3:
            error = "Low"
        elif val == -4:
            error = "High"
        elif val < 0:
            error = "Error"
        else:
            self._f = val
            self._frequency.setText("{:.7f}".format(val))

        # Get the text to be shown in the detuning box
        if not error:
            # Detuning in MHz not THz
            text = "{:.1f}".format(self.detuning*1e6)
            color = "ffffff"
        else:
            text = error
            color = "ff9900"

        # Default font size for detuning is 64 point
        self._set_text_no_resize(self._detuning, text, size=64, color=color)

    def _set_text_no_resize(self, labelitem, text, size, color="ffffff"):
        """Set text to maximum size in a labelitem without resizing the box"""
        font = labelitem.item.font()
        font.setPointSize(size)
        predicted = QtGui.QFontMetrics(font).width(text)
        available = labelitem.boundingRect().width()
        while predicted > available:
            size = int(0.75*size)
            font.setPointSize(size)
            predicted = QtGui.QFontMetrics(font).width(text)

        labelitem.setText(text, color=color, size="{}pt".format(size))

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
        self._alias.setText(self.alias, color=self.color)
        # If the colour isn't grey then we can enable the buttons
        self._enable_all(self.color != "7c7c7c")

    @property
    def dock(self):
        return self._dock

    @property
    def locked(self):
        return self._locked

    @locked.setter
    def locked(self, val):
        self._locked = val

        self._plot.setBackground(self.bg)

    @property
    def queued(self):
        return self._queued.isChecked()

    @queued.setter
    def queued(self, val):
        if val ^ self.queued:
            self._queued.toggle()

        self._plot.setBackground(self.bg)

    @property
    def bg(self):
        bright = QtGui.QColor(0, 0, 0)
        dim = QtGui.QColor(50, 50, 50)

        if self.locked or (not self.server.locked and self.queued):
            return bright
        else:
            return dim


@with_log
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
        self._pause = QtGui.QRadioButton("Pause")
        self._fast = QtGui.QRadioButton("Fast Mode")

    def _add_all(self):
        for widget in [self._name, self._pause, self._fast]:
            self.addWidget(widget)
            self.addSeparator()

    # -------------------------------------------------------------------------
    # Widget callbacks
    #
    def _connect_callbacks(self):
        self._echo.editingFinished.connect(self.cb_echo)
        self._pause.clicked[bool].connect(self.cb_pause)
        self._fast.clicked[bool].connect(self.cb_fast)

    def cb_echo(self):
        self.client.request_echo(self.name, self._echo.text())

    def cb_pause(self, pause):
        self.client.request_pause(self.name, pause)

    def cb_fast(self, fast):
        self.client.request_fast(self.name, fast)

    # -------------------------------------------------------------------------
    # Updates
    #
    def set_paused(self, paused):
        # paused and isChecked() *must* be proper booleans for XOR to work
        if self._pause.isChecked() ^ paused:
            self._log.debug("{}: toggled pause to {}".format(self.name,
                                                             paused))
            self._pause.toggle()

    def set_fast(self, fast):
        if self._fast.isChecked() ^ fast:
            self._log.debug("{}: toggled fast to {}".format(self.name, fast))
            self._fast.toggle()


class GUIServerLite(Server):
    """docstring for GUIServer"""

    def __init__(self, *args, **kwargs):
        self._attrs.update({"channels": GUIChannel})
        super().__init__(*args, **kwargs)

    @property
    def color(self):
        """Background color for channels to use"""
        if not self.locked:
            return QtGui.QColor(0, 0, 0)
        else:
            return QtGui.QColor(50, 50, 50)


@with_log
class ClientGUI(ClientBackend):
    def __init__(self, *args, **kwargs):
        self._attrs.update({"servers": GUIServerLite})

        self.win = QtGui.QMainWindow()
        self.area = dock.DockArea()
        self.win.setCentralWidget(self.area)
        self.win.setWindowTitle("Super-duper Python Wavemeter Viewer!")

        super().__init__(*args, **kwargs)

        self.place_channels()
        self.create_toolbars()

    def show(self):
        self.win.show()

    def place_channels(self):
        """Place the channel docks into the dock area"""
        for row in self.layout:
            prev = None
            pos = 'bottom'
            for channel in row:
                c = self.get_channel_by_alias(channel)
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
