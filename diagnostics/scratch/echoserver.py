import asyncio
import json
import random
import time
import itertools
import sys

from diagnostics.common import JSONStreamIterator

channels = ["393", "397", "866"]

def fake_osa():
    data = [random.randrange(1, 10) for _ in range(0, 20)]
    ch = random.choice(channels)
    return {"jsonrpc":"2.0", "method":"osa", "params":{"time":time.time(), "data":data, "channel":ch}}

def fake_wavemeter():
    number = 775000 + 1000*random.random()
    ch = random.choice(channels)
    return {"jsonrpc":"2.0", "method":"wavemeter", "params":{"time":time.time(), "data":number, "channel":ch}}

def fake_configure():
    cfg = {
            "reference":775500.0000,
            "exposure":5,
            "number":2,
            "blue":True
        },
    ch = random.choice(channels)
    return {"jsonrpc":"2.0", "method":"refresh_channel", "params":{"cfg":cfg, "channel":ch}}


def notifications():
    for f in itertools.cycle([fake_osa, fake_wavemeter, fake_configure]):
        yield f()
    

async def handle_echo(reader, writer):
    g = JSONStreamIterator(reader)
    n = notifications()

    async for obj in g:
        print("<-- {}".format(json.dumps(obj)))
        msg = json.dumps(next(n))
        print("--> {}".format(msg))
        writer.write(msg.encode())
        await writer.drain()

    print("all items streamed")


async def do_nothing(loop):
    """loop needs to think it's doing something to get interrupts"""
    await asyncio.sleep(1)
    loop.create_task(do_nothing(loop))

def main():
    loop = asyncio.get_event_loop()
    coro = asyncio.start_server(handle_echo, 'localhost', 8888)
    server = loop.run_until_complete(coro)
    loop.create_task(do_nothing(loop))
    print('Serving on {}'.format(server.sockets[0].getsockname()))
    try:
        loop.run_forever()
    except KeyboardInterrupt:
        print("interrupted")
    else:
        print("normal exit")
    finally:
        loop.stop()
        tasks = asyncio.Task.all_tasks()
        for t in tasks:
            t.cancel()
        asyncio.wait(tasks, timeout=0.1)

        server.close()
        loop.run_until_complete(server.wait_closed())
        loop.close()
        sys.exit()
