import asyncio
import argparse
import sys

def set_nickname():
    while True:
        nickname = input('New Nickname (16 chars max): ').strip()
        if len(nickname) == 0:
            print("Nickname cannot be empty.")
        elif len(nickname) > 16:
            print("Nickname is too long.")
        else:
            break
    return nickname


class ChatClient:
    def __init__(self, server_host, server_port, nickname):
        self.server_host = server_host
        self.server_port = server_port
        self.nickname = nickname


    async def start_connection(self):
        reader, writer = await asyncio.open_connection(self.server_host, self.server_port)
        writer.write(self.nickname.encode())
        await writer.drain()
        while True:
            answer = (await reader.read(4096)).decode()
            if answer == "[ ! ] This nickname is already taken.":
                print(answer)
                self.nickname = set_nickname()
                writer.write(self.nickname.encode())
                await writer.drain()
            elif answer == f"[ ! ] {self.nickname} joined the chat!":
                print(answer)
                break
            else:
                print("Unexpected response from server.")
                writer.close()
                await writer.wait_closed()
                sys.exit(1)

        await asyncio.gather(
            self.listen_for_messages(reader),
            self.send_messages(writer)
        )
        writer.close()
        await writer.wait_closed()
        sys.exit(0)


    async def listen_for_messages(self, reader):
        while True:
            data = await reader.read(4096)
            if not data:
                print("\nConnection closed")
                break
            print(f"{data.decode()}")


    async def send_messages(self, writer):
        while True:
            message = await asyncio.get_event_loop().run_in_executor(None, input)
            if message.lower() == "disconnect":
                writer.write(message.encode())
                await writer.drain()
                break
            writer.write(message.encode())
            await writer.drain()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="Клиент для временно централизованного мессенджера"
    )
    parser.add_argument("--cmd", type = bool, default = False, help = "Запуск через параметры или нет")
    parser.add_argument("--host", type = str, default = "127.0.0.1", help = "Адрес для сервера")
    parser.add_argument("--port", type = str, default = "12345", help = "Порт для сервера")
    args = parser.parse_args()

    server_host = args.host if args.cmd else input('Server host: ')
    server_port = args.port if args.cmd else input('Server port: ')

    nickname = set_nickname()

    client = ChatClient(server_host, server_port, nickname)
    asyncio.run(client.start_connection())
