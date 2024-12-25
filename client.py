import argparse
import asyncio
import struct
import sys
from enum import Enum


def number_to_rgb(number):
    number = int(number)
    r = (number * 123) % 256
    g = (number * 321) % 256
    b = (number * 213) % 256
    return r, g, b


def find_free_port():
    from socket import socket, AF_INET, SOCK_STREAM
    temp_socket = socket(AF_INET, SOCK_STREAM)
    temp_socket.bind(('', 0))
    port = temp_socket.getsockname()[1]
    temp_socket.close()
    return port


def get_my_ip():
    import psutil
    from socket import AddressFamily
    for interface, addrs in psutil.net_if_addrs().items():
        if "Radmin VPN" in interface:  # I temporarily use Radmin VPN
            for addr in addrs:
                if addr.family == AddressFamily.AF_INET:
                    return addr.address
    return None


class Command(Enum):
    PRINT_MESSAGE = 0
    DISCONNECTED_MESSAGE = 1
    CONNECTED_MESSAGE = 2
    GIVE_ID = 3
    HANDLE_NEW_CONNECTION = 4


class User_Connection:
    def __init__(self, host, port, reader=None, writer=None):
        self.host = host
        self.port = port
        self.reader = reader
        self.writer = writer

    def __str__(self):
        return f"{self.host}:{self.port}"


