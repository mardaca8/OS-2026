import random

from cpu import CPU, SAVE_AREA, translate
from devices import HardDisk, Keyboard, Screen, ChannelDevice
from memory import Memory
from supervisor import Supervisor, RUNNING


class RealMachine:
    def __init__(self, programs_folder):
        self.random = random.Random()
        self.output = []
        self.last_action = ''
        self.memory = Memory(0x0C00)
        self.disk = HardDisk()
        self.keyboard = Keyboard()
        self.screen = Screen(self.output)
        self.cpu = CPU(self.memory)
        self.channels = ChannelDevice(self.cpu, self.memory, self.disk, self.keyboard, self.screen)
        self.cpu.channels = self.channels
        self.os = Supervisor(self)
        count = self.disk.load_folder(programs_folder)
        self.say('Į diską įrašyta programų: %d. Įveskite RUN <vardas>.' % count)

    def say(self, text):
        self.output.append(('os', text))

    def step(self):
        if self.cpu.MODE == 0:
            self.last_action = 'VM %s  %s' % (self.os.current.label(), self.cpu.user_step())
        else:
            self.last_action = 'OS  ' + self.os.step()

    def is_idle(self):
        return self.cpu.MODE == 1 and self.os.is_idle()

    def run(self, max_steps=100000):
        for i in range(max_steps):
            if self.is_idle():
                return True
            self.step()
        return False

    def shown_vm(self):
        if self.os.current is not None:
            return self.os.current
        if self.os.processes:
            return self.os.processes[-1]
        return None

    def vm_registers(self, vm):
        if vm is self.os.current and vm.state == RUNNING:
            if self.cpu.MODE == 0:
                return {'R': self.cpu.R, 'IC': self.cpu.IC, 'C': self.cpu.C, 'PTR': self.cpu.PTR}
            return {'R': self.memory.read_int(SAVE_AREA), 'IC': self.memory.read_uint(SAVE_AREA + 1),
                    'C': self.memory.read_uint(SAVE_AREA + 2), 'PTR': self.memory.read_uint(SAVE_AREA + 3)}
        return {'R': vm.R, 'IC': vm.IC, 'C': vm.C, 'PTR': vm.PTR}

    def set_vm_register(self, vm, name, value):
        names = ['R', 'IC', 'C']
        if vm is self.os.current and vm.state == RUNNING:
            if self.cpu.MODE == 0:
                setattr(self.cpu, name, value)
            else:
                self.memory.write_int(SAVE_AREA + names.index(name), value)
        else:
            setattr(vm, name, value)

    def vm_real_address(self, vm, address):
        return translate(self.memory, self.vm_registers(vm)['PTR'], address)
