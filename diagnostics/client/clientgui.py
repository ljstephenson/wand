from PyQt4 import QtGui
import pyqtgraph as pg
import numpy as np
import threading

import diagnostics.client.client as client
app = QtGui.QApplication([])

class GUIChannel(pg.GraphicsLayoutWidget):
    def __init__(parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.parent = parent

        self.name_display = pg.TextItem(parent=self)

        self.osa_plot = self.addPlot()

        self.exposure_display = pg.SpinBox(parent=self, bounds=(0,50), step=1.0, int=True)
        self.reference_display = QtGui.QLineEdit(parent=self)

        self.detuning_display = pg.TextItem(parent=self)
        self.frequency_display = pg.TextItem(parent=self)


class ClientGUI(client.ClientBackend):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)