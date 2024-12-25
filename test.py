import struct
from struct import unpack

processed_hashs = set()
peer = {}
peer[0] = "192.168.0.0"
peer[1] = "21234"

def number_to_rgb(number):
    # Ensure number is non-negative
    number = abs(number)
    # Map the number to a color
    r = (number * 123) % 256  # Vary red component
    g = (number * 321) % 256  # Vary green component
    b = (number * 213) % 256  # Vary blue component
    print(f"\033[38;2;{r};{g};{b}m{(r, g, b)}\033[0m")

new_hash = hash(str(peer[0])+":"+str(peer[1])) % 10 ** 9
number_to_rgb(new_hash)

header = "<BHH"
nickname = "123456789"
def unpack_message(data):
    try:
        header_size = struct.calcsize(header)
        if len(data) < header_size:
            raise ValueError("Incomplete message header")
        command, data_length, nickname_length = struct.unpack(header, data[:header_size])
        if len(data[header_size:]) < data_length:
            raise ValueError("Incomplete message payload")
        unpack_format = f"{nickname_length}s{data_length - nickname_length}s"
        nickname, message = struct.unpack(unpack_format, data[header_size:header_size + data_length])
        nickname = nickname.decode()
        message = message.decode()
        return int(command), nickname, message
    except Exception as e:
        print(f"Failed to unpack message: {e}")

def pack_message(command, message):
    message = message.strip()
    nick_len = len(nickname.encode())
    mes_len = len(message.encode())
    total_length = nick_len + mes_len
    return struct.pack(header + f"{nick_len}s{mes_len}s", command, total_length, nick_len, nickname.encode(), message.encode())

packed = pack_message(0, "thing")
packed1 = pack_message(0, "штучка")
print(packed)
print(packed1)
unpacked = unpack_message(packed)
unpacked1 = unpack_message(packed1)
print(unpacked)
print(unpacked1)