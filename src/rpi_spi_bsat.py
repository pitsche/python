import sys
import time
import spidev
import numpy as np
import tkinter as tk
from tkinter import ttk

# HW config
bus = 0 # We only have SPI bus 0 available to us on the Pi
device = 0 #Device is the chip select pin. Set to 0 or 1, depending on the connections
spi = spidev.SpiDev() # Enable SPI
spi.open(bus, device) # Open a connection
# Set SPI speed and mode
spi.max_speed_hz = 100000
spi.mode = 0b00 #[CPOL,CPHA]

LARGE_FONT= ("Verdana", 12)

class RaspiBSAT(tk.Tk):

    def __init__(self, *args, **kwargs):
        
        tk.Tk.__init__(self, *args, **kwargs)

        tk.Tk.wm_title(self, "BSAT Interface")
        # Top Menu
        btn_menu1 = ttk.Button(self, text="Status", command=lambda: self.show_frame(Status))
        btn_menu2 = ttk.Button(self, text="Ports", command=lambda: self.show_frame(Ports))
        btn_menu3 = ttk.Button(self, text="S-Ports", command=lambda: self.show_frame(S_Ports))
        btn_menu1.grid (column=0, row=0, sticky=(tk.EW))
        btn_menu2.grid (column=1, row=0, sticky=(tk.EW))
        btn_menu3.grid (column=2, row=0, sticky=(tk.EW))


        container = ttk.Frame(self, padding="3 3 12 12")
        container.grid(column=0, row=1, columnspan=3, sticky=(tk.NSEW))

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
        tk.Frame.__init__(self,parent)
        slave = tk.IntVar()
        boardType = tk.StringVar()
        boardNumber = tk.StringVar()
        
        def enblSlave():
            try:
                slv = slave.get()
                b1 = (1<<6)+(slv<<2)
                pack0 = [b1,0x11,0x00,0x00] #reset
                pack1 = [b1,0x11,0x00,0x08] #NodeEnable
                pack2 = [b1,0x11,0x00,0x0C] #IdSuccessful
                pack3 = [b1,0x11,0x00,0x0E] #ScanDone
                spi.xfer(pack0)
                spi.xfer(pack1)
                spi.xfer(pack2)
                spi.xfer(pack3)
            except:
                pass

        def updateInfo():
            try:
                slv = slave.get()
                spi.xfer([(slv<<2),(0x53),0,0]) #initial address
                mem = []
                brdType = ""
                brdNmbr = ""
                for i in range(16): # read memory
                    rx = (spi.xfer([(slv<<2),(0x53+i+1),0,0]))       #address first read
                    mem.append(rx[0])
                    mem.append(rx[1])
                for x in range(0,16): #convert to string Board Type
                    if mem[x]:
                        brdType += chr(mem[x])
                for y in range(16,32): #convert to string Board Number
                    if mem[y]:
                        brdNmbr += chr(mem[y])
                boardType.set(brdType)
                boardNumber.set(brdNmbr)
            except:
                print('mööp @ updateInfo')


        lbl_pageName = ttk.Label(self, text="Status Slave: ", font=LARGE_FONT)
        ent_slave = ttk.Entry(self, width=2, textvariable=slave)
        ent_slave.delete(0, tk.END)
        ent_slave.insert(0,"0") # default
        btn_enblSlave = ttk.Button(self, text="Enable Slave", command=enblSlave)
        lbl_boardInfo = ttk.Label(self, text="Board Info: ")
        lbl_boardType = ttk.Label(self, textvariable=boardType)
        lbl_boardNumber = ttk.Label(self, textvariable=boardNumber)
        btn_update = ttk.Button(self, text="Update", command=updateInfo)
