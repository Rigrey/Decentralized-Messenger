import argparse
import asyncio
from turtledemo.clock import datum


class ChatServer():
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.clients = {}


    async def handle_client(self, reader, writer):
        nickname = (await reader.read(16)).decode().strip()
        if nickname in self.clients.values():
            writer.write("[ ! ] This nickname is already taken.".encode())
            await writer.drain()
        else:
            self.clients[writer] = nickname
            await self.broadcast(f"[ ! ] {nickname} joined the chat!")
            try:
                while True:
                    data = await reader.read(4096)
                    message = data.decode().strip()
                    if not message or message == 'disconnect':
                        break
                    await self.broadcast(f"{nickname}: {message}")
            finally:
                await self.disconnect_client(writer)


    async def disconnect_client(self, writer):
        nickname = self.clients.pop(writer)
        await self.broadcast(f"[ ! ] {nickname} left the chat!")
        writer.close()
        await writer.wait_closed()


    async def broadcast(self, message):
        for writer in self.clients.keys():
            writer.write(message.encode())
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