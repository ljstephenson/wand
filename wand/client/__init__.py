"""
Client modules for WAnD
"""
# Get whatever version of Qt is available
for QtModuleName in ('PyQt5', 'PyQt4', 'PySide'):
	try:
		QtModule = __import__(QtModuleName)
	except ImportError:
		continue
	else:
		break
else:
	raise ImportError('No Qt implementations found')

QtCore = __import__(QtModuleName + '.QtCore', fromlist=(QtModuleName,))
QtGui = __import__(QtModuleName + '.QtGui', fromlist=(QtModuleName,))
QtNetwork = __import__(QtModuleName + '.QtNetwork', fromlist=(QtModuleName,))
if QtModuleName == 'PyQt5':
	from PyQt5 import QtWidgets
	QApplication = QtWidgets.QApplication
else:
	QApplication = QtGui.QApplication
