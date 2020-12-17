#!/usr/bin/env python

import sys
import os
import time
import csv
import u2b_spi as spi
from PyQt5.QtWidgets import (QApplication, QWidget, QCheckBox, QPushButton, QRadioButton, QButtonGroup, QProgressBar,\
                             QHBoxLayout, QVBoxLayout, QGridLayout, QGroupBox, QLabel, QFileDialog, QLineEdit, QTextEdit)
from PyQt5.QtGui import (QIcon, QPixmap, QIntValidator)
from PyQt5.QtCore import QTimer, pyqtSignal, Qt

# FTDI Command Processor for MPSSE (FTDI AN-108)
CMD_OUT = 0x11  # Clock Data Bytes Out on -ve clock edge MSB first (no read)
CMD_INOUT = 0x31  # out on -ve edge, in on +ve edge

# Other Constants
PWR_ON  = (1 << 7)
WR = 1
RD = 0
RD_NEXT = 1
PORT_0 = 0
PORT_1 = 1
S_PORT = 2
BUS_CTRL = 3
 # BSAT_Memory_Map
BSAT_UID0 = 2
BSAT_UID1 = 3
BSAT_MODE0 = 14
BSAT_MODE1 = 15
BSAT_CTRL0 = 16
BSAT_CTRL1 = 17
BSAT_WR_DL_ADDR = 27
BSAT_HID_MASK_0 = 63
BSAT_HID_MASK_1 = 64
BSAT_NODE_ERR_MASK = 67
BSAT_ERR_MASK_PORT_0_0 = 71
BSAT_ERR_MASK_PORT_0_1 = 72
BSAT_ERR_MASK_PORT_1_0 = 76
BSAT_ERR_MASK_PORT_1_1 = 77
BSAT_BOARD_TYPE = 83
BSAT_NODE_INFO = 99

S_USR_START = 0  # 0xB0
# Flash Ranges
RANGE_AUX = 1
RANGE_STD = 2
RANGE_MFD = 7

LARGE_FONT = ("Verdana", 12)

# Open FTDI device as dev
dev = spi.openFTDI()

class Usb2Bsat(QWidget):

    def __init__(self):
        super().__init__()
        self.title = 'BSAT Interface'
        self.left = 100
        self.top = 100
        self.width = 600
        self.hight = 300
        self.initUI()

    def initUI(self):
        self.setGeometry(self.left, self.top, self.width, self.hight)
        self.setWindowTitle(self.title)
        self.setWindowIcon(QIcon(self.resource_path('besi.png')))

        self.RedLabel = '''color: white; background-color: red;'''
        self.GreenLabel = '''color: white; background-color: green;'''
        self.OrgLabel = '''color: black; background-color: light grey;'''
        self.GreenLedOn = QPixmap(self.resource_path('green-led-on.png')).scaledToWidth(20)
        self.LedOff = QPixmap(self.resource_path('led-off.png')).scaledToWidth(20)

        #some projektwide used variables
        self.bsatPwr = 0
        self.bsatSlave = 0
        self.numOfPorts = 2
        self.lblRx = [None] * 64  # create list. used to display Port LED's
        self.btnTx = [None] * 64  
        self.errorButton = [None] * 2
        self.updateButton = [None] * 2
        self.port_tx = [[0, 0, 0, 0], [0, 0, 0, 0]] # 2 * (4*8bit) array to transmitt
        self.portWrite = [0, 0] # 2 * true or false if port_tx has been updated
        # Ctrl Bytes 0, 1, 2 are not used.
        # Ctrl Byte 3 : 7 = bsat pwr, 6..4 = bsat slave, 3 = write, 2..0 = data select (0=Port0, 1=Port1, 2=S-Port, 3=BSAT-BusCtrl)
        self.ctrlBytes = [0, 0, 0, 0]
        self.MFDDataMap = ['Map ID', 'Board Number', 'Board Index', 'Board Name', 'Board ID', 'Supplier Lot', 'Supplier Name', \
                           'Date of manufacture', 'Configuration', 'Test Location', 'FPGA Design Number', 'Test Date', 'Board History', 'Test ID']
        self.MFDValue = [None] * 14

        self.bsatPwrCheckBox = QCheckBox('&BSAT Power')
        self.bsatPwrCheckBox.toggled.connect(self.changePower)
        slvLbl = QLabel('    Slv: ')
        self.slvRBtn = {}
        self.slvBtnGrp = QButtonGroup()
        for i in range(8):
            self.slvRBtn[i] = 0

        self.createInfoGroupBox()
        self.createUserPortGroupBox()
        self.portGroupBox = {}
        for i in range(self.numOfPorts):
            self.createPortGroupBox(i)
            self.createPortGroupBox(i)
        self.createDownloadGroupBox()
        self.createMFDGroupBox()

        self.topLayout = QHBoxLayout()
        self.topLayout.addWidget(self.bsatPwrCheckBox)
        self.topLayout.addWidget(slvLbl)
 
        mainLayout = QGridLayout()
        mainLayout.addLayout(self.topLayout, 0, 0, 1, 1)
        mainLayout.addWidget(self.infoGroupBox, 1, 0, 1, 1)
        mainLayout.addWidget(self.userPortGroupBox, 1, 1, 1, 2)
        mainLayout.addWidget(self.portGroupBox[0], 2, 0, 1, 3)
        mainLayout.addWidget(self.portGroupBox[1], 3, 0, 1, 3)
        mainLayout.addWidget(self.downloadGroupBox, 4, 0, 1, 3)
        mainLayout.addWidget(self.MFDGroupBox, 5, 0, 1, 3)
        self.setLayout(mainLayout)

        # setup timer to update spi inputs
        self.updateTimer = QTimer()
        self.updateTimer.timeout.connect(self.updateInputs)


    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)

