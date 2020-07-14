import sys
from time import sleep
# import spidev #raspi
import ftd2xx as ftd  # usb
import tkinter as tk
from tkinter import ttk

# HW config Raspi
# bus = 0 # We only have SPI bus 0 available to us on the Pi
# device = 0 #Device is the chip select pin. Set to 0 or 1, depending on the connections
# spi = spidev.SpiDev() # Enable SPI
# spi.open(bus, device) # Open a connection
# spi.max_speed_hz = 100000
# spi.mode = 0b00 #[CPOL,CPHA]

# HW config USB
FTDI_TIMEOUT = 1000  # Timeout for D2XX read/write (msec)
OPS = 0x0B  # Bit mask for CS, SPI clock and data out

# FTDI Command Processor for MPSSE (FTDI AN-108)
CMD_OUT = 0x11  # Clock Data Bytes Out on -ve clock edge MSB first (no read)
CMD_INOUT = 0x31  # out on -ve edge, in on +ve edge

# Other Constants
WR = (1 << 3)
PORT_0 = 0
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
        ft_write(dev, (0x80, 0x08, OPS))  # Set outputs

LARGE_FONT = ("Verdana", 12)


class MainWindow(tk.Tk):

    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        tk.Tk.wm_title(self, "BSAT Interface")
        self.bsat_pwr = tk.IntVar(value=0)

        # Top Menu
        btn_menu1 = ttk.Button(self, text="Status", command=lambda: self.show_frame(Status))
        btn_menu2 = ttk.Button(self, text="Ports", command=lambda: self.show_frame(Ports))
        btn_menu3 = ttk.Button(self, text="S-Ports", command=lambda: self.show_frame(S_Ports))
        btn_pwr = ttk.Checkbutton(self, text="BSAT Power", variable=self.bsat_pwr)
        btn_menu1.grid(column=0, row=0, sticky=tk.EW)
        btn_menu2.grid(column=1, row=0, sticky=tk.EW)
        btn_menu3.grid(column=2, row=0, sticky=tk.EW)
        btn_pwr.grid(column=0, row=1, sticky=tk.EW)

        container = ttk.Frame(self, padding="3 3 12 12")
        container.grid(column=0, row=2, columnspan=3, sticky=tk.NSEW)

        self.frames = {}

        for F in (Status, Ports, S_Ports):
            frame = F(container, self)
            self.frames[F] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        self.show_frame(Status)

    def show_frame(self, cont):
        frame = self.frames[cont]
        frame.tkraise()


