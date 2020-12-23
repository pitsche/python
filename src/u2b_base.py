import ftd2xx as ftd  # usb
import sys
import os

# HW config USB
FTDI_TIMEOUT = 1000  # Timeout for D2XX read/write (msec)
OPS = 0x1B  # Bit mask for CS, SPI clock and data out
SER_NR = b'5008-5758'

# FTDI Command Processor for MPSSE (FTDI AN-108)
CMD_OUT = 0x11  # Clock Data Bytes Out on -ve clock edge MSB first (no read)
CMD_INOUT = 0x31  # out on -ve edge, in on +ve edge

# USB2BSAT FPGA related
PWR_ON  = (1<<7)
WR =  (1<<3)
RD = ~(1<<3)
PORT_0 = 0 # FPGA Addresses for Data selection
PORT_1 = 1
S_PORT = 2
BUS_CTRL = 3
RD_NEXT = 1 # read request for FPGA FIFO handling

# Set mode (bitbang / MPSSE)
def set_bitmode(d, bits, mode):
    return d.setBitMode(bits, mode)


# Open device for read/write
def ft_openEx(nr):
    d = ftd.openEx(nr)
    d.setTimeouts(FTDI_TIMEOUT, FTDI_TIMEOUT)
    return d


# Set SPI clock rate
def set_spi_clock(d, hz):
    div = int((12000000 / (hz * 2)) - 1)  # Set SPI clock
    ft_write(d, (0x86, div % 256, div // 256))


# Write list of integers as byte data
def ft_write(d: object, data: object) -> object:
    s = str(bytearray(data)) if sys.version_info < (3,) else bytes(data)
    return d.write(s)


# Return a 3-tuple of rx queue bytes, tx queue bytes and event status
def getStatus(d):
    return d.getStatus()

# Write MPSSE command with word-value argument
def write_cmd_bytes(d, cmd, data):
    n = len(data) - 1
    ft_write(d, [cmd, n % 256, n // 256] + list(data))

# Read byte data into list of integers
def read(d, nbytes):
    s = d.read(nbytes)
    return [ord(c) for c in s] if type(s) is str else list(s)

# Activate CS0_N
def activate_CS0_n(dev):
    ft_write(dev, (0x80, 0x10, OPS))

# Activate CS1_N
def activate_CS1_n(dev):
    ft_write(dev, (0x80, 0x08, OPS))

# Deactivate CSx_N
def reset_CSx_n(dev):
    ft_write(dev, (0x80, 0x18, OPS))

# Open Device
def openFTDI():
    devList = ftd.createDeviceInfoList()
    if devList < 1:
        print("no FTDI Device installed")
    else:
        for i in range(devList):
            print(ftd.getDeviceInfoDetail(i))
        try:
            dev = ft_openEx(SER_NR)
        except:
            dev = ft_openEx(b'')
        if dev:
            print("FTDI device opened")
            set_bitmode(dev, 0x0, 0x00)  # Reset Controller
            set_bitmode(dev, 0x0, 0x02)  # Enable MPSSE mode
            set_spi_clock(dev, 10_000_000)  # Set SPI clock
            ft_write(dev, (0x80, 0x18, OPS))  # Set outputs
            return(dev)

# common functions

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)

# BSAT Bus control
#------------------
def busCtrl(dev, wr, data):
    ctrlByte = PWR_ON + (wr << 3) + BUS_CTRL
    hb = data // 256  # floor division
    lb = data % 256  # modulus
    txData = [0, 0, 0, ctrlByte, 0, 0, hb, lb]
    write_cmd_bytes(dev, CMD_INOUT, txData) # set Address
    rx = read(dev, 8)
    return(rx)

# S-Port handling with FPGA FIFO
#--------------------------------
def readSPort(dev, slv, addr):
    ctrlByte = PWR_ON + ((slv & 0x7) << 4) + S_PORT
    txData = [0, 0, 0, ctrlByte, RD_NEXT, addr, 0, 0]
    write_cmd_bytes(dev, CMD_OUT, txData) # set Address
    txData[4] = 0 # reset RD_NEXT
    rx = [0, 0, 0, 0, 0, 0, 0, 0] # preinitialyze rx for first while loop
    while (not (rx[5] & 1<<0)):  # read until data valid (fifo was not empty)
        write_cmd_bytes(dev, CMD_INOUT, txData) # read Address
        rx = read(dev, 8)
    return(rx[6] * (2**8) + rx[7]) # returns integer value of 16bit

def writeSPort(dev, slv, addr, data):
    ctrlByte = PWR_ON + WR + ((slv & 0x7) << 4) + S_PORT
    hb = data // 256  # floor division
    lb = data % 256  # modulus
    txData = [0, 0, 0, ctrlByte, 0, addr, hb, lb]
    write_cmd_bytes(dev, CMD_OUT, txData) # set Address

# Port 0 and 1 read and write
#-----------------------------
def updatePorts(dev, slv, port0tx, port1tx): #Ports are 4 bytes
    activate_CS0_n(dev)
    ctrlByte = PWR_ON + WR + ((slv & 0x7) << 4) + PORT_0 # select port0
    txData = [0, 0, 0, ctrlByte, port0tx[3], port0tx[2], port0tx[1], port0tx[0]]
    write_cmd_bytes(dev, CMD_OUT, txData)  # Port 0 write
    ctrlByte = PWR_ON + WR + ((slv & 0x7) << 4) + PORT_1 # select port1
    txData = [0, 0, 0, ctrlByte, port1tx[3], port1tx[2], port1tx[1], port1tx[0]]
    write_cmd_bytes(dev, CMD_INOUT, txData) # Port 0 read, Port 1 write
    txData[3] &= RD # reset Write Bit
    write_cmd_bytes(dev, CMD_INOUT, txData)  # Port 1 read
    reset_CSx_n(dev)
    rx = read(dev, 16)
    rx0 = rx[4], rx[5], rx[6], rx[7] # port 0
    rx1 = rx[12], rx[13], rx[14], rx[15] # port 1
    sumErr = ((rx[9] * 2**8) + rx[10]) # slv7(p1,p0),slv6(p1,p0)..slv0(p1,p0)
    return([rx0, rx1], sumErr) # returns 2 * 4 byte + integer
