import sys
import argparse
import asyncio

import diagnostics.server.server as server

#import diagnostics.server.wavemeter as wavemeter

def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", help="Filename to load JSON from", default=server.DEFAULT_CFG_FILE)
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)

    #wavemeter.init()

    loop = asyncio.get_event_loop()

    s = server.Server(fname=args.file)
    s.startup()

    try:
        loop.run_forever()
    except KeyboardInterrupt as e:  
        print("\n**KeyboardInterupt**")
    except SystemExit as e:
        print("\n**SystemExit**")
        raise
    finally:
        print("Cleaning up")
        s.shutdown()
        loop.stop()
        loop.close()
        sys.exit()

if __name__ == "__main__":
    main(sys.argv[1:])