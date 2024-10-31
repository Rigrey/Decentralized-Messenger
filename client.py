import asyncio

async def tcp_echo_client():
    reader, writer = await asyncio.open_connection("127.0.0.1", 12345)

    print("Connected to the server. Type your messages below.")

    while True:
        message = input("Client: ")
        writer.write(message.encode())
        await writer.drain()

        data = await reader.read(100)
        print(f"Server: {data.decode()}")

        if message.lower() == "exit":
            print("Closing the connection.")
            break

    writer.close()
    await writer.wait_closed()

asyncio.run(tcp_echo_client())