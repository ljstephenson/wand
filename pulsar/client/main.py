import sys
import argparse
from PyQt4 import QtGui
from quamash import QEventLoop
import asyncio

import diagnostics.client.client as client
import diagnostics.client.clientgui as clientgui

def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", help="Filename to load JSON from", default=client.CFG_FILE)
    return parser.parse_args(argv)

def main(argv):
    args = parse_args(argv)
    fname = args.file

    app = QtGui.QApplication([])
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    c = clientgui.ClientGUI(fname=fname)
    c.startup()

    # Main event loop running forever
    try:
        c.show()
        loop.run_forever()
    except KeyboardInterrupt as e:  
        print("**KeyboardInterupt**")
    except SystemExit as e:
        print("**SystemExit**")
        raise
    finally:
        print("cleaning up")
        c.shutdown()
        loop.stop()
        loop.close()

    sys.exit()

if __name__ == "__main__":
    main(sys.argv[1:])