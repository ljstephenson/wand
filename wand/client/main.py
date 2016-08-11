import sys
import argparse
from . import QtGui
import logging
import pkg_resources

import wand.client.clientgui as clientgui
import wand.common as common

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="JSON configuration file")
    common.add_verbosity_args(parser)
    return parser.parse_args()

def main():
    args = parse_args()
    level = common.get_verbosity_level(args)
    log = logging.getLogger(__package__)
    logging.getLogger('wand').setLevel(level)

    app = QtGui.QApplication([])
    set_icon(app)

    c = clientgui.ClientGUI(fname=args.filename)
    c.startup()

    # Main event loop running forever
    try:
        c.show()
        app.exec_()
    except Exception as e:
        log.exception("Exception occurred in main loop")
        raise
    finally:
        c.shutdown()

def set_icon(app):
    fname = pkg_resources.resource_filename("wand", "resources/wand.svg")
    icon = QtGui.QIcon()
    icon.addFile(fname)
    app.setWindowIcon(icon)


if __name__ == "__main__":
    main()
