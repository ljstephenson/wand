import sys
import argparse
import asyncio
import logging

import wand.server.server as server
import wand.server.wavemeter as wavemeter

def parse_args(argv):
    parser = argparse.ArgumentParser("Python powered Wavemeter server")
    parser.add_argument("filename", help="JSON configuration file")
    parser.add_argument("-s", "--simulate", help="Run as simulation", action='store_true')
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-v", "--verbose", help="Increase output verbosity", action="count")
    group.add_argument("-q", "--quiet", help="Decrease output verbosity", action="count")
    return parser.parse_args(argv)

def set_verbosity(args):
    # Default log level is warning
    level = logging.WARNING
    if args.verbose:
        new_level = (logging.WARNING - 10*args.verbose)
        level = new_level if new_level >= logging.DEBUG else logging.DEBUG
    elif args.quiet:
        new_level = (logging.WARNING + 10*args.quiet)
        level = new_level if new_level <= logging.CRITICAL else logging.CRITICAL
    logging.basicConfig(format="%(asctime)s:%(levelname)s:%(name)s:%(message)s",level=level)

def main(argv):
    args = parse_args(argv)
    set_verbosity(args)
    log = logging.getLogger(__name__)

    if not args.simulate:
        log.info("Initialising wavemeter... ")
        wavemeter.init()
        log.info("Done initialising wavemeter")

    loop = asyncio.get_event_loop()

    log.info("Initialising TCP server... ")
    s = server.Server(fname=args.filename, simulate=args.simulate)
    s.startup()
    log.info("Done initialising TCP server")

    try:
        log.info("Wavemeter server ready")
        if args.simulate:
            log.info("Running as simulation, will not access hardware")
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
        log.info("Server loop exited, performing cleanup")
        s.shutdown()
        loop.stop()
        loop.close()
        sys.exit()

if __name__ == "__main__":
    main(sys.argv[1:])