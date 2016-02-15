#from diagnostics.server.osa import OSATask
from diagnostics.server.wavemeter import WavemeterTask, init, switch
import asyncio
import time
import PyDAQmx

loop = asyncio.get_event_loop()
queue = asyncio.Queue(loop=loop)

class Object(object):
    pass

channel = Object()
channel.name = "test_channel"
channel.exposure = 5
channel.number = 2
channel.array = 1
channel.blue = True

#task = OSATask(loop, queue, channel)
task = WavemeterTask(loop, queue, channel)

async def ashow():
    print("queue get scheduled")
    t_start = loop.time()
    d = await queue.get()
    t_end = loop.time()
    print("got data from queue:")
    print("{}".format(d))
    print("time from start to data acquired {}".format(t_start - t_end))

def show(loop):
    print("no waiting from queue")
    displayed = 0
    qsize = queue.qsize()
    while not queue.empty() and displayed < 10:
        displayed = displayed + 1
        d = queue.get_nowait()
        print("{}".format(d))
    print("queue size was: {}".format(qsize))
    loop.stop()

t = None
def main():
    try:
        print("starting")
        start = loop.time()
        task.StartTask()
    except Exception as e:
        print("exception")
        print(e)
    else:
        print("waiting for data")
        # loop.run_until_complete(ashow())
        loop.call_later(2, show, loop)
        loop.call_later(2.5, task.StopTask)
        loop.call_later(3, loop.stop)
        loop.run_forever()
    finally:
        end = loop.time()
        t = end - start
        print("finally, after {:.6}s".format(t))
        try:
            task.StopTask()
        except PyDAQmx.DAQmxFunctions.DAQError as e:
            print("encountered DAQ error on stop")
            print(e)
            pass


if __name__ == "__main__":
    main()