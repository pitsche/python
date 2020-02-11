import sys
import time
import spidev
import numpy as np
from tkinter import *
from PIL import Image, ImageOps, ImageTk
try:
    import RPi.GPIO as GPIO
except RuntimeError:
    print("Error importing RPi.GPIO!  This is probably because you need superuser privileges.")
# HW config    
bus = 0 # We only have SPI bus 0 available to us on the Pi
device = 0 #Device is the chip select pin. Set to 0 or 1, depending on the connections
spi = spidev.SpiDev() # Enable SPI
spi.open(bus, device) # Open a connection
spi.no_cs= True # we create manual cs
# Set SPI speed and mode
spi.max_speed_hz = 100000
spi.mode = 0b11 #[CPOL,CPHA]
# Set CS0 as GPIO
GPIO.setmode(GPIO.BOARD)
GPIO.setup(22, GPIO.OUT, initial=GPIO.HIGH)
# pat9102 related
rdClk = 8000 # to ensure the 160us srad between address and readbyte, spidev bug in delay_usec !
tSrad = 160e-6
regProdID = 0x00
regRevID = 0x01
regMotion = 0x02
regDeltaXL = 0x03
regDeltaXH = 0x04
regDeltaYL = 0x05
regDeltaYH = 0x06
regConf2 = 0x14
regConf3 = 0x23
regConf5 = 0x25
regConf6 = 0x5E
regPwrUp = 0x3A
regFrameCap = 0x12
regRawDataBurst = 0x64


class MasterGUI:
    def __init__(self, master):
#        global img
        self.master = master
        master.title("PAT9102 Interface")

        self.label = Label(master, text = 'mööp')
        self.label.pack()
        
        self.frame = PhotoImage('image.png')
        self.canvas = Canvas(master, width=520, height=520)
        self.imgArea = self.canvas.create_image(10, 10, image=self.frame, anchor='nw', tags="frame")
        self.canvas.pack()

        self.get_button = Button(master, text="New Frame", command=self.getFrame)
        self.get_button.pack(side=LEFT)

        self.live_button = Button(master, text="Live Frame", command=self.liveFrame)
        self.live_button.pack(side=LEFT)

        self.stop_button = Button(master, text="Stop Frame", command=self.stopFrame)
        self.stop_button.pack(side=LEFT)

        self.close_button = Button(master, text="Close", command=master.quit)
        self.close_button.pack(side=LEFT)
        


    def getFrame(self):
        self.initFrame()
        self.updateFrame()

    def liveFrame(self):
        self.updateFrame()
        self.auto = root.after(200, self.liveFrame)
            
    def stopFrame(self):
        root.after_cancel(self.auto)
            
    def initFrame(self):
        self.wrByte(regPwrUp,0x5A) # PowerUpRes
        time.sleep(5e-3)
        self.wrByte(0x1E,0x08)
        self.wrByte(0x20,0x84)
        self.wrByte(0x1F,0x03)
        self.wrByte(regConf3,0x01) # Kickstart
        time.sleep(35e-3)
        
    def updateFrame(self):
        rawFrame = self.ReadFrame()
        img = Image.fromarray(rawFrame)
        img = img.resize((500, 500), Image.ANTIALIAS)
        img = ImageTk.PhotoImage(img)
        self.frame = img
        self.canvas.itemconfig(self.imgArea, image=self.frame)

    def clr_CS0(self):
        GPIO.output(22, GPIO.LOW)
     
    def set_CS0(self):
        GPIO.output(22, GPIO.HIGH)

    def rdByte(self, addr):
        GPIO.output(22, GPIO.LOW)
        rx = spi.xfer([addr,0], rdClk)
        GPIO.output(22, GPIO.HIGH)
        return(rx[1])
    
    def wrByte(self, addr, data):
        wr = 0x80
        GPIO.output(22, GPIO.LOW)
        spi.xfer([wr + addr,data])
        GPIO.output(22, GPIO.HIGH)

    def ReadFrame(self):
        img = np.zeros((32,32),dtype='uint8') #create array
        self.wrByte(regFrameCap, 0x93)
        self.wrByte(regFrameCap, 0xC5)
        time.sleep(5e-3)
        MotReg0 = 0
        while MotReg0 == 0: # check if data is ready
            rx = self.rdByte(regMotion)
            MotReg0 = rx & 0x01
        self.clr_CS0() #Start Burst Read
        spi.xfer([regRawDataBurst])
        time.sleep(tSrad)
        for x in range(0,32):
            for y in range(0,32):
                rx = spi.readbytes(1)
                img[x,y] = rx[0]
                time.sleep(120e-6)
        self.set_CS0()
        return(img)


root = Tk()
my_gui = MasterGUI(root)
root.mainloop()