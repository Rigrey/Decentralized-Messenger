import struct
from struct import calcsize

FORMAT = "<BH"
def pack_message(message):
    return struct.pack(FORMAT+f"{len(message)}s", 0, len(message), message.encode())


def unpack_message(data):
    if len(data) < calcsize(FORMAT):
        return data.decode()
    identifier, length = struct.unpack(FORMAT, data[:calcsize(FORMAT)])
    if len(data) < calcsize(FORMAT) + length:
        message = data[calcsize(FORMAT):]
    else:
        message = struct.unpack(f"<{length}s", data[calcsize(FORMAT):calcsize(FORMAT) + length])[0]
    return message.decode('utf-8')



base = pack_message("hello, my name is david, what's yours? are you good feeling this?")
print(base)
print(unpack_message(base))
base1 = pack_message("hello")
print(base1)
print(unpack_message(base1))
