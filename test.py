import struct

FORMAT = "<BH"

def pack_message(message):
    return struct.pack(FORMAT+f"{len(message)}s", 1, len(message), message.encode())

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

data = pack_message(65535*"a")
print(data)
size = struct.calcsize(FORMAT + f"{len(data)-struct.calcsize(FORMAT)}s")
print(size)
