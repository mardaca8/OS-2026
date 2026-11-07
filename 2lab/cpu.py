from memory import INT_MIN, INT_MAX, is_text

SAVE_AREA = 0x0800
HANDLER = 0x0810

COMMANDS = ['LR', 'SR', 'AD', 'SU', 'MU', 'DV', 'CM',
            'JM', 'JE', 'JN', 'JG', 'JL', 'GN', 'PN', 'PD', 'RN']
PRIVILEGED = ['RI', 'XC']

PI_TEXT = {1: 'neleistinas adresas', 2: 'nežinoma komanda', 3: 'dalyba iš nulio',
           4: 'perpildymas', 5: 'privilegijuota komanda'}


class AddressError(Exception):
    pass


def is_hex(text):
    for ch in text:
        if ch not in '0123456789ABCDEF':
            return False
    return True


def is_valid_command(text):
    if text == 'HALT' or text == 'IRET':
        return True
    return len(text) == 4 and (text[:2] in COMMANDS or text[:2] in PRIVILEGED) and is_hex(text[2:])


def split_ptr(ptr):
    return list((ptr & 0xFFFFFFFF).to_bytes(4, 'big'))


def translate(memory, ptr, address):
    a = split_ptr(ptr)
    x1 = address // 16
    x2 = address % 16
    if x1 >= a[1]:
        raise AddressError('adresas %X viršija VM atmintį' % address)
    table = 16 * a[2] + a[3]
    block = memory.read_uint(16 * table + x1)
    if block >= 0x80:
        raise AddressError('puslapis ne vartotojo atmintyje')
    return 16 * block + x2


class CPU:
    def __init__(self, memory):
        self.memory = memory
        self.channels = None
        self.R = 0
        self.IC = HANDLER
        self.C = 0
        self.PTR = 0
        self.MODE = 1
        self.TI = 0
        self.PI = 0
        self.SI = 0
        self.IOI = 0

    def zf(self):
        return self.C & 1

    def sf(self):
        return (self.C >> 1) & 1

    def set_flags(self, zero, negative):
        self.C = 0
        if zero:
            self.C += 1
        if negative:
            self.C += 2

    def user_step(self):
        a = split_ptr(self.PTR)
        page = self.IC // 16
        if page < 8 or page >= 8 + a[0]:
            self.PI = 1
            text = '%02X: adresas ne kodo segmente' % self.IC
        else:
            try:
                word = self.memory.read_word(translate(self.memory, self.PTR, self.IC))
                text = '%02X: %s' % (self.IC, word_to_text(word))
                self.IC += 1
                self.execute(word)
            except AddressError:
                self.PI = 1
                text = '%02X: neleistinas adresas' % self.IC

        if self.TI > 0:
            self.TI -= 1
        if self.PI != 0 or self.SI != 0 or self.TI == 0 or self.IOI != 0:
            text += ' -> pertraukimas'
            self.interrupt()
        return text

    def execute(self, word):
        if not is_text(word):
            self.PI = 2
            return
        text = word.decode('latin-1')
        if text == 'HALT':
            self.SI = 5
            return
        code = text[:2]
        if text == 'IRET' or code in PRIVILEGED:
            self.PI = 5
            return
        if code not in COMMANDS or not is_hex(text[2:]):
            self.PI = 2
            return
        xy = int(text[2:], 16)

        if code == 'GN':
            self.SI = 1
        elif code == 'PN':
            self.SI = 2
        elif code == 'PD':
            self.SI = 3
        elif code == 'RN':
            self.SI = 4

        elif code == 'JM':
            self.IC = xy
        elif code == 'JE':
            if self.zf() == 1:
                self.IC = xy
        elif code == 'JN':
            if self.zf() == 0:
                self.IC = xy
        elif code == 'JG':
            if self.zf() == 0 and self.sf() == 0:
                self.IC = xy
        elif code == 'JL':
            if self.sf() == 1:
                self.IC = xy

        else:
            real = translate(self.memory, self.PTR, xy)
            value = self.memory.read_int(real)
            if code == 'LR':
                self.R = value
            elif code == 'SR':
                self.memory.write_int(real, self.R)
            elif code == 'CM':
                self.set_flags(self.R == value, self.R < value)
            elif code == 'DV' and value == 0:
                self.PI = 3
            else:
                if code == 'AD':
                    result = self.R + value
                elif code == 'SU':
                    result = self.R - value
                elif code == 'MU':
                    result = self.R * value
                else:
                    result = abs(self.R) // abs(value)
                    if (self.R < 0) != (value < 0):
                        result = -result
                if result < INT_MIN or result > INT_MAX:
                    self.PI = 4
                else:
                    self.R = result
                    self.set_flags(result == 0, result < 0)

    def interrupt(self):
        self.memory.write_int(SAVE_AREA, self.R)
        self.memory.write_int(SAVE_AREA + 1, self.IC)
        self.memory.write_int(SAVE_AREA + 2, self.C)
        self.memory.write_int(SAVE_AREA + 3, self.PTR)
        self.memory.write_int(SAVE_AREA + 4, self.TI)
        self.MODE = 1
        self.IC = HANDLER

    def ri(self, address):
        self.memory.write_int(address, self.PI)
        self.memory.write_int(address + 1, self.SI)
        self.memory.write_int(address + 2, self.IOI)
        self.PI = 0
        self.SI = 0
        self.IOI = 0

    def xc(self, address):
        st = self.memory.read_uint(address) & 0xFF
        src = self.memory.read_uint(address + 1) & 0xFFFF
        dt = self.memory.read_uint(address + 2) & 0xFF
        dst = self.memory.read_uint(address + 3) & 0xFFFF
        if not self.channels.start(st, src, dt, dst):
            self.PI = 5

    def iret(self):
        self.R = self.memory.read_int(SAVE_AREA)
        self.IC = self.memory.read_uint(SAVE_AREA + 1)
        self.C = self.memory.read_uint(SAVE_AREA + 2)
        self.PTR = self.memory.read_uint(SAVE_AREA + 3)
        self.TI = self.memory.read_uint(SAVE_AREA + 4)
        self.MODE = 0


def word_to_text(word):
    if is_text(word):
        return word.decode('latin-1')
    return word.hex().upper()
