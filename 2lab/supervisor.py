from cpu import SAVE_AREA, PI_TEXT, AddressError, translate, is_valid_command
from devices import MEMORY, DISK, KEYBOARD, SCREEN
from memory import int_to_word, text_to_word

QUANTUM = 10
INT_AREA = 0x0805
XC_AREA = 0x0808
KEYBOARD_BUFFER = 0x98
SCREEN_BUFFER = 0x99
CATALOG_COPY = 0x9C
FILE_BUFFER = 0xA0

READY = 'pasiruošusi'
RUNNING = 'vykdoma'
WAITING_INPUT = 'laukia įvedimo'
WAITING_CHILD = 'laukia vaiko'


class ProgramError(Exception):
    pass


def parse_program(text):
    data = []
    code = []
    section = None
    for line in text.split('\n'):
        line = line.lstrip()
        upper = line.upper()
        if upper == '$DATA':
            section = 'data'
        elif upper == '$CODE':
            section = 'code'
        elif section == 'data' and upper.startswith('DW'):
            number = line[2:].strip()
            if number == '':
                number = '0'
            if not number.lstrip('+-').isdigit():
                raise ProgramError('neteisingas skaičius: ' + line)
            data.append(int_to_word(int(number)))
        elif section == 'data' and upper.startswith('DB'):
            if len(line) > 7:
                raise ProgramError('DB tekstas ilgesnis nei 4 simboliai: ' + line)
            data.append(text_to_word(line[3:]))
        elif section == 'code' and is_valid_command(upper.strip()):
            code.append(upper.strip().encode('ascii'))
        else:
            raise ProgramError('neatpažinta eilutė: ' + line)
    if len(data) > 128 or len(code) > 112:
        raise ProgramError('per daug duomenų arba komandų')
    if b'HALT' not in code:
        raise ProgramError('nėra HALT komandos')
    return data, code


class VMProcess:

    def __init__(self, number, name, ptr, table_block, pages, parent):
        self.number = number
        self.name = name
        self.table_block = table_block
        self.pages = pages
        self.parent = parent
        self.state = READY
        self.gn_address = 0
        self.R = 0
        self.IC = 0x80
        self.C = 0
        self.PTR = ptr
        self.TI = QUANTUM

    def label(self):
        return '%s#%d' % (self.name, self.number)


