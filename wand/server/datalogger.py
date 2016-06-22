import os
import time
import json

class OsaLogger(object):
    def __init__(self):
        if os.name == "nt":
            # Windows machine, shared area at Z;
            shared = 'Z:\\'
        else:
            shared = os.path.expanduser('~/steaneShared')

        dirname = 'wavemeters'
        subdir = 'osa'
        self.prefix = os.path.join(shared, dirname, subdir)

    def log(self, data):
        """log data to a file"""
        date = time.strftime("%Y-%m-%d")
        now = time.time()
        fname = date + '-' + data['channel'] + '.json'

        with open(os.path.join(self.prefix, fname), 'ab+') as f:
            str = "{}\n".format(json.dumps([now, data]))
            f.write(str.encode())