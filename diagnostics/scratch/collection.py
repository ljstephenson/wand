"""
Bleurgh
"""
import asyncio
from osa import OSATask

async def slow_operation(future):
    await asyncio.sleep(1)
    future.set_result("done")

def got_result(future):
    print(future.result())
    loop.stop()

loop = asyncio.get_event_loop()
future = asyncio.ensure_future(slow_operation(future))
future.add_done_callback(got_result)
try:
    loop.run_forever()
finally:
    loop.close()

async def switch(channel, otask, wtask):
    # stop tasks, switch and return the new tasks
    if otask is not None:
        otask.StopTask()
        otask.ClearTask()
        otask = None

    if wtask is not None:
        wtask.StopTask()
        wtask.ClearTask()
        wtask = None

    # switch
    otask = OSATask(loop, queue, channel)
    wtask = WavemeterTask(loop, queue, channel)