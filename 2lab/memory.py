BLOCK_SIZE = 16
INT_MIN = -2 ** 31
INT_MAX = 2 ** 31 - 1


def int_to_word(value):
    return (value & 0xFFFFFFFF).to_bytes(4, 'big')


def word_to_int(word):
    value = int.from_bytes(word, 'big')
    if value >= 2 ** 31:
        value -= 2 ** 32
    return value


def text_to_word(text):
    return text[:4].ljust(4).encode('latin-1', errors='replace')


def is_text(word):
    for b in word:
        if b < 32 or b > 126:
            return False
    return True


def word_to_string(word):
    if is_text(word):
        return word.decode('latin-1')
    return str(word_to_int(word))


def parse_value(text):
    if text.lstrip('+-').isdigit():
        return int_to_word(int(text))
    if len(text) <= 4:
        return text_to_word(text)
    raise ValueError('reikšmė turi būti skaičius arba iki 4 simbolių')


class Memory:
    def __init__(self, size):
        self.size = size
        self.data = bytearray(size * 4)

    def read_word(self, address):
        if address < 0 or address >= self.size:
            raise IndexError('adresas %04X už atminties ribų' % address)
        return bytes(self.data[address * 4:address * 4 + 4])

    def write_word(self, address, word):
        if address < 0 or address >= self.size:
            raise IndexError('adresas %04X už atminties ribų' % address)
        self.data[address * 4:address * 4 + 4] = word

    def read_int(self, address):
        return word_to_int(self.read_word(address))

    def read_uint(self, address):
        return int.from_bytes(self.read_word(address), 'big')

    def write_int(self, address, value):
        self.write_word(address, int_to_word(value))

    def read_text(self, address):
        return self.read_word(address).decode('latin-1')

    def read_block(self, block):
        start = block * BLOCK_SIZE * 4
        return bytes(self.data[start:start + BLOCK_SIZE * 4])

    def write_block(self, block, data):
        data = bytes(data[:64]).ljust(64, b'\0')
        start = block * BLOCK_SIZE * 4
        self.data[start:start + 64] = data
