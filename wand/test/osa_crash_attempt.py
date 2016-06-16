from pulsar.server.osa import OSATask
import asyncio
import time
import sys
import PyDAQmx

loop = asyncio.get_event_loop()
queue = asyncio.Queue(loop=loop)

class Object(object):
    pass

counts = 0
async def noop(data):
    counts = counts + 1

queue = Object()
queue.put = noop

channel = Object()
channel.name = "test_channel"
channel.exposure = 5
channel.number = 2
channel.array = 1
channel.blue = True

task = OSATask(loop, queue, channel)

def exit_loop():
    sys.stdin.readline()
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
        print("Hit enter to exit")
        loop.add_reader(sys.stdin, exit_loop)
        loop.run_forever()
    finally:
        loop.stop()
        try:
            task.StopTask()
        except PyDAQmx.DAQmxFunctions.DAQError as e:
            print("encountered DAQ error on stop")
            print(e)
            pass
        print(counts)


if __name__ == "__main__":
    main()