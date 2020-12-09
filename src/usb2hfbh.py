#!/usr/bin/env python

import sys
import os
import time
import u2b_spi as spi
import ftd2xx as ftd  # usb
from PyQt5.QtWidgets import (QApplication, QWidget, QCheckBox, QProgressBar, QHBoxLayout, QVBoxLayout, QGridLayout, QGroupBox, QLabel)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QTimer, pyqtSignal, Qt

# FTDI Command Processor for MPSSE (FTDI AN-108)
CMD_OUT = 0x11  # Clock Data Bytes Out on -ve clock edge MSB first (no read)
CMD_IN = 0x22  # Clock Data Bits In on +ve clock edge MSB first (no write)
CMD_INOUT = 0x31  # out on -ve edge, in on +ve edge

# Other Constants
STD = (2 << 4)
AUX = (1 << 4)
CHA_FAIL = (1 << 0)
CHB_FAIL = (1 << 1)
CHI_FAIL = (1 << 2)
OW_HID = (1 << 4)
I2C_HID = (1 << 5)
BUS_CTRL = 3


# Open FTDI device as dev
dev = spi.openFTDI()


class HfbhTest(QWidget):

    def __init__(self):
        super().__init__()
        self.title = 'HPBH Main PCB Tester'
        self.left = 100
        self.top = 100
        self.width = 550
        self.hight = 200
        self.initUI()

    def initUI(self):
        self.setGeometry(self.left, self.top, self.width, self.hight)
        self.setWindowTitle(self.title)
        self.setWindowIcon(QIcon(self.resource_path('besi.png')))
        '''
        Values for Analog check:
        An0 target 1.825V min 1.75V max 1.9V
        An1 min 0.52V (20°C) max 1.07V (40°C)
        An2 min 
        An3 target 1.465V min 1.415 max 1.515
                     An0    An1   An2    An3 '''
        self.gMin = [11468, 3407, 6000,  9273]  # minimum Values far AD to be green
        self.gMax = [12452, 7012, 13000, 9929]  # maximum Values far AD to be green

        self.dutPwrCheckBox = QCheckBox('&DUT Power')
        self.dutPwrCheckBox.toggled.connect(self.changePower)
    
        self.createAnalogGroupBox()
        self.createEncoderGroupBox()
        self.createOneWireGroupBox()

        self.RedLabel = '''color: white; background-color: red;'''
        self.GreenLabel = '''color: white; background-color: green;'''
        self.OrgLabel = '''color: black; background-color: light grey;'''

        topLayout = QHBoxLayout()
        topLayout.addWidget(self.dutPwrCheckBox)

        mainLayout = QGridLayout()
        mainLayout.addLayout(topLayout, 0, 0, 1, 2)
        mainLayout.addWidget(self.analogGroupBox, 1, 0, 2, 1)
        mainLayout.addWidget(self.encoderGroupBox, 3, 0, 1, 1)
        mainLayout.addWidget(self.oneWireGroupBox, 1, 1, 3, 1)
        mainLayout.setRowStretch(1, 1)
        mainLayout.setRowStretch(2, 1)
        mainLayout.setColumnStretch(0, 1)
        mainLayout.setColumnStretch(1, 1)
        self.setLayout(mainLayout)

        # setup timer to update spi inputs
        self.updateTimer = QTimer()
        self.updateTimer.timeout.connect(self.updateInputs)

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)
        
    def changePower(self):
        if self.dutPwrCheckBox.isChecked():
            self.updateTimer.stop()
            spi.activate_CS0_n(dev)
            spi.write_cmd_bytes(dev, CMD_OUT, [1, 0])  # enable DUT Pwr
            time.sleep(0.2) # wait until fpga has read OneWire Memory
            self.owReadMem()
            self.updateTimer.start(100)
        else:
            self.updateTimer.stop()
            spi.activate_CS0_n(dev)
            spi.write_cmd_bytes(dev, CMD_OUT, [0, 0])  # disable DUT Pwr
            spi.reset_CSx_n(dev)
            self.resetGui()

    def resetGui(self):
        for i in range(4):
            self.anBar[i].update_bar(0,self.gMin[i], self.gMax[i])
        self.labelChA.setStyleSheet(self.OrgLabel)
        self.labelChB.setStyleSheet(self.OrgLabel)
        self.labelChI.setStyleSheet(self.OrgLabel)
        self.labelOW.setStyleSheet(self.OrgLabel)
        self.labelOWRam.setText('')

    def createAnalogGroupBox(self):
        self.analogGroupBox = QGroupBox('Analog Inputs')
        layout = QGridLayout()
        self.label = {}
        self.anBar = {}
        for i in range(4):
            self.label[i] = QLabel()
            self.label[i].setText('AnIn %d:' % i)
            self.anBar[i] = PbWidget(total=16384)
            layout.addWidget(self.label[i], i, 0)
            layout.addWidget(self.anBar[i], i, 1)
        self.analogGroupBox.setLayout(layout)

    def createEncoderGroupBox(self):
        self.encoderGroupBox = QGroupBox('Encoder Check')
        layout = QHBoxLayout()
        self.labelChA = QLabel('CHA')
        self.labelChA.setAlignment(Qt.AlignCenter)
        self.labelChA.setFixedSize(50,20)
        self.labelChB = QLabel('CHB')
        self.labelChB.setAlignment(Qt.AlignCenter)
        self.labelChB.setFixedSize(50,20)
        self.labelChI = QLabel('CHI')
        self.labelChI.setAlignment(Qt.AlignCenter)
        self.labelChI.setFixedSize(50,20)
        layout.addWidget(self.labelChA)
        layout.addWidget(self.labelChB)
        layout.addWidget(self.labelChI)
        layout.addStretch(1)
        self.encoderGroupBox.setLayout(layout)

    def createOneWireGroupBox(self):
        self.oneWireGroupBox = QGroupBox('One Wire')
        layout = QVBoxLayout()
        self.labelOW = QLabel('Memory')
        self.labelOW.setAlignment(Qt.AlignCenter)
        self.labelOW.setFixedSize(70,20)
        self.labelOWRam = QLabel()
        self.labelOWRam.setStyleSheet("border: 1px solid LightGray;")
        self.labelOWRam.setText('')
        layout.addWidget(self.labelOW)
        layout.addWidget(self.labelOWRam)
        layout.addStretch(1)
        self.oneWireGroupBox.setLayout(layout)

    def owReadMem(self):
        spi.activate_CS0_n(dev)
        spi.write_cmd_bytes(dev, CMD_OUT, [1, 0])  # initial address write only
        for i in range(1,65):
            spi.write_cmd_bytes(dev, CMD_INOUT, [1, i])  # read addr range 0 to 63
        spi.reset_CSx_n(dev)
        rx = spi.read(dev, 128)
        # update OneWire Memory
        mem = ''
        for i in range(64):
            word = f"{(rx[i*2] * (2**8) + rx[(i*2)+1]):0{4}X} "  # convert to '01C3 '
            if i % 8 == 0: # add linefeed after 8 words
                mem += '\n'
            mem += word # add to string
        self.labelOWRam.setText(mem)

    def updateInputs(self):
        spi.activate_CS0_n(dev)
        spi.write_cmd_bytes(dev, CMD_OUT, [1, 64])  # initial address write only
        for i in range(65,70):
            spi.write_cmd_bytes(dev, CMD_INOUT, [1, i])  # read addr range 64 to 68
        spi.reset_CSx_n(dev)
        rx = spi.read(dev, 10)
        # update analog graph bars
        for i in range(4):
            an = rx[(i*2)] * (2**8) + rx[(i*2)+1]
            self.anBar[i].update_bar(an,self.gMin[i], self.gMax[i])
        # update Encoder Status
        if rx[9] & I2C_HID:  # Testhardware connected
            if rx[9] & CHA_FAIL:  # test CHA
                self.labelChA.setStyleSheet(self.RedLabel)
            else:
                self.labelChA.setStyleSheet(self.GreenLabel)
            if rx[9] & CHB_FAIL:  # test CHB
                self.labelChB.setStyleSheet(self.RedLabel)
            else:
                self.labelChB.setStyleSheet(self.GreenLabel)
            if rx[9] & CHI_FAIL:  # test CHI
                self.labelChI.setStyleSheet(self.RedLabel)
            else:
                self.labelChI.setStyleSheet(self.GreenLabel)
            if rx[9] & OW_HID:  # test OneWire
                self.labelOW.setStyleSheet(self.GreenLabel)
            else:
                self.labelOW.setStyleSheet(self.RedLabel)
        else:
            self.labelChA.setStyleSheet(self.OrgLabel)
            self.labelChB.setStyleSheet(self.OrgLabel)
            self.labelChI.setStyleSheet(self.OrgLabel)
            self.labelOW.setStyleSheet(self.OrgLabel)

class PbWidget(QProgressBar):

    def __init__(self, parent=None, total=100):
        super(PbWidget, self).__init__(format='%v')
        self.setMinimum(0)
        self.setMaximum(total)        
        self._active = False
        self.setValue(0)
        self.change_color("red")

    def update_bar(self, value, gMin, gMax):
        while True:
            time.sleep(0.01)
            self.setValue(value)
            if value in range(gMin, gMax):
                self.change_color("green")
            else:
                self.change_color("red")
            if (not self._active or value >= self.maximum()):                
                break
        self._active = False

    def closeEvent(self, event):
        self._active = False

    def change_color(self, color):
        template_css = '''
                        QProgressBar{
                        border: 1px solid grey;
                        border-radius: 5px;
                        text-align: right;
                        margin-right: 10ex;
                    }
                        QProgressBar::chunk {
                        background-color: %s;
                        width: 10px;
                        margin: 1px;
                    }
                    '''
        css = template_css % color
        self.setStyleSheet(css)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    test = HfbhTest()
    test.show()
    sys.exit(app.exec_())
