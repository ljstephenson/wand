import sys
import argparse
from PyQt4 import QtGui  # (the example applies equally well to PySide)

import diagnostics.client.client as client

def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", help="Filename to load JSON from", default=server.CFG_FILE)
    return parser.parse_argsargv)

def main(argv):
    args = parse_args(argv)
    fname = args.file

    c = client.Client(fname=fname)

    app.exec_()
    c.run()

if __name__ == "__main__":
    main(sys.argv[1:])