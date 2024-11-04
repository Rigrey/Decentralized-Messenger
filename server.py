import argparse
import asyncio
import struct

# TODO: Continue Binary Protocol. Update for every command, nickname storage for client

FORMAT = "<BH"

def pack_message(command, message):
    return struct.pack(FORMAT+f"{len(message)}s", command, len(message), message.strip().encode())

def unpack_message(data):
    format_size = struct.calcsize(FORMAT)
    if len(data) < format_size:
        return data.decode()
    command, length = struct.unpack(FORMAT, data[:format_size])
    if len(data) < format_size + length:
        message = data[format_size:]
    else:
        message = struct.unpack(f"<{length}s", data[format_size:format_size + length])[0]
    return message.decode()


class ChatServer():
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.clients = {}


    async def handle_client(self, reader, writer):
        while True:
            nickname = unpack_message(await reader.read(struct.calcsize(FORMAT) + 16))
            if nickname in self.clients.values():
                writer.write(pack_message("[ ! ] This nickname is already taken."))
                await writer.drain()
            else:
                self.clients[writer] = nickname
                await self.broadcast(f"[ ! ] {nickname} joined the chat!")
                try:
                    while True:
                        data = await reader.read(struct.calcsize(FORMAT) + 65535)
                        message = unpack_message(data)
                        if not message or message == 'disconnect':
                            break
                        await self.broadcast(f"{nickname}: {message}")
                finally:
                    await self.disconnect_client(writer)
                    break


    async def disconnect_client(self, writer):
        nickname = self.clients.pop(writer)
        await self.broadcast(f"[ ! ] {nickname} left the chat!")
        writer.close()
        await writer.wait_closed()


    async def broadcast(self, message):
        for writer in self.clients.keys():
            writer.write(pack_message(0, message))
            await writer.drain()


    async def start_server(self):
        server = await asyncio.start_server(self.handle_client, self.host, self.port)
        print(f"Server running on {self.host}:{self.port}")
        async with server:
            await server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Сервер для временно централизованного мессенджера"
    )
    parser.add_argument("--host", type = str, default = "127.0.0.1", help = "Адрес для сервера")
    parser.add_argument("--port", type = str, default = "12345", help = "Порт для сервера")
    args = parser.parse_args()
    chat_server = ChatServer(args.host, args.port)
    asyncio.run(chat_server.start_server())
