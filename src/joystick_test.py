#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test for Besi Joystick on Universal USB HID 5009-8904
"""

import sys
import os
import time
import pywinusb.hid as hid
from PyQt5.QtWidgets import (QApplication, QWidget, QCheckBox, QProgressBar, QPushButton, QHBoxLayout, QVBoxLayout, QGridLayout, QGroupBox, QLabel, QFileDialog)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QTimer, pyqtSignal, Qt

# Other Constants
VENDOR_ID  = 0x04D8
PRODUCT_ID = 0x0041

class joyTest(QWidget):

    def __init__(self):
        super().__init__()
        self.title = 'Besi Joystick Tester'
        self.left = 100
        self.top = 100
        self.width = 550
        self.hight = 200
        self.initUI()

    def initUI(self):
        self.setGeometry(self.left, self.top, self.width, self.hight)
        self.setWindowTitle(self.title)
        self.setWindowIcon(QIcon(self.resource_path('besi.png')))

        self.createAnalogGroupBox()

        self.RedLabel = '''color: white; background-color: red;'''
        self.GreenLabel = '''color: white; background-color: green;'''
        self.OrgLabel = '''color: black; background-color: light grey;'''

        mainLayout = QGridLayout()
        mainLayout.addWidget(self.analogGroupBox, 0, 0, 1, 1)
        mainLayout.setRowStretch(1, 1)
        mainLayout.setRowStretch(2, 1)
        mainLayout.setColumnStretch(0, 1)
        mainLayout.setColumnStretch(1, 1)
        self.setLayout(mainLayout)

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)
        
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
        for i in range(2):
            self.label[i] = QLabel()
            self.label[i].setText('AnIn %d:' % i)
            self.anBar[i] = PbWidget(total=16384)
            layout.addWidget(self.label[i], i, 0)
            layout.addWidget(self.anBar[i], i, 1)
        self.analogGroupBox.setLayout(layout)

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
    test = joyTest()
    test.show()
    sys.exit(app.exec_())