# ***************************************
# ******** START creating LAYOUT ********

    def createInfoGroupBox(self):
        self.infoGroupBox = QGroupBox('Slave Information')
        layout = QGridLayout()
        lblBrdType = QLabel('Type:')
        lblBrdNmbr = QLabel('Number:')
        lblSysInfo = QLabel('System:')
        lblFeature = QLabel('FeatureID:')
        lblBugfix  = QLabel('BugfixID:')
        lblPorts   = QLabel('Ports:')
        self.valBrdType = QLabel()
        self.valBrdNmbr = QLabel()
        self.valSysInfo = QLabel()
        self.valFeature = QLabel()
        self.valBugfix = QLabel()
        self.valPorts = QLabel()
        layout.addWidget(lblBrdType, 0, 0)
        layout.addWidget(lblBrdNmbr, 1, 0)
        layout.addWidget(lblSysInfo, 2, 0)
        layout.addWidget(lblFeature, 3, 0)
        layout.addWidget(lblBugfix, 4, 0)
        layout.addWidget(lblPorts, 5, 0)
        layout.addWidget(self.valBrdType, 0, 1)
        layout.addWidget(self.valBrdNmbr, 1, 1)
        layout.addWidget(self.valSysInfo, 2, 1)
        layout.addWidget(self.valFeature, 3, 1)
        layout.addWidget(self.valBugfix, 4, 1)
        layout.addWidget(self.valPorts, 5, 1)
        self.infoGroupBox.setLayout(layout)

    def createPortGroupBox(self, port):
        # we create port unique bitnumbers
        # P0: 31 .. 0
        # P1: 63 .. 32
        self.portGroupBox[port] = QGroupBox(f'Port {port}')
        layout = QGridLayout()
        layout.setAlignment(Qt.AlignCenter)
        lblBit = {}
        for i in range(32):
            # Rx line
            self.lblRx[i + (port * 32)] = QLabel()
            self.lblRx[i + (port * 32)].setPixmap(self.LedOff)
            self.lblRx[i + (port * 32)].setAlignment(Qt.AlignCenter)
            layout.addWidget(self.lblRx[i + (port * 32)], 0, 31-i)  # place lblRx[0] to grid pos 31 ..
            # Bit number
            lblBit[i] = QLabel(f'{31 - i}')
            lblBit[i].setAlignment(Qt.AlignCenter)
            layout.addWidget(lblBit[i], 1, i)
            # Tx line
            self.btnTx[i + (port * 32)] = QCheckBox()
            layout.addWidget(self.btnTx[i + (port * 32)], 2, 31-i)  # place lblRx[0] to grid pos 31 .
        # Error Button
        self.errorButton[port] = QPushButton('Error')
        self.errorButton[port].clicked.connect(lambda: self.errorPort(port))
        layout.addWidget(self.errorButton[port], 0, 32)
        # Update Button
        self.updateButton[port] = QPushButton('Update')
        self.updateButton[port].clicked.connect(lambda: self.updatePort(port))
        layout.addWidget(self.updateButton[port], 2, 32)
        self.portGroupBox[port].setLayout(layout)

    def createUserPortGroupBox(self):
        self.userPortGroupBox = QGroupBox('User Port')
        layout = QGridLayout()
        self.startAddr = QLineEdit()
        self.startAddr.setValidator(QIntValidator(0, 999))
        self.numOfWords = QLineEdit()
        self.numOfWords.setValidator(QIntValidator(1, 999))
        self.sPortDisply = QTextEdit()
        lblStartAddr = QLabel('Start Address:')
        lblNumOfWords = QLabel('Num of Words:')
        sRead = QPushButton('read')
        sRead.clicked.connect(self.readMem)
        sWrite = QPushButton('write')
        sWrite.clicked.connect(self.writeMem)
        layout.addWidget(lblStartAddr, 0, 0)
        layout.addWidget(self.startAddr, 0, 1)
        layout.addWidget(lblNumOfWords, 0, 2)
        layout.addWidget(self.numOfWords, 0, 3)
        layout.addWidget(sRead, 1, 0)
        layout.addWidget(sWrite, 1, 1)
        layout.addWidget(self.sPortDisply, 2, 0, 3, 5)
        self.userPortGroupBox.setLayout(layout)

    def createDownloadGroupBox(self):
        self.downloadGroupBox = QGroupBox('Download Firmware')
        layout = QGridLayout()
        self.rpdFileName = [0]
        self.sys = RANGE_STD  # default

        self.stdSysRBtn = QRadioButton("Standard Sys")
        self.auxSysRBtn = QRadioButton("Auxiliary Sys")
        self.sysBtnGrp = QButtonGroup()
        self.sysBtnGrp.addButton(self.stdSysRBtn)
        self.sysBtnGrp.addButton(self.auxSysRBtn)
        self.stdSysRBtn.setChecked(True)
        self.stdSysRBtn.toggled.connect(self.setSys)
        self.auxSysRBtn.toggled.connect(self.setSys)

        self.rpdGetFileButton = QPushButton("File: ")
        self.rpdGetFileButton.clicked.connect(self.readRpd)
        self.rpdLblFileName = QLabel()
        self.rpdStartButton = QPushButton("Start")
        self.rpdStartButton.clicked.connect(lambda: self.downloadFirmware(self.sys))
        self.rpdDlBar = QProgressBar()
        self.rpdDlBar.setRange(0,100)
        layout.addWidget(self.stdSysRBtn, 0, 0)
        layout.addWidget(self.auxSysRBtn, 0, 1)
        layout.addWidget(self.rpdGetFileButton, 1, 0)
        layout.addWidget(self.rpdLblFileName, 1, 1)
        layout.addWidget(self.rpdStartButton, 2, 0)
        layout.addWidget(self.rpdDlBar, 2, 1)
        self.downloadGroupBox.setLayout(layout)

    def createMFDGroupBox(self):
        self.MFDGroupBox = QGroupBox('Manufacturing Data')
        layout = QGridLayout()
        btnMFDRead = QPushButton('read MFD')
        btnMFDRead.clicked.connect(self.readManufacturingData)
        self.btnMFDWrite = QPushButton('write MFD')
        self.btnMFDWrite.clicked.connect(self.writeManufacturingData)
        btnSafeFile = QPushButton('safe to File')
        btnSafeFile.clicked.connect(self.safeMFDFile)
        btnLoadFile = QPushButton('load from File')
        btnLoadFile.clicked.connect(self.loadMFDFile)
        lblMFDName = {}
        for collumn in range(2):
            for row in range(7):
                lblMFDName[row + (collumn * 7)] = QLabel(f'{self.MFDDataMap[row + (collumn * 7)]} :')
                layout.addWidget(lblMFDName[row + (collumn * 7)], row, collumn * 2)
                if ((row == 0) & (collumn == 0)): # The first line is Label only 
                    self.MFDValue[0] = QLabel()
                    layout.addWidget(self.MFDValue[0], 0, 1)
                else:
                    self.MFDValue[row + (collumn * 7)] = QLineEdit()
                    layout.addWidget(self.MFDValue[row + (collumn * 7)], row, (collumn * 2) + 1)
        layout.addWidget(btnMFDRead, 0, 4)
        layout.addWidget(self.btnMFDWrite, 1, 4)
        layout.addWidget(btnSafeFile, 3, 4)
        layout.addWidget(btnLoadFile, 4, 4)
        self.MFDGroupBox.setLayout(layout)

