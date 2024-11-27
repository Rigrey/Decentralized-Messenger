import argparse
import asyncio
import string
import struct
import sys
#TODO: DO NEW SERVER

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
        if "Radmin VPN" in interface: # I temporarily use Radmin VPN
            for addr in addrs:
                if addr.family == AddressFamily.AF_INET:
                    return addr.address
    return None


class User_Connection:
    def __init__(self, host, port, reader = None, writer = None):
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
        self.format = "<BH"
        self.nicknames = set()
        self.command_handlers = {
            0: self.print_message,
            1: self.disconnected_message,
            2: self.connected_message,
            3: self.update_nicknames,
            4: self.handle_new_connection,
        }

#FIXME: CHILD?
    async def start_connection(self):
        try:
            if self.parent.host == 'localhost':
                await self.server_startup()
                await self.set_nickname()
                print(f"New person can join by this: {self.me}")
            else:
                self.me.reader, self.me.writer = await asyncio.open_connection(self.parent.host, self.parent.port)
                await self.unpack_message(await self.me.reader.read(65538))
                await self.set_nickname()
                data = await self.pack_message(2, self.nickname)
                await self.broadcast_message(data, self.me.writer)
            await asyncio.gather(
                self.receive_messages(),
                self.send_messages(),
            )
        except ConnectionError as e:
            print(f'Connection failed: {e}')
        finally:
            if self.me.writer:
                self.me.writer.close()
                await self.me.writer.wait_closed()
            sys.exit(0)

# FIXME: RECEIVE-FUNC TRANSFORM TO BROADCAST-FUNC / SEND TO BROADCAST-FUNC
    async def receive_messages(self):
        while True:
            try:
                if self.child:
                    child_data = await self.child.reader.read(65538)
                    if child_data:
                        await self.unpack_message(child_data)
                        await self.broadcast_message(child_data, self.me.writer)
                if self.me.reader:
                    parent_data = await self.me.reader.read(65538)
                    if parent_data:
                        await self.unpack_message(parent_data)
                        await self.broadcast_message(parent_data, self.child.writer)
            except Exception as e:
                print(f"Failed to receive message: {e}")
                pass

    async def send_messages(self):
        while True:
            message = await asyncio.to_thread(input)
            if message.lower() == "disconnect": # FIXME: THIS SHOULD GIVE INFO ABOUT CONNECTIONS. LISTENER SHOULD CONNECT BOTH
                data_child = await self.pack_message(1, f'{self.nickname};{self.me}')
                data_parent = await self.pack_message(1, self.nickname)
                await self.broadcast_message(data_child, self.child.writer)
                await self.broadcast_message(data_parent, self.me.writer)
                break
            elif message.lower() == "new_connection":
                if not self.child:
                    print(f"You can connect new user by this data: {message.split(';')[0]}")
                    continue
                data = await self.pack_message(4, str(self.me))
                await self.broadcast_message(data, self.child.writer) # FIXME : NOT DONE YET. ADD THIS COMMAND TO COMMAND_HANDLER + ADD NEW FUNC
                continue
            if self.me.writer or self.child:
                data = await self.pack_message(4, message)
            if self.me.writer:
                await self.broadcast_message(data, self.me.writer)
            if self.child:
                await self.broadcast_message(data, self.child.writer)

    async def broadcast_message(self, data, writer):
        if writer:
            writer.write(data)
            await writer.drain()

    async def pack_message(self, command, message):
        return struct.pack(self.format + f"{len(message)}s", command, len(message), message.strip().encode())

    async def unpack_message(self, data):
        try:
            format_size = struct.calcsize(self.format)
            if len(data) < format_size:
                raise ValueError("Incomplete message header.")
            command, length = struct.unpack(self.format, data[:format_size])
            if command not in self.command_handlers:
                raise ValueError("Unknown command received.")

            message = data[format_size:format_size + length].decode()
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

    async def print_message(self, message):
        print(message)

#FIXME: THIS SHIT DON'T RECONNECT AFTER DISCONNECTION
    async def disconnected_message(self, message):
        print(f"[ ! ] {message} left the chat!")
        self.nicknames.discard(message)

    async def connected_message(self, message):
        print(f"[ ! ] {message} joined the chat!")
        self.nicknames.add(message)

    async def update_nicknames(self, message):
        self.nicknames.update(message.split(', '))

    async def handle_new_connection(self, message): #TODO: CONTINUE WORKING ON THIS FUNCTION
        if not self.child:
            data = await self.pack_message(4, f'{self.me};{message}')
            await self.broadcast_message(data, self.me.writer)
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
            data = await self.pack_message(3, str(self.nicknames)[1:-1])
            await self.broadcast_message(data, self.child.writer)
        except Exception as e:
            print(f"Failed to handle new connection: {e}")

# TODO: ADD LOCALHOST AS START
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description=' Client for temporarily (De)centralized Messenger'
    )
    parser.add_argument('-c', '--cmd', type=bool, default=False, help='Run through command line with parameters')
    parser.add_argument('-s', '--server', type=str, default='localhost', help='Server host')
    parser.add_argument('-p', '--port', type=str, default=f'{find_free_port()}', help='Server port')
    args = parser.parse_args()

    server_host = args.server if args.cmd else input('Server host: ')
    server_port = args.port if args.cmd else input('Server port: ')

    client = ChatClient(server_host, server_port)
    asyncio.run(client.start_connection())
