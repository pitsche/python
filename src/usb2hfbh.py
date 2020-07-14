import sys
import time
from time import sleep
# import spidev #raspi
import ftd2xx as ftd  # usb
import tkinter as tk
from tkinter import ttk
from tkinter import filedialog

# HW config Raspi
# bus = 0 # We only have SPI bus 0 available to us on the Pi
# device = 0 #Device is the chip select pin. Set to 0 or 1, depending on the connections
# spi = spidev.SpiDev() # Enable SPI
# spi.open(bus, device) # Open a connection
# spi.max_speed_hz = 100000
# spi.mode = 0b00 #[CPOL,CPHA]

# HW config USB
FTDI_TIMEOUT = 1000  # Timeout for D2XX read/write (msec)
OPS = 0x1B  # Bit mask for CS, SPI clock and data out

# FTDI Command Processor for MPSSE (FTDI AN-108)
CMD_OUT = 0x11  # Clock Data Bytes Out on -ve clock edge MSB first (no read)
CMD_IN = 0x22  # Clock Data Bits In on +ve clock edge MSB first (no write)
CMD_INOUT = 0x31  # out on -ve edge, in on +ve edge

# Other Constants
STD = (2 << 4)
AUX = (1 << 4)
PORT_1 = 1
S_PORT = 2
BUS_CTRL = 3
S_USR_START = 0  # 0xB0

# Set mode (bitbang / MPSSE)
def set_bitmode(d, bits, mode):
    return d.setBitMode(bits, mode)


# Open device for read/write
def ft_openEx():
    d = ftd.openEx('')
    d.setTimeouts(FTDI_TIMEOUT, FTDI_TIMEOUT)
    return d


