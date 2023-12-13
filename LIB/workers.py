# -*- coding: utf-8 -*-
"""
Created on Thu Sep 23 09:33:11 2021

@author=  Grégory Sainton

"""
__author__ = "Grégory Sainton"
__email__="sainton@ipgp.fr"
__copyright= "IPGP France"
__purpose__ =""
__licence__=""
__version__="1.0"
__status__=""


import sys
import traceback
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QRunnable


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
    progress = pyqtSignal(int)


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