class Status(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        self.slave = tk.IntVar()
        self.boardType = tk.StringVar()
        self.boardNumber = tk.StringVar()
        self.scanResult = tk.StringVar()

        def enblSlave():
            try:
                slv = self.slave.get()
                bsat_pwr = self.controller.bsat_pwr.get()
                cByte = (bsat_pwr << 7) + (slv << 4) + WR + S_PORT
                ft_write(dev, (0x80, 0x00, OPS))  # clear CS0
                ft_write_cmd_bytes(dev, CMD_OUT, [0,0,0, cByte, 0, 0x11, 0, 0x00])  # set all bits 0 on S-Port address 0x11
                ft_write_cmd_bytes(dev, CMD_OUT, [0,0,0, cByte, 0, 0x11, 0, 0x08])  # NodeEnable
                ft_write_cmd_bytes(dev, CMD_OUT, [0,0,0, cByte, 0, 0x11, 0, 0x0C])  # IdSuccessful
                ft_write_cmd_bytes(dev, CMD_OUT, [0,0,0, cByte, 0, 0x11, 0, 0x0E])  # ScanDone
                ft_write(dev, (0x80, 0x08, OPS))  # set CS0
            except:
                print('fail at enable slave')

        def rescanBsat():
            try:
                slv = self.slave.get()
                bsat_pwr = self.controller.bsat_pwr.get()
                ft_write(dev, (0x80, 0x00, OPS))  # clear CS0
                cByte = (bsat_pwr << 7) + WR + BUS_CTRL
                ft_write_cmd_bytes(dev, CMD_OUT, [0, 0, 0, cByte, 0, 0, 0x00, 0x02])  # reset rescan bit (0)
                ft_write_cmd_bytes(dev, CMD_OUT, [0, 0, 0, cByte, 0, 0, 0xF0, 0x03])  # initialize rescan
                ft_write_cmd_bytes(dev, CMD_OUT, [0, 0, 0, cByte, 0, 0, 0x00, 0x02])  # reset rescan bit (0)
#                sleep(0.2) # wait till rescan is done
                cByte = (bsat_pwr << 7) + (slv << 4) + S_PORT
                ft_write_cmd_bytes(dev, CMD_OUT, [0,0,0, cByte, 0, 0x53, 0, 0])  # initial S-Port address 0x53
                mem = []
                brdType = ""
                brdNmbr = ""
                for i in range(16):  # read memory
                    ft_write_cmd_bytes(dev, CMD_INOUT, [0,0,0, cByte, 0, (0x53 + i + 1), 0, 0])  # address read to buffer
                    rx = ft_read(dev, 8)  #read buffer
                    mem.append(rx[6])
                    mem.append(rx[7])
                ft_write(dev, (0x80, 0x08, OPS))  # set CS0
                scanRes = f"{(rx[4] * (2 ** 8) + rx[5]):0{4}X} "  # convert to '01C3 '
                for x in range(0, 16):  # convert to string Board Type
                    if mem[x]:
                        brdType += chr(mem[x])
                for y in range(16, 32):  # convert to string Board Number
                    if mem[y]:
                        brdNmbr += chr(mem[y])
                self.boardType.set(brdType)
                self.boardNumber.set(brdNmbr)
                self.scanResult.set(f'Bsat Scan Result: 0x{scanRes}')
            except:
                print('fail at updateInfo')

        lbl_pageName = ttk.Label(self, text="Status Slave: ", font=LARGE_FONT)
        ent_slave = ttk.Entry(self, width=2, textvariable=self.slave)
        ent_slave.delete(0, tk.END)
        ent_slave.insert(0, "0")  # default
        btn_enblSlave = ttk.Button(self, text="Enable Slave", command=enblSlave)
        lbl_boardInfo = ttk.Label(self, text="Board Info: ")
        lbl_boardType = ttk.Label(self, textvariable=self.boardType)
        lbl_boardNumber = ttk.Label(self, textvariable=self.boardNumber)
        btn_rescan = ttk.Button(self, text="Rescan", command=rescanBsat)
        lbl_bsatScan = ttk.Label(self, textvariable=self.scanResult)

        # LayOut

        lbl_pageName.grid(column=1, row=1, sticky=tk.W)
        ent_slave.grid(column=2, row=1, sticky=tk.W)
        btn_enblSlave.grid(column=3, row=1, sticky=tk.EW)
        lbl_boardInfo.grid(column=1, row=4)
        lbl_boardType.grid(column=2, row=4, columnspan=2, sticky=tk.W)
        lbl_boardNumber.grid(column=2, row=5, columnspan=2, sticky=tk.W)
        btn_rescan.grid(column=1, row=6)
        lbl_bsatScan.grid(column=1, row=7)

        for child in self.winfo_children(): child.grid_configure(padx=5, pady=5)


class Ports(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        self.controller = controller
        self.slave = tk.IntVar()
        self.p0_rx = tk.StringVar()
        self.p0_tx = tk.StringVar()
        self.p0_upd = tk.BooleanVar()
        self.p1_rx = tk.StringVar()
        self.p1_tx = tk.StringVar()
        self.p1_upd = tk.BooleanVar()

        lbl_pageName = ttk.Label(self, text="Ports Slave: ", font=LARGE_FONT)
        ent_slave = ttk.Entry(self, width=2, textvariable=self.slave)
        ent_slave.delete(0, tk.END)
        ent_slave.insert(0, "0")  # default

        def updatePorts():
            try:
                tx_p0 = (int(self.p0_tx.get(), 2)).to_bytes(4, byteorder='big')
                tx_p1 = (int(self.p1_tx.get(), 2)).to_bytes(4, byteorder='big')
                slv = self.slave.get()
                bsat_pwr = self.controller.bsat_pwr.get()
                p0wr = self.p0_upd.get()  # ports to write?
                p1wr = self.p1_upd.get()
                ft_write(dev, (0x80, 0x00, OPS))  # clear CS0
                ft_write_cmd_bytes(dev, CMD_OUT,[0,0,0, (bsat_pwr << 7) + (slv << 4) + (p0wr << 3) + PORT_0, tx_p0[0], tx_p0[1], tx_p0[2], tx_p0[3]])  # initial address write only
                ft_write_cmd_bytes(dev, CMD_INOUT, [0,0,0, (bsat_pwr << 7) + (slv << 4) + (p1wr << 3) + PORT_1, tx_p1[0], tx_p1[1], tx_p1[2], tx_p1[3]])
                ft_write_cmd_bytes(dev, CMD_INOUT, [0,0,0, (bsat_pwr << 7) + (slv << 4) + PORT_1, 0, 0, 0, 0])  # read last
                ft_write(dev, (0x80, 0x08, OPS))  # set CS0
                rx = ft_read(dev, 16)
                self.p0_upd.set(False)  # only update once
                self.p1_upd.set(False)
                rx0_32 = rx[4] * (2 ** 24) + rx[5] * (2 ** 16) + rx[6] * (2 ** 8) + rx[7]  # generate integer range 0 to 2**32
                rx1_32 = rx[12] * (2 ** 24) + rx[13] * (2 ** 16) + rx[14] * (2 ** 8) + rx[15]
                self.p0_rx.set(f"{rx0_32:0{32}b}")  # format binary 32
                self.p1_rx.set(f"{rx1_32:0{32}b}")
                self.after(500, updatePorts)
            except:
                self.after(500, updatePorts)
                print('fail at update ports')

        def updateP0():
            self.p0_upd.set(True)
            updatePorts()

        def updateP1():
            self.p1_upd.set(True)
            updatePorts()

        ent_p0tx = ttk.Entry(self, width=38, textvariable=self.p0_tx)
        ent_p0tx.delete(0, tk.END)
        ent_p0tx.insert(0, "0000_0000_0000_0000_0000_0000_0000_0000")  # default
        btn_p0upd = ttk.Button(self, text="Update", command=updateP0)

        ent_p1tx = ttk.Entry(self, width=32, textvariable=self.p1_tx)
        ent_p1tx.delete(0, tk.END)
        ent_p1tx.insert(0, "0000_0000_0000_0000_0000_0000_0000_0000")  # default
        btn_p1upd = ttk.Button(self, text="Update", command=updateP1)

        lbl_P0Rx = ttk.Label(self, text="Port0 Rx:")
        lbl_P0Tx = ttk.Label(self, text="Tx:")
        lbl_P0Var = ttk.Label(self, textvariable=self.p0_rx)

        lbl_P1Rx = ttk.Label(self, text="Port1 Rx:")
        lbl_P1Tx = ttk.Label(self, text="Tx:")
        lbl_P1Var = ttk.Label(self, textvariable=self.p1_rx)

        # LayOut

        lbl_pageName.grid(column=1, row=1, sticky=tk.W)
        ent_slave.grid(column=2, row=1, sticky=tk.W)
        lbl_P0Rx.grid(column=1, row=2, sticky=tk.EW)
        lbl_P0Var.grid(column=2, row=2, columnspan=3, sticky=tk.EW)
        lbl_P0Tx.grid(column=1, row=3, sticky=tk.E)
        ent_p0tx.grid(column=2, row=3, columnspan=3, sticky=tk.EW)
        btn_p0upd.grid(column=5, row=3, columnspan=3, sticky=tk.EW)
        lbl_P1Rx.grid(column=1, row=4, sticky=tk.EW)
        lbl_P1Var.grid(column=2, row=4, columnspan=3, sticky=tk.EW)
        lbl_P1Tx.grid(column=1, row=5, sticky=tk.E)
        ent_p1tx.grid(column=2, row=5, columnspan=3, sticky=tk.EW)
        btn_p1upd.grid(column=5, row=5, columnspan=3, sticky=tk.EW)

        for child in self.winfo_children(): child.grid_configure(padx=5, pady=5)

        self.after(500, updatePorts)


class S_Ports(tk.Frame):

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
                ft_write(dev, (0x80, 0x00, OPS))  # clear CS0
                ft_write_cmd_bytes(dev, CMD_OUT, [0,0,0, cByte, 0, (S_USR_START + self.startAddr.get()), 0, 0])  # initial address
                mem = ""
                for i in range(0, self.numWords.get()):
                    ft_write_cmd_bytes(dev, CMD_INOUT,[0,0,0, cByte, 0, (S_USR_START + self.startAddr.get() + i + 1), 0, 0])  # address first read
                    rx = ft_read(dev, 8)
                    word = f"{(rx[6] * (2 ** 8) + rx[7]):0{4}X} "  # convert to '01C3 '
                    mem += word  # add to string
                ft_write(dev, (0x80, 0x08, OPS))  # set CS0
                self.memField.set(mem)
            except:
                print('fail at readMem')

        def writeMem():
            try:
                slv = self.slave.get()
                bsat_pwr = self.controller.bsat_pwr.get()
                cByte = (bsat_pwr << 7) + (slv << 4) + WR + S_PORT
                mem = self.memField.get().split()
                ft_write(dev, (0x80, 0x00, OPS))  # clear CS0
                for i in range(len(mem)):
                    word_int = int(mem[i], 16)
                    hb = word_int // 256  # floor division
                    lb = word_int % 256  # modulus
                    ft_write_cmd_bytes(dev, CMD_OUT, [0,0,0, cByte, 0, (S_USR_START + self.startAddr.get() + i), hb, lb])
                ft_write(dev, (0x80, 0x08, OPS))  # set CS0
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
