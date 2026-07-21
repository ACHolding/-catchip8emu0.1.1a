#!/usr/bin/env python3
# ac's chip 8 emu 0.1
# Fixed: buttons and menustrip now work.
# Opens blank with no ROM loaded.
# Set FILES = False if you want ROM loading turned off.

import os
import random
import tkinter as tk
from tkinter import filedialog, messagebox


WINDOW_TITLE = "ac's chip 8 emu 0.1"

# True  = Load ROM works
# False = Load ROM is disabled by logic, but buttons/menus still respond
FILES = True

SUBTITLE = f"FILES = {'ON' if FILES else 'OFF'}   BLANK START   NO ROM"

SCALE = 8
CYCLES_PER_FRAME = 10

# Blue hue theme
BG = "#001133"
PANEL = "#002255"
TEXT = "#66ccff"

BUTTON_BG = "black"
BUTTON_FG = "#66ccff"
BUTTON_DISABLED_FG = "#335577"

CANVAS_BG = "#000814"
PIXEL_ON = "#33aaff"
PIXEL_OFF = "#001122"

# Physical keyboard -> Chip-8 hex key
# Chip-8 keypad:
# 1 2 3 C
# 4 5 6 D
# 7 8 9 E
# A 0 B F
#
# Mapped to:
# 1 2 3 4
# Q W E R
# A S D F
# Z X C V
KEY_MAP = {
    "1": 0x1,
    "2": 0x2,
    "3": 0x3,
    "4": 0xC,

    "q": 0x4,
    "w": 0x5,
    "e": 0x6,
    "r": 0xD,

    "a": 0x7,
    "s": 0x8,
    "d": 0x9,
    "f": 0xE,

    "z": 0xA,
    "x": 0x0,
    "c": 0xB,
    "v": 0xF,
}

FONT_SET = [
    0xF0, 0x90, 0x90, 0x90, 0xF0,  # 0
    0x20, 0x60, 0x20, 0x20, 0x70,  # 1
    0xF0, 0x10, 0xF0, 0x80, 0xF0,  # 2
    0xF0, 0x10, 0xF0, 0x10, 0xF0,  # 3
    0x90, 0x90, 0xF0, 0x10, 0x10,  # 4
    0xF0, 0x80, 0xF0, 0x10, 0xF0,  # 5
    0xF0, 0x80, 0xF0, 0x90, 0xF0,  # 6
    0xF0, 0x10, 0x20, 0x40, 0x40,  # 7
    0xF0, 0x90, 0xF0, 0x90, 0xF0,  # 8
    0xF0, 0x90, 0xF0, 0x10, 0xF0,  # 9
    0xF0, 0x90, 0xF0, 0x90, 0x90,  # A
    0xE0, 0x90, 0xE0, 0x90, 0xE0,  # B
    0xF0, 0x80, 0x80, 0x80, 0xF0,  # C
    0xE0, 0x90, 0x90, 0x90, 0xE0,  # D
    0xF0, 0x80, 0xF0, 0x80, 0xF0,  # E
    0xF0, 0x80, 0xF0, 0x80, 0x80,  # F
]


