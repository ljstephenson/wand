import logging
import time
from wand.server.switcher import LeoniSwitcher

def main():
    logging.basicConfig(level=logging.DEBUG)
    dev = LeoniSwitcher('10.255.6.93')
    print('Current channel : {}'.format(dev.getChannel()) )

    i = 1
    while 1:
        time.sleep(2)
        dev.setChannel(i)
        i = (i+1) % 10

if __name__ == "__main__":
    main()