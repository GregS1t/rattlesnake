#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Mar 22 00:23:04 2018

@author: sainton
"""
# pylint: disable=C0103
import sys
import os

import numpy as np
from random import random
import time
import datetime
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
from PyQt5 import uic, QtGui, QtWidgets
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot,\
                            Qt, QThreadPool, QRunnable
import ATTOCUBE.IDS as IDS
import ATTOCUBE.streaming.stream as ids_stream
import ATTOCUBE.streaming.streaming as ids_streaming
# import qdarkstyle
pg.setConfigOption('background', 'w')

IDS3010ADDRESS = "172.27.36.217"
isMaster = True
intervalInMicroseconds = 1000
kwargs_stream = {"filePath": None, 
                 "axis0": False, "axis1": True, "axis2": False
                }
bandwidth = 1000
BUFFERSIZE = int((min(1023, max(1,1000000/bandwidth/25))+1+2)*4)
print(f"Buffersize: {BUFFERSIZE}")
TIME_RANGE_PLOT = 5          # time range of the plot in seconds
MAX_BINS_PLOT = TIME_RANGE_PLOT /(intervalInMicroseconds*1e-6)
print(MAX_BINS_PLOT)


CURRENT_DIR = os.getcwd()


class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.
    https://www.pythonguis.com/tutorials/multithreading-pyqt-applications-qthreadpool/
    Supported signals are:

    finished
        No data

    error
        tuple (exctype, value, traceback.format_exc() )

    result
        object data returned from processing, anything

    progress
        int indicating % progress

    '''
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(object)


class Worker(QRunnable):
    '''
    Worker thread

    Inherits from QRunnable to handler worker thread setup

    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    '''

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.function = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''

        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.function(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value,
                                     traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the proc
        finally:
            self.signals.finished.emit()  # Done


class IDS_IPGP(IDS.Device):
    def __init__(self, idsipaddress):
        super().__init__(idsipaddress)

    def action_request_alignement(self):
        """
            Function to handle aligment request from GUI

        """
        current_mode = self.system.getCurrentMode()
        if current_mode == 'system idle':
            self.system.startOpticsAlignment()

            while current_mode != 'optics alignment running':
                time.sleep(1)
                current_mode = self.system.getCurrentMode()
            print(f"IDS aligned: {self.adjustment.getContrastInPermille(self.axis.getMasterAxis())}")
            self.system.stopOpticsAlignment()
            time.sleep(5)
        else:
            print(f"{self.system.getCurrentMode()}: no aligment is possible")

    def action_request_start_measurement(self):
        current_mode = self.system.getCurrentMode()
        if current_mode == 'system idle':
            self.system.startMeasurement()
            current_mode = self.system.getCurrentMode()
            while current_mode != 'measurement running':
                time.sleep(1)
                current_mode = self.system.getCurrentMode()
            print(f" Status: {self.system.getCurrentMode()}")


class MainWindow(QtWidgets.QWidget):
    """
    mon interface pyqtgraph
    """
    def __init__(self):
        super().__init__()
        # Create the main window
        self.period_timer = 1
        self.mon_timer = None
        self.ids = None
        self.on_init()
        self.show()
       

    def on_init(self):
        """
        personnalisation de l'interface
        """
        # une méthode pour créer les objets graphiques
        # et les organiser puis les insérer dans la fenêtre
        self.creation_agencement()
        
        self.ids = IDS_IPGP(IDS3010ADDRESS)
        self.ids.connect()
        self.lendata_temp = 0
        current_mode = self.ids.system.getCurrentMode()
        print(current_mode)
        master_axis = self.ids.axis.getMasterAxis()
        print(master_axis)
        if current_mode == "system idle":
            self.ids.system.startMeasurement()
        elif current_mode != "measurement running":
            print("mearurement already started")
        elif current_mode in ["optics alignment starting",
                              "optics alignment running"]:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setText("Alignment is running")
            msg.setInformativeText("Stop alignment before acquisition.")
            msg.setWindowTitle("Device unavailable.")
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
        # une méthode pour intégrer les connexions
        # lors de l'utilisation des boutons
        # et insertion des tracer vides dans l'espace graphique
        self.connexion_and_init_plot()
        self.windowWidth = int(MAX_BINS_PLOT)
        self.Xm = np.linspace(0, 0,self.windowWidth)
        self.timevec = np.linspace(0, 0, self.windowWidth)
        self.ptr = -self.windowWidth
        self.data = np.array([])
        self.stopsig = False
        # Threads part
        self.threadpool = QThreadPool()
        self.recording_state = False
    
    
    def read_streaming_data(self, buffersize):
        while not self.stopsig:
            numBytes, _, axis1, _ = self.ids_stream.read(buffersize)
            self.data = np.append(self.data, axis1)
    
    def start_datastreaming(self):
        if self.mon_timer is None:
            if self.ids.system.getCurrentMode() == "measurement running":
                self.mon_timer = self.startTimer(self.period_timer)
                self.ids_stream = ids_stream.Stream(IDS3010ADDRESS, isMaster,
                                                intervalInMicroseconds,
                                                **kwargs_stream)
                self.ids_stream.open()
                
                print("Streaming opened")

                worker = Worker(self.read_streaming_data,
                                BUFFERSIZE)
                self.threadpool.start(worker)

            else:
                msg = QtWidgets.QMessageBox()
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setText("Please wait, interfero not yes ready")
                msg.setInformativeText("Initialization on going")
                msg.setWindowTitle("Device unavailable.")
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()
                
    def stop_datastreaming(self):
        if self.mon_timer is not None:
            self.killTimer(self.mon_timer)
            self.mon_timer = None
            self.stopsig = True
            self.ids_stream.close()
            self.ids.system.stopMeasurement()
    
    def record_datastreaming(self):
        """
        Function to handle the recording ot the streaming
        into a file
        
        """
        if self.recording_state is not True:
            timenow = datetime.datetime.utcnow().isoformat()
            timenow = timenow.replace(":", "_")
            timenow = timenow.replace("-", "_")
            timenow = timenow.replace(".", "_")
            self.record_filename = os.path.join(CURRENT_DIR, f"streaming_{timenow}.aws")
            print(self.record_filename)
            self.ids_stream.startRecording(self.record_filename)
            self.pb_record.setStyleSheet("background-color : red")
            self.recording_state = True
        else:
            self.ids_stream.stopRecording()
            
            self.pb_record.setStyleSheet("background-color : None")
            self.recording_state = True
        
        
    
    def timerEvent(self, _):
        """
        Function executed every "period_timer"
        It updates the plot by comparing the size already plotted 
        with the complete size of the data.
        """
        new_len_data = len(self.data)
        old_len_data = self.lendata_temp
        
        if new_len_data > old_len_data:
            #print(new_len_data, old_len_data)
            for i in range(old_len_data, new_len_data):
                self.Xm[:-1] = self.Xm[1:]             # shift data in the temporal mean 1 sample left
                self.Xm[-1] = float(self.data[i]/1e9)      # vector containing the instantaneous values      
                self.ptr += 1     
            self.plt_accel_x.setData(self.Xm, _callSync='off')
            #self.plt_accel_x.setPos(self.ptr, 0)
            self.lendata_temp = new_len_data
        else:
            pass
       
    def connexion_and_init_plot(self):
        # connexion des boutons
        self.pb_start.clicked.connect(self.start_datastreaming)
        self.pb_stop.clicked.connect(self.stop_datastreaming)
        self.pb_record.clicked.connect(self.record_datastreaming)
        # création des zones de tracer
        # première ligne
        zt_accel_x = self.gw_tracer.addPlot(title="Displacement")
        zt_accel_x.setXRange(-5, 0, padding=0)
        # création d'un plot vide dans chaque zt
        self.plt_accel_x = zt_accel_x.plot(pen='r')

    
    def creation_agencement(self):
        # création de l'objet graphique
        # pour accueillir les tracés (acc et gyro)
        self.gw_tracer = pg.GraphicsWindow()
        # création d'un bouton START
        self.pb_start = QtWidgets.QPushButton("START")
        # création d'un bouton STOP
        self.pb_stop = QtWidgets.QPushButton("STOP")
        # création d'un bouton RECORD
        self.pb_record = QtWidgets.QPushButton("RECORD")
        
        # agencement
        # les boutons côte-à-côte
        hbox = QtWidgets.QHBoxLayout()
        hbox.addWidget(self.pb_start)
        hbox.addWidget(self.pb_stop)
        hbox.addWidget(self.pb_record)
        
        # gw_tracer au-dessus des boutons
        vbox = QtWidgets.QVBoxLayout()
        vbox.addWidget(self.gw_tracer)
        vbox.addLayout(hbox)
        # on insère le Layout dans la fenêtre
        self.setLayout(vbox)

    def closeEvent(self, event):
        """
        code exécuté quand l'interface est fermée
        """
        # ajoute une boite de dialogue pour confirmation de fermeture
        result = QtWidgets.QMessageBox.question(self,
                                                "Confirm Exit...",
                                                "Do you want to exit ?",
                                                (QtWidgets.QMessageBox.Yes |
                                                 QtWidgets.QMessageBox.No))
        if result == QtWidgets.QMessageBox.Yes:
            # permet d'ajouter du code pour fermer proprement
            self.stop_datastreaming()
            event.accept()
        else:
            event.ignore()


if __name__ == '__main__':
    # dark_stylesheet = qdarkstyle.load_stylesheet_pyqt5()
    APP = pg.mkQApp()
    # APP.setStyleSheet(dark_stylesheet)
    FEN = MainWindow()
    FEN.activateWindow()
    sys.exit(APP.exec())
