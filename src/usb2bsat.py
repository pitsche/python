#!/usr/bin/env python

import sys
import os
import time
import csv
import u2b_base as u2b
from PyQt5.QtWidgets import (QApplication, QWidget, QCheckBox, QPushButton, QRadioButton, QButtonGroup, QProgressBar,\
                             QHBoxLayout, QVBoxLayout, QGridLayout, QGroupBox, QLabel, QFileDialog, QLineEdit, QTextEdit)
from PyQt5.QtGui import (QIcon, QPixmap, QIntValidator)
from PyQt5.QtCore import QTimer, pyqtSignal, Qt


# Other Constants
WR = 1
RD = 0
 # BSAT_Memory_Map
BSAT_UID0 = 2
BSAT_UID1 = 3
BSAT_MODE0 = 14
BSAT_MODE1 = 15
BSAT_CTRL0 = 16
BSAT_CTRL1 = 17
BSAT_WR_DL_ADDR = 27
BSAT_HID_STATUS = 60
BSAT_HID_PORT_0 = 61
BSAT_HID_PORT_1 = 62
BSAT_HID_MASK_0 = 63
BSAT_HID_MASK_1 = 64
BSAT_NODE_ERR_MASK = 67
BSAT_PORT_STATUS = [68, 73] # for Port [0, 1]
BSAT_ERR_PORT_0 = [69, 74] # errors 15..0
BSAT_ERR_PORT_1 = [70, 75] # errors 15..0
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
dev = u2b.openFTDI()

class HIDWindow(QWidget):

    def __init__(self, dev, slv):
        super().__init__()
        self.setGeometry(400, 400, 400, 200)
        self.setWindowTitle('HIDs')
        self.setWindowIcon(QIcon(u2b.resource_path('besi.png')))
        self.GreenLedOn = QPixmap(u2b.resource_path('green-led-on.png')).scaledToWidth(20)
        self.LedOff = QPixmap(u2b.resource_path('led-off.png')).scaledToWidth(20)
        self.createHIDBox(dev, slv)

        layout = QGridLayout()
        layout.addWidget(self.HIDBox, 0, 0, 1, 1)
        self.setLayout(layout)

    def createHIDBox(self, dev, slv):
        self.HIDBox = QGroupBox(f'HID Slave: {slv}')
        # get HID's from actual slave
        u2b.activate_CS0_n(dev)
        numOfHID = u2b.readSPort(dev, slv, BSAT_HID_STATUS) & 0x00FF
        actHID0 = u2b.readSPort(dev, slv, BSAT_HID_PORT_0)
        actHID1 = u2b.readSPort(dev, slv, BSAT_HID_PORT_1)
        actHID = actHID0 + (actHID1 * 2 ** 16) # maximum of 32 HID's per Slave
        u2b.reset_CSx_n(dev)

        layout = QGridLayout()
        layout.setAlignment(Qt.AlignCenter)
        self.lblHID = [None] * numOfHID
        lblBit = {}
        for i in range(numOfHID):
            # Rx line
            self.lblHID[i] = QLabel()
            if (actHID & 1 << i):
                self.lblHID[i].setPixmap(self.GreenLedOn)
            else:
                self.lblHID[i].setPixmap(self.LedOff)

            self.lblHID[i].setAlignment(Qt.AlignCenter)
            layout.addWidget(self.lblHID[i], 0, numOfHID - 1 - i)  # place lblHID to grid pos
            # Bit number
            lblBit[i] = QLabel(f'{numOfHID -1 - i}')
            lblBit[i].setAlignment(Qt.AlignCenter)
            layout.addWidget(lblBit[i], 1, i)
        self.HIDBox.setLayout(layout)


