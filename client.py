"""
ChatClient.py - A Decentralized Messenger Client

This script implements a decentralized messaging client using Python's asyncio framework.
The client communicates with peers in a circular topology, supports dynamic connection handling,
and includes message passing with duplicate detection.

Modules Used:
- argparse: Parse command-line arguments.
- asyncio: Handle asynchronous operations.
- queue: Manage message history.
- struct: Pack and unpack binary data.
- sys: System-specific parameters and functions.
- enum: Define enumerations for commands.
- socket: Network socket operations.
- psutil: Fetch network interface information.
- zlib: Compute CRC32 checksums.
"""

import argparse
import asyncio
import queue
import struct
import sys
from enum import Enum
from socket import AddressFamily, AF_INET, SOCK_STREAM, socket
from psutil import net_if_addrs
from zlib import crc32

# Converts a number into an RGB color based on arbitrary multipliers
def number_to_rgb(number):
    number = int(number)
    r = (number * 123) % 256
    g = (number * 321) % 256
    b = (number * 213) % 256
    return r, g, b

# Finds an available port on the system by binding to a temporary socket
def find_free_port():
    temp_socket = socket(AF_INET, SOCK_STREAM)
    temp_socket.bind(("", 0))
    port = temp_socket.getsockname()[1]
    temp_socket.close()
    return port

# Retrieves the current system's IP address using "Radmin VPN" interface
def get_my_ip():
    for interface, addrs in net_if_addrs().items():
        if "Radmin VPN" in interface:  # I temporarily use Radmin VPN
            for addr in addrs:
                if addr.family == AddressFamily.AF_INET:
                    return addr.address
    return None

# Enumeration of commands used in the chat client
class Command(Enum):
    PRINT_MESSAGE = 0
    DISCONNECTED_MESSAGE = 1
    CONNECTED_MESSAGE = 2
    GIVE_ID = 3
    HANDLE_NEW_CONNECTION = 4

# Represents a connection to a user in the chat system
class UserConnection:
    def __init__(self, host, port, reader=None, writer=None):
        self.host = host
        self.port = port
        self.reader = reader
        self.writer = writer

    def __str__(self):
        return f"{self.host}:{self.port}"

