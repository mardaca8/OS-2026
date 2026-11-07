import tkinter as tk
from tkinter import ttk

from cpu import split_ptr, word_to_text
from machine import RealMachine
from memory import word_to_string, parse_value

FONT = ('Consolas', 10)
SMALL = ('Consolas', 9)
CHANGED = '#ffe066'

HELP = """Komandos:
  RUN <vardas>        paleisti programą iš disko (apdoroja OS)
  <skaičius>          įvestis programai, kuri laukia GN
  DIR                 programos diske
  SET <reg> <sk>      pakeisti VM registrą R, IC (hex) arba C
  MEM <xy> <reikšmė>  pakeisti VM atminties žodį (skaičius arba tekstas)
Mygtukai: Žingsnis (F10) - vienas mašinos žingsnis, Vykdyti (F5) - iki pabaigos arba įvedimo."""


class EmulatorApp:
    def __init__(self, root, programs_folder):
        self.root = root
        self.programs_folder = programs_folder
        self.machine = RealMachine(programs_folder)
        self.old_values = {}
        self.rm_block = tk.StringVar(value='00')

        root.title('Virtuali ir reali mašina')
        root.geometry('1400x850')
        self.build_toolbar()
        panes = ttk.PanedWindow(root, orient='horizontal')
        panes.pack(fill='both', expand=True)
        left = ttk.Frame(panes, padding=4)
        right = ttk.Frame(panes, padding=4)
        panes.add(left, weight=3)
        panes.add(right, weight=1)
        self.build_machine_view(left)
        self.build_console(right)
        root.bind('<F10>', lambda e: self.step())
        root.bind('<F5>', lambda e: self.run())
        self.refresh()

    def build_toolbar(self):
        bar = ttk.Frame(self.root, padding=4)
        bar.pack(fill='x')
        ttk.Button(bar, text='Žingsnis (F10)', command=self.step).pack(side='left')
        ttk.Button(bar, text='Vykdyti (F5)', command=self.run).pack(side='left', padx=4)
        ttk.Button(bar, text='Perkrauti', command=self.reset).pack(side='left')
        self.action_label = ttk.Label(bar, font=FONT)
        self.action_label.pack(side='left', padx=12)

    def make_value_rows(self, frame, names, width):
        labels = {}
        for i in range(len(names)):
            ttk.Label(frame, text=names[i]).grid(row=i, column=0, sticky='w')
            label = tk.Label(frame, font=FONT, width=width, anchor='w', bg='white', relief='groove')
            label.grid(row=i, column=1, sticky='w', padx=4, pady=1)
            labels[names[i]] = label
        return labels

    def build_machine_view(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill='x')

        cpu_frame = ttk.LabelFrame(top, text='RM procesorius', padding=4)
        cpu_frame.grid(row=0, column=0, sticky='n')
        self.cpu_labels = self.make_value_rows(
            cpu_frame, ['R', 'IC', 'C', 'PTR', 'MODE', 'TI', 'PI', 'SI', 'IOI', 'CH1', 'CH2', 'CH3'], 16)

        middle = ttk.Frame(top)
        middle.grid(row=0, column=1, sticky='n', padx=6)
        vm_frame = ttk.LabelFrame(middle, text='Virtuali mašina', padding=4)
        vm_frame.pack(fill='x')
        self.vm_labels = self.make_value_rows(vm_frame, ['Programa', 'Būsena', 'R', 'IC', 'C', 'Komanda'], 22)
        dev_frame = ttk.LabelFrame(middle, text='Išoriniai įrenginiai', padding=4)
        dev_frame.pack(fill='x', pady=(6, 0))
        self.devices_label = tk.Label(dev_frame, font=FONT, justify='left', anchor='w')
        self.devices_label.pack(fill='x')

        page_frame = ttk.LabelFrame(top, text='Vykdomos komandos puslapis', padding=4)
        page_frame.grid(row=0, column=2, sticky='n')
        self.page_text = tk.Text(page_frame, font=FONT, width=28, height=18)
        self.page_text.pack()
        self.page_text.tag_configure('ic', background=CHANGED)

        notebook = ttk.Notebook(parent)
        notebook.pack(fill='both', expand=True, pady=(6, 0))
        vm_tab = ttk.Frame(notebook)
        rm_tab = ttk.Frame(notebook)
        notebook.add(vm_tab, text='VM atmintis')
        notebook.add(rm_tab, text='RM atmintis')
        self.vm_memory_text = tk.Text(vm_tab, font=SMALL, wrap='none')
        self.vm_memory_text.pack(fill='both', expand=True)
        self.vm_memory_text.tag_configure('ic', background=CHANGED)

        bar = ttk.Frame(rm_tab)
        bar.pack(fill='x')
        ttk.Label(bar, text='Nuo bloko (hex):').pack(side='left')
        entry = ttk.Entry(bar, textvariable=self.rm_block, width=4)
        entry.pack(side='left', padx=4)
        entry.bind('<Return>', lambda e: self.refresh())
        ttk.Button(bar, text='Rodyti', command=self.refresh).pack(side='left')
        self.rm_memory_text = tk.Text(rm_tab, font=SMALL, wrap='none')
        self.rm_memory_text.pack(fill='both', expand=True)

    def build_console(self, parent):
        ttk.Label(parent, text='Ekranas').pack(anchor='w')
        self.console = tk.Text(parent, font=FONT, bg='black', fg='white', state='disabled', wrap='word')
        self.console.pack(fill='both', expand=True)
        self.console.tag_configure('os', foreground='#f0c674')
        self.console.tag_configure('input', foreground='#7cfc9a')
        row = ttk.Frame(parent)
        row.pack(fill='x', pady=4)
        self.prompt = ttk.Label(row, text='>', width=22)
        self.prompt.pack(side='left')
        self.entry = ttk.Entry(row, font=FONT)
        self.entry.pack(side='left', fill='x', expand=True)
        self.entry.bind('<Return>', self.enter_pressed)
        self.entry.focus_set()

    def step(self):
        self.machine.step()
        self.refresh()

    def run(self):
        if not self.machine.run():
            self.write('Programa vykdoma per ilgai - sustabdyta\n', 'os')
        self.refresh()

    def reset(self):
        self.machine = RealMachine(self.programs_folder)
        self.old_values = {}
        self.write('--- perkrauta ---\n', 'os')
        self.refresh()

    def write(self, text, tag=None):
        self.console.configure(state='normal')
        self.console.insert('end', text, tag)
        self.console.configure(state='disabled')
        self.console.see('end')

    def enter_pressed(self, event):
        line = self.entry.get().strip()
        self.entry.delete(0, 'end')
        if line == '':
            return
        self.write(line + '\n', 'input')
        words = line.split()
        command = words[0].upper()
        try:
            if command == 'HELP':
                self.write(HELP + '\n', 'os')
            elif command == 'DIR':
                self.write('Diske: ' + ' '.join(self.machine.disk.file_names()) + '\n', 'os')
            elif command == 'SET':
                self.set_register(words[1].upper(), words[2])
            elif command == 'MEM':
                self.set_memory(int(words[1], 16), words[2])
            else:
                self.machine.keyboard.lines.append(line)
                if self.machine.cpu.MODE == 1:
                    self.machine.step()
        except (ValueError, IndexError) as error:
            self.write('Klaida: %s\n' % error, 'os')
        self.refresh()

    def set_register(self, name, value):
        vm = self.machine.shown_vm()
        if vm is None or name not in ('R', 'IC', 'C'):
            raise ValueError('galima keisti R, IC, C, kai yra programa')
        if name == 'IC':
            self.machine.set_vm_register(vm, name, int(value, 16))
        else:
            self.machine.set_vm_register(vm, name, int(value))

    def set_memory(self, address, value):
        vm = self.machine.shown_vm()
        if vm is None or address > 0xFF:
            raise ValueError('nėra programos arba adresas ne 00..FF')
        real = self.machine.vm_real_address(vm, address)
        self.machine.memory.write_word(real, parse_value(value))

    def show(self, labels, key, values):
        for name in values:
            text = values[name]
            changed = (key + name) in self.old_values and self.old_values[key + name] != text
            labels[name].configure(text=text, bg=CHANGED if changed else 'white')
            self.old_values[key + name] = text

    def refresh(self):
        m = self.machine
        for kind, text in m.output:
            self.write(text if kind == 'screen' else text + '\n', None if kind == 'screen' else 'os')
        m.output.clear()
        self.action_label.configure(text=m.last_action)
        waiting = m.os.waiting_vm()
        self.prompt.configure(text=waiting.label() + ' laukia skaičiaus >' if waiting else 'OS >')

        cpu = m.cpu
        a = split_ptr(cpu.PTR)
        self.show(self.cpu_labels, 'cpu', {
            'R': str(cpu.R), 'IC': '%04X' % cpu.IC, 'C': 'ZF=%d SF=%d' % (cpu.zf(), cpu.sf()),
            'PTR': '%02X %02X %02X %02X' % (a[0], a[1], a[2], a[3]),
            'MODE': 'vartotojas' if cpu.MODE == 0 else 'supervizorius',
            'TI': str(cpu.TI), 'PI': str(cpu.PI), 'SI': str(cpu.SI), 'IOI': str(cpu.IOI),
            'CH1': str(m.channels.busy[1]), 'CH2': str(m.channels.busy[2]), 'CH3': str(m.channels.busy[3])})

        ch = m.channels
        keyboard = m.keyboard.lines[0] if m.keyboard.has_line() else '(tuščias)'
        self.devices_label.configure(text='Kanalų reg.: ST=%d SRC=%02X DT=%d DST=%02X\n'
                                          'Klaviatūros buferis: %s\n'
                                          'Diskas: %d programos' % (ch.ST, ch.SRC, ch.DT, ch.DST, keyboard,
                                                                     len(m.disk.file_names())))
        self.refresh_vm(m.shown_vm())
        self.refresh_rm_memory()

    def refresh_vm(self, vm):
        m = self.machine
        for widget in (self.page_text, self.vm_memory_text):
            widget.delete('1.0', 'end')
        if vm is None:
            self.show(self.vm_labels, 'vm', {'Programa': '-', 'Būsena': '-', 'R': '-', 'IC': '-', 'C': '-',
                                             'Komanda': '-'})
            return
        regs = m.vm_registers(vm)
        ic = regs['IC']
        try:
            command = word_to_text(m.memory.read_word(m.vm_real_address(vm, ic)))
        except Exception:
            command = '?'
        self.show(self.vm_labels, 'vm', {
            'Programa': vm.label(), 'Būsena': vm.state, 'R': str(regs['R']), 'IC': '%02X' % ic,
            'C': 'ZF=%d SF=%d' % (regs['C'] & 1, regs['C'] >> 1 & 1), 'Komanda': command})

        page = (ic // 16) % 16
        for i in range(16):
            address = page * 16 + i
            real = m.vm_real_address(vm, address)
            word = m.memory.read_word(real)
            self.page_text.insert('end', '%02X  %04X  %s  %s\n' % (address, real, word.hex().upper(),
                                                                word_to_string(word)))
            if address == ic:
                self.page_text.tag_add('ic', '%d.0' % (i + 1), '%d.end' % (i + 1))

        text = self.vm_memory_text
        text.insert('end', '    ' + ''.join('%7X' % i for i in range(16)) + '\n')
        for block in range(16):
            line = '%X0  ' % block
            for i in range(16):
                word = m.memory.read_word(m.vm_real_address(vm, block * 16 + i))
                line += '%7s' % word_to_string(word)[:6]
            text.insert('end', line + '\n')
            if block == ic // 16:
                column = 4 + (ic % 16) * 7
                text.tag_add('ic', '%d.%d' % (block + 2, column), '%d.%d' % (block + 2, column + 7))

    def refresh_rm_memory(self):
        try:
            start = int(self.rm_block.get(), 16)
        except ValueError:
            start = 0
        start = max(0, min(start, 0xC0 - 16))
        text = self.rm_memory_text
        text.delete('1.0', 'end')
        text.insert('end', '      ' + ''.join('%7X' % i for i in range(16)) + '\n')
        for block in range(start, start + 16):
            line = '%04X  ' % (block * 16)
            for i in range(16):
                line += '%7s' % word_to_string(self.machine.memory.read_word(block * 16 + i))[:6]
            text.insert('end', line + '\n')