# Set SPI clock rate
def set_spi_clock(d, hz):
    div = int((12000000 / (hz * 2)) - 1)  # Set SPI clock
    ft_write(d, (0x86, div % 256, div // 256))


# Read byte data into list of integers
def ft_read(d, nbytes):
    s = d.read(nbytes)
    return [ord(c) for c in s] if type(s) is str else list(s)


# Write list of integers as byte data
def ft_write(d: object, data: object) -> object:
    s = str(bytearray(data)) if sys.version_info < (3,) else bytes(data)
    return d.write(s)


# Write MPSSE command with word-value argument
def ft_write_cmd_bytes(d, cmd, data):
    n = len(data) - 1
    ft_write(d, [cmd, n % 256, n // 256] + list(data))

# Activate CS0_N
def activate_CS0_n():
    ft_write(dev, (0x80, 0x10, OPS))

# Activate CS1_N
def activate_CS1_n():
    ft_write(dev, (0x80, 0x08, OPS))

# Deactivate CSx_N
def reset_CSx_n():
    ft_write(dev, (0x80, 0x18, OPS))

devList = ftd.createDeviceInfoList()
if devList < 1:
    print("no FTDI Device installed")
else:
    for i in range(devList):
        print(ftd.getDeviceInfoDetail(i))
    dev = ft_openEx()
    if dev:
        print("FTDI device opened")
        set_bitmode(dev, 0x0, 0x00)  # Reset Controller
        set_bitmode(dev, 0x0, 0x02)  # Enable MPSSE mode
        set_spi_clock(dev, 10_000_000)  # Set SPI clock
        ft_write(dev, (0x80, 0x18, OPS))  # Set outputs

LARGE_FONT = ("Verdana", 12)


class MainWindow(tk.Tk):

    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        tk.Tk.wm_title(self, "HFBH Main 5002-8335 Test ")

        # Top Menu
        btn_menu1 = ttk.Button(self, text="MainTest", command=lambda: self.show_frame(MainTest))
        btn_menu2 = ttk.Button(self, text="OneWire", command=lambda: self.show_frame(OneWire))
        btn_menu3 = ttk.Button(self, text="FwDownload", command=lambda: self.show_frame(FwDownload))
        btn_menu1.grid(column=0, row=0, sticky=tk.EW)
        btn_menu2.grid(column=1, row=0, sticky=tk.EW)
        btn_menu3.grid(column=2, row=0, sticky=tk.EW)

        container = ttk.Frame(self, padding="3 3 12 12")
        container.grid(column=0, row=2, columnspan=3, sticky=tk.NSEW)

        self.frames = {}

        for F in (MainTest, OneWire, FwDownload):
            frame = F(container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame(MainTest)

    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()


class FwDownload(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        self.fileName = tk.StringVar()
        self.erase_stat = tk.StringVar()
        self.download_stat = tk.StringVar()
        self.reboot_stat = tk.StringVar()

        def readRbf():
            try:
                self.fileName.set(filedialog.askopenfilename())
                self.erase_stat.set("")
                self.download_stat.set("")
                self.reboot_stat.set("")
            except:
                print('fail at openFile')



        def download():
            try:
                self.erase_stat.set("Erase:")
                self.download_stat.set("")
                self.reboot_stat.set("")
                activate_CS1_n()
                ft_write_cmd_bytes(dev, CMD_OUT, [0, 0x00, 0])  # one zero write for sync
                ft_write_cmd_bytes(dev, CMD_OUT, [16, 0xFF, STD])  # Erase Sequence 1
                ft_write_cmd_bytes(dev, CMD_OUT, [16, 0xDA, STD])  # Erase Sequence 2
                ft_write_cmd_bytes(dev, CMD_OUT, [16, 0x91, STD])  # Erase Sequence 3
                ft_write_cmd_bytes(dev, CMD_OUT, [16, 0x20, STD])  # Erase Sequence 4
                ft_write_cmd_bytes(dev, CMD_OUT, [16, 0xC0, STD])  # Erase Sequence 5
                ft_write_cmd_bytes(dev, CMD_OUT, [16, 0x87, STD])  # Erase Sequence 6
                ft_write_cmd_bytes(dev, CMD_OUT, [16, 0xAA, STD])  # Erase Sequence 7
                timeout = 5 # seconds
                timeout_start = time.time()
                while time.time() < timeout_start + timeout:
                    ft_write_cmd_bytes(dev, CMD_INOUT, [16, 0x00, STD + (1 << 0)])  # sAdr16 Erase Request
                    rx = ft_read(dev, 3)
                    if rx[1] & 1 << 7: # erase done?
                        self.erase_stat.set("Erase:  done")
                        break
                rptfile=self.fileName.get()
                self.download_stat.set("Download:")
                with open(rptfile, 'rb') as in_file:
                    while True:
                        byte = in_file.read(2)
                        if len(byte) == 0:
                            break
                        ft_write_cmd_bytes(dev, CMD_OUT, [27, byte[0], byte[1]])  # Firmware Download
                timeout_start = time.time()
                while time.time() < timeout_start + timeout:
                    ft_write_cmd_bytes(dev, CMD_INOUT, [16, 0x00, 1 << 3])  # Download Data End
                    rx = ft_read(dev, 3)
                    if rx[1] & 1 << 6: # Download done?
                        self.download_stat.set("Download:  done")
                        break
                self.reboot_stat.set("Reboot:")
                ft_write_cmd_bytes(dev, CMD_OUT, [16, 0x91, 0])  # Reboot Sequence 1
                ft_write_cmd_bytes(dev, CMD_OUT, [16, 0x20, 0])  # Reboot Sequence 2
                ft_write_cmd_bytes(dev, CMD_OUT, [16, 0xC0, 0])  # Reboot Sequence 3
                ft_write_cmd_bytes(dev, CMD_OUT, [16, 0x87, 0])  # Reboot Sequence 4
                ft_write_cmd_bytes(dev, CMD_OUT, [16, 0xAA, 0])  # Reboot Sequence 5
                ft_write_cmd_bytes(dev, CMD_OUT, [16, 0xF1, 0])  # Reboot Sequence 6
                ft_write_cmd_bytes(dev, CMD_OUT, [16, 0x60, 0])  # Reboot Sequence 7
                ft_write_cmd_bytes(dev, CMD_OUT, [16, 0x00, 1 << 1])  # Reboot !
                reset_CSx_n()
                self.reboot_stat.set("Reboot:  done")
            except:
                print('fail at download')

        self.lbl_file = ttk.Label(self, text="File: ", font=LARGE_FONT)
        self.ent_filename = ttk.Entry(self, width=40, textvariable=self.fileName)
        self.ent_filename.delete(0, tk.END)
        self.btn_browse = ttk.Button(self, text="browse", command=readRbf)
        self.btn_download = ttk.Button(self, text="download", command=download)
        self.lbl_erase = ttk.Label(self, textvariable=self.erase_stat)
        self.lbl_download = ttk.Label(self, textvariable=self.download_stat)
        self.lbl_reboot = ttk.Label(self, textvariable=self.reboot_stat)

# LayOut

        self.lbl_file.grid(column=0, row=1, sticky=tk.W)
        self.ent_filename.grid(column=1, row=1, sticky=tk.W)
        self.btn_browse.grid(column=2, row=1, sticky=tk.W)
        self.btn_download.grid(column=2, row=2, sticky=tk.W)
        self.lbl_erase.grid(column=0, row=2, sticky=tk.W)
        self.lbl_download.grid(column=0, row=3, sticky=tk.W)
        self.lbl_reboot.grid(column=0, row=4, sticky=tk.W)

        for child in self.winfo_children(): child.grid_configure(padx=5, pady=5)


class MainTest(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        style = ttk.Style()
        style.configure("Red.TLabel", foreground ="white", background="red")
        style.configure("Green.TLabel", foreground ="white", background="green")
        self.controller = controller
        self.analog0 = tk.StringVar()
        self.analog1 = tk.StringVar()
        self.analog2 = tk.StringVar()
        self.analog3 = tk.StringVar()

        self.lbl_pageName = ttk.Label(self, text="Inputs: ", font=LARGE_FONT)

        def updateInputs():
            try:
                activate_CS0_n()
                ft_write_cmd_bytes(dev, CMD_OUT, [0,64])  # initial address write only
                ft_write_cmd_bytes(dev, CMD_OUT, [0,65])  # second address write only
                ft_write_cmd_bytes(dev, CMD_INOUT, [0,66])  # first react on addresses
                ft_write_cmd_bytes(dev, CMD_INOUT, [0,67])
                ft_write_cmd_bytes(dev, CMD_INOUT, [0,68])
                ft_write_cmd_bytes(dev, CMD_INOUT, [0,0])  # read last two reacts
                ft_write_cmd_bytes(dev, CMD_INOUT, [0,0])  # read last two reacts
                reset_CSx_n()
                rx = ft_read(dev, 10)
                an0 = rx[0] * (2 ** 8) + rx[1]  # generate integer range 0 to 2**16
                an1 = rx[2] * (2 ** 8) + rx[3]  # generate integer range 0 to 2**16
                an2 = rx[4] * (2 ** 8) + rx[5]  # generate integer range 0 to 2**16
                an3 = rx[6] * (2 ** 8) + rx[7]  # generate integer range 0 to 2**16
                if rx[9] & 1<<2: # bit2 test
                    self.lbl_CHA.configure(style="Red.TLabel")
                else:
                    self.lbl_CHA.configure(style="Green.TLabel")
                self.analog0.set(an0)
                self.analog1.set(an1)
                self.analog2.set(an2)
                self.analog3.set(an3)
                self.after(500, updateInputs)
            except:
                self.after(500, updateInputs)
                print('fail at update ports')

        self.lbl_AN0Rx = ttk.Label(self, text="An0:")
        self.lbl_AN0Var = ttk.Label(self, textvariable=self.analog0)
        self.lbl_AN1Rx = ttk.Label(self, text="An1:")
        self.lbl_AN1Var = ttk.Label(self, textvariable=self.analog1)
        self.lbl_AN2Rx = ttk.Label(self, text="An2:")
        self.lbl_AN2Var = ttk.Label(self, textvariable=self.analog2)
        self.lbl_AN3Rx = ttk.Label(self, text="An3:")
        self.lbl_AN3Var = ttk.Label(self, textvariable=self.analog3)
        self.lbl_GPIO = ttk.Label(self, text="Encoder:")
        self.lbl_CHA = ttk.Label(self, text="CHA")

        # LayOut

        self.lbl_pageName.grid(column=1, row=1, sticky=tk.W)
        self.lbl_AN0Rx.grid(column=1, row=2, sticky=tk.EW)
        self.lbl_AN0Var.grid(column=2, row=2, columnspan=3, sticky=tk.EW)
        self.lbl_AN1Rx.grid(column=1, row=3, sticky=tk.EW)
        self.lbl_AN1Var.grid(column=2, row=3, columnspan=3, sticky=tk.EW)
        self.lbl_AN2Rx.grid(column=1, row=4, sticky=tk.EW)
        self.lbl_AN2Var.grid(column=2, row=4, columnspan=3, sticky=tk.EW)
        self.lbl_AN3Rx.grid(column=1, row=5, sticky=tk.EW)
        self.lbl_AN3Var.grid(column=2, row=5, columnspan=3, sticky=tk.EW)
        self.lbl_GPIO.grid(column=1, row=6, sticky=tk.EW)
        self.lbl_CHA.grid(column=2, row=6, columnspan=3, sticky=tk.EW)

        for child in self.winfo_children(): child.grid_configure(padx=5, pady=5)

        self.after(500, updateInputs)


class OneWire(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        self.slave = tk.IntVar()
        self.startAddr = tk.IntVar()
        self.numWords = tk.IntVar()
        self.memField = tk.StringVar()

        def readMem():
            try:
                slv = self.slave.get()
                bsat_pwr = self.controller.bsat_pwr.get()
                cByte = (bsat_pwr << 7) + (slv << 4) + S_PORT
                activate_CS0_n()
                ft_write_cmd_bytes(dev, CMD_OUT, [0,0,0, cByte, 0, (S_USR_START + self.startAddr.get()), 0, 0])  # initial address
                mem = ""
                for i in range(0, self.numWords.get()):
                    ft_write_cmd_bytes(dev, CMD_INOUT,[0,0,0, cByte, 0, (S_USR_START + self.startAddr.get() + i + 1), 0, 0])  # address first read
                    rx = ft_read(dev, 8)
                    word = f"{(rx[6] * (2 ** 8) + rx[7]):0{4}X} "  # convert to '01C3 '
                    mem += word  # add to string
                reset_CSx_n()
                self.memField.set(mem)
            except:
                print('fail at readMem')

        def writeMem():
            try:
                slv = self.slave.get()
                bsat_pwr = self.controller.bsat_pwr.get()
                cByte = (bsat_pwr << 7) + (slv << 4) + WR + S_PORT
                mem = self.memField.get().split()
                activate_CS0_n()
                for i in range(len(mem)):
                    word_int = int(mem[i], 16)
                    hb = word_int // 256  # floor division
                    lb = word_int % 256  # modulus
                    ft_write_cmd_bytes(dev, CMD_OUT, [0,0,0, cByte, 0, (S_USR_START + self.startAddr.get() + i), hb, lb])
                reset_CSx_n()
            except:
                print('fail at writeMem')

        lbl_pageName = ttk.Label(self, text="S-Ports Slave: ", font=LARGE_FONT)
        ent_slave = ttk.Entry(self, width=2, textvariable=self.slave)
        ent_slave.delete(0, tk.END)
        ent_slave.insert(0, "0")  # default
        lbl_text = ttk.Label(self, text="User Memory:")
        lbl_startAddr = ttk.Label(self, text="Start Address: ")
        ent_startAddr = ttk.Entry(self, width=4, textvariable=self.startAddr)
        lbl_numWords = ttk.Label(self, text="Number of Words: ")
        ent_numWords = ttk.Entry(self, width=4, textvariable=self.numWords)
        btn_read = ttk.Button(self, text="Read", command=readMem)
        btn_write = ttk.Button(self, text="Write", command=writeMem)
        ent_memField = ttk.Entry(self, width=40, textvariable=self.memField)
        ent_memField.delete(0, tk.END)

        # LayOut

        lbl_pageName.grid(column=1, row=1, sticky=tk.W)
        ent_slave.grid(column=2, row=1, sticky=tk.W)
        lbl_text.grid(column=1, row=2, sticky=tk.W)
        lbl_startAddr.grid(column=2, row=2, sticky=tk.W)
        ent_startAddr.grid(column=3, row=2, sticky=tk.W)
        lbl_numWords.grid(column=4, row=2, sticky=tk.W)
        ent_numWords.grid(column=5, row=2, sticky=tk.W)
        btn_read.grid(column=1, row=3, sticky=tk.W)
        btn_write.grid(column=2, row=3, sticky=tk.W)
        ent_memField.grid(column=1, row=4, columnspan=5, sticky=tk.EW)

        for child in self.winfo_children():
            child.grid_configure(padx=5, pady=5)


app = MainWindow()
app.mainloop()
