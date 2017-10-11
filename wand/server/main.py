import sys
import argparse
import asyncio
import logging

import wand.server.server as server
import wand.common as common


def parse_args():
    parser = argparse.ArgumentParser("Python powered Wavemeter server")
    parser.add_argument("filename", help="JSON configuration file")
    parser.add_argument("-s", "--simulate",
                        help="Run as simulation", action='store_true')
    parser.add_argument("--ignore_unsecure_ssl",
        help=("Ignore unsecure warnings when SSL is used to connect to an" +
            " InfluxDB server with a self-signed certificate")
        default=False,
        const='store_true')
    common.add_verbosity_args(parser)
    return parser.parse_args()


def main():
    args = parse_args()
    level = common.get_verbosity_level(args)
    log = logging.getLogger(__package__)
    logging.getLogger('wand').setLevel(level)

    loop = asyncio.get_event_loop()

    s = server.Server(
            fname=args.filename,
            simulate=args.simulate,
            unsecure_ssl=args.ignore_unsecure_ssl)
    s.startup()

    try:
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
        s.shutdown()
        loop.stop()
        loop.close()
        sys.exit()

if __name__ == "__main__":
    main()
