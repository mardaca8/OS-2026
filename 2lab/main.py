import os
import tkinter as tk

from gui import EmulatorApp

folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'programos')
root = tk.Tk()
EmulatorApp(root, folder)
root.mainloop()