#        self.lbl_slaveNr = []
#        for i in range(8):
#            self.lbl_slaveNr.append(ttk.Label(self, text='Slave '+str(i)+':'))
#            self.lbl_slaveNr[i].grid(column=1, row=i+2, sticky=(tk.W))
            
        
        #LayOut

        lbl_pageName.grid     (column=1, row=1, sticky=(tk.W))
        ent_slave.grid        (column=2, row=1, sticky=(tk.W))
        btn_enblSlave.grid    (column=3, row=1, sticky=(tk.EW))
        lbl_boardInfo.grid    (column=1, row=4)
        lbl_boardType.grid    (column=2, row=4, columnspan=2, sticky=(tk.W))
        lbl_boardNumber.grid  (column=2, row=5, columnspan=2, sticky=(tk.W))
        btn_update.grid       (column=1, row=6)

        for child in self.winfo_children(): child.grid_configure(padx=5, pady=5)



class Ports(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        slave = tk.IntVar()
        p0_rx = tk.StringVar()
        p0_tx = tk.StringVar()
        p0_upd = tk.BooleanVar()
        p1_rx = tk.StringVar()
        p1_tx = tk.StringVar()
        p1_upd = tk.BooleanVar()

        lbl_pageName = ttk.Label(self, text="Ports Slave: ", font=LARGE_FONT)
        ent_slave = ttk.Entry(self, width=2, textvariable=slave)
        ent_slave.delete(0, tk.END)
        ent_slave.insert(0,"0") # default

        def updatePorts():
            try:
                tx_p0 = (int(p0_tx.get(),2)).to_bytes(4, byteorder='big')
                tx_p1 = (int(p1_tx.get(),2)).to_bytes(4, byteorder='big')
                slv = slave.get()
                p0wr = p0_upd.get() # ports to write?
                p1wr = p1_upd.get()
                spi.xfer([(p0wr<<7) + (slv<<2) + 0,0,tx_p0[0],tx_p0[1]])         #address first read, write first
                rx0_h = spi.xfer([(p0wr<<7) + (slv<<2) + 1,0,tx_p0[2],tx_p0[3]]) #read first, write second...
                rx0_l = spi.xfer([(p1wr<<7) + (slv<<2) + 2,0,tx_p1[0],tx_p1[1]])
                rx1_h = spi.xfer([(p1wr<<7) + (slv<<2) + 3,0,tx_p1[2],tx_p1[3]])
                rx1_l = spi.readbytes(4)               #read last
                p0_upd.set(False) #only update once
                p1_upd.set(False)
                rx0_32 = rx0_h[2]*(2**24) + rx0_h[3]*(2**16) + rx0_l[2]*(2**8) + rx0_l[3] #generate integer range 0 to 2**32
                rx1_32 = rx1_h[2]*(2**24) + rx1_h[3]*(2**16) + rx1_l[2]*(2**8) + rx1_l[3]
                p0_rx.set(f"{rx0_32:0{32}b}") #format binary 32
                p1_rx.set(f"{rx1_32:0{32}b}")
#                if RaspiBSAT.frames(Ports).visible
                self.after(500, updatePorts)
            except:
                self.after(500, updatePorts)

        def updateP0():
            p0_upd.set(True)
            updatePorts()

        def updateP1():
            p1_upd.set(True)

 
        ent_p0tx = ttk.Entry(self, width=32, textvariable=p0_tx)
        ent_p0tx.delete(0, tk.END)
        ent_p0tx.insert(0,"00000000000000000000000000000000") # default
        btn_p0upd = ttk.Button(self, text="Update", command=updateP0)

        ent_p1tx = ttk.Entry(self, width=32, textvariable=p1_tx)
        ent_p1tx.delete(0, tk.END)
        ent_p1tx.insert(0,"00000000000000000000000000000000") # default
        btn_p1upd = ttk.Button(self, text="Update", command=updateP1)


        lbl_P0Rx = ttk.Label(self, text="Port0 Rx:")
        lbl_P0Tx = ttk.Label(self, text="Tx:")
        lbl_P0Var = ttk.Label(self, textvariable=p0_rx)

        lbl_P1Rx = ttk.Label(self, text="Port1 Rx:")
        lbl_P1Tx = ttk.Label(self, text="Tx:")
        lbl_P1Var = ttk.Label(self, textvariable=p1_rx)

        #LayOut

        lbl_pageName.grid   (column=1, row=1, sticky=(tk.W))
        ent_slave.grid      (column=2, row=1, sticky=(tk.W))
        lbl_P0Rx.grid       (column=1, row=2, sticky=(tk.EW))
        lbl_P0Var.grid      (column=2, row=2, columnspan=3, sticky=(tk.EW))
        lbl_P0Tx.grid       (column=1, row=3, sticky=(tk.E))
        ent_p0tx.grid       (column=2, row=3, columnspan=3, sticky=(tk.EW))
        btn_p0upd.grid      (column=5, row=3, columnspan=3, sticky=(tk.EW))
        lbl_P1Rx.grid       (column=1, row=4, sticky=(tk.EW))
        lbl_P1Var.grid      (column=2, row=4, columnspan=3, sticky=(tk.EW))
        lbl_P1Tx.grid       (column=1, row=5, sticky=(tk.E))
        ent_p1tx.grid       (column=2, row=5, columnspan=3, sticky=(tk.EW))
        btn_p1upd.grid      (column=5, row=5, columnspan=3, sticky=(tk.EW))
        
        for child in self.winfo_children(): child.grid_configure(padx=5, pady=5)
        
        self.after(500, updatePorts)



class S_Ports(tk.Frame):

    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        slave = tk.IntVar()
        startAddr = tk.IntVar()
        numWords = tk.IntVar()
        memField = tk.StringVar()
        
        def readMem():
            try:
                slv = slave.get()
                spi.xfer([(slv<<2),(0xb0 + startAddr.get()),0,0]) #initial address
                mem = ""
                for i in range(0,numWords.get()):
                    rx = (spi.xfer([(slv<<2),(0xb0 + startAddr.get() + i + 1),0,0]))       #address first read
                    word = f"{(rx[0]*(2**8) + rx[1]):0{4}x} " # convert to '01C3 '
                    mem += word # add to string
                memField.set(mem)
            except:
                print('mööp @ readMem')
                
        def writeMem():
            try:
                slv = slave.get()
                mem = memField.get().split()
                for i in range(len(mem)):
                    word_int = int(mem[i],16)
                    hb = word_int // 256 # floor division
                    lb = word_int % 256 # modulus
                    spi.xfer([(1<<6)+(slv<<2),(0xb0 + startAddr.get() + i),hb,lb])
            except:
                print('mööp @ writeMem')
            
        
        lbl_pageName = ttk.Label(self, text="S-Ports Slave: ", font=LARGE_FONT)
        ent_slave = ttk.Entry(self, width=2, textvariable=slave)
        ent_slave.delete(0, tk.END)
        ent_slave.insert(0,"0") # default
        lbl_text = ttk.Label(self, text="User Memory:")
        lbl_startAddr = ttk.Label(self, text="Start Address: ")
        ent_startAddr = ttk.Entry(self, width=4, textvariable=startAddr)
        lbl_numWords = ttk.Label(self, text="Number of Words: ")
        ent_numWords = ttk.Entry(self, width=4, textvariable=numWords)
        btn_read = ttk.Button(self, text="Read", command=readMem)
        btn_write = ttk.Button(self, text="Write", command=writeMem)
        ent_memField = ttk.Entry(self, width= 40,textvariable=memField)
        ent_memField.delete(0, tk.END)

        #LayOut

        lbl_pageName.grid   (column=1, row=1, sticky=(tk.W))
        ent_slave.grid      (column=2, row=1, sticky=(tk.W))
        lbl_text.grid       (column=1, row=2, sticky=(tk.W))
        lbl_startAddr.grid  (column=2, row=2, sticky=(tk.W))
        ent_startAddr.grid  (column=3, row=2, sticky=(tk.W))
        lbl_numWords.grid   (column=4, row=2, sticky=(tk.W))
        ent_numWords.grid   (column=5, row=2, sticky=(tk.W))
        btn_read.grid       (column=1, row=3, sticky=(tk.W))
        btn_write.grid      (column=2, row=3, sticky=(tk.W))
        ent_memField.grid   (column=1, row=4, columnspan=5, sticky=(tk.EW))

        for child in self.winfo_children(): child.grid_configure(padx=5, pady=5)


app = RaspiBSAT()
app.mainloop()