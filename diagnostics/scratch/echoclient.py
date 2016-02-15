import asyncio
import json

async def tcp_echo_client(message, loop):
    reader, writer = await asyncio.open_connection('127.0.0.1', 8888, loop=loop)
    print('Send: %r' % message)
    writer.write(message.encode())
    data = await reader.read()
    print('Received: %r' % data.decode())
    print('Close the socket')
    writer.close()



loop = asyncio.get_event_loop()


def main(json_list):
    message = ""
    for j in json_list:
        message = message + json.dumps(j)

    loop.run_until_complete(tcp_echo_client(message, loop))


def close():
    loop.close()