# ******** END creating LAYOUT ********
# *************************************

    def changePower(self):
        if self.bsatPwrCheckBox.isChecked():
            self.ctrlBytes[3] = PWR_ON
            self.scanBsat()
            self.updateTimer.start(100)
        else:
            self.updateTimer.stop()
            self.ctrlBytes[3] = 0
            spi.activate_CS0_n(dev)
            spi.write_cmd_bytes(dev, CMD_OUT, self.ctrlBytes + [0, 0, 0, 0])  # BSAT Power off 
            spi.reset_CSx_n(dev)
            self.resetGui()

    def createSlaveButtons(self, scaned):
        checked = False
        # first, we delete all existing slave radio buttons
        for i in range(8):
            if (self.slvRBtn[i]):
                self.slvBtnGrp.removeButton(self.slvRBtn[i])
                self.slvRBtn[i].toggled.disconnect(self.setSlave)
                self.topLayout.removeWidget(self.slvRBtn[i])
                self.slvRBtn[i].deleteLater()
                self.slvRBtn[i] = None
        # then we generate a button for each detected slave number
        for i in range(8):
            if (scaned & 1 << i):
                self.slvRBtn[i] = QRadioButton(f'{i}')
                self.slvBtnGrp.addButton(self.slvRBtn[i])
                self.slvRBtn[i].toggled.connect(self.setSlave)
                self.topLayout.addWidget(self.slvRBtn[i])
                if (not checked):
                    self.slvRBtn[i].setChecked(True)
                    checked = True

    def setSlave(self):
        rBtn = self.sender()
        if rBtn.isChecked():
            slv = int(rBtn.text())
            self.ctrlBytes[3] &= int('10001111', 2) # reset actual slave bits
            self.ctrlBytes[3] += slv << 4 # set new slave number
        self.getSlaveInfo()

    def setWrSel(self, wrRdn, sel):
        self.ctrlBytes[3] &= 0xF0 # reset wr & select
        self.ctrlBytes[3] += wrRdn << 3
        self.ctrlBytes[3] += sel

    def readBSAT(self, ctrl, addr): # returns integer value of 16bit
        self.setWrSel(RD, ctrl) # read S-Port or BUS_CTRL
        txData = [RD_NEXT, addr, 0, 0]
        rx = [0, 0, 0, 0, 0, 0, 0, 0] # preinitialyze rx for first while loop
        spi.write_cmd_bytes(dev, CMD_OUT, self.ctrlBytes + txData) # set Address
        txData = [0, addr, 0, 0]
        while (not (rx[5] & 1 << 0)):  # read until data valid (fifo was not empty)
            spi.write_cmd_bytes(dev, CMD_INOUT, self.ctrlBytes + txData) # read Address
            rx = spi.read(dev, 8)
            if (ctrl == BUS_CTRL): # no fifo function on BUS_CTRL
                break
        return(rx[6] * (2**8) + rx[7])

    def writeBSAT(self, ctrl, addr, hByte, lByte):
        self.setWrSel(WR, ctrl) # write S-Port or BUS_CTRL
        txData = [0, addr, hByte, lByte]
        spi.write_cmd_bytes(dev, CMD_OUT, self.ctrlBytes + txData) # set Address


    def scanBsat(self):
        spi.activate_CS0_n(dev)
        self.setWrSel(WR, BUS_CTRL)
        txData = [0, 0, 0x00, 0x02]  # disable continous autoscan, reset rescan bit (0)
        spi.write_cmd_bytes(dev, CMD_OUT, self.ctrlBytes + txData)  # 
        txData = [0, 0, 0xF0, 0x03]  # max scandelay, initialize rescan
        spi.write_cmd_bytes(dev, CMD_OUT, self.ctrlBytes + txData)
        txData = [0, 0, 0x00, 0x02]  # disable continous autoscan, reset rescan bit (0)
        spi.write_cmd_bytes(dev, CMD_OUT, self.ctrlBytes + txData)
        rx = [0, 0, 0, 0, 0, 0, 0, 0]
        timeout = 2 # seconds
        timeout_start = time.time()
        while time.time() < timeout_start + timeout:
            spi.write_cmd_bytes(dev, CMD_INOUT, self.ctrlBytes + txData)
            rx = spi.read(dev, 8)  #read buffer
            if (rx[4] & 1 << 3):  # scan done?
                break
        else: # erase timeout
            print('scan timeout')
        spi.reset_CSx_n(dev)
        self.createSlaveButtons(rx[5])

    def getSlaveInfo(self):
        brdType = ""
        brdNmbr = ""
        mem = []
        spi.activate_CS0_n(dev)
        for i in range(16):  # read memory
            word = self.readBSAT(S_PORT, BSAT_BOARD_TYPE + i)
            hByte = word >> 8
            lByte = word & 0x00FF
            mem.append(hByte)
            mem.append(lByte)
        nodeInfo = self.readBSAT(S_PORT, BSAT_NODE_INFO)
        if (nodeInfo & 1 << 0):
            self.valSysInfo.setText('Auxiliary')
        else:
            self.valSysInfo.setText('Standard')
        self.numOfPorts = (nodeInfo & 0x00F0) // 16 # upper 4 bits
        self.valPorts.setText(f'{self.numOfPorts}')
        uID_0 = self.readBSAT(S_PORT, BSAT_UID0)
        featureID = uID_0 & 0x00FF
        self.valFeature.setText(f'{featureID}')
        uID_1 = self.readBSAT(S_PORT, BSAT_UID1)
        bugFix = uID_1 >> 8
        self.valBugfix.setText(f'{bugFix}')
        spi.reset_CSx_n(dev)
        for x in range(0, 16):  # convert to string Board Type
            if mem[x]:
                brdType += chr(mem[x])
        for y in range(16, 32):  # convert to string Board Number
            if mem[y]:
                brdNmbr += chr(mem[y])
        self.valBrdType.setText(brdType)
        self.valBrdNmbr.setText(brdNmbr)
        self.enblSlave()

    def enblSlave(self):
        spi.activate_CS0_n(dev)
        rx = self.readBSAT(S_PORT, BSAT_MODE1)
        if (rx & 1 << 2): #outputs are disabled
            self.writeBSAT(S_PORT, BSAT_CTRL1, 0, 0x00) # set all bits 0 on S-Port address 0x11
            self.writeBSAT(S_PORT, BSAT_CTRL1, 0, 0x08)  # NodeEnable
            self.writeBSAT(S_PORT, BSAT_CTRL1, 0, 0x0C)  # IdSuccessful
            self.writeBSAT(S_PORT, BSAT_CTRL1, 0, 0x0E)  # ScanDone
        self.writeBSAT(S_PORT, BSAT_HID_MASK_0, 0xFF, 0xFF) # start writing S-Port Mask defaults
        self.writeBSAT(S_PORT, BSAT_HID_MASK_1, 0xFF, 0xFF)
        self.writeBSAT(S_PORT, BSAT_NODE_ERR_MASK, 0xFF, 0xFF)
        self.writeBSAT(S_PORT, BSAT_ERR_MASK_PORT_0_0, 0xFF, 0xFF)
        self.writeBSAT(S_PORT, BSAT_ERR_MASK_PORT_0_1, 0xFF, 0xFF)
        self.writeBSAT(S_PORT, BSAT_ERR_MASK_PORT_1_0, 0xFF, 0xFF)
        self.writeBSAT(S_PORT, BSAT_ERR_MASK_PORT_1_1, 0xFF, 0xFF) # end writing S-Port Mask defaults
        spi.reset_CSx_n(dev)

    def setSys(self):
        rBtn = self.sender()
        if rBtn.isChecked():
            if rBtn.text() == "Auxiliary Sys":
                self.sys = RANGE_AUX
            else:
                self.sys = RANGE_STD

    def readRpd(self):
        self.rpdFileName = QFileDialog.getOpenFileName(self, "Select File", "", "*.rpd")
        print(self.rpdFileName[0])
        if (self.rpdFileName[0]):
            head, tail = os.path.split(self.rpdFileName[0])
            self.rpdLblFileName.setText(tail)

    def resetGui(self):
        self.valBrdType.clear()
        self.valBrdNmbr.clear()
        self.valSysInfo.clear()
        self.valFeature.clear()
        self.valBugfix.clear()
        self.valPorts.clear()
        for i in range(14): # clear all TextBoxes
            self.MFDValue[i].clear()
        self.updatePortGui([(0, 0, 0, 0),(0, 0, 0, 0)], 0)

    def errorPort(self, port): # read and display errors of the port
        pass

    def updatePort(self, port): # sets the flag that the corresponding port must be written
        self.port_tx[port] = [0, 0, 0, 0]
        for i in range(4): # bytes
            for j in range(8): # bites
                if self.btnTx[j + (i * 8) + (port * 32)].isChecked():
                    self.port_tx[port][i] += (2 ** j)
        self.portWrite[port] = 1 # set update flag

    def updateInputs(self): # read and write (if the flag is set) the ports
        spi.activate_CS0_n(dev)
        self.setWrSel(self.portWrite[0], PORT_0)
        spi.write_cmd_bytes(dev, CMD_OUT, self.ctrlBytes + [self.port_tx[0][3], self.port_tx[0][2], self.port_tx[0][1], self.port_tx[0][0]])  # Port 0 write
        self.setWrSel(self.portWrite[1], PORT_1)
        spi.write_cmd_bytes(dev, CMD_INOUT, self.ctrlBytes + [self.port_tx[1][3], self.port_tx[1][2], self.port_tx[1][1], self.port_tx[1][0]]) # Port 0 read, Port 1 write
        self.setWrSel(RD, PORT_1)
        spi.write_cmd_bytes(dev, CMD_INOUT, self.ctrlBytes + [0, 0, 0, 0])  # Port 1 read
        spi.reset_CSx_n(dev)
        rx = spi.read(dev, 16)
        self.portWrite = [0, 0]  # only update once
