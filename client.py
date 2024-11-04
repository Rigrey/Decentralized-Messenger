import asyncio
import argparse
import struct
import sys

FORMAT = "<BH"

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

def pack_message(command, message):
    return struct.pack(FORMAT+f"{len(message)}s", 0, len(message), message.strip().encode())

def unpack_message(data):
    format_size = struct.calcsize(FORMAT)
    if len(data) < format_size:
        return data.decode()
    identifier, length = struct.unpack(FORMAT, data[:format_size])
    if len(data) < format_size + length:
        message = data[format_size:]
    else:
        message = struct.unpack(f"<{length}s", data[format_size:format_size + length])[0]
    return message.decode()


class ChatClient:
    def __init__(self, server_host, server_port, nickname):
        self.server_host = server_host
        self.server_port = server_port
        self.nickname = nickname


    async def start_connection(self):
        reader, writer = await asyncio.open_connection(self.server_host, self.server_port)
        writer.write(pack_message(0, self.nickname))
        await writer.drain()
        while True:
            answer = unpack_message(await reader.read(65538))
            if answer == "[ ! ] This nickname is already taken.":
                print(answer)
                self.nickname = set_nickname()
                writer.write(pack_message(0, self.nickname))
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
            message = unpack_message(await reader.read(65538))
            if not message:
                print("Connection closed")
                break
            print(message)


    async def send_messages(self, writer):
        while True:
            message = await asyncio.get_event_loop().run_in_executor(None, input)
            if message.lower() == "disconnect":
                writer.write(1, pack_message(message))
                await writer.drain()
                break
            writer.write(pack_message(message))
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
