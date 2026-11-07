import os

MEMORY = 1
DISK = 2
KEYBOARD = 3
SCREEN = 4


def remove_comment(line):
    if ';' in line:
        line = line[:line.index(';')]
    return line.rstrip()


class HardDisk:

    def __init__(self):
        self.data = bytearray(256 * 64)

    def read_block(self, number):
        return bytes(self.data[number * 64:number * 64 + 64])

    def load_folder(self, folder):
        next_block = 4
        count = 0
        for file_name in sorted(os.listdir(folder)):
            if not file_name.lower().endswith('.txt') or count == 16:
                continue
            with open(os.path.join(folder, file_name), encoding='utf-8') as f:
                lines = []
                for line in f:
                    line = remove_comment(line)
                    if line.strip() != '':
                        lines.append(line)
            content = '\n'.join(lines).encode('latin-1', errors='replace')
            blocks = (len(content) + 63) // 64
            name = file_name[:-4].upper()[:4].ljust(4)
            entry = (name.encode('latin-1') + next_block.to_bytes(4, 'big')
                     + blocks.to_bytes(4, 'big') + len(content).to_bytes(4, 'big'))
            self.data[count * 16:count * 16 + 16] = entry
            self.data[next_block * 64:next_block * 64 + len(content)] = content
            next_block += blocks
            count += 1
        return count

    def file_names(self):
        names = []
        for i in range(16):
            name = self.data[i * 16:i * 16 + 4]
            if name != b'\0\0\0\0':
                names.append(name.decode('latin-1').strip())
        return names


class Keyboard:
    def __init__(self):
        self.lines = []

    def has_line(self):
        return len(self.lines) > 0


class Screen:

    def __init__(self, output):
        self.output = output

    def print_text(self, text):
        self.output.append(('screen', text))


class ChannelDevice:

    def __init__(self, cpu, memory, disk, keyboard, screen):
        self.cpu = cpu
        self.memory = memory
        self.disk = disk
        self.keyboard = keyboard
        self.screen = screen
        self.busy = {1: 0, 2: 0, 3: 0}
        self.ST = 0
        self.SRC = 0
        self.DT = 0
        self.DST = 0

    def start(self, st, src, dt, dst):
        if st == KEYBOARD and dt == MEMORY:
            channel = 1
        elif st == MEMORY and dt == SCREEN:
            channel = 2
        elif st == DISK and dt == MEMORY:
            channel = 3
        else:
            return False
        if self.busy[channel]:
            return False
        self.ST, self.SRC, self.DT, self.DST = st, src, dt, dst
        self.busy[channel] = 1

        if channel == 1:
            line = self.keyboard.lines.pop(0)
            self.memory.write_block(dst, line.encode('latin-1', errors='replace'))
        elif channel == 2:
            text = self.memory.read_block(src).split(b'\0')[0]
            self.screen.print_text(text.decode('latin-1'))
        else:
            self.memory.write_block(dst, self.disk.read_block(src))

        self.busy[channel] = 0
        self.cpu.IOI += [0, 1, 2, 4][channel]
        return True
