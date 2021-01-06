#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Test for Besi Joystick on Universal USB HID 5009-8904
"""

import sys
import os
import time
import pywinusb.hid as hid
import numpy as np
import matplotlib
matplotlib.use('Qt5Agg')
from PyQt5.QtWidgets import (QApplication, QWidget, QCheckBox, QProgressBar, QPushButton, QHBoxLayout, QVBoxLayout, QGridLayout, QGroupBox, QLabel, QFileDialog)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QTimer, pyqtSignal, Qt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import Circle, Rectangle

# Other Constants
VENDOR_ID  = 0x04D8
PRODUCT_ID = 0x0041

class MplCanvas(FigureCanvas):

    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super(MplCanvas, self).__init__(fig)


class joyTest(QWidget):

    def __init__(self):
        super().__init__()
        self.title = 'Besi Joystick Tester'
        self.left = 100
        self.top = 100
        self.width = 1000
        self.hight = 1000
        self.initUI()

    def initUI(self):
        self.setGeometry(self.left, self.top, self.width, self.hight)
        self.setWindowTitle(self.title)
        self.setWindowIcon(QIcon(self.resource_path('besi.png')))

        self.createAnalogGroupBox()

        self.RedLabel = '''color: white; background-color: red;'''
        self.GreenLabel = '''color: white; background-color: green;'''
        self.OrgLabel = '''color: black; background-color: light grey;'''

        #some projektwide used variables
        self.xValue = 0
        self.yValue = 0

        topLayout = QHBoxLayout()
        #connect to Common_USB_Controller
        HidTarget = hid.HidDeviceFilter(vendor_id = VENDOR_ID, product_id = PRODUCT_ID)
        self.HidDevices = HidTarget.get_devices()
        deviceLabel = QLabel(f'{len(self.HidDevices)} Besi USB Controller found')
        if self.HidDevices:
            self.HidDevices[0].open() # we assume that only 1 USB_Controller [0] is connected
            #set custom raw data handler
            self.HidDevices[0].set_raw_data_handler(self.raw_handler)
        topLayout.addWidget(deviceLabel)

        mainLayout = QGridLayout()
        mainLayout.addLayout(topLayout, 0, 0, 1, 3,)
        mainLayout.addWidget(self.analogGroupBox, 1, 0, 2, 2)
        mainLayout.setRowStretch(1, 1)
        mainLayout.setRowStretch(2, 1)
        mainLayout.setColumnStretch(0, 1)
        mainLayout.setColumnStretch(1, 1)
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
        numPoints = 42                    # number of points in the graph line
        self.x = np.zeros(numPoints, dtype=int)  # create empty numpy array to store xAxis data
        self.y = np.zeros(numPoints, dtype=int)
        layout = QVBoxLayout()
        self.lblX = QLabel()
        self.lblY = QLabel()
        # define graphic widget
        self.graph = MplCanvas(self, width=4, height=5, dpi=100)
        # set size
        self.graph.axes.set_ylim(-600, 600)
        self.graph.axes.set_xlim(-600, 600)
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

        layout.addWidget(self.graph)
        self.analogGroupBox.setLayout(layout)

    def raw_handler(self, data): # triggered from HID input
        self.xValue = self.to_signed(data[1] + (data[2] * 256), 16) # signed integer
        self.yValue = (self.to_signed(data[3] + (data[4] * 256), 16)) * -1 # inverted Y axis

    def updateGraph(self):
        self.x[:-1] = self.x[1:]; self.x[-1] = self.xValue # graphic fifo array x
        self.y[:-1] = self.y[1:]; self.y[-1] = self.yValue # graphic fifo array y
        if self._plot_ref is None:
            # First time we have no plot reference, so do a normal plot.
            # .plot returns a list of line <reference>s, as we're
            # only getting one we can take the first element.
            plot_refs = self.graph.axes.plot(self.x, self.y, linewidth=5, color='g')
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
