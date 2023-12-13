#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jul  2 15:52:14 2021

@author : greg
@purpose:
@version: 
"""

from PyQt5 import QtGui, QtCore, QtWidgets
import sys, os


class Dialog_01(QtWidgets.QMainWindow):
    def __init__(self):
        super(QtWidgets.QMainWindow,self).__init__()

        mainWidget=QWidgets()
        self.setCentralWidget(mainWidget)
        mainLayout = QtGui.QVBoxLayout()
        mainWidget.setLayout(mainLayout)

        self.tabWidget = QtGui.QTabWidget()
        mainLayout.addWidget(self.tabWidget)

        self.tabWidget.connect(self.tabWidget, QtCore.SIGNAL("currentChanged(int)"), self.tabSelected)

        myBoxLayout = QtGui.QVBoxLayout()
        self.tabWidget.setLayout(myBoxLayout)

        self.tabWidget.addTab(QtGui.QWidget(),'Tab_01')
        self.tabWidget.addTab(QtGui.QWidget(),'Tab_02')
        self.tabWidget.addTab(QtGui.QWidget(),'Tab_03')


        ButtonBox = QtGui.QGroupBox() 
        ButtonsLayout = QtGui.QHBoxLayout()
        ButtonBox.setLayout(ButtonsLayout)

        Button_01 = QtGui.QPushButton("What Tab?")
        ButtonsLayout.addWidget(Button_01)
        Button_01.clicked.connect(self.whatTab)

        mainLayout.addWidget(ButtonBox)


    def tabSelected(self, arg=None):
        print (f"tabSelected() current Tab index = {arg}")

    def whatTab(self):
        currentIndex=self.tabWidget.currentIndex()
        currentWidget=self.tabWidget.currentWidget()

        print ("\n\t Query: current Tab index =, {currentIndex}")


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    dialog_1 = Dialog_01()
    dialog_1.show()
    dialog_1.resize(480,320)
    sys.exit(app.exec_())