#        rx0 = rx[4], rx[5], rx[6], rx[7] # port 0
        rx0 = rx[8], rx[9], rx[10], rx[11] # port 0
        rx1 = rx[12], rx[13], rx[14], rx[15] # port 1
        sumErr = ((rx[9] * 2**8) + rx[10]) # slv7(p1,p0),slv6(p1,p0)..slv0(p1,p0)
        self.updatePortGui([rx0, rx1], sumErr)

    def updatePortGui(self, rx0_1, sumErr):
        actSlv = (self.ctrlBytes[3] >> 4) & 0x7 # get actual controlled slave number
        for i in range(self.numOfPorts):
            if (sumErr & 1 << (actSlv * 2 + i)): #sumErr on actSlv actPort
                self.errorButton[i].setStyleSheet(self.RedLabel)
            else:
                self.errorButton[i].setStyleSheet(self.OrgLabel)
            for j in range(4): # byte wise
                for k in range(8):
                    if (rx0_1[i][3 - j] & 1 << k):  # starting with bit 0, port 0
                        self.lblRx[i*32 + j*8 + k].setPixmap(self.GreenLedOn)
                    else:
                        self.lblRx[i*32 + j*8 + k].setPixmap(self.LedOff)
    
    def readMem(self): # read and displays the sPort memory
        if (self.startAddr.text()):
            if (self.numOfWords.text()):
                spi.activate_CS0_n(dev)
                mem = ""
                for i in range(int(self.numOfWords.text())):
                    rx = self.readBSAT(S_PORT, int(self.startAddr.text()) + i)
                    word = f"{(rx):0{4}X} "  # convert to '01C3 '
                    mem += word  # add to string
                self.sPortDisply.setText(mem)
                spi.reset_CSx_n(dev)
            else:
                self.sPortDisply.setText('enter number of words')
        else:
            self.sPortDisply.setText('enter start Address')

    def writeMem(self):
        if (self.startAddr.text()):
            if (self.sPortDisply.toPlainText()):
                mem = self.sPortDisply.toPlainText().split()
                spi.activate_CS0_n(dev)
                for i in range(len(mem)):
                    word_int = int(mem[i], 16)
                    hb = word_int // 256  # floor division
                    lb = word_int % 256  # modulus
                    self.writeBSAT(S_PORT, int(self.startAddr.text()) + i, hb, lb)
                spi.reset_CSx_n(dev)
            else:
                self.sPortDisply.setText('enter values to write')
        else:
            self.sPortDisply.setText('enter start Address')

    def readManufacturingData(self):
        # S-Port Addresses
        RD_AD_Flash_LSB = 0x1D
        RD_AD_Flash_MSB = 0x1E
        RD_AD_Flash_Data = 0x20
        # Flash Addresses
        MFD_Start_AD_MSB = 0x00FF
        MFD_Start_AD_LSB = 0x0000
        MFD_MAX_RANGE = 512
        mem = []
        spi.activate_CS0_n(dev)
        for i in range(0, MFD_MAX_RANGE, 2): # read only every second address
            actual_AD_LSB = MFD_Start_AD_LSB + i
            self.writeBSAT(S_PORT, RD_AD_Flash_LSB, actual_AD_LSB // 256, actual_AD_LSB % 256)
            self.writeBSAT(S_PORT, RD_AD_Flash_MSB, MFD_Start_AD_MSB // 256, MFD_Start_AD_MSB % 256)
            word = self.readBSAT(S_PORT, RD_AD_Flash_Data)
            if (word == 0xFFFF): # all read
                break
            hByte = word >> 8
            lByte = word & 0x00FF
            mem.append(hByte)
            mem.append(lByte)
        spi.reset_CSx_n(dev)
        for i in range(14): # clear all TextBoxes
            self.MFDValue[i].clear()
        actVal = 0
        actStr = ''
        for value in mem: # write Manufacturing data to GUI
            if (value == 13): # CR
                if (actVal < 14): # we only have 14 text lines
                    self.MFDValue[actVal].setText(actStr) # write actual string
                actVal += 1
                actStr = ''
            elif (32 <= value <= 126): # only ascii chars allowed
                actStr += chr(value)
            elif (value <= 9): # MAP_ID is stored as number
                actStr += str(value)

    def eraseManufacturingData(self):
        self.MFDEraseBtn.setStyleSheet(self.OrgLabel)
        if self.eraseFlashRange(RANGE_MFD):
            self.MFDEraseBtn.setStyleSheet(self.GreenLabel)
        else:
            self.MFDEraseBtn.setStyleSheet(self.RedLabel)

    def writeManufacturingData(self):
        # S-Port Addresses
        WR_AD_Flash_LSB = 0x19
        WR_AD_Flash_MSB = 0x1A
        WR_AD_Flash_Data = 0x1C
        # Flash Addresses
        MFD_Start_AD_MSB = 0x00FF
        MFD_Start_AD_LSB = 0x0000
        MFD_MAX_RANGE = 512
        ListToWrite = [1, 0, 13] # special case MANU_MAP_ID
        for i in range(1, 14): # read the rest 
            for char in self.MFDValue[i].text():
                if char.isascii():
                    ListToWrite.append(ord(char))
            ListToWrite.append(13) # append CR after each word
        if (len(ListToWrite) % 2): # lenght is odd, we have to appent a 0
            ListToWrite.append(0)
        spi.activate_CS0_n(dev)
        # Flash erease
        self.writeBSAT(S_PORT, BSAT_CTRL0, 0x84, (RANGE_MFD << 4))  # erase Sequence 1
        self.writeBSAT(S_PORT, BSAT_CTRL0, 0x8B, (RANGE_MFD << 4))  # erase Sequence 2
        self.writeBSAT(S_PORT, BSAT_CTRL0, 0x36, (RANGE_MFD << 4))  # erase Sequence 3
        self.writeBSAT(S_PORT, BSAT_CTRL0, 0x4A, (RANGE_MFD << 4))  # erase Sequence 4
        self.writeBSAT(S_PORT, BSAT_CTRL0, 0xB6, (RANGE_MFD << 4))  # erase Sequence 5
        self.writeBSAT(S_PORT, BSAT_CTRL0, 0x4D, (RANGE_MFD << 4))  # erase Sequence 6
        self.writeBSAT(S_PORT, BSAT_CTRL0, 0x1B, (RANGE_MFD << 4))  # erase Sequence 7
        self.writeBSAT(S_PORT, BSAT_CTRL0, 0x00, (RANGE_MFD << 4) + (1 << 0))  # erase Request
        timeout = 5 # seconds
        timeout_start = time.time()
        while time.time() < timeout_start + timeout:
            nMode_1 = self.readBSAT(S_PORT, BSAT_MODE1)
            if (nMode_1 & 1 << 15): # erase done?
                break
        else: # erase timeout
            self.btnMFDWrite.setStyleSheet(self.RedLabel)
            spi.reset_CSx_n(dev)
            return
        self.writeBSAT(S_PORT, BSAT_CTRL0, 0x84, 0)  # Unlock Sequence 1
        self.writeBSAT(S_PORT, BSAT_CTRL0, 0x8B, 0)  # Unlock Sequence 2
        self.writeBSAT(S_PORT, BSAT_CTRL0, 0x36, 0)  # Unlock Sequence 3
        self.writeBSAT(S_PORT, BSAT_CTRL0, 0x4A, 0)  # Unlock Sequence 4
        self.writeBSAT(S_PORT, BSAT_CTRL0, 0xB6, 0)  # Unlock Sequence 5
        self.writeBSAT(S_PORT, BSAT_CTRL0, 0x4D, 0)  # Unlock Sequence 6
        self.writeBSAT(S_PORT, BSAT_CTRL0, 0x1B, 0)  # Unlock Sequence 7
        self.writeBSAT(S_PORT, BSAT_CTRL1, (1 << 6), 0)  # Unlock Request
        for i in range(0, len(ListToWrite), 2):
            if (i > MFD_MAX_RANGE):
                print('range error')
                break
            actual_AD_LSB = MFD_Start_AD_LSB + i
            self.writeBSAT(S_PORT, WR_AD_Flash_LSB, actual_AD_LSB // 256, actual_AD_LSB % 256)
            self.writeBSAT(S_PORT, WR_AD_Flash_MSB, MFD_Start_AD_MSB // 256, MFD_Start_AD_MSB % 256)
            self.writeBSAT(S_PORT, WR_AD_Flash_Data, ListToWrite[i], ListToWrite[i + 1])
        self.writeBSAT(S_PORT, BSAT_CTRL1, (1 << 7), 0)  # lock Request
        spi.reset_CSx_n(dev)

    def safeMFDFile(self):
        filename = QFileDialog.getSaveFileName(self, "Select File", "", "*.csv")
        if (filename[0]):
            textArray = []
            for i in range(1, 14): # read the textBoxes
                textArray.append(self.MFDValue[i].text())
            with open(filename[0], 'w') as csvfile:
                csvwriter = csv.writer(csvfile) # creating csv writer object
                csvwriter.writerow(textArray) # write data row

    def loadMFDFile(self):
        filename = QFileDialog.getOpenFileName(self, "Select File", "", "*.csv")
        if (filename[0]):
            with open(filename[0]) as csvfile:
                csv_reader_object = csv.reader(csvfile)
                textArray = next(csv_reader_object) # read only the first line
            for i in range(len(textArray)):
                if (i < 14): # should not, only to avoid errors
                    self.MFDValue[i + 1].setText(textArray[i])
            

    def downloadFirmware(self, sys):
        self.rpdStartButton.setStyleSheet(self.OrgLabel)
        if (self.rpdFileName[0]):
            self.updateTimer.stop() # no port read during FW download
            # ****** Erase Section ******
            spi.activate_CS0_n(dev)
            self.writeBSAT(S_PORT, BSAT_CTRL0, 0xFF, (sys << 4))  # Erase Sequence 1
            self.writeBSAT(S_PORT, BSAT_CTRL0, 0xDA, (sys << 4))  # Erase Sequence 2
            self.writeBSAT(S_PORT, BSAT_CTRL0, 0x91, (sys << 4))  # Erase Sequence 3
            self.writeBSAT(S_PORT, BSAT_CTRL0, 0x20, (sys << 4))  # Erase Sequence 4
            self.writeBSAT(S_PORT, BSAT_CTRL0, 0xC0, (sys << 4))  # Erase Sequence 5
            self.writeBSAT(S_PORT, BSAT_CTRL0, 0x87, (sys << 4))  # Erase Sequence 6
            self.writeBSAT(S_PORT, BSAT_CTRL0, 0xAA, (sys << 4))  # Erase Sequence 7
            self.writeBSAT(S_PORT, BSAT_CTRL0, 0x00, (sys << 4) + (1 << 0))  # Erase Request
            timeout = 5 # seconds
            timeout_start = time.time()
            while time.time() < timeout_start + timeout:
                nMode_1 = self.readBSAT(S_PORT, BSAT_MODE1)
                if (nMode_1 & 1 << 15): # erase done?
                    break
            else: # erase timeout
                self.rpdStartButton.setStyleSheet(self.RedLabel)
                self.updateTimer.start(100)
                spi.reset_CSx_n(dev)
                return
            # ****** Download Section ******
            rpdDlBarAct = 0
            rpdDlBarMax = (os.stat(self.rpdFileName[0]).st_size) # get download file size in bytes
            with open(self.rpdFileName[0], 'rb') as in_file:
                while True:
                    fifoHalf = self.readBSAT(BUS_CTRL,0) #check if SPort fifo is less than half full
                    fifoHalf &= 0x0001
                    if (not fifoHalf):
                        for i in range(1000): # we have at least 1k free fifo
                            self.rpdDlBar.setValue(int(100 / rpdDlBarMax * rpdDlBarAct))
                            rpdDlBarAct += 2 # we write 2 bytes at a time
                            byte = in_file.read(2)
                            if len(byte) == 0: # all written
                                break
                            self.writeBSAT(S_PORT, BSAT_WR_DL_ADDR, byte[0], byte[1])  # Firmware Download
                        if len(byte) == 0: # all written
                            break
            self.writeBSAT(S_PORT, BSAT_CTRL0, 0x00, (sys << 4) + (1 << 3))  # Download Data End
            timeout = 5 # seconds
            timeout_start = time.time()
            while time.time() < timeout_start + timeout:
                nMode_1 = self.readBSAT(S_PORT, BSAT_MODE1)
                if (nMode_1 & 1 << 14): # download done?
                    break
            else: # prog timeout
                self.rpdStartButton.setStyleSheet(self.RedLabel)
                spi.reset_CSx_n(dev)
                self.updateTimer.start(100)
                return
            # ****** Reboot Section ******
            self.writeBSAT(S_PORT, BSAT_CTRL0, 0x91, 0)  # Reboot Sequence 1
            self.writeBSAT(S_PORT, BSAT_CTRL0, 0x20, 0)  # Reboot Sequence 2
            self.writeBSAT(S_PORT, BSAT_CTRL0, 0xC0, 0)  # Reboot Sequence 3
            self.writeBSAT(S_PORT, BSAT_CTRL0, 0x87, 0)  # Reboot Sequence 4
            self.writeBSAT(S_PORT, BSAT_CTRL0, 0xAA, 0)  # Reboot Sequence 5
            self.writeBSAT(S_PORT, BSAT_CTRL0, 0xF1, 0)  # Reboot Sequence 6
            self.writeBSAT(S_PORT, BSAT_CTRL0, 0x60, 0)  # Reboot Sequence 7
            self.writeBSAT(S_PORT, BSAT_CTRL0, 0x60, 0 + (1 << 1))  # Reboot !
            spi.reset_CSx_n(dev)
            time.sleep(1) # wait for reboot
            self.rpdStartButton.setStyleSheet(self.GreenLabel)
            self.getSlaveInfo() # update slave information
            self.updateTimer.start(100)
        else:
            self.rpdLblFileName.setText("select rpd File first !")


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main = Usb2Bsat()
    main.show()
    sys.exit(app.exec_())
