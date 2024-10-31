import asyncio

async def handle_client(reader, writer):
    address = writer.get_extra_info('peername')
    print(f"Connected to {address}")

    while True:
        data = await reader.read(100)
        message = data.decode()

        if not data:
            print(f"Connection closed by {address}")
            break

        print(f"Received from client: {message}")
        writer.write(data)
        await writer.drain()

    writer.close()
    await writer.wait_closed()

async def start_server():
    server = await asyncio.start_server(handle_client, "127.0.0.1", 12345)
    addr = server.sockets[0].getsockname()
    print(f"Server started on {addr}")

    async with server:
        await server.serve_forever()

asyncio.run(start_server())