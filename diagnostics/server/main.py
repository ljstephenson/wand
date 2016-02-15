import sys
import argparse

import diagnostics.server.server as server
import diagnostics.server.wavemeter as wavemeter

def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("-f", "--file", help="Filename to load JSON from", default=server.CFG_FILE)
    return parser.parse_argsargv)

def main(argv):
    args = parse_args(argv)
    fname = args.file

    wavemeter.init()

    s = server.Server(fname=fname)
    s.run()

if __name__ == "__main__":
    main(sys.argv[1:])