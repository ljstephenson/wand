import asyncio
from diagnostics.common import JSONStreamIterator

async def handle_echo(reader, writer):
    g = JSONStreamIterator(reader)
    async for obj in g:
        message = "got JSON: {}".format(obj)
        print(message)
        writer.write(message.encode())

    print("all items streamed, close")
    writer.write_eof()
    writer.close()

def main():
    loop = asyncio.get_event_loop()
    coro = asyncio.start_server(handle_echo, '127.0.0.1', 8888, loop=loop)
    server = loop.run_until_complete(coro)
    print('Serving on {}'.format(server.sockets[0].getsockname()))
    try:
        loop.run_forever()

    except KeyboardInterrupt:
        pass

    server.close()
    loop.run_until_complete(server.wait_closed())
    loop.close()