class ChatClient:
    def __init__(self, server_host, server_port):
        self.parent = User_Connection(server_host, server_port)
        self.me = User_Connection(get_my_ip(), find_free_port())
        self.child = None
        self.nickname = ''
        self.header = "<BHH"
        self.nicknames = set()
        self.command_handlers = {
            Command.PRINT_MESSAGE: self.print_message,
            Command.DISCONNECTED_MESSAGE: self.disconnected_message,
            Command.CONNECTED_MESSAGE: self.connected_message,
            Command.GIVE_ID: self.get_id,
            Command.HANDLE_NEW_CONNECTION: self.handle_new_connection,
        }

    async def start_connection(self):
        try:
            if self.parent.host is None:
                await self.server_startup()
                self.nickname = str(hash(str(self.me.host) + ":" + str(self.me.host)) % 10 ** 9)
                print(f"New person can join by this: {self.me}")
            else:
                self.parent.reader, self.parent.writer = await asyncio.open_connection(self.parent.host,
                                                                                       self.parent.port)
                header = await asyncio.wait_for(self.parent.reader.readexactly(struct.calcsize(self.header)), timeout=5)
                if not header:
                    raise Exception("Connection failed on header part")
                command, length, nickname_length = struct.unpack(self.header, header)
                body_data = await asyncio.wait_for(self.parent.reader.readexactly(length), timeout=5)
                if not body_data:
                    raise Exception("Connection on body part")
                full_message = header + body_data
                command, nickname, message = await self.unpack_message(full_message)
                await self.command_handlers[Command(command)](nickname, message)
                await self.server_startup()
                data = await self.pack_message(Command.CONNECTED_MESSAGE.value, self.nickname)
                await self.send_message(data, self.parent.writer)
            await asyncio.gather(
                self.receive_messages(),
                self.process_input(),
            )
        except ConnectionError as e:
            print(f'Connection failed: {e}')
        finally:
            if self.parent.writer:
                self.parent.writer.close()
                await self.parent.writer.wait_closed()
            sys.exit(0)

    async def receive_messages(self):
        while True:
            try:
                if self.child and self.child.reader:
                    await self.process_stream(self.child.reader, self.parent.writer)

                if self.me and self.parent.reader:
                    await self.process_stream(self.parent.reader, self.child.writer if self.child else None)

                await asyncio.sleep(0)
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                print(f"Failed to receive message: {e}")
                pass

    async def process_stream(self, reader, writer):
        while True:
            header = await asyncio.wait_for(reader.readexactly(struct.calcsize(self.header)), timeout=5)
            if not header:
                break
            command, length, nickname_length = struct.unpack(self.header, header)
            body_data = await asyncio.wait_for(reader.readexactly(length), timeout=5)
            if not body_data:
                break
            full_message = header + body_data
            command, nickname, message = await self.unpack_message(full_message)
            await self.command_handlers[Command(command)](nickname, message)
            if writer:
                await self.send_message(full_message, writer)
            await asyncio.sleep(0)

    async def process_input(self):
        while True:
            message = await asyncio.to_thread(input)
            if message.lower() == "!disconnect":  # TODO: THIS SHOULD GIVE INFO ABOUT CONNECTIONS
                data_child = await self.pack_message(Command.DISCONNECTED_MESSAGE.value, f'{self.nickname};{self.me}')
                data_parent = await self.pack_message(Command.DISCONNECTED_MESSAGE.value, self.nickname)
                await self.send_message(data_child, self.child.writer)
                await self.send_message(data_parent, self.parent.writer)
                break
            elif message.lower() == "!new_connection":
                if not self.child:
                    print(f"You can connect new user by this data: {self.me}")
                    continue
                data = await self.pack_message(Command.HANDLE_NEW_CONNECTION.value, str(self.me))
                await self.send_message(data, self.child.writer)
                continue
            if self.parent.writer or self.child:
                data = await self.pack_message(Command.PRINT_MESSAGE.value, message)
            if self.parent.writer:
                await self.send_message(data, self.parent.writer)
            if self.child:
                await self.send_message(data, self.child.writer)

    async def send_message(self, data, writer):
        if writer:
            writer.write(data)
            await writer.drain()

    async def pack_message(self, command, message):
        message = message.strip()
        return struct.pack(self.header + f"{len(self.nickname)}s{len(message.encode())}s", command,
                           len(self.nickname) + len(message.encode()),
                           len(self.nickname), self.nickname.encode(), message.encode())

    async def unpack_message(self, data):
        try:
            header_size = struct.calcsize(self.header)
            if len(data) < header_size:
                raise ValueError("Incomplete message header")
            command, data_length, nickname_length = struct.unpack(self.header, data[:header_size])
            if Command(int(command)) not in self.command_handlers:
                raise ValueError("Unknown command received")
            if len(data[header_size:]) < data_length:
                raise ValueError("Incomplete message payload")
            unpack_format = f"{nickname_length}s{data_length - nickname_length}s"
            nickname, message = struct.unpack(unpack_format, data[header_size:header_size + data_length])
            nickname = nickname.decode()
            message = message.decode()
            return int(command), nickname, message
        except Exception as e:
            print(f"Failed to unpack message: {e}")

    async def print_message(self, nickname, message):
        r, g, b = number_to_rgb(nickname)
        print(f"\033[38;2;{r};{g};{b}m{nickname}\033[0m: {message}")

    # TODO: Reconnection of users (child to parent)
    async def disconnected_message(self, nickname, message):
        print(f"[ ! ] {message} left the chat!")

    async def connected_message(self, nickname, message):
        print(f"[ ! ] {message} joined the chat!")

    async def get_id(self, nickname, message):
        self.nickname = message

    async def handle_new_connection(self, nickname, message):
        if not self.child:
            data = await self.pack_message(Command.HANDLE_NEW_CONNECTION.value, f'{self.me};{message}')
            await self.send_message(data, self.parent.writer)
        elif message.split(';')[1] == str(self.me):
            print(f"You can connect new user by this data: {message.split(';')[0]}")

    async def server_startup(self):
        if not self.me.host:
            raise Exception("Server can't be started!")
        server = await asyncio.start_server(self.handle_connection, self.me.host, self.me.port)
        asyncio.create_task(self.run_server(server))

    async def run_server(self, server):
        async with server:
            await server.serve_forever()

    async def handle_connection(self, reader, writer):
        try:
            if self.child:
                writer.close()
                await writer.closed()
                raise Exception("This node has max amount of connections.")
            peer = writer.get_extra_info('peername')
            self.child = User_Connection(peer[0], peer[1], reader, writer)
            data = await self.pack_message(Command.GIVE_ID.value,
                                           str(hash(str(peer[0]) + ":" + str(peer[1])) % 10 ** 9))
            await self.send_message(data, self.child.writer)
        except Exception as e:
            print(f"Failed to handle new connection: {e}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=' Client for temporarily (De)centralized Messenger'
    )
    parser.add_argument('-c', '--cmd', type=bool, default=False, help='Run through command line with parameters')
    parser.add_argument('-s', '--server', type=str, default=None, help='Server host')
    parser.add_argument('-p', '--port', type=str, default=f'{find_free_port()}', help='Server port')
    args = parser.parse_args()

    server_host = args.server if args.cmd else input('Server host: ')
    server_port = args.port if args.cmd else input('Server port: ')
    client = ChatClient(server_host, server_port)
    asyncio.run(client.start_connection())
