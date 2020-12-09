#!/usr/bin/env python

import u2b_spi as spi
import sys
import os
import time
from PyQt5.QtWidgets import (QApplication, QPushButton, QWidget, QCheckBox, QRadioButton, QProgressBar, QHBoxLayout, QVBoxLayout, QGridLayout, QGroupBox, QLabel, QFileDialog)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QTimer, pyqtSignal, Qt



# FTDI Command Processor for MPSSE (FTDI AN-108)
CMD_OUT = 0x11  # Clock Data Bytes Out on -ve clock edge MSB first (no read)
CMD_IN = 0x22  # Clock Data Bits In on +ve clock edge MSB first (no write)
CMD_INOUT = 0x31  # out on -ve edge, in on +ve edge

# Other Constants
STD = (2 << 4)
AUX = (1 << 4)
 # BSAT_Memory_Map
BSAT_UID0 = 2
BSAT_UID1 = 3
BSAT_MODE0 = 14
BSAT_MODE1 = 15
BSAT_CTRL0 = 16
BSAT_CTRL1 = 17
BSAT_WR_DL_ADDR = 27
BSAT_BOARD_TYPE = 83
BSAT_NODE_INFO = 99

dev =spi.openFTDI()


class DownloadApp(QWidget):

    def __init__(self):
        super().__init__()
        self.title = 'USB2BSAT Firmware downloader'
        self.left = 100
        self.top = 100
        self.width = 550
        self.hight = 200
        self.initUI()

    def initUI(self):
        self.RedLabel = '''color: white; background-color: red;'''
        self.GreenLabel = '''color: white; background-color: green;'''
        self.OrgLabel = '''color: black; background-color: light grey;'''

        self.setGeometry(self.left, self.top, self.width, self.hight)
        self.setWindowTitle(self.title)
        self.setWindowIcon(QIcon(self.resource_path('besi.png')))
        
        self.createInfoGroupBox()
        self.createDLGroupBox()
    
        mainLayout = QGridLayout()
        mainLayout.addWidget(self.InfoGroupBox, 1, 0, 1, 1)
        mainLayout.addWidget(self.DLGroupBox, 2, 0, 1, 1)
        mainLayout.setRowStretch(1, 1)
        mainLayout.setColumnStretch(0, 1)
        self.setLayout(mainLayout)

        self.updateInfo()

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)
        
    def createInfoGroupBox(self):
        self.InfoGroupBox = QGroupBox('USB2BSAT Firmware Information')
        layout = QGridLayout()
        lblBrdType = QLabel('Type:')
        lblBrdNmbr = QLabel('Number:')
        lblSysInfo = QLabel('System:')
        lblFeature = QLabel('FeatureID:')
        lblBugfix  = QLabel('BugfixID:')
        self.valBrdType = QLabel()
        self.valBrdNmbr = QLabel()
        self.valSysInfo = QLabel()
        self.valFeature = QLabel()
        self.valBugfix = QLabel()
        self.valPorts = QLabel()
        updateButton = QPushButton("update")
        updateButton.clicked.connect(self.updateInfo)
        layout.addWidget(lblBrdType, 0, 0)
        layout.addWidget(lblBrdNmbr, 1, 0)
        layout.addWidget(lblSysInfo, 2, 0)
        layout.addWidget(lblFeature, 3, 0)
        layout.addWidget(lblBugfix, 4, 0)
        layout.addWidget(self.valBrdType, 0, 1)
        layout.addWidget(self.valBrdNmbr, 1, 1)
        layout.addWidget(self.valSysInfo, 2, 1)
        layout.addWidget(self.valFeature, 3, 1)
        layout.addWidget(self.valBugfix, 4, 1)
        layout.setColumnStretch(2, 1)
        layout.addWidget(updateButton, 0, 3)
        self.InfoGroupBox.setLayout(layout)

    def createDLGroupBox(self):
        self.DLGroupBox = QGroupBox('Download to USB2BSAT')
        layout = QGridLayout()
        self.rpdFileName = [0]
        self.sys = STD  # default

        self.radioButton1 = QRadioButton("Standard Sys")
        self.radioButton2 = QRadioButton("Auxiliary Sys")
        self.radioButton1.setChecked(True)
        self.radioButton1.toggled.connect(self.setSys)
        self.radioButton2.toggled.connect(self.setSys)

        self.rpdGetFileButton = QPushButton("File: ")
        self.rpdGetFileButton.clicked.connect(self.readRpd)
        self.rpdLblFileName = QLabel()
        self.rpdStartButton = QPushButton("Start")
        self.rpdStartButton.clicked.connect(lambda: self.downloadSelf(self.sys))
        self.rpdDlBar = QProgressBar()
        self.rpdDlBar.setRange(0,100)
        layout.addWidget(self.radioButton1, 0, 0)
        layout.addWidget(self.radioButton2, 0, 1)
        layout.addWidget(self.rpdGetFileButton, 1, 0)
        layout.addWidget(self.rpdLblFileName, 1, 1)
        layout.addWidget(self.rpdStartButton, 2, 0)
        layout.addWidget(self.rpdDlBar, 2, 1)
        self.DLGroupBox.setLayout(layout)

    def setSys(self):
        rBtn = self.sender()
        if rBtn.isChecked():
            if rBtn.text() == "Auxiliary Sys":
                self.sys = AUX
            else:
                self.sys = STD

    def readRpd(self):
        self.rpdFileName = QFileDialog.getOpenFileName(self, "Select File", "", "*.rpd")
        if (self.rpdFileName[0]):
            head, tail = os.path.split(self.rpdFileName[0])
            self.rpdLblFileName.setText(tail)

    def readSPort(self, addr): # returns integer value of 16bit
        spi.write_cmd_bytes(dev, CMD_OUT, [addr, 0, 0]) # set Address
        spi.write_cmd_bytes(dev, CMD_INOUT, [addr, 0, 0]) # read Address
        rx = spi.read(dev, 3)
        return(rx[1] * (2**8) + rx[2])

    def writeSPort(self, addr, hByte, lByte):
        spi.write_cmd_bytes(dev, CMD_OUT, [addr, hByte, lByte]) # set Address

    def updateInfo(self):
        brdType = ""
        brdNmbr = ""
        mem = []
        spi.activate_CS1_n(dev)
        for i in range(16):  # read memory
            word = self.readSPort(BSAT_BOARD_TYPE + i)
            hByte = word >> 8
            lByte = word & 0x00FF
            mem.append(hByte)
            mem.append(lByte)
        nodeInfo = self.readSPort(BSAT_NODE_INFO)
        if (nodeInfo & 1 << 0):
            self.valSysInfo.setText('Auxiliary')
        else:
            self.valSysInfo.setText('Standard')
        self.numOfPorts = (nodeInfo & 0x00F0) // 16 # upper 4 bits
        self.valPorts.setText(f'{self.numOfPorts}')
        uID_0 = self.readSPort(BSAT_UID0)
        featureID = uID_0 & 0x00FF
        self.valFeature.setText(f'{featureID}')
        uID_1 = self.readSPort(BSAT_UID1)
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
 

    def downloadSelf(self, sys):
        self.rpdStartButton.setStyleSheet(self.OrgLabel)
        if (self.rpdFileName[0]):
            spi.activate_CS1_n(dev)
            # ****** Erase Section ******
            self.writeSPort(BSAT_CTRL0, 0xFF, sys)  # Erase Sequence 1
            self.writeSPort(BSAT_CTRL0, 0xDA, sys)  # Erase Sequence 2
            self.writeSPort(BSAT_CTRL0, 0x91, sys)  # Erase Sequence 3
            self.writeSPort(BSAT_CTRL0, 0x20, sys)  # Erase Sequence 4
            self.writeSPort(BSAT_CTRL0, 0xC0, sys)  # Erase Sequence 5
            self.writeSPort(BSAT_CTRL0, 0x87, sys)  # Erase Sequence 6
            self.writeSPort(BSAT_CTRL0, 0xAA, sys)  # Erase Sequence 7
            self.writeSPort(BSAT_CTRL0, 0xAA, sys + (1 << 0))  # Erase Request
            timeout = 5 # seconds
            timeout_start = time.time()
            while time.time() < timeout_start + timeout:
                nMode_1 = self.readSPort(BSAT_MODE1)
                if (nMode_1 & 1 << 15): # erase done?
                    break
            else: # erase timeout
                self.rpdStartButton.setStyleSheet(self.RedLabel)
                spi.reset_CSx_n(dev)
                return
            # ****** Download Section ******
            dl_prog = 0
            rpdDlBarMax = (os.stat(self.rpdFileName[0]).st_size) # get download file size in bytes
            with open(self.rpdFileName[0], 'rb') as in_file:
                while True:
                    rpdDlBarAct = dl_prog
                    self.rpdDlBar.setValue(int(100 / rpdDlBarMax * rpdDlBarAct))
                    dl_prog += 2 # we write 2 bytes at a time
                    byte = in_file.read(2)
                    if len(byte) == 0: # all written
                        break
                    self.writeSPort(BSAT_WR_DL_ADDR, byte[0], byte[1])  # Firmware Download
            self.writeSPort(BSAT_CTRL0, 0x00, sys + (1 << 3))  # Download Data End
            timeout_start = time.time()
            while time.time() < timeout_start + timeout:
                nMode_1 = self.readSPort(BSAT_MODE1)
                if (nMode_1 & 1 << 14): # download done?
                    break
            else: # prog timeout
                self.rpdStartButton.setStyleSheet(self.RedLabel)
                spi.reset_CSx_n(dev)
                return
            # ****** Reboot Section ******
            self.writeSPort(BSAT_CTRL0, 0x91, sys)  # Reboot Sequence 1
            self.writeSPort(BSAT_CTRL0, 0x20, sys)  # Reboot Sequence 2
            self.writeSPort(BSAT_CTRL0, 0xC0, sys)  # Reboot Sequence 3
            self.writeSPort(BSAT_CTRL0, 0x87, sys)  # Reboot Sequence 4
            self.writeSPort(BSAT_CTRL0, 0xAA, sys)  # Reboot Sequence 5
            self.writeSPort(BSAT_CTRL0, 0xF1, sys)  # Reboot Sequence 6
            self.writeSPort(BSAT_CTRL0, 0x60, sys)  # Reboot Sequence 7
            self.writeSPort(BSAT_CTRL0, 0x00, sys + (1 << 1))  # Reboot !
            spi.reset_CSx_n(dev)
            time.sleep(1) # wait for reboot
            self.rpdStartButton.setStyleSheet(self.GreenLabel)
            self.updateInfo
        else:
            self.rpdLblFileName.setText("select rpd File first !")



if __name__ == '__main__':
    app = QApplication(sys.argv)
    dlApp = DownloadApp()
    dlApp.show()
    sys.exit(app.exec_())