class Chip8:
    def __init__(self):
        self.reset()

    def reset(self):
        self.ram = bytearray(4096)

        # Font set lives at 0x050.
        for i, b in enumerate(FONT_SET):
            self.ram[0x50 + i] = b

        self.pc = 0x200
        self.I = 0
        self.stack = []

        self.V = [0] * 16

        self.delay_timer = 0
        self.sound_timer = 0

        self.display = [[False] * 64 for _ in range(32)]
        self.keys = [False] * 16

        self.waiting_for_key = False
        self.pending_key = None

        self.halted = True
        self.draw_flag = True

    def load_rom_bytes(self, data):
        self.reset()

        if len(data) > 0x1000 - 0x200:
            data = data[:0x1000 - 0x200]

        self.ram[0x200:0x200 + len(data)] = data
        self.pc = 0x200
        self.halted = False

    def key_down(self, key):
        key &= 0xF

        if not self.keys[key] and self.waiting_for_key:
            self.pending_key = key

        self.keys[key] = True

    def key_up(self, key):
        self.keys[key & 0xF] = False

    def tick_timers(self):
        if self.delay_timer > 0:
            self.delay_timer -= 1

        if self.sound_timer > 0:
            self.sound_timer -= 1

    def skip(self):
        self.pc = (self.pc + 2) & 0xFFF

    def cycle(self):
        if self.halted:
            return

        if self.pc > 0xFFE:
            self.halted = True
            return

        old_pc = self.pc
        opcode = (self.ram[self.pc] << 8) | self.ram[self.pc + 1]
        self.pc = (self.pc + 2) & 0xFFF

        self.execute(opcode, old_pc)

    def execute(self, op, old_pc):
        nnn = op & 0x0FFF
        x = (op >> 8) & 0x0F
        y = (op >> 4) & 0x0F
        n = op & 0x000F
        nn = op & 0x00FF

        # 00E0 - Clear display
        if op == 0x00E0:
            self.display = [[False] * 64 for _ in range(32)]
            self.draw_flag = True

        # 00EE - Return from subroutine
        elif op == 0x00EE:
            if self.stack:
                self.pc = self.stack.pop()
            else:
                self.halted = True

        # 0NNN - Machine code routine, ignored
        elif (op & 0xF000) == 0x0000:
            pass

        # 1NNN - Jump
        elif (op & 0xF000) == 0x1000:
            if nnn == old_pc:
                self.halted = True
            else:
                self.pc = nnn

        # 2NNN - Call subroutine
        elif (op & 0xF000) == 0x2000:
            self.stack.append(self.pc)
            self.pc = nnn

        # 3XKK - Skip if VX == KK
        elif (op & 0xF000) == 0x3000:
            if self.V[x] == nn:
                self.skip()

        # 4XKK - Skip if VX != KK
        elif (op & 0xF000) == 0x4000:
            if self.V[x] != nn:
                self.skip()

        # 5XY0 - Skip if VX == VY
        elif (op & 0xF000) == 0x5000:
            if n == 0x0:
                if self.V[x] == self.V[y]:
                    self.skip()
            else:
                self.halted = True

        # 6XKK - Set VX = KK
        elif (op & 0xF000) == 0x6000:
            self.V[x] = nn

        # 7XKK - Add KK to VX
        elif (op & 0xF000) == 0x7000:
            self.V[x] = (self.V[x] + nn) & 0xFF

        # 8XY_ - ALU opcodes
        elif (op & 0xF000) == 0x8000:
            if n == 0x0:
                # 8XY0 - VX = VY
                self.V[x] = self.V[y] & 0xFF

            elif n == 0x1:
                # 8XY1 - VX |= VY
                self.V[x] = (self.V[x] | self.V[y]) & 0xFF

            elif n == 0x2:
                # 8XY2 - VX &= VY
                self.V[x] = (self.V[x] & self.V[y]) & 0xFF

            elif n == 0x3:
                # 8XY3 - VX ^= VY
                self.V[x] = (self.V[x] ^ self.V[y]) & 0xFF

            elif n == 0x4:
                # 8XY4 - VX += VY, VF = carry
                total = self.V[x] + self.V[y]
                self.V[x] = total & 0xFF
                self.V[0xF] = 1 if total > 0xFF else 0

            elif n == 0x5:
                # 8XY5 - VX -= VY, VF = borrow
                vx = self.V[x]
                vy = self.V[y]
                self.V[x] = (vx - vy) & 0xFF
                self.V[0xF] = 1 if vx >= vy else 0

            elif n == 0x6:
                # 8XY6 - VX >>= 1, VF = shifted bit
                vx = self.V[x]
                self.V[0xF] = vx & 0x1
                self.V[x] = (vx >> 1) & 0xFF

            elif n == 0x7:
                # 8XY7 - VX = VY - VX, VF = borrow
                vx = self.V[x]
                vy = self.V[y]
                self.V[x] = (vy - vx) & 0xFF
                self.V[0xF] = 1 if vy >= vx else 0

            elif n == 0xE:
                # 8XYE - VX <<= 1, VF = shifted bit
                vx = self.V[x]
                self.V[0xF] = (vx >> 7) & 0x1
                self.V[x] = (vx << 1) & 0xFF

            else:
                self.halted = True

        # 9XY0 - Skip if VX != VY
        elif (op & 0xF000) == 0x9000:
            if n == 0x0:
                if self.V[x] != self.V[y]:
                    self.skip()
            else:
                self.halted = True

        # ANNN - Set I = NNN
        elif (op & 0xF000) == 0xA000:
            self.I = nnn & 0xFFF

        # BNNN - Jump to NNN + V0
        elif (op & 0xF000) == 0xB000:
            self.pc = (nnn + self.V[0]) & 0xFFF

        # CXKK - VX = random & KK
        elif (op & 0xF000) == 0xC000:
            self.V[x] = random.randrange(256) & nn

        # DXYN - Draw sprite
        elif (op & 0xF000) == 0xD000:
            vx = self.V[x]
            vy = self.V[y]

            # Some docs treat DXY0 as 16 pixels high.
            height = n if n != 0 else 16

            collision = False

            for row in range(height):
                sprite_byte = self.ram[(self.I + row) & 0xFFF]
                py = (vy + row) % 32

                for col in range(8):
                    if sprite_byte & (0x80 >> col):
                        px = (vx + col) % 64

                        if self.display[py][px]:
                            collision = True

                        self.display[py][px] = not self.display[py][px]

            self.V[0xF] = 1 if collision else 0
            self.draw_flag = True

        # EX__ - Key opcodes
        elif (op & 0xF000) == 0xE000:
            if nn == 0x9E:
                # EX9E - Skip if key VX pressed
                if self.keys[self.V[x] & 0xF]:
                    self.skip()

            elif nn == 0xA1:
                # EXA1 - Skip if key VX not pressed
                if not self.keys[self.V[x] & 0xF]:
                    self.skip()

            else:
                self.halted = True

        # FX__ - Misc opcodes
        elif (op & 0xF000) == 0xF000:
            fx = op & 0xF0FF

            if fx == 0xF007:
                # FX07 - VX = delay_timer
                self.V[x] = self.delay_timer & 0xFF

            elif fx == 0xF00A:
                # FX0A - Wait for key press
                if self.waiting_for_key:
                    if self.pending_key is not None:
                        self.V[x] = self.pending_key & 0xF
                        self.pending_key = None
                        self.waiting_for_key = False
                    else:
                        self.pc = old_pc
                else:
                    held = next((i for i, pressed in enumerate(self.keys) if pressed), None)

                    if held is not None:
                        self.V[x] = held & 0xF
                    else:
                        self.waiting_for_key = True
                        self.pc = old_pc

            elif fx == 0xF015:
                # FX15 - delay_timer = VX
                self.delay_timer = self.V[x] & 0xFF

            elif fx == 0xF018:
                # FX18 - sound_timer = VX
                self.sound_timer = self.V[x] & 0xFF

            elif fx == 0xF01E:
                # FX1E - I += VX
                self.I = (self.I + self.V[x]) & 0xFFF

            elif fx == 0xF029:
                # FX29 - I = font sprite for digit VX
                self.I = 0x50 + ((self.V[x] & 0xF) * 5)

            elif fx == 0xF033:
                # FX33 - Store BCD of VX at I, I+1, I+2
                value = self.V[x] & 0xFF
                self.ram[self.I & 0xFFF] = value // 100
                self.ram[(self.I + 1) & 0xFFF] = (value // 10) % 10
                self.ram[(self.I + 2) & 0xFFF] = value % 10

            elif fx == 0xF055:
                # FX55 - Store V0..VX starting at I
                # Modern behavior: I unchanged.
                base = self.I
                for i in range(x + 1):
                    self.ram[(base + i) & 0xFFF] = self.V[i] & 0xFF

            elif fx == 0xF065:
                # FX65 - Load V0..VX starting at I
                # Modern behavior: I unchanged.
                base = self.I
                for i in range(x + 1):
                    self.V[i] = self.ram[(base + i) & 0xFFF] & 0xFF

            else:
                self.halted = True

        else:
            self.halted = True


class App:
    def __init__(self, root):
        self.root = root

        # No ROM loaded on startup.
        self.current_rom = None
        self.current_file = "None"
        self.has_rom = False

        self.chip = Chip8()
        self.chip.reset()
        self.chip.halted = True

        self.running = False

        self.root.title(WINDOW_TITLE)
        self.root.configure(bg=BG)
        self.root.resizable(False, False)

        self.build_menu()
        self.build_toolbar()
        self.build_screen()
        self.build_keypad()
        self.build_help_label()
        self.build_status_bar()

        # Keyboard bindings
        self.root.bind("<KeyPress>", self.on_key_press)
        self.root.bind("<KeyRelease>", self.on_key_release)
        self.root.bind("<FocusOut>", self.release_all_keys)

        # Close window safely
        self.root.protocol("WM_DELETE_WINDOW", self.exit_app)

        self.root.after(100, self.root.focus_set)

        # Start GUI/emulation loop
        self.loop()

    def build_menu(self):
        menubar = tk.Menu(
            self.root,
            bg=PANEL,
            fg=TEXT,
            activebackground=BUTTON_BG,
            activeforeground=TEXT,
            bd=1,
            relief=tk.RAISED,
        )

        # File menu
        filemenu = tk.Menu(
            menubar,
            tearoff=0,
            bg=PANEL,
            fg=TEXT,
            activebackground=BUTTON_BG,
            activeforeground=TEXT,
        )

        filemenu.add_command(
            label="Load ROM...",
            command=self.load_rom,
            accelerator="Ctrl+O",
        )

        filemenu.add_separator()

        filemenu.add_command(
            label="Exit",
            command=self.exit_app,
            accelerator="Alt+F4",
        )

        menubar.add_cascade(label="File", menu=filemenu)

        # Emulation menu
        emumenu = tk.Menu(
            menubar,
            tearoff=0,
            bg=PANEL,
            fg=TEXT,
            activebackground=BUTTON_BG,
            activeforeground=TEXT,
        )

        emumenu.add_command(
            label="Play Game",
            command=self.play_game,
            accelerator="F5",
        )

        emumenu.add_command(
            label="Pause",
            command=self.pause_game,
            accelerator="F6",
        )

        emumenu.add_separator()

        emumenu.add_command(
            label="Reset",
            command=self.reset,
            accelerator="F7",
        )

        emumenu.add_command(
            label="Step",
            command=self.step,
            accelerator="F8",
        )

        menubar.add_cascade(label="Emulation", menu=emumenu)

        # Help menu
        helpmenu = tk.Menu(
            menubar,
            tearoff=0,
            bg=PANEL,
            fg=TEXT,
            activebackground=BUTTON_BG,
            activeforeground=TEXT,
        )

        helpmenu.add_command(
            label="About",
            command=self.show_about,
        )

        menubar.add_cascade(label="Help", menu=helpmenu)

        self.root.config(menu=menubar)

        # Menu accelerator bindings
        self.root.bind_all("<Control-o>", lambda e: self.load_rom())
        self.root.bind_all("<Command-o>", lambda e: self.load_rom())

        self.root.bind_all("<F5>", lambda e: self.play_game())
        self.root.bind_all("<F6>", lambda e: self.pause_game())
        self.root.bind_all("<F7>", lambda e: self.reset())
        self.root.bind_all("<F8>", lambda e: self.step())

    def build_toolbar(self):
        toolbar = tk.Frame(self.root, bg=BG)
        toolbar.pack(side="top", fill="x", padx=6, pady=(6, 2))

        self.load_btn = self.make_button(toolbar, "Load ROM", self.load_rom, width=10)
        self.load_btn.grid(row=0, column=0, padx=2)

        self.play_btn = self.make_button(toolbar, "Play Game", self.play_game, width=10)
        self.play_btn.grid(row=0, column=1, padx=2)

        self.pause_btn = self.make_button(toolbar, "Pause", self.pause_game, width=8)
        self.pause_btn.grid(row=0, column=2, padx=2)

        self.reset_btn = self.make_button(toolbar, "Reset", self.reset, width=8)
        self.reset_btn.grid(row=0, column=3, padx=2)

        self.exit_btn = self.make_button(toolbar, "Exit", self.exit_app, width=6)
        self.exit_btn.grid(row=0, column=4, padx=2)

    def build_screen(self):
        screen_frame = tk.Frame(self.root, bg=BUTTON_BG, padx=4, pady=4)
        screen_frame.pack(side="top", padx=10, pady=(4, 6))

        self.canvas = tk.Canvas(
            screen_frame,
            width=64 * SCALE,
            height=32 * SCALE,
            bg=CANVAS_BG,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack()

        self.cells = []
        for y in range(32):
            row = []
            for x in range(64):
                rect = self.canvas.create_rectangle(
                    x * SCALE,
                    y * SCALE,
                    (x + 1) * SCALE,
                    (y + 1) * SCALE,
                    fill=PIXEL_OFF,
                    outline="",
                    width=0,
                )
                row.append(rect)
            self.cells.append(row)

    def build_keypad(self):
        keypad = tk.Frame(self.root, bg=BG)
        keypad.pack(side="top", pady=(0, 6))

        keypad_keys = [
            ("1", 0x1), ("2", 0x2), ("3", 0x3), ("C", 0xC),
            ("4", 0x4), ("5", 0x5), ("6", 0x6), ("D", 0xD),
            ("7", 0x7), ("8", 0x8), ("9", 0x9), ("E", 0xE),
            ("A", 0xA), ("0", 0x0), ("B", 0xB), ("F", 0xF),
        ]

        for i, (label, value) in enumerate(keypad_keys):
            btn = tk.Button(
                keypad,
                text=label,
                width=4,
                height=2,
                bg=BUTTON_BG,
                fg=BUTTON_FG,
                activebackground=BUTTON_BG,
                activeforeground=BUTTON_FG,
                disabledforeground=BUTTON_DISABLED_FG,
                font=("Courier", 11, "bold"),
                relief=tk.RAISED,
                bd=2,
            )
            btn.grid(row=i // 4, column=i % 4, padx=2, pady=2)

            btn.bind("<ButtonPress-1>", lambda e, v=value: self.chip.key_down(v))
            btn.bind("<ButtonRelease-1>", lambda e, v=value: self.chip.key_up(v))
            btn.bind("<Leave>", lambda e, v=value: self.chip.key_up(v))

    def build_help_label(self):
        tk.Label(
            self.root,
            text="Keyboard: 1 2 3 4 / Q W E R / A S D F / Z X C V",
            bg=BG,
            fg=TEXT,
            font=("Courier", 8, "bold"),
        ).pack(side="top", pady=(0, 8))

    def build_status_bar(self):
        self.status_var = tk.StringVar(value="")

        tk.Label(
            self.root,
            textvariable=self.status_var,
            bg=PANEL,
            fg=TEXT,
            font=("Courier", 9, "bold"),
            anchor="w",
            padx=6,
            pady=3,
        ).pack(side="bottom", fill="x")

    def make_button(self, parent, text, command, width=8):
        return tk.Button(
            parent,
            text=text,
            command=command,
            width=width,
            bg=BUTTON_BG,
            fg=BUTTON_FG,
            activebackground=BUTTON_BG,
            activeforeground=BUTTON_FG,
            disabledforeground=BUTTON_DISABLED_FG,
            font=("Courier", 10, "bold"),
            relief=tk.RAISED,
            bd=2,
        )

    def load_rom(self, event=None):
        if not FILES:
            messagebox.showinfo(
                parent=self.root,
                title="ROM Files OFF",
                message="ROM files are OFF.\n\nSet FILES = True in the code to enable Load ROM.",
            )
            return

        was_running = self.running
        self.running = False

        initial_dir = os.path.expanduser("~")

        filename = filedialog.askopenfilename(
            parent=self.root,
            title="Load CHIP-8 ROM",
            initialdir=initial_dir,
            filetypes=(
                ("CHIP-8 ROMs", "*.ch8 *.c8 *.rom *.bin"),
                ("All files", "*.*"),
            ),
        )

        if not filename:
            self.running = was_running
            return

        try:
            with open(filename, "rb") as f:
                data = f.read()
        except Exception as exc:
            messagebox.showerror(
                parent=self.root,
                title="Load Error",
                message=f"Could not load ROM:\n{exc}",
            )
            self.running = was_running
            return

        if not data:
            messagebox.showwarning(
                parent=self.root,
                title="Empty ROM",
                message="The selected file is empty.",
            )
            self.running = was_running
            return

        # Standard CHIP-8 ROM space is 0x200..0xFFF = 3584 bytes.
        if len(data) > 0xE00:
            messagebox.showwarning(
                parent=self.root,
                title="ROM Too Large",
                message=(
                    "Standard CHIP-8 ROM space is 3584 bytes.\n"
                    "The ROM will be truncated."
                ),
            )
            data = data[:0xE00]

        self.current_rom = data
        self.current_file = os.path.basename(filename)
        self.has_rom = True

        self.chip.load_rom_bytes(self.current_rom)
        self.running = True

    def play_game(self, event=None):
        # If no ROM is loaded, still allow the button/menu to respond.
        # It just runs in blank idle mode.
        if not self.has_rom:
            self.running = True
            self.chip.halted = False
            return

        if self.chip.halted:
            self.reset()
        else:
            self.running = True

    def pause_game(self, event=None):
        self.running = False

    def reset(self, event=None):
        if not self.has_rom:
            self.chip.reset()
            self.chip.halted = True
            self.running = False
            return

        self.chip.load_rom_bytes(self.current_rom)
        self.running = True

    def step(self, event=None):
        if not self.has_rom:
            return

        if self.chip.halted:
            return

        self.running = False
        self.chip.cycle()
        self.refresh_display()
        self.update_status()

    def exit_app(self, event=None):
        self.root.destroy()

    def show_about(self):
        messagebox.showinfo(
            parent=self.root,
            title="About",
            message=(
                "ac's chip 8 emu 0.1\n\n"
                "mGBA-style GUI\n"
                "Blank start\n"
                "No ROM loaded\n"
                "CHIP-8 engine present\n\n"
                "Blue hue theme\n"
                "Black buttons\n"
            ),
        )

    def on_key_press(self, event):
        key = KEY_MAP.get(event.keysym.lower())
        if key is not None:
            self.chip.key_down(key)
            return "break"

    def on_key_release(self, event):
        key = KEY_MAP.get(event.keysym.lower())
        if key is not None:
            self.chip.key_up(key)
            return "break"

    def release_all_keys(self, event=None):
        for key in range(16):
            self.chip.key_up(key)

    def refresh_display(self):
        if not self.chip.draw_flag:
            return

        disp = self.chip.display

        for y in range(32):
            for x in range(64):
                color = PIXEL_ON if disp[y][x] else PIXEL_OFF
                self.canvas.itemconfig(self.cells[y][x], fill=color)

        self.chip.draw_flag = False

    def update_status(self):
        c = self.chip

        if not self.has_rom:
            if self.running:
                state = "BLANK RUN"
            else:
                state = "BLANK"
        elif c.halted:
            state = "HALT"
        elif self.running:
            state = "RUN"
        else:
            state = "PAUSE"

        short_file = self.current_file if self.current_file else "None"
        if len(short_file) > 24:
            short_file = short_file[:21] + "..."

        self.status_var.set(
            f"STATE:{state} "
            f"FILE:{short_file} "
            f"PC:{c.pc:03X} "
            f"I:{c.I:03X} "
            f"V0:{c.V[0]:02X} "
            f"V1:{c.V[1]:02X} "
            f"V2:{c.V[2]:02X} "
            f"DT:{c.delay_timer} "
            f"ST:{c.sound_timer}"
        )

    def loop(self):
        if self.running and self.has_rom:
            for _ in range(CYCLES_PER_FRAME):
                self.chip.cycle()

                if self.chip.halted:
                    break

            if not self.chip.halted:
                self.chip.tick_timers()

        self.refresh_display()
        self.update_status()

        self.root.after(16, self.loop)


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
