import time
import sys
import argparse
import asyncio

import diagnostics.server.server as server
import diagnostics.server.wavemeter as wavemeter

def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", help="Filename to load JSON from", default=server.DEFAULT_CFG_FILE)
    parser.add_argument("-s", "--simulate", help="Run simulation", action='store_true')
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)
    ts = time.time()

    if not args.simulate:
        print("[{:.3f}] Initialising wavemeter... ".format(time.time()-ts), end='', flush=True)
        wavemeter.init()
        print("Done")

    loop = asyncio.get_event_loop()

    print("[{:.3f}] Initialising TCP server... ".format(time.time()-ts), end='', flush=True)
    s = server.Server(fname=args.file, simulate=args.simulate)
    s.startup()
    print("Done")

    try:
        print("**Server Ready**")
        if args.simulate:
            print("THIS IS A SIMULATION!")
            print("Does not access hardware so works simultaneously with old wavemeter")
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