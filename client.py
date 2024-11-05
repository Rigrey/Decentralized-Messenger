import argparse
import asyncio
import string
import struct
import sys


class ChatClient:
    def __init__(self, server_host, server_port):
        self.server_host = server_host
        self.server_port = server_port
        self.nickname = ''
        self.reader = None
        self.writer = None
        self.format = "<BH"
        self.nicknames = set()
        self.command_handlers = {
            0: self.broadcast_message,
            1: self.disconnected_message,
            2: self.connected_message,
            3: self.get_nicknames
        }


    async def start_connection(self):
        try:
            self.reader, self.writer = await asyncio.open_connection(self.server_host, self.server_port)
            await self.unpack_message(await self.reader.read(65538))
            await self.set_nickname()
            await self.send_command(2, self.nickname)
            await asyncio.gather(
                self.receive_messages(),
                self.send_messages()
            )
        except ConnectionError as e:
            print(f'Connection failed: {e}')
        finally:
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
            sys.exit(0)


    async def receive_messages(self):
        while True:
            try:
                data = await self.reader.read(65538)
                if not data:
                    print("Disconnected from server.")
                    break
                await self.unpack_message(data)
            except Exception as e:
                print(f"Failed to receive message: {e}")
                pass

    async def send_messages(self):
        while True:
            message = await asyncio.to_thread(input)
            if message.lower() == "disconnect":
                await self.send_command(1, self.nickname)
                break
            await self.send_command(0, message)

    async def send_command(self, command, message):
        packed_message = self.pack_message(command, message)
        self.writer.write(packed_message)
        await self.writer.drain()


    def pack_message(self, command, message):
        return struct.pack(self.format + f"{len(message)}s", command, len(message), message.strip().encode())

    async def unpack_message(self, data):
        try:
            format_size = struct.calcsize(self.format)
            if len(data) < format_size:
                raise ValueError("Incomplete message header.")
            command, length = struct.unpack(self.format, data[:format_size])
            if command not in self.command_handlers:
                raise ValueError("Unknown command received.")

            if len(data) < format_size + length:
                message = data[format_size:].decode()  # TODO: check if this works correct, im not sure
            else:
                message = struct.unpack(f"<{length}s", data[format_size:format_size + length])[0].decode()

            await self.command_handlers[command](message)
        except Exception as e:
            print(f"Failed to unpack message: {e}")


    async def set_nickname(self):
        while True:
            nickname = input('New Nickname (16 chars max): ').strip()
            if len(nickname) == 0:
                print("Nickname cannot be empty.")
            elif nickname in self.nicknames:
                print(f'Nickname {nickname} already set! Choose another one.')
            elif len(nickname) > 16:
                print("Nickname is too long.")
            elif any(char in string.punctuation for char in nickname):
                print("Nickname contains punctuation.")
            else:
                self.nickname = nickname
                self.nicknames.add(nickname)
                break

    async def broadcast_message(self, message):
        print(message)

    async def disconnected_message(self, message):
        print(f"[ ! ] {message} left the chat!")
        self.nicknames.discard(message)

    async def connected_message(self, message):
        print(f"[ ! ] {message} joined the chat!")
        self.nicknames.add(message)

    async def get_nicknames(self, message):
        self.nicknames.update(message.split('; '))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=' Client for temporarily (De)centralized Messenger'
    )
    parser.add_argument('-c', '--cmd', type=bool, default=False, help='Run through commandline with parameters')
    parser.add_argument('-s', '--server', type=str, default='127.0.0.1', help='Server host')
    parser.add_argument('-p', '--port', type=str, default='12345', help='Server port')
    args = parser.parse_args()
    server_host = args.server if args.cmd else input('Server host: ')
    server_port = args.port if args.cmd else input('Server port: ')

    client = ChatClient(server_host, server_port)
    asyncio.run(client.start_connection())
