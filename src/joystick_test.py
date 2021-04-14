#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test for Besi Joystick on Universal USB HID 5009-8904
"""

import sys
import os
import time
import csv
import io
import pywinusb.hid as hid
import numpy as np
import matplotlib
matplotlib.use('Qt5Agg')
from PyQt5.QtWidgets import (QApplication, QWidget, QCheckBox, QProgressBar, QPushButton, QHBoxLayout, QVBoxLayout, QGridLayout, QGroupBox, QLabel, QLineEdit, QFileDialog)
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtCore import QTimer, pyqtSignal, Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Rectangle
from PIL import Image, ImageFont, ImageDraw

# Other Constants
VENDOR_ID  = 0x04D8
PRODUCT_ID = 0x0041

class MplCanvas(FigureCanvas):

    def __init__(self, parent=None, width=5, height=4, dpi=100, tight_layout=None):
        fig = Figure(figsize=(width, height), dpi=dpi, tight_layout=tight_layout)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)


class joyTest(QWidget):

    def __init__(self):
        super().__init__()
        self.title = 'Besi Joystick Tester'
        self.left = 100
        self.top = 100
        self.width = 1500
        self.hight = 1000
        self.initUI()

    def initUI(self):
        self.setGeometry(self.left, self.top, self.width, self.hight)
        self.setWindowTitle(self.title)
        self.setWindowIcon(QIcon(self.resource_path('besi.png')))

        #some projektwide used variables
        self.xValue = 0
        self.yValue = 0
        self.recOn = False

        self.createAnalogGroupBox()
        self.createControlGroupBox()

        self.RedLabel = '''color: white; background-color: red;'''
        self.GreenLabel = '''color: white; background-color: green;'''
        self.OrgLabel = '''color: black; background-color: light grey;'''

        topLayout = QHBoxLayout()
        #connect to Common_USB_Controller
        HidTarget = hid.HidDeviceFilter(vendor_id = VENDOR_ID, product_id = PRODUCT_ID)
        self.HidDevices = HidTarget.get_devices()
        deviceLabel = QLabel(f'{len(self.HidDevices)} Besi USB Controller found')
        if (len(self.HidDevices) == 0):
            deviceLabel.setStyleSheet('''color: red;''')
        if self.HidDevices:
            self.HidDevices[0].open() # we assume that only 1 USB_Controller [0] is connected
            #set custom raw data handler
            self.HidDevices[0].set_raw_data_handler(self.raw_handler)
        topLayout.addWidget(deviceLabel)

        mainLayout = QGridLayout()
        mainLayout.addLayout(topLayout, 0, 0, 1, 2,)
        mainLayout.addWidget(self.analogGroupBox, 1, 0, 1, 1)
        mainLayout.addWidget(self.controlGroupBox, 1, 1, 1, 1)
        mainLayout.setRowStretch(1, 1)
        mainLayout.setColumnStretch(0, 1)
        self.setLayout(mainLayout)

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base_path, relative_path)
        
    def createAnalogGroupBox(self):
        self.analogGroupBox = QGroupBox('Real-time joystick analog signal')
        # initialize sensor data variables
        self.xValue = 0
        self.yValue = 0
        self.x = np.zeros(1, dtype=int)  # create empty numpy array to store xAxis data
        self.y = np.zeros(1, dtype=int)
        self.lblX = QLabel()
        self.lblY = QLabel()
        # define graphic widget
        self.graph = MplCanvas(self, width=4, height=5, dpi=100, tight_layout=True)
        # set size
        self.graph.axes.set_ylim(-600, 600)
        self.graph.axes.set_xlim(-600, 600)
        # aspect ratio
        self.graph.axes.set_aspect('equal')
        # add graphics
        self.graph.axes.add_artist(Rectangle((-500, -500), 1000, 1000, color='g', fill=False))
        self.graph.axes.add_artist(Circle((0, 0), 20, color='g', fill=False))
        # add grid
        self.graph.axes.grid(color='b', linestyle=':')
        self._plot_ref = None
        self.updateGraph()
        # setup timer to update graphic
        self.updateTimer = QTimer()
        self.updateTimer.timeout.connect(self.updateGraph)
        self.updateTimer.start(20)
        # setup layout
        layout = QVBoxLayout()
        layout.addWidget(self.graph)
        self.analogGroupBox.setLayout(layout)

    def createControlGroupBox(self):
        self.controlGroupBox = QGroupBox('Test control')
        lblStep1 = QLabel("1: Adjust Potentiometer to the inner circle (+/- 10)")
        lblStep1.setFont(QFont('Arial',10))
        lblStep2 = QLabel("2: Pull the Joystick to all four directions and release it. \n"
                          "   The point must stop inside the circle")
        lblStep2.setFont(QFont('Arial',10))
        lblStep3 = QLabel("3: - Press 'Start Rec',\n"
                          "    - Move the Joystick once along the outer side,\n"
                          "    - Press 'Stop Rec' ")
        lblStep3.setFont(QFont('Arial',10))
        self.btnStart = QPushButton('Start Rec')
        self.btnStart.clicked.connect(self.startRecord)
        self.btnStop = QPushButton('Stop Rec')
        self.btnStop.clicked.connect(self.stopRecord)
        lblStep4 = QLabel("4: Scan Joystick barcode")
        lblStep4.setFont(QFont('Arial',10))
        self.barcode = QLineEdit()
        lblStep5 = QLabel("5: Press 'Save Test' to finish")
        lblStep5.setFont(QFont('Arial',10))
        self.btnSave = QPushButton('Save Test')
        self.btnSave.clicked.connect(self.saveTest)
        self.lblMessage = QLabel("")

        # setup layout
        layout = QVBoxLayout()
        layout.addWidget(lblStep1)
        layout.addWidget(lblStep2)
        layout.addWidget(lblStep3)
        layout.addWidget(self.btnStart)
        layout.addWidget(self.btnStop)
        layout.addWidget(lblStep4)
        layout.addWidget(self.barcode)
        layout.addWidget(self.btnSave)
        layout.addWidget(self.lblMessage)
        layout.addStretch(1)
        self.controlGroupBox.setLayout(layout)

    def raw_handler(self, data): # triggered from HID input
        self.xValue = self.to_signed(data[1] + (data[2] * 256), 16) # signed integer
        self.yValue = (self.to_signed(data[3] + (data[4] * 256), 16)) * -1 # inverted Y axis

    def startRecord(self):
        self.x = np.array([self.xValue]) # reinitialyze 0dim ndarray
        self.y = np.array([self.yValue])
        self.recOn = True
        self.btnStart.setStyleSheet(self.GreenLabel)

    def stopRecord(self):
        self.recOn = False
        self.btnStart.setStyleSheet(self.OrgLabel)
        # clear barcode text entry and set the cursor in it
        self.barcode.clear()
        self.barcode.setFocus()

    def saveTest(self):
        workDir = os.getcwd()
        self.lblMessage.setFont(QFont('Arial',10))
        try:
            barcode = self.barcode.text().split(",")
            if (len(barcode) > 7):
                self.btnSave.setStyleSheet(self.RedLabel)
                self.lblMessage.setText("Barcode is too long")
            elif (barcode[0] == 'www.besi.com/mrs'):
                filename = barcode[2] + '_' + barcode[3] + '_' + barcode[4] + '_' + barcode[5] + '_' + barcode[6] + '.png'
                # save graph as img object 
                buf = io.BytesIO()
                self.graph.figure.savefig(buf, format='png')
                buf.seek(0)
                img = Image.open(buf)
                img.save(filename)
                self.btnSave.setStyleSheet(self.GreenLabel)
                self.lblMessage.setFont(QFont('Arial',8))
                self.lblMessage.setText(f'File is saved under\n{workDir}\{filename}')
            else:
                self.btnSave.setStyleSheet(self.RedLabel)
                self.lblMessage.setText("Be sure to have a correct Barcode")
        except:
            self.btnSave.setStyleSheet(self.RedLabel)
            self.lblMessage.setText("Be sure to have a correct Barcode")


    def updateGraph(self):
        if self.recOn: # store in array
            if (len(self.x) < 1000): # to limit size of array
                self.x = np.append(self.x, self.xValue)
                self.y = np.append(self.y, self.yValue)
            else: # fifo array functionality
                self.x[:-1] = self.x[1:]; self.x[-1] = self.xValue 
                self.y[:-1] = self.y[1:]; self.y[-1] = self.yValue
        else: # only one point
            self.x[0] = self.xValue
            self.y[0] = self.yValue
        if self._plot_ref is None:
            # First time we have no plot reference, so do a normal plot.
            # .plot returns a list of line <reference>s, as we're
            # only getting one we can take the first element.
            plot_refs = self.graph.axes.plot(self.x, self.y, marker='o', color='g')
            self._plot_ref = plot_refs[0]
        else:
            # We have a reference, we can use it to update the data for that line.
            self.graph.axes.set_xlabel(f'X: {self.xValue}', fontsize=20)
            self.graph.axes.set_ylabel(f'Y: {self.yValue}', fontsize=20)
            self._plot_ref.set_data(self.x, self.y,)
        self.graph.draw()

    def to_signed(self, value, width):
        if value >= 2**(width-1): # negative
            value -= 2**width
        return value

    def closeEvent(self, event):
        if self.HidDevices:
            self.HidDevices[0].close()
            print('und tschüss')



if __name__ == '__main__':
    app = QApplication(sys.argv)
    test = joyTest()
    test.show()
    sys.exit(app.exec_())
