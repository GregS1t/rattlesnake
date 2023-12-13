#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Aug 24 17:53:42 2021

@author : greg
@purpose:
@version: 
"""


#-*- coding: utf-8 -*-
import random
import time
from collections import deque
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtGui
import numpy as np
import os

win = pg.GraphicsWindow()
win.setWindowTitle('DOTS')


p1 = win.addPlot()
p1.setRange(yRange=[0,25])
p1.setRange(xRange=[0,25])
curve1 = p1.plot()


nsamples=300 #Number of lines for the data

dataRed= np.zeros((nsamples,2),float) #Matrix for the Red dots
dataBlue=np.zeros((nsamples,2),float) #Matrix for the Blue dots

def getData():
    global dataRed, dataBlue

    t0= random.uniform(1.6,20.5) #Acquiring Data
    d0= random.uniform(1.6,20.5) #Acquiring Data
    vec=(t0, d0)

    dataRed[:-1] = dataRed[1:]
    dataRed[-1]=np.array(vec)

    t0= random.uniform(1.6,20.5) #Acquiring Data
    d0= random.uniform(1.6,20.5) #Acquiring Data
    vec=(t0, d0)

    dataBlue[:-1] = dataBlue[1:]
    dataBlue[-1]=np.array(vec)


def plot():

    #Blue Dots
    curve1.setData(dataBlue, pen=None, symbol='o', symbolPen=None, symbolSize=4, symbolBrush=('b'))
    #Red Dots
    curve1.setData(dataRed, pen=None, symbol='o', symbolPen=None, symbolSize=4, symbolBrush=('r'))   


def update():

    getData()
    plot()

timer = pg.QtCore.QTimer()
timer.timeout.connect(update)
timer.start(50)

## Start Qt event loop unless running in interactive mode or using pyside.
if __name__ == '__main__':
    import sys
    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        QtGui.QApplication.instance().exec_()# -*- coding: utf-8 -*-
