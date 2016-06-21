import sys
import argparse
from . import QtGui
from quamash import QEventLoop
import asyncio
import logging

import wand.client.clientgui as clientgui
import wand.common as common

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("filename", help="JSON configuration file")
    common.add_verbosty_args(parser)
    return parser.parse_args()

def main():
    args = parse_args()
    level = common.get_verbosity_level(args)
    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",level=level)
    log = logging.getLogger(__name__)

    app = QtGui.QApplication([])
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    c = clientgui.ClientGUI(fname=args.filename)
    c.startup()

    # Main event loop running forever
    try:
        c.show()
        loop.run_forever()
    except KeyboardInterrupt as e:  
        log.info("Quitting due to user keyboard interrupt")
    except SystemExit as e:
        log.exception("SystemExit occurred in main loop")
        raise
    except Exception as e:
        log.exception("Exception occurred in main loop")
        raise
    finally:
        c.shutdown()
        loop.stop()
        loop.close()

    sys.exit()

if __name__ == "__main__":
    main()