class errorWindow(QWidget):

    def __init__(self, dev, slv, port):
        super().__init__()
        self.setGeometry(300, 300, 400, 200)
        self.setWindowTitle('Port Errors')
        self.setWindowIcon(QIcon(u2b.resource_path('besi.png')))
        self.RedLedOn = QPixmap(u2b.resource_path('red-led-on.png')).scaledToWidth(20)
        self.LedOff = QPixmap(u2b.resource_path('led-off.png')).scaledToWidth(20)
        self.createErrorBox(dev, slv, port)

        layout = QGridLayout()
        layout.addWidget(self.errorBox, 0, 0, 1, 1)
        self.setLayout(layout)

    def createErrorBox(self, dev, slv, port):
        self.errorBox = QGroupBox(f'Errors Port {port}')
        # get errors from actual port
        u2b.activate_CS0_n(dev)
        numOfErr = u2b.readSPort(dev, slv, BSAT_PORT_STATUS[port]) & 0x003F
        actErr0 = u2b.readSPort(dev, slv, BSAT_ERR_PORT_0[port])
        actErr1 = u2b.readSPort(dev, slv, BSAT_ERR_PORT_1[port])
        actErr = actErr0 + (actErr1 * 2 ** 16) # maximum of 32 Errors per port
        u2b.reset_CSx_n(dev)

        layout = QGridLayout()
        layout.setAlignment(Qt.AlignCenter)
        self.lblErr = [None] * numOfErr
        lblBit = {}
        for i in range(numOfErr):
            # Rx line
            self.lblErr[i] = QLabel()
            if (actErr & 1 << i):
                self.lblErr[i].setPixmap(self.RedLedOn)
            else:
                self.lblErr[i].setPixmap(self.LedOff)

            self.lblErr[i].setAlignment(Qt.AlignCenter)
            layout.addWidget(self.lblErr[i], 0, numOfErr - 1 - i)  # place lblErr to grid pos
            # Bit number
            lblBit[i] = QLabel(f'{numOfErr -1 - i}')
            lblBit[i].setAlignment(Qt.AlignCenter)
            layout.addWidget(lblBit[i], 1, i)
        # Reset Button
        self.resetButton = QPushButton('Reset')
        self.resetButton.clicked.connect(lambda: self.resetErr(dev, slv, port, numOfErr))
        layout.addWidget(self.resetButton, 0, numOfErr)
        self.errorBox.setLayout(layout)

    def resetErr(self, dev, slv, port, numOfErr):
        # write 0 to error ports
        u2b.activate_CS0_n(dev)
        u2b.writeSPort(dev, slv, BSAT_ERR_PORT_0[port], 0x000) 
        u2b.writeSPort(dev, slv, BSAT_ERR_PORT_1[port], 0x000)
        # re-read port errors 
        actErr0 = u2b.readSPort(dev, slv, BSAT_ERR_PORT_0[port])
        actErr1 = u2b.readSPort(dev, slv, BSAT_ERR_PORT_1[port])
        actErr = actErr0 + (actErr1 * 2 ** 16) # maximum of 32 Errors per port
        u2b.reset_CSx_n(dev)
        # update led status
        for i in range(numOfErr):
            # Rx line
            if (actErr & 1 << i):
                self.lblErr[i].setPixmap(self.RedLedOn)
            else:
                self.lblErr[i].setPixmap(self.LedOff)


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
        self.setWindowIcon(QIcon(u2b.resource_path('besi.png')))

        self.RedLabel = '''color: white; background-color: red;'''
        self.GreenLabel = '''color: white; background-color: green;'''
        self.OrgLabel = '''color: black; background-color: light grey;'''
        self.GreenLedOn = QPixmap(u2b.resource_path('green-led-on.png')).scaledToWidth(20)
        self.LedOff = QPixmap(u2b.resource_path('led-off.png')).scaledToWidth(20)

        #some projektwide used variables
        self.slv = 0 # actual slave number
        self.numOfPorts = 2
        self.lblRx = [None] * 64  # create list. used to display Port LED's
        self.btnTx = [None] * 64  
        self.errorButton = [None] * 2
        self.updateButton = [None] * 2
        self.port_tx = [[0, 0, 0, 0], [0, 0, 0, 0]] # 2 * (4*8bit) array to transmitt
        self.MFDDataMap = ['Map ID', 'Board Number', 'Board Index', 'Board Name', 'Board ID', 'Supplier Lot', 'Supplier Name', \
                           'Date of manufacture', 'Configuration', 'Test Location', 'FPGA Design Number', 'Test Date', 'Board History', 'Test ID']
        self.MFDValue = [None] * 14
        self.popUpWin = None

        self.bsatPwrCheckBox = QCheckBox('&BSAT Power    Slv: ')
        self.bsatPwrCheckBox.toggled.connect(self.changePower)
        self.slvRBtn = {}
        self.slvBtnGrp = QButtonGroup()
        for i in range(8):
            self.slvRBtn[i] = 0

        self.lblBlank = QLabel(' ')
        self.btnHID = QPushButton("HID")
        self.btnHID.clicked.connect(self.HIDPort)

        self.createInfoGroupBox()
        self.createUserPortGroupBox()
        self.portGroupBox = {}
        for i in range(self.numOfPorts):
            self.createPortGroupBox(i)
            self.createPortGroupBox(i)
        self.createDownloadGroupBox()
        self.createMFDGroupBox()

        self.topLayout = QHBoxLayout()
        self.topLayout.addWidget(self.bsatPwrCheckBox, )
 
        mainLayout = QGridLayout()
        mainLayout.addLayout(self.topLayout, 0, 0, 1, 3,)
        mainLayout.addWidget(self.infoGroupBox, 1, 0, 1, 1)
        mainLayout.addWidget(self.userPortGroupBox, 1, 1, 1, 2)
        mainLayout.addWidget(self.portGroupBox[0], 2, 0, 1, 3)
        mainLayout.addWidget(self.portGroupBox[1], 3, 0, 1, 3)
        mainLayout.addWidget(self.downloadGroupBox, 4, 0, 1, 3)
        mainLayout.addWidget(self.MFDGroupBox, 5, 0, 1, 3)
        self.setLayout(mainLayout)

        # setup timer to update BSAT Ports
        self.updateTimer = QTimer()
        self.updateTimer.timeout.connect(self.readWritePorts)


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
        self.updateButton[port].clicked.connect(lambda: self.updatePortTx(port))
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
            self.scanBsat()
            self.updateTimer.start(100)
        else:
            self.updateTimer.stop()
            u2b.activate_CS0_n(dev)
            u2b.write_cmd_bytes(dev, 0x11, [0, 0, 0, 0, 0, 0, 0, 0])  # CMD_OUT all 0 
            u2b.reset_CSx_n(dev)
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
        self.topLayout.removeWidget(self.lblBlank)
        self.topLayout.removeWidget(self.btnHID)
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
        self.topLayout.addWidget(self.lblBlank, 1)
        self.topLayout.addWidget(self.btnHID)

    def setSlave(self):
        rBtn = self.sender()
        if rBtn.isChecked():
            self.slv = int(rBtn.text())
            self.getSlaveInfo()

    def scanBsat(self):
        u2b.activate_CS0_n(dev)
        u2b.busCtrl(dev, WR, 0x0002) # disable continous autoscan, reset rescan bit (0)
        u2b.busCtrl(dev, WR, 0xF003) # max scandelay, initialize rescan
        u2b.busCtrl(dev, WR, 0x0002) # disable continous autoscan, reset rescan bit (0)
        rx = [0, 0, 0, 0, 0, 0, 0, 0]
        timeout = 2 # seconds
        timeout_start = time.time()
        while time.time() < timeout_start + timeout:
            rx = u2b.busCtrl(dev, RD, 0)
            if (rx[4] & 1 << 3):  # scan done?
                break
        else: # scan timeout
            print('scan timeout')
        u2b.reset_CSx_n(dev)
        self.createSlaveButtons(rx[5])

    def getSlaveInfo(self):
        brdType = ""
        brdNmbr = ""
        mem = []
        u2b.activate_CS0_n(dev)
        for i in range(16):  # read memory
            word = u2b.readSPort(dev, self.slv, BSAT_BOARD_TYPE + i)
            hByte = word >> 8
            lByte = word & 0x00FF
            mem.append(hByte)
            mem.append(lByte)
        nodeInfo = u2b.readSPort(dev, self.slv, BSAT_NODE_INFO)
        if (nodeInfo & 1 << 0):
            self.valSysInfo.setText('Auxiliary')
        else:
            self.valSysInfo.setText('Standard')
        self.numOfPorts = (nodeInfo & 0x00F0) // 16 # upper 4 bits
        self.valPorts.setText(f'{self.numOfPorts}')
        uID_0 = u2b.readSPort(dev, self.slv, BSAT_UID0)
        featureID = uID_0 & 0x00FF
        self.valFeature.setText(f'{featureID}')
        uID_1 = u2b.readSPort(dev, self.slv, BSAT_UID1)
        bugFix = uID_1 >> 8
        self.valBugfix.setText(f'{bugFix}')
        u2b.reset_CSx_n(dev)
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
        u2b.activate_CS0_n(dev)
        rx = u2b.readSPort(dev, self.slv, BSAT_MODE1)
        if (rx & 1 << 2): #outputs are disabled
            u2b.writeSPort(dev, self.slv, BSAT_CTRL1, 0x0000) # set all bits 0 on S-Port address 0x11
            u2b.writeSPort(dev, self.slv, BSAT_CTRL1, 0x0008)  # NodeEnable
            u2b.writeSPort(dev, self.slv, BSAT_CTRL1, 0x000C)  # IdSuccessful
            u2b.writeSPort(dev, self.slv, BSAT_CTRL1, 0x000E)  # ScanDone
        u2b.writeSPort(dev, self.slv, BSAT_HID_MASK_0, 0xFFFF) # start writing S-Port Mask defaults
        u2b.writeSPort(dev, self.slv, BSAT_HID_MASK_1, 0xFFFF)
        u2b.writeSPort(dev, self.slv, BSAT_NODE_ERR_MASK, 0xFFFF)
        u2b.writeSPort(dev, self.slv, BSAT_ERR_MASK_PORT_0_0, 0xFFFF)
        u2b.writeSPort(dev, self.slv, BSAT_ERR_MASK_PORT_0_1, 0xFFFF)
        u2b.writeSPort(dev, self.slv, BSAT_ERR_MASK_PORT_1_0, 0xFFFF)
        u2b.writeSPort(dev, self.slv, BSAT_ERR_MASK_PORT_1_1, 0xFFFF) # end writing S-Port Mask defaults
        u2b.reset_CSx_n(dev)

    def setSys(self):
        rBtn = self.sender()
        if rBtn.isChecked():
            if rBtn.text() == "Auxiliary Sys":
                self.sys = RANGE_AUX
            else:
                self.sys = RANGE_STD

    def readRpd(self):
        self.rpdFileName = QFileDialog.getOpenFileName(self, "Select File", "", "*.rpd")
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

    def errorPort(self, port): # calls the error window
        self.popErrWin = errorWindow(dev, self.slv, port)
        self.popErrWin.show()

    def HIDPort(self, port): # calls the HID window
        self.popHIDWin = HIDWindow(dev, self.slv)
        self.popHIDWin.show()

    def updatePortTx(self, port): # sets the flag that the corresponding port must be written
        self.port_tx[port] = [0, 0, 0, 0]
        for i in range(4): # bytes
            for j in range(8): # bites
                if self.btnTx[j + (i * 8) + (port * 32)].isChecked():
                    self.port_tx[port][i] += (2 ** j)

    def readWritePorts(self):
        port_rec = u2b.updatePorts(dev, self.slv, self.port_tx[0], self.port_tx[1])
        self.updatePortGui(port_rec[0], port_rec[1])

    def updatePortGui(self, rx0_1, sumErr):
        for i in range(self.numOfPorts):
            if (sumErr & 1 << (self.slv * 2 + i)): #sumErr on actSlv actPort
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
                u2b.activate_CS0_n(dev)
                mem = ""
                for i in range(int(self.numOfWords.text())):
                    rx = u2b.readSPort(dev, self.slv, int(self.startAddr.text()) + i)
                    word = f"{(rx):0{4}X} "  # convert to '01C3 '
                    mem += word  # add to string
                self.sPortDisply.setText(mem)
                u2b.reset_CSx_n(dev)
            else:
                self.sPortDisply.setText('enter number of words')
        else:
            self.sPortDisply.setText('enter start Address')

    def writeMem(self):
        if (self.startAddr.text()):
            if (self.sPortDisply.toPlainText()):
                mem = self.sPortDisply.toPlainText().split()
                u2b.activate_CS0_n(dev)
                for i in range(len(mem)):
                    word_int = int(mem[i], 16)
                    u2b.writeSPort(dev, self.slv, int(self.startAddr.text()) + i, word_int)
                u2b.reset_CSx_n(dev)
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
        u2b.activate_CS0_n(dev)
        for i in range(0, MFD_MAX_RANGE, 2): # read only every second address
            actual_AD_LSB = MFD_Start_AD_LSB + i
            u2b.writeSPort(dev, self.slv, RD_AD_Flash_LSB, actual_AD_LSB)
            u2b.writeSPort(dev, self.slv, RD_AD_Flash_MSB, MFD_Start_AD_MSB)
            word = u2b.readSPort(dev, self.slv, RD_AD_Flash_Data)
            if (word == 0xFFFF): # all read
                break
            hByte = word >> 8
            lByte = word & 0x00FF
            mem.append(hByte)
            mem.append(lByte)
        u2b.reset_CSx_n(dev)
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
        u2b.activate_CS0_n(dev)
        # Flash erease
        u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x8400 + (RANGE_MFD << 4))  # erase Sequence 1
        u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x8B00 + (RANGE_MFD << 4))  # erase Sequence 2
        u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x3600 + (RANGE_MFD << 4))  # erase Sequence 3
        u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x4A00 + (RANGE_MFD << 4))  # erase Sequence 4
        u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0xB600 + (RANGE_MFD << 4))  # erase Sequence 5
        u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x4D00 + (RANGE_MFD << 4))  # erase Sequence 6
        u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x1B00 + (RANGE_MFD << 4))  # erase Sequence 7
        u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x0000 + (RANGE_MFD << 4) + (1 << 0))  # erase Request
        timeout = 5 # seconds
        timeout_start = time.time()
        while time.time() < timeout_start + timeout:
            nMode_1 = u2b.readSPort(dev, self.slv, BSAT_MODE1)
            if (nMode_1 & 1 << 15): # erase done?
                break
        else: # erase timeout
            self.btnMFDWrite.setStyleSheet(self.RedLabel)
            u2b.reset_CSx_n(dev)
            return
        u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x8400)  # Unlock Sequence 1
        u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x8B00)  # Unlock Sequence 2
        u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x3600)  # Unlock Sequence 3
        u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x4A00)  # Unlock Sequence 4
        u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0xB600)  # Unlock Sequence 5
        u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x4D00)  # Unlock Sequence 6
        u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x1B00)  # Unlock Sequence 7
        u2b.writeSPort(dev, self.slv, BSAT_CTRL1, 1 << 14)  # Unlock Request
        for i in range(0, len(ListToWrite), 2):
            if (i > MFD_MAX_RANGE):
                print('range error')
                break
            actual_AD_LSB = MFD_Start_AD_LSB + i
            u2b.writeSPort(dev, self.slv, WR_AD_Flash_LSB, actual_AD_LSB)
            u2b.writeSPort(dev, self.slv, WR_AD_Flash_MSB, MFD_Start_AD_MSB)
            u2b.writeSPort(dev, self.slv, WR_AD_Flash_Data, ListToWrite[i] * (2**8) + ListToWrite[i + 1])
        u2b.writeSPort(dev, self.slv, BSAT_CTRL1, 1 << 15)  # lock Request
        u2b.reset_CSx_n(dev)

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
            u2b.activate_CS0_n(dev)
            u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0xFF00 + (sys << 4))  # Erase Sequence 1
            u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0xDA00 + (sys << 4))  # Erase Sequence 2
            u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x9100 + (sys << 4))  # Erase Sequence 3
            u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x2000 + (sys << 4))  # Erase Sequence 4
            u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0xC000 + (sys << 4))  # Erase Sequence 5
            u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x8700 + (sys << 4))  # Erase Sequence 6
            u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0xAA00 + (sys << 4))  # Erase Sequence 7
            u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x0000 + (sys << 4) + (1 << 0))  # Erase Request
            timeout = 5 # seconds
            timeout_start = time.time()
            while time.time() < timeout_start + timeout:
                nMode_1 = u2b.readSPort(dev, self.slv, BSAT_MODE1)
                if (nMode_1 & 1 << 15): # erase done?
                    break
            else: # erase timeout
                self.rpdStartButton.setStyleSheet(self.RedLabel)
                self.updateTimer.start(100)
                u2b.reset_CSx_n(dev)
                return
            # ****** Download Section ******
            rpdDlBarAct = 0
            rpdDlBarMax = (os.stat(self.rpdFileName[0]).st_size) # get download file size in bytes
            rnd = 0
            with open(self.rpdFileName[0], 'rb') as in_file:
                while True:
                    busCtrl = u2b.busCtrl(dev, RD, 0) #check if SPort fifo is less than half full
                    fifoHalf = busCtrl[7] & 0x01
                    if (not fifoHalf):
                        rnd += 1
                        for i in range(2000): # we have at least 2k free fifo
                            self.rpdDlBar.setValue(int(100 / rpdDlBarMax * rpdDlBarAct))
                            rpdDlBarAct += 2 # we write 2 bytes at a time
                            byte = in_file.read(2)
                            if len(byte) == 0: # all written
                                break
                            u2b.writeSPort(dev, self.slv, BSAT_WR_DL_ADDR, byte[0] * (2**8 ) + byte[1])  # Firmware Download
                        if len(byte) == 0: # all written
                            break
            print(rnd)
            u2b.writeSPort(dev, self.slv, BSAT_CTRL0, (sys << 4) + (1 << 3))  # Download Data End
            timeout = 5 # seconds
            timeout_start = time.time()
            while time.time() < timeout_start + timeout:
                nMode_1 = u2b.readSPort(dev, self.slv, BSAT_MODE1)
                if (nMode_1 & 1 << 14): # download done?
                    break
            else: # prog timeout
                self.rpdStartButton.setStyleSheet(self.RedLabel)
                u2b.reset_CSx_n(dev)
                self.updateTimer.start(100)
                return
            # ****** Reboot Section ******
            u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x9100)  # Reboot Sequence 1
            u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x2000)  # Reboot Sequence 2
            u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0xC000)  # Reboot Sequence 3
            u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x8700)  # Reboot Sequence 4
            u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0xAA00)  # Reboot Sequence 5
            u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0xF100)  # Reboot Sequence 6
            u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x6000)  # Reboot Sequence 7
            u2b.writeSPort(dev, self.slv, BSAT_CTRL0, 0x6000 + (1 << 1))  # Reboot !
            u2b.reset_CSx_n(dev)
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
