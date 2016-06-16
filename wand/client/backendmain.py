"""
backendmain.py

Runs backend client with no GUI, using quamash event loop, for testing purposes
"""
import sys
import argparse
from PyQt4 import QtGui, QtCore
from quamash import QEventLoop
import asyncio

import wand.client.client as client

def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", help="Filename to load JSON from", default=client.CFG_FILE)
    return parser.parse_args(argv)

def main(argv):
    args = parse_args(argv)
    fname = args.file

    app = QtCore.QCoreApplication([])
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    c = client.ClientBackend(None, fname=fname)
    c.startup()

    # Main event loop running forever
    try:
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