class Supervisor:
    def __init__(self, machine):
        self.machine = machine
        self.cpu = machine.cpu
        self.memory = machine.memory
        self.keyboard = machine.keyboard
        self.processes = []
        self.used_blocks = [False] * 128
        self.current = None
        self.counter = 0
        self.actions = []

    def step(self):
        self.actions = []
        if self.current is not None:
            vm = self.current
            self.current = None
            self.handle_interrupt(vm)
        if self.keyboard.has_line():
            self.handle_keyboard_line()
        vm = self.choose_vm()
        if vm is not None:
            self.start_vm(vm)
        elif len(self.actions) == 0:
            self.actions.append('laukia')
        return ', '.join(self.actions)

    def is_idle(self):
        return self.current is None and not self.keyboard.has_line() and self.choose_vm() is None

    def choose_vm(self):
        for vm in reversed(self.processes):
            if vm.state == READY:
                return vm
        return None

    def waiting_vm(self):
        for vm in reversed(self.processes):
            if vm.state == WAITING_INPUT:
                return vm
        return None

    def start_vm(self, vm):
        if vm.TI == 0:
            vm.TI = QUANTUM
        self.memory.write_int(SAVE_AREA, vm.R)
        self.memory.write_int(SAVE_AREA + 1, vm.IC)
        self.memory.write_int(SAVE_AREA + 2, vm.C)
        self.memory.write_int(SAVE_AREA + 3, vm.PTR)
        self.memory.write_int(SAVE_AREA + 4, vm.TI)
        self.cpu.iret()
        vm.state = RUNNING
        self.current = vm
        self.actions.append('IRET -> %s' % vm.label())

    def real_address(self, vm, address):
        return translate(self.memory, vm.PTR, address)

    def start_channel(self, st, src, dt, dst):
        self.memory.write_int(XC_AREA, st)
        self.memory.write_int(XC_AREA + 1, src)
        self.memory.write_int(XC_AREA + 2, dt)
        self.memory.write_int(XC_AREA + 3, dst)
        self.cpu.xc(XC_AREA)
        self.cpu.ri(INT_AREA)

    def handle_interrupt(self, vm):
        self.cpu.ri(INT_AREA)
        pi = self.memory.read_uint(INT_AREA)
        si = self.memory.read_uint(INT_AREA + 1)
        vm.R = self.memory.read_int(SAVE_AREA)
        vm.IC = self.memory.read_uint(SAVE_AREA + 1)
        vm.C = self.memory.read_uint(SAVE_AREA + 2)
        vm.PTR = self.memory.read_uint(SAVE_AREA + 3)
        vm.TI = self.memory.read_uint(SAVE_AREA + 4)
        vm.state = READY
        self.actions.append('pertraukimas PI=%d SI=%d TI=%d' % (pi, si, vm.TI))

        try:
            if pi != 0:
                self.end_vm(vm, 'klaida: %s (PI=%d)' % (PI_TEXT[pi], pi))
                return
            if si == 0:
                return
            text = self.memory.read_text(self.real_address(vm, vm.IC - 1))
            xy = int(text[2:], 16) if si != 5 else 0
            if si == 1:
                vm.state = WAITING_INPUT
                vm.gn_address = xy
                self.actions.append('%s laukia skaičiaus' % vm.label())
            elif si == 2:
                value = self.memory.read_int(self.real_address(vm, xy))
                self.print_text(str(value) + '\n')
            elif si == 3:
                self.print_text(self.read_string(vm, xy))
            elif si == 4:
                self.run_child(vm, xy)
            elif si == 5:
                self.end_vm(vm, 'baigė darbą')
        except AddressError as error:
            self.end_vm(vm, 'klaida: %s' % error)

    def read_string(self, vm, address):
        text = ''
        while address <= 0xFF:
            for ch in self.memory.read_text(self.real_address(vm, address)):
                if ch == '$':
                    return text
                text += ch
            address += 1
        return text

    def print_text(self, text):
        for i in range(0, len(text), 64):
            self.memory.write_block(SCREEN_BUFFER, text[i:i + 64].encode('latin-1'))
            self.start_channel(MEMORY, SCREEN_BUFFER, SCREEN, 0)
        self.actions.append('išvesta per CH2: "%s"' % text.strip())

    def run_child(self, parent, xy):
        name = self.memory.read_text(self.real_address(parent, xy))
        params = []
        for i in range(16):
            params.append(self.memory.read_word(self.real_address(parent, 0xF0 + i)))
        child = self.load_program(name, params, parent)
        if child is None:
            parent.R = 1
        else:
            parent.R = 0
            parent.state = WAITING_CHILD

    def end_vm(self, vm, reason):
        for block in vm.pages + [vm.table_block]:
            self.used_blocks[block] = False
        self.processes.remove(vm)
        if vm.parent is not None and vm.parent.state == WAITING_CHILD:
            vm.parent.state = READY
        self.actions.append('%s panaikinta' % vm.label())
        self.machine.say('%s: %s' % (vm.label(), reason))

    def handle_keyboard_line(self):
        self.start_channel(KEYBOARD, 0, MEMORY, KEYBOARD_BUFFER)
        line = self.memory.read_block(KEYBOARD_BUFFER).split(b'\0')[0].decode('latin-1').strip()
        self.actions.append('CH1: "%s"' % line)
        words = line.split()
        if len(words) == 0:
            return
        if words[0].upper() == 'RUN' and len(words) == 2:
            self.load_program(words[1], [], None)
            return
        vm = self.waiting_vm()
        if vm is None:
            self.machine.say('Nežinoma komanda: ' + line)
        elif not line.lstrip('+-').isdigit():
            self.machine.say('Įveskite sveikąjį skaičių')
        else:
            self.memory.write_int(self.real_address(vm, vm.gn_address), int(line))
            vm.state = READY

    def load_program(self, name, params, parent):
        name = name.strip().upper()

        for i in range(4):
            self.start_channel(DISK, i, MEMORY, CATALOG_COPY + i)
        entry = None
        for i in range(16):
            address = CATALOG_COPY * 16 + i * 4
            if self.memory.read_text(address).strip() == name:
                entry = i
        if entry is None:
            self.machine.say('Programa %s nerasta diske' % name)
            return None
        address = CATALOG_COPY * 16 + entry * 4
        first = self.memory.read_uint(address + 1)
        count = self.memory.read_uint(address + 2)
        length = self.memory.read_uint(address + 3)
        text = b''
        for i in range(count):
            self.start_channel(DISK, first + i, MEMORY, FILE_BUFFER + i)
            text += self.memory.read_block(FILE_BUFFER + i)

        try:
            data, code = parse_program(text[:length].decode('latin-1'))
        except ProgramError as error:
            self.machine.say('Programa %s nepaleista: %s' % (name, error))
            return None

        free = []
        for block in range(128):
            if not self.used_blocks[block]:
                free.append(block)
        if len(free) < 17:
            self.machine.say('Nepakanka atminties programai %s' % name)
            return None
        chosen = self.machine.random.sample(free, 17)
        table = chosen[0]
        pages = chosen[1:]
        for block in chosen:
            self.used_blocks[block] = True
            self.memory.write_block(block, b'')
        for i in range(16):
            self.memory.write_int(table * 16 + i, pages[i])

        for i in range(len(data)):
            self.memory.write_word(pages[i // 16] * 16 + i % 16, data[i])
        for i in range(len(code)):
            self.memory.write_word(pages[8 + i // 16] * 16 + i % 16, code[i])
        for i in range(len(params)):
            self.memory.write_word(pages[15] * 16 + i, params[i])

        code_blocks = (len(code) + 15) // 16
        ptr = (code_blocks << 24) | (16 << 16) | ((table // 16) << 8) | (table % 16)
        self.counter += 1
        vm = VMProcess(self.counter, name, ptr, table, pages, parent)
        self.processes.append(vm)
        self.actions.append('užkrauta %s' % vm.label())
        return vm
