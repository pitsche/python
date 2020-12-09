import ftd2xx as ftd  # usb
import sys

# HW config USB
FTDI_TIMEOUT = 1000  # Timeout for D2XX read/write (msec)
OPS = 0x1B  # Bit mask for CS, SPI clock and data out
SER_NR = b'5008-5758'

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