# Main chat client class handling messaging, connections, and server logic
class ChatClient:
    def __init__(self, server_host, server_port):
        self.left_node = UserConnection(server_host, server_port)
        self.right_node = None
        self.me = UserConnection(get_my_ip(), find_free_port())
        self.nickname = ""
        self.header = "<BHH"
        self.command_handlers = {
            Command.PRINT_MESSAGE: self.print_message,
            Command.DISCONNECTED_MESSAGE: self.disconnected_message,
            Command.CONNECTED_MESSAGE: self.connected_message,
            Command.GIVE_ID: self.get_id,
            Command.HANDLE_NEW_CONNECTION: self.handle_new_connection,
        }
        self.history = queue.Queue(maxsize=64)
        self.passed_messages = set()
        self.awaited_connection = list()
        self.new_node = None

    # Establishes initial connection or starts server for the client
    async def start_connection(self):
        try:
            if self.left_node.host is None:
                await self.server_startup()
                self.nickname = str(hash(str(self.me)) % 10**9)
                print(f"New person can join by this: {self.me}")
                self.left_node = self.me
                self.right_node = self.me
            else:
                self.left_node.reader, self.left_node.writer = await asyncio.open_connection(
                    self.left_node.host, self.left_node.port
                )
                header = await asyncio.wait_for(
                    self.left_node.reader.readexactly(struct.calcsize(self.header)),
                    timeout=15,
                )
                if not header:
                    raise Exception("Connection failed on header part")
                command, length, nickname_length = struct.unpack(self.header, header)
                body_data = await asyncio.wait_for(
                    self.left_node.reader.readexactly(length), timeout=5
                )
                if not body_data:
                    raise Exception("Connection failed on body part")
                full_message = header + body_data
                command, nickname, message = await self.unpack_message(full_message)
                await self.command_handlers[Command(command)](nickname, message)
                header = await asyncio.wait_for(
                    self.left_node.reader.readexactly(struct.calcsize(self.header)),
                    timeout=5,
                )
                if not header:
                    raise Exception("Connection failed on header part")
                command, length, nickname_length = struct.unpack(self.header, header)
                body_data = await asyncio.wait_for(
                    self.left_node.reader.readexactly(length), timeout=5
                )
                if not body_data:
                    raise Exception("Connection failed on body part")
                full_message = header + body_data
                command, nickname, message = await self.unpack_message(full_message)
                await self.command_handlers[Command(command)](nickname, message)
                await self.server_startup()
                print("You are joined!")
                # data = await self.pack_message(Command.CONNECTED_MESSAGE, self.nickname)
                # await self.send_message(data, self.left_node)
                # await self.send_message(data, self.right_node)
            await asyncio.gather(
                self.receive_messages(),
                self.process_input(),
            )
        except ConnectionError as e:
            print(f"Connection failed: {e}")
        finally:
            if self.left_node and self.left_node.writer:
                self.left_node.writer.close()
                await self.left_node.writer.wait_closed()
            if self.right_node and self.right_node.writer:
                self.right_node.writer.close()
                await self.right_node.writer.wait_closed()
            print("Exiting...")
            sys.exit(0)

    # Handles incoming messages from both left and right nodes
    async def receive_messages(self):
        while True:
            async def process_node(reader, writer, node_name):
                try:
                    while reader:
                        await self.process_stream(reader, writer)
                except asyncio.TimeoutError:
                    pass
                except Exception as e:
                    print(f"Failed to process {node_name}: {e}")

            try:
                tasks = []
                if self.right_node and self.right_node.reader:
                    tasks.append(
                        process_node(self.right_node.reader, self.left_node.writer, "right_node")
                    )
                if self.left_node and self.left_node.reader:
                    tasks.append(
                        process_node(self.left_node.reader, self.right_node.writer, "left_node")
                    )
                if tasks:
                    await asyncio.gather(*tasks)
                await asyncio.sleep(0.1)
            except Exception as e:
                print(f"General failure in receive_messages: {e}")

    # Process a single message stream from a reader/writer pair
    async def process_stream(self, reader, writer):
        while True:
            header = await asyncio.wait_for(
                reader.readexactly(struct.calcsize(self.header)), timeout=2
            )
            if not header:
                break
            command, length, nickname_length = struct.unpack(self.header, header)
            body_data = await asyncio.wait_for(reader.readexactly(length), timeout=2)
            if not body_data:
                break
            full_message = header + body_data
            hashed_message = crc32(full_message)
            if hashed_message in self.passed_messages:
                break
            command, nickname, message = await self.unpack_message(full_message)
            if command == Command.HANDLE_NEW_CONNECTION.value and message[0] == "1":
                if self.history.full():
                    deleted_item = self.history.get()
                    self.passed_messages.remove(deleted_item)
                self.passed_messages.add(hashed_message)
                self.history.put(hashed_message)
                await self.send_message(full_message, self.new_node.writer)
                data = await self.pack_message(Command.GIVE_ID.value, str(hash(str(self.new_node)) % 10 ** 9))
                await self.send_message(data, self.new_node.writer)
                self.right_node = self.new_node
                break
            await self.command_handlers[Command(command)](nickname, message)
            if self.history.full():
                deleted_item = self.history.get()
                self.passed_messages.remove(deleted_item)
            self.passed_messages.add(hashed_message)
            self.history.put(hashed_message)
            if command == Command.HANDLE_NEW_CONNECTION.value:
                if message[0] == "0":
                    await self.send_message(full_message, self.left_node.writer)
                break
            if writer:
                await self.send_message(full_message, writer)

            await asyncio.sleep(0)

    # Processes user input from the command line
    async def process_input(self):
        while True:
            message = await asyncio.to_thread(input)
            if message.lower() == "!disconnect":
                data = await self.pack_message(Command.DISCONNECTED_MESSAGE.value, self.nickname)
                right_data = await self.pack_message(Command.HANDLE_NEW_CONNECTION.value, "2r"+str(self.right_node))
                left_data = await self.pack_message(Command.HANDLE_NEW_CONNECTION.value, "2l"+str(self.left_node))
                await self.send_message(data, self.left_node.writer)
                await self.send_message(data, self.right_node.writer)
                await self.send_message(right_data, self.left_node.writer)
                await self.send_message(left_data, self.right_node.writer)
                raise Exception("Disconnected")
            elif message.lower() == "!new_connection":
                print(f"You can connect new user by this data: {self.me}")
                continue
            elif message.lower() == "!get_id":
                print(f"This is your id: {self.nickname}")
                continue
            if self.left_node.writer or self.right_node.writer:
                data = await self.pack_message(Command.PRINT_MESSAGE.value, message)
                hashed_message = crc32(data)
                if self.history.full():
                    deleted_item = self.history.get()
                    self.passed_messages.remove(deleted_item)
                self.history.put(hashed_message)
                self.passed_messages.add(hashed_message)
            if self.left_node.writer:
                await self.send_message(data, self.left_node.writer)
            if self.right_node.writer:
                await self.send_message(data, self.right_node.writer)

    # Sends a message to the network
    async def send_message(self, data, writer):
        if writer:
            writer.write(data)
            await writer.drain()

    async def pack_message(self, command, message):
        message = message.strip()
        packed_message = struct.pack(
            self.header + f"{len(self.nickname)}s{len(message.encode())}s",
            command,
            len(self.nickname) + len(message.encode()),
            len(self.nickname),
            self.nickname.encode(),
            message.encode(),
        )
        return packed_message

    # Parses the header and body of a message
    async def unpack_message(self, data):
        try:
            header_size = struct.calcsize(self.header)
            if len(data) < header_size:
                raise ValueError("Incomplete message header")
            command, data_length, nickname_length = struct.unpack(
                self.header, data[:header_size]
            )
            if Command(int(command)) not in self.command_handlers:
                raise ValueError("Unknown command received")
            if len(data[header_size:]) < data_length:
                raise ValueError("Incomplete message payload")
            unpack_format = f"{nickname_length}s{data_length - nickname_length}s"
            nickname, message = struct.unpack(
                unpack_format, data[header_size : header_size + data_length]
            )
            nickname = nickname.decode()
            message = message.decode()
            return int(command), nickname, message
        except Exception as e:
            print(f"Failed to unpack message: {e}")

    # Handles incoming PRINT_MESSAGE commands
    async def print_message(self, nickname, message):
        r, g, b = number_to_rgb(nickname)
        print(f"\033[38;2;{r};{g};{b}m{nickname}\033[0m: {message}")

    # Handles incoming DISCONNECTED_MESSAGE commands
    async def disconnected_message(self, nickname, message):
        print(f"[ ! ] {message} left the chat!")

    # Handles incoming CONNECTED_MESSAGE commands
    async def connected_message(self, nickname, message):
        print(f"[ ! ] {message} joined the chat!")

    # Handles requests to provide the user's ID
    async def get_id(self, nickname, message):
        self.nickname = message
        print(f"Received ID: {self.nickname}")

    # Handles new connections in the network
    async def handle_new_connection(self, nickname, message):
        if not self.right_node:
            right_host, right_port = message[1:].split(":")
            right_reader, right_writer = await asyncio.open_connection(
                right_host, int(right_port)
            )
            self.right_node = UserConnection(right_host, int(right_port), right_reader, right_writer)
        elif message[0] == "2":
            if message[1] == "l":
                self.left_node = UserConnection(message[2:].split(":")[0], int(message[2:].split(":")[1]))
                self.awaited_connection.append(self.left_node.host)
            else:
                self.right_node = UserConnection(message[2:].split(":")[0], int(message[2:].split(":")[1]))
                self.right_node.reader, self.right_node.writer = await asyncio.open_connection(self.right_node.host, self.right_node.port)
        else:
            new_node_host, new_node_port = message[1:].split(":")
            self.awaited_connection.append(new_node_host)
            data = await self.pack_message(Command.HANDLE_NEW_CONNECTION.value, "1"+str(self.me))
            await self.send_message(data, self.left_node.writer)

    # Starts the server for incoming connections
    async def server_startup(self):
        if not self.me.host:
            raise Exception("Server can't be started!")
        server = await asyncio.start_server(
            self.handle_connection, self.me.host, self.me.port
        )
        asyncio.create_task(self.run_server(server))

    async def run_server(self, server):
        async with server:
            await server.serve_forever()

    # Handles incoming connections to the server
    async def handle_connection(self, reader, writer):
        try:
            peer = writer.get_extra_info("peername")
            new_node = UserConnection(peer[0], peer[1], reader, writer)
            if str(self.right_node) == str(self.me):
                data = await self.pack_message(Command.HANDLE_NEW_CONNECTION.value, "1"+str(self.me))
                self.awaited_connection.append(new_node.host)
                await self.send_message(data, new_node.writer)
                data = await self.pack_message(Command.GIVE_ID.value, str(hash(str(new_node)) % 10 ** 9))
                await self.send_message(data, new_node.writer)
                self.right_node = new_node
            else:
                if new_node.host not in self.awaited_connection:
                    self.new_node = new_node
                    data = await self.pack_message(Command.HANDLE_NEW_CONNECTION.value, "0"+str(new_node))
                    await self.send_message(data, self.right_node.writer)
                else:
                        self.left_node = new_node
                        self.awaited_connection.remove(new_node.host)
        except Exception as e:
            print(f"Failed to handle new connection: {e}")

# Entry point for the script
def main():
    parser = argparse.ArgumentParser(
        description="Client and Server for Decentralized Messenger"
    )
    parser.add_argument(
        "-c",
        "--cmd",
        type=bool,
        default=False,
        help="Run through command line with parameters",
    )
    parser.add_argument("-s", "--server", type=str, default=None, help="Server host")
    parser.add_argument(
        "-p", "--port", type=str, default=f"{find_free_port()}", help="Server port"
    )
    args = parser.parse_args()

    server_host = args.server if args.cmd else input("Server host: ")
    server_port = args.port if args.cmd else input("Server port: ")
    client = ChatClient(server_host, server_port)
    asyncio.run(client.start_connection())

# Boilerplate for running the script
if __name__ == "__main__":
    main()