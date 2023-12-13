#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jun 18 11:39:18 2021

@author : Grégory Sainton on behalf PIONEERS Project
@email  : sainton@ipgp.fr
@purpose: Graphical User Interface to control NewPort Picomotor and
            Attocube IDS Inteferometer
@version: 1.0
"""

import datetime
import time
import pathlib
import os
import sys
from pathlib import Path
import glob
import json
import logging
import usb
import csv
import numpy as np

# import numpy as np

from PyQt5 import uic, QtGui, QtWidgets
from PyQt5.QtCore import pyqtSignal, Qt, QThreadPool, QLocale
from PyQt5.QtGui import QPixmap

# Internal lib to read and command the motor
from LIB.MOTOR.pico8742ctrl import Pico8742Ctrl
from LIB.workers import Worker
#import LIB.ATTOCUBE.streaming.stream as ids_stream
#import gui_interfero

# Internal lib to read and compute the interferometer
try:
    import LIB.ATTOCUBE.streaming.stream as ids_stream
    import gui_interfero
    INTERFERO_LIB_MISSING = False
except:
    print("No connexion possible with the IDS 3010 Interferometer")
    INTERFERO_LIB_MISSING = True
# Lib to connect Agilent power supply instrument 
try:
    import pyvisa as visa
except ModuleNotFoundError as err:
    print(err)
    print("This module is absolutly necessary to run the power supply instrument")
    print("In a terminal: $pip install pyvisa")
# -------------------- OPEN THE GLOBAL CONFIG FILE

CURRENT_FILE_DIR = pathlib.Path(__file__).parent.absolute()
SETUP_PARAM_DIR = "CONFIG"
SETUP_DATA_DIR = "DATA"
MAIN_CONFIG_FILE = "rattlesnake_conf.json"
# Default set if nothing found in config file
DEFAULT_RECORD_DIR = os.path.join(CURRENT_FILE_DIR, SETUP_DATA_DIR)
# Load setup file
SETUP_PARAM_FILE = os.path.join(CURRENT_FILE_DIR,
                                SETUP_PARAM_DIR, MAIN_CONFIG_FILE)

MESSAGEDEVICENOTFOUND = None
MESSAGEMOTORALREADYCONNECTED = None
MESSAGEMOTORPERMISSIONERROR = None
MESSAGEMOTORDISCONNECTED = None
MAXNUMBEROFCYCLE = None
MAXNUMBEROFDWELL = None
DEFAULTIDPRODUCT = None
DEFAULTIDVENDOR = None
MINDWELLTIME = None
MAXVELOCITY = None
MAXACCELERATION = None
FILESESSIONPREFIX = None
FILE_EXTENTION = None
SESSIONFILENAME = None
VERSION = None
INTERFERO_IP = None

INTERFERO_INTERVAL_MICROSEC = 1000
bandwidth = 1000
BUFFERSIZE = int((min(1023, max(1, 1000000/bandwidth/25)) + 1 + 2) * 4)
INTERFERO_TIME_RANGE_PLOT = 5          # time range of the plot in seconds
MAX_BINS_PLOT = INTERFERO_TIME_RANGE_PLOT / (INTERFERO_INTERVAL_MICROSEC*1e-6)

SESSIONDIRNAME = "gpsession"
# ------------------------- FEW GLOBAL VARIABLES ----------------------------

timenow = datetime.datetime.now().isoformat()
timenow = timenow.replace(":", "_")
timenow = timenow.replace("-", "_")
timenow = timenow.replace(".", "_")

LOG_SESSION_FILENAME = os.path.join(CURRENT_FILE_DIR, SESSIONDIRNAME,
                                    f"rs_session_{timenow}.log")

# logging options

logging.basicConfig(level=logging.INFO,
                 handlers=[logging.FileHandler(LOG_SESSION_FILENAME, mode='w'),
                           logging.StreamHandler()],
                         format='[%(asctime)-15s] %(message)s')

stream_handler = [h for h in logging.root.handlers if isinstance(h,
                                                     logging.StreamHandler)][0]
stream_handler.setLevel(logging.INFO)

# ---------------------------- GET UI FILES PATH ----------------------------

UI_SUBDIRECTORY = "UIDIR"

# Main window UI file
UI_MAIN_WINDOW_FILENAME = "rattlesnake_mv_0.10.ui"
UI_MAIN_WINDOW = os.path.join(CURRENT_FILE_DIR, UI_SUBDIRECTORY,
                              UI_MAIN_WINDOW_FILENAME)

# About window UI file
UI_ABOUT_WINDOW_FILENAME = "rattlesnake_about_dialog1.0.ui"
UI_ABOUT_WINDOW = os.path.join(CURRENT_FILE_DIR, UI_SUBDIRECTORY,
                               UI_ABOUT_WINDOW_FILENAME)

# Inteference preference windows
UI_PREF_WINDOW_FILENAME = "rattlesnake_interfero_preference1.1.ui"
UI_PREF_WINDOW = os.path.join(CURRENT_FILE_DIR, UI_SUBDIRECTORY,
                              UI_PREF_WINDOW_FILENAME)

# Path to app icon
icon_dir = os.path.join(CURRENT_FILE_DIR, "icon", 'moon_phase_full.ico')

# ------------------------ CLASS OF THE GUI ---------------------------------


class GuiPioneersMainWindow(QtWidgets.QMainWindow):
    """
    Main graphical interface
    - Each devices are put into separate Tab Widget -> Necessary to add new
      instruments if needed.
    - So far only 2 instruments are managed
    """
    
    sig_abort_workers = pyqtSignal()  # Must be define as class level

    def __init__(self):
        """
        Initial instantiation of a GuiPioneersMainWindow object

        Returns
        -------
        None.

        """
        QtWidgets.QMainWindow.__init__(self)
        self.setObjectName("RATTLE SNAKE")
        self.user_interface = uic.loadUi(UI_MAIN_WINDOW, self)
        logging.info(f"RATTLE SNAKE v {VERSION} opening.")
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(icon_dir), QtGui.QIcon.Normal,
                       QtGui.QIcon.Off)
        self.setWindowIcon(icon)
        self.plainTextEditMotorConnexion.setReadOnly(True)
        self.statusBar().showMessage('Ready')
        self.version = VERSION

        self.action_clear_console.triggered.connect(self.actionClear_Console)
        self.actionAbout.triggered.connect(self.mw_open_about_dialog)
        self.actionHelp.setEnabled(False)
        self.actionExportWaveToCSV.triggered.connect(self.actionOpenWaveExport)
        self.mw_checkexist_or_create_dir()
        # Set Tab to "Motor"
        self.tabWidget.setCurrentIndex(0)

        # Graphic part
        # Timer managnement
        self.period_timer = 1
        self.mon_timer = None
        
        # Interfero
        self.lendata_temp = 0
        
        # Motor
        self.ptr_motor = 0
        self.lendata_temp_motor = 0

        # Agilent power supply
        self.ptr_agilent = 0
        self.lendata_temp_agilent = 0

        # Interfero
        if INTERFERO_LIB_MISSING:
            self.action_connect_interfero.setEnabled(False)

        self.interfero_recording_state = False
        self.data = np.array([])
        self.graphicsView.setBackground((0, 0, 0))
        self.graphicsView.viewRect()
        self.windowWidth = 10000

        # Variable initiatialization
        self.rs_custom_pref = {}
        self.init_motor()
        self.init_agilent()
        self.init_interfero()

        # Threads part
        self.threadpool = QThreadPool()

        # Graphical part
        self.displacement_interfero = self.graphicsView.addPlot(
                                                        title="Interferometer")

        self.graphicsView.nextRow()

        self.displacement_motor = self.graphicsView.addPlot(
                                        title="Device")
        self.displacement_motor.setDownsampling(mode='peak')
        self.displacement_motor.setClipToView(True)
        self.displacement_motor.setLabel('left',
                                         text="Displacement",
                                         units="steps")
        self.displacement_motor.setLabel('bottom',
                                         text="Time",
                                         units="s")
        self.displacement_motor.showGrid(x=True, y=True)

        #self.curve_motor = self.displacement_motor.plot()

        self.displacement_interfero.setDownsampling(mode='peak')
        self.displacement_interfero.setClipToView(True)
        self.displacement_interfero.setLabel('left',
                                    text=self.rs_custom_pref["ylabel"])
        self.displacement_interfero.setLabel('bottom',
                                    text=self.rs_custom_pref["xlabel"])
        self.displacement_interfero.showGrid(x=True, y=True)
        #self.displacement_interfero.setRange(xRange=[-self.windowWidth, 0])
        #self.displacement_interfero.setLimits(xMax=0)
        self.curve_interfero = self.displacement_interfero.plot(self.data)

    def actionOpenWaveExport(self):
        """
        Function to open WAVE Software to export AWS files to CSV files.

        Returns
        -------
        None.

        """
        import subprocess
        WAVE_DIR = r"C:\Users\cave\Documents\RATTLESNAKE\WAVE"
        wave_export_fn = os.path.join(WAVE_DIR, "WAVEExport.exe")
        logging.info(f"RATTLE SNAKE: {wave_export_fn}")
        try:
            subprocess.Popen(wave_export_fn)
            logging.info("RATTLE SNAKE: ATTOCUBE Wave Export Opening...")
        except:
            logging.info("RATTLE SNAKE: ATTOCUBE Wave Export Opening failed.")
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setText("Unable to open WAVE Export")
            msg.setWindowTitle("Wave Export unreachable.")
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()

    def mw_checkexist_or_create_dir(self):
        """
        Function to check if the directories useful to run the app
        already exist of need to be created

        There are 3 directories:
            - SESSIONDIRNAME -> contains the session parameters saved
                                or reloaded
            - DEFAULT_RECORD_DIR -> Default directory to save the files
                                    recorded
        Returns
        -------
        None.

        """
        Path(SESSIONDIRNAME).mkdir(parents=True, exist_ok=True)
        Path(DEFAULT_RECORD_DIR).mkdir(parents=True, exist_ok=True)

    def init_motor(self):
        """
        Function to group all the initialisation of the motor

        Returns
        -------
        None.

        """
        self.motor_id_product = None
        self.motor_id_vendor = None
        self.picomotor = None

        self.motor_default_pos = None
        self.motor_default_vel = None
        self.motor_default_acc = None

        self.motor_vel = None
        self.motor_acc = None
        self.motor_pos = None
        self.motor_current_pos = None

        self.rb_motor_jog_is_checked = None
        self.rb_motor_relative_is_checked = None

        # Motor variables inititialisation
        self.motor_console_message = ""
        self.motordirection = None
        self.motor_run_status = None
        self.motor_connexion_status = 0
        self.motor_relative_step_number_value = 0
        self.motor_cycle_running = False
        self.motor_start_cycle_time = None
        self.motor_start_cycle_fn = None
        self.stop_the_motor = False
        self.save_data_from_motor_cycle = True

        self.motor_save_sequence_file = os.path.join(DEFAULT_RECORD_DIR,
                                    f"{DEFAULT_RECORD_PREFIX_MOTOR_FILE}.csv")
        # Desactivate all buttons relative to the motor
        # Toolbar

        self.action_connect_motor.triggered.connect(
                                    lambda: self.actionConnectMotor())

        # Setup tab
        self.btnApplyMotorApply.setEnabled(False)
        self.btnApplyMotorDefault.setEnabled(False)

        # Job Tab
        self.lineEditrelativeStepNumber.textChanged.connect(
                    lambda: self.motor_update_pref_jog_tab())
        self.pbMotorJogRun.setEnabled(False)
        self.pbMotorJogStop.setEnabled(False)
        self.pbMotorJogClockWise.setEnabled(False)
        self.pbMotorJogAntiClockWise.setEnabled(False)
        self.lineEditAbsolutePosition.setEnabled(False)
        self.lineEditrelativeStepNumber.setEnabled(False)
        # Cycle tab
        self.pbMotorCycleInit2zero.clicked.connect(
            lambda: self.motor_initialize_number_of_cycle())
        self.le_motor_cycle_relative_step_nb.textChanged.connect(
            lambda: self.motor_update_pref_cycle_tab())
        self.pb_modify_filepath_motor.clicked.connect(
                                                self.interfero_set_preferences)
        self.pbMotorCycleRun.setEnabled(False)
        self.pbMotorCycleStop.setEnabled(False)

        self.cb_record_at_start.setEnabled(False)

        self.motor_cycle_param_dict = {}
        self.motor_position_vec = {"time": np.array([]),
                                   "pos": np.array([]),
                                   "datetime": np.array([])}

    def init_interfero(self):
        """
         Function to group all the initialisation of the interferometer

        Returns
        -------
        None.
        """
        self.action_connect_interfero.triggered.connect(
                            lambda: self.action_connectInterfero(INTERFERO_IP))
        self.actionPreferences.triggered.connect(
                            lambda: self.interfero_set_preferences())
        self.pb_modify_filepath.clicked.connect(self.interfero_set_preferences)

        self.pb_align_update.setEnabled(False)
        self.pb_align_stop.setEnabled(False)
        self.pb_measure_record.setEnabled(False)
        self.pb_measure_start.setEnabled(False)
        self.pb_measure_init.setEnabled(False)
        self.interfero_connected = False
        self.interfero_start_meas = False

        self.rs_custom_pref["record_dir"] = DEFAULT_RECORD_DIR
        self.rs_custom_pref["record_prefix"] = DEFAULT_RECORD_PREFIX_FILE
        self.rs_custom_pref["freq"] = int(1/(INTERFERO_INTERVAL_MICROSEC*1e-6))
        self.rs_custom_pref["xlabel"] = INTERFERO_XLABEL_PLOT
        self.rs_custom_pref["ylabel"] = INTERFERO_YLABEL_PLOT
        self.rs_custom_pref["time_range"] = INTERFERO_TIME_RANGE_PLOT
        self.lbl_filepath.setText(f"{self.rs_custom_pref.get('record_dir')}/{self.rs_custom_pref.get('record_prefix')}")

        # OVNI Mal placé
        self.rs_custom_pref["record_prefix_motor"] = DEFAULT_RECORD_PREFIX_MOTOR_FILE
        self.le_motor_record_fn.setText(os.path.join(
            DEFAULT_RECORD_DIR, f"{DEFAULT_RECORD_PREFIX_MOTOR_FILE}_DATE.csv"
            ))
        self.ptr = 0
        
    def init_agilent(self):
        """
        Function to initialize the Agilent 3631E Power Supply instrument


        Returns
        -------
        None.

        """
        self.action_connect_agilent.triggered.connect(
                            lambda: self.actionConnect_agilent())
        self.agilent_instance = None
        self.agilent_connected = False
        self.agilent_param_dict = {}
        self.agilent_start_cycle_time = None
        self.agilent_cycle_running = False
        self.agilent_jog_voltage_is_running = False
        self.stop_agilent = False
        self.agilent_run_status = False
        self.agilent_connexion_status = 0
        self.agilent_param_dict["reference"] = AGILENT_INSTR_RESSOURCE
        self.agilent_param_dict["vmin"] = AGILENT_VOLT_MIN
        self.agilent_param_dict["vmax"] = AGILENT_VOLT_MAX
        self.agilent_param_dict["vstep"] = AGILENT_VOLT_STEP
        self.agilent_param_dict["dwelltime"] = AGILENT_DWELL_TIME
        self.agilent_param_dict["dwelltimelow"] = AGILENT_DWELL_TIME_LOW
        self.agilent_param_dict["current"] = AGILENT_CURRENT
        self.agilent_param_dict["mode"] = AGILENT_VOLT_SETUP
        self.agilent_param_dict["savedata"] = True
        self.agilent_param_dict["filename"] = None
        self.agilent_param_dict["jogstep"] = AGILENT_JOG_STEP
        self.agilent_param_dict["jogvoltage"] = AGILENT_JOG_VOLTAGE

        self.agilent_save_sequence_file = os.path.join(DEFAULT_RECORD_DIR,
                                    f"{DEFAULT_RECORD_PREFIX_AGILENT_FILE}.csv")

        self.le_agilent_record_fn.setText(os.path.join(
            DEFAULT_RECORD_DIR, f"{DEFAULT_RECORD_PREFIX_AGILENT_FILE}_[DATE].csv"
            ))
        self.ptr_agilent = 0

        # Desactivate all buttons relative to the power supply
        # Toolbar
        self.pb_modify_filepath_agilent.setEnabled(False)
        self.pb_modify_filepath_agilent.clicked.connect(
                                            self.interfero_set_preferences)
        self.pbAgilentCycleRun.setEnabled(False)
        self.pbAgilentCycleStop.setEnabled(False)
        self.cb_agilent_record_at_start.setEnabled(False)
        self.le_agilent_current.setEnabled(False)
        self.cb_agilent_voltage_setup.setCurrentText(
                        "".join([self.agilent_param_dict.get("mode"), "V"]))

        self.le_agilent_vmin.setText(self.agilent_param_dict.get("vmin"))
        self.le_agilent_vmax.setText(self.agilent_param_dict.get("vmax"))
        self.le_agilent_vstep.setText(self.agilent_param_dict.get("vstep"))
        self.le_agilent_dwell_vmin.setText(self.agilent_param_dict.get("dwelltimelow"))
        self.le_agilent_cycle_dwell.setText(self.agilent_param_dict.get("dwelltime"))
        self.le_agilent_current.setText(self.agilent_param_dict.get("current"))
        self.le_agilent_jog_voltage_value.setText(self.agilent_param_dict["jogvoltage"])
        self.le_agilent_jog_step_value.setText(self.agilent_param_dict["jogstep"])

        self.pb_agilent_jog_stop_voltage.setEnabled(False)
        self.pb_agilent_jog_apply_voltage.setEnabled(False)
        self.pb_agilent_jog_apply_voltage.clicked.connect(self.agilent_run_jog_style)
        self.pb_agilent_jog_stop_voltage.clicked.connect(self.agilent_stop_jog_style)
        self.pb_agilent_jog_add_step.clicked.connect(self.agilent_jog_add_voltage)
        self.pb_agilent_jog_sub_step.clicked.connect(self.agilent_jog_sub_voltage)
        validator = QtGui.QDoubleValidator(0.000,25.000,1)
        locale = QLocale(QLocale.English, QLocale.UnitedStates)
        validator.setLocale(locale)
        validator.setNotation(QtGui.QDoubleValidator.StandardNotation)
        self.le_agilent_jog_step_value.setValidator(validator)
        self.le_agilent_jog_voltage_value.setValidator(validator)
        self.agilent_position_vec = {"time": np.array([]),
                                     "voltage": np.array([]),
                                     "datetime": np.array([])}
        self.rs_custom_pref["record_prefix_agilent"] = DEFAULT_RECORD_PREFIX_AGILENT_FILE

    def closeEvent(self, event):
        """
        Function associated to close the main windows
        This action is connected to all actios to close the Main Windows
        Confirmation is asked before closing all.

        Parameters
        ----------
        event : TYPE
            DESCRIPTION.

        Returns
        -------
        None.

        """
        reply = QtWidgets.QMessageBox.question(self,
                                               'Quit',
                                               'Are you sure you want to quit?',
                                               QtWidgets.QMessageBox.Yes |
                                               QtWidgets.QMessageBox.No,
                                               QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            save2jsondict = {}
            if self.le_motor_cycle_relative_step_nb.text() == '':
                save2jsondict["number_of_steps"] = 0
            else:
                save2jsondict["number_of_steps"] = \
                    int(self.le_motor_cycle_relative_step_nb.text())
            save2jsondict["number_of_cycles"] = int(self.le_motor_number_of_cycle.text())
            save2jsondict["dwell_time"] = int(self.le_motor_cycle_dwell.text())
            if self.rb_motor_cycle_up.isChecked():
                save2jsondict["direction"] = "up"
            elif self.rb_motor_cycle_down.isChecked():
                save2jsondict["direction"] = "down"
            else:
                save2jsondict["direction"] = "updown"
            with open(os.path.join(PREFDIR, SESSIONFILENAME), "w") as outfile:
                json.dump(save2jsondict, outfile)
            logging.info("RATTLE SNAKE - session closed.")
            #self.ids.close()
            event.accept()
        else:
            event.ignore()

    def mw_open_about_dialog(self):
        """
        Handler to open the Windows About

        Returns
        -------
        None.

        """
        about_window = RattleSnakeAboutWindows()
        about_window.show()

    def actionClear_Console(self):
        """
        Function to clear the console Text Edit window
        Returns
        -------
        None.
        """
        self.motor_console_message = ""
        self.plainTextEditMotorConnexion.clear()
        self.plainTextEditMotorConnexion.setPlainText(
                                    self.motor_console_message)

    def interfero_set_preferences(self):
        """
        Function to set preference to run interferometer

        Returns
        -------
        None.

        """
        self.interfero_pref_window = IDS3010_preference_windows()
        self.interfero_pref_window.show()
        # Set the value already stored
        self.interfero_pref_window.le_interfero_record_fn.setReadOnly(True)
        self.interfero_pref_window.le_interfero_record_fn.setText(
                                self.rs_custom_pref.get("record_dir"))
        self.interfero_pref_window.le_interfero_prefix_fn.setText(
                                self.rs_custom_pref.get("record_prefix"))
        #self.rs_custom_pref["record_prefix_motor"]
        self.interfero_pref_window.le_motor_prefix_fn.setText(
                                self.rs_custom_pref.get("record_prefix_motor"))
        self.interfero_pref_window.cb_interfero_freq.setCurrentText(
                            f"{self.rs_custom_pref.get('freq')} Hz")
        self.interfero_pref_window.le_interfero_graph_xlabel.setText(
                                self.rs_custom_pref.get("xlabel"))
        self.interfero_pref_window.le_interfero_graph_ylabel.setText(
                                self.rs_custom_pref.get("ylabel"))
        self.interfero_pref_window.sb_interfero_time_range.setValue(int(
                                self.rs_custom_pref.get("time_range")))

        self.interfero_pref_window.pb_interfero_select_fn.clicked.connect(
                                    lambda: self.interfero_select_record_dir())
        self.interfero_pref_window.buttonBox.clicked.connect(
                                            self.interfero_pref_window.accept)
        self.interfero_pref_window.buttonBox.accepted.connect(
                                        self.interfero_accept_record_changes)
        self.interfero_pref_window.buttonBox.rejected.connect(
                                            self.interfero_pref_window.reject)
        # Update labels
        self.displacement_interfero.setLabel('bottom',
                                    text=self.rs_custom_pref["xlabel"])
        self.displacement_interfero.setLabel('left',
                                    text=self.rs_custom_pref["ylabel"])

    def interfero_accept_record_changes(self):
        """
        Function to manage the changes from the preference windows

        Returns
        -------
        None.

        """
        self.rs_custom_pref["record_dir"] = \
                    self.interfero_pref_window.le_interfero_record_fn.text()

        self.rs_custom_pref["record_prefix"] = \
                    self.interfero_pref_window.le_interfero_prefix_fn.text()

        self.rs_custom_pref["record_prefix_motor"] = \
                    self.interfero_pref_window.le_motor_prefix_fn.text()

        self.motor_save_sequence_file = \
            os.path.join(self.rs_custom_pref.get("record_dir"),
                f"{self.rs_custom_pref.get('record_prefix_motor')}.csv")

        self.le_motor_record_fn.setText(os.path.join(
                        self.rs_custom_pref.get("record_dir"),
                        f"{self.rs_custom_pref.get('record_prefix_motor')}_DATE.csv"))

        self.lbl_filepath.setText(f"{self.rs_custom_pref.get('record_dir')}/{self.rs_custom_pref.get('record_prefix')}")
        freq = self.interfero_pref_window.cb_interfero_freq.currentText()
        freq = int(freq.replace("Hz", ""))
        self.rs_custom_pref["freq"] = freq
        self.rs_custom_pref["xlabel"] = \
                    self.interfero_pref_window.le_interfero_graph_xlabel.text()
        self.rs_custom_pref["ylabel"] = \
                    self.interfero_pref_window.le_interfero_graph_ylabel.text()
        self.rs_custom_pref["time_range"] = \
                    self.interfero_pref_window.sb_interfero_time_range.value()
        logging.info("RATTLESNAKE: preferences updated.")
        
        self.displacement_interfero.setLabel('left',
                                    text= self.rs_custom_pref["ylabel"])
        self.displacement_interfero.setLabel('bottom',
                                    text=self.rs_custom_pref["xlabel"])

        self.motor_console_message += "> RATTLESNAKE: preferences updated.\n"
        self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)

    def action_connectInterfero(self, interfero_ipaddress):
        """
        function to establish connexion with interferometer

        Returns
        -------
        None.

        """
        if self.interfero_connected is False:
            self.ids = gui_interfero.IDS_IPGP(interfero_ipaddress)

            status = self.ids.connect()
            if status == "OK":
                self.ids.name = self.ids.system_service.getDeviceName()
                self.ids.current_mode = self.ids.system.getCurrentMode()
                logging.info(f"INTERFERO: {self.ids.name} device connected.")
                self.motor_console_message += f"> INTERFERO: \"{self.ids.name}\" connected at IP: {interfero_ipaddress}\n"
                self.plainTextEditMotorConnexion.setPlainText(
                                                self.motor_console_message)

                # Stop the distance measurement at start of the instantiation.
                if self.ids.current_mode == "measurement running":
                    self.ids.system.stopMeasurement()

                self.ids.master_axis = self.ids.axis.getMasterAxis()
                self.lbl_master_axis_value.setText(str(self.ids.master_axis+1))

                # Alignment windows
                self.pb_align_update.setEnabled(True)
                logging.info(f"INTERFERO: Master axis is Axis {str(self.ids.master_axis+1)}.")
                self.motor_console_message += f"> INTERFERO: Master axis is Axis {str(self.ids.master_axis+1)}.\n"
                self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
                self.pb_align_update.clicked.connect(
                                    lambda: self.interfero_request_aligment())
                self.pb_align_stop.setEnabled(True)
                self.pb_align_stop.clicked.connect(
                                    lambda: self.interfero_stop_aligment())
                self.comboBox_axis_mode.setEnabled(True)
                self.comboBox_axis_mode.currentIndexChanged.connect(
                                    lambda: self.interfero_change_axis_mode())
                # Activate laser
                laser_status = self.ids.pilotlaser.getEnabled()
                if laser_status:
                    self. cb_laser_enabled.setChecked(True)
                else:
                    self.cb_laser_enabled.setChecked(False)
                self. cb_laser_enabled.stateChanged.connect(
                                    lambda: self.interfero_change_laser_mode())

                # Measurement windows
                self.pb_measure_start.setText("Start measurement")
                init_mode = self.ids.system.getInitMode()

                self.cb_init.setCurrentIndex(init_mode)
                self.cb_init.currentIndexChanged.connect(
                            lambda: self.interfero_change_initialization())
                self.pb_measure_start.setEnabled(True)
                self.pb_measure_start.clicked.connect(
                                    lambda: self.interfero_init_measurement())
                self.pb_measure_init.setEnabled(True)
                self.pb_measure_init.clicked.connect(
                                                self.interfero_restart_acq)

                self.interfero_connected = True
                self.stopsig = True
            else:
                logging.info(f"INTERFERO: Connexion failed at IP: {interfero_ipaddress}")
                msg = QtWidgets.QMessageBox()
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setText(f"No device available at {interfero_ipaddress}")
                msg.setInformativeText("Please check address in the config file.")
                msg.setWindowTitle("Device unavailable.")
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()
        else:
            if self.ids.current_mode == "measurement running":
                self.ids.system.stopMeasurement()
                logging.info("INTERFERO: Stop measurement.")
                self.motor_console_message += "> INTERFERO: Stop measurement.\n"
                self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
            self.ids.close()
            logging.info("INTERFERO: Connexion closed")
            self.motor_console_message += "> INTERFERO: Connexion closed.\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
            self.interfero_start_meas = False
            self.pb_align_update.setEnabled(False)
            self.pb_align_stop.setEnabled(False)
            self.pb_measure_record.setEnabled(False)
            self.pb_measure_start.setEnabled(False)
            self.pb_measure_start.setText("Start measurement")
            self.interfero_connected = False
            self.pb_measure_init.setEnabled(True)
            self.pb_measure_init.clicked.connect(self.interfero_restart_acq)

    def interfero_select_record_dir(self):
        """
        Open a subwindows to select another directory to save file.

        Returns
        -------
        None.

        """
        record_dir = QtWidgets.QFileDialog.getExistingDirectory(
                                                    self.interfero_pref_window,
                                                    "Select Directory")
        self.interfero_pref_window.le_interfero_record_fn.setText(record_dir)
        self.rs_custom_pref["record_dir"] = record_dir
        self.interfero_pref_window.le_interfero_prefix_fn.setText(
                            self.rs_custom_pref.get("record_prefix"))

    def interfero_request_aligment(self):
        """
        Handler to start alignement of the interferometer

        Returns
        -------
        None.

        """
        logging.info("INTERFERO: Alignment requested.")
        self.motor_console_message += "> INTERFERO: Alignment requested.s\n"
        self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
        aligned_value = self.ids.action_request_alignement(
                                                        self.ids.master_axis)
        self.pb_align_update.setEnabled(False)
        if aligned_value:
            self.motor_console_message += f"> {self.ids.name} is aligned\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
            self.lbl_contrast_min.setText(str(aligned_value[1]))
            self.lbl_contrast_max.setText(str(aligned_value[2]))
            self.lbl_contrast_min.setToolTip("Contrast of the base band in permille.")
            self.lbl_contrast_max.setToolTip("Offset of the contrast measurement.")
            self.pb_align_update.setEnabled(True)
            logging.info(f"INTERFERO: Alignment: {str(aligned_value[1])}-{str(aligned_value[2])}")
        else:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setText("An error occured during alignement")
            msg.setInformativeText("Please check that the device is not already in use.")
            msg.setWindowTitle("Alignment impossible")
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
            logging.info("INTERFERO: Alignment impossible -> measure on going ?")
            self.pb_align_update.setEnabled(True)

    def interfero_stop_aligment(self):
        """
        Function to stop aligment if on. It may happened if it has
        been requested from the Ethernet interface or Wave software

        Returns
        -------
        None.

        """
        current_mode = self.ids.system.getCurrentMode()
        align_mode_list = ['optics alignment running',
                           "optics alignment starting"]
        if current_mode in align_mode_list:
            self.ids.system.stopOpticsAlignment()
            logging.info("INTERFERO: Stop alignment")

        else:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setText("Alignment mode is not active.")
            msg.setInformativeText(
                    "You can either update constrast or start measurements.")
            msg.setWindowTitle("No alignment on going !")
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()

    def interfero_change_axis_mode(self):
        """
        Handler to modify the axis mode for alignment

        Returns
        -------
        None.

        """
        cb_current_idx = self.comboBox_axis_mode.currentIndex()

        if cb_current_idx in [0, 1]:
            self.ids.axis.setPassMode(cb_current_idx)
            axis_mode = self.comboBox_axis_mode.currentText()
            self.motor_console_message += \
                    f"> INTERFERO: axis mode changed to {axis_mode}\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
            logging.info(f"INTERFERO: axis mode changed to {axis_mode}")
        else:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setText("Single pass and Dual pass are the only available modes")
            msg.setWindowTitle("Axis mode selection error !")
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()

    def interfero_change_laser_mode(self):
        """
        Handler to enable or disable the laser
        The status is checked while connecting the interferometer

        Returns
        -------
        None.

        """
        laserstatus = {"True": "ON", "False": "OFF"}
        cb_laser_status = self.cb_laser_enabled.isChecked()
        if cb_laser_status:
            self.ids.pilotlaser.enable()
        else:
            self.ids.pilotlaser.disable()
        self.motor_console_message += \
                    f"> INTERFERO: pilot laser {laserstatus.get(str(cb_laser_status))}\n"
        self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
        logging.info(f"INTERFERO: pilot laser {laserstatus.get(str(cb_laser_status))}")

    def interfero_init_measurement(self):
        """
        Handler to start streaming the signal
        Alignment must be off before starting measurements

        This function is based on the beta version of streaming provided by
        ATTOCUBE on its github:
            https://github.com/attocube-systems/IDS-APIs

        Returns
        -------
        None.

        """
        if self.interfero_start_meas is False:
            current_mode = self.ids.system.getCurrentMode()
            if current_mode == "system idle":
                self.motor_console_message += "> INTERFERO: initialization on going..\n"
                self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
                logging.info("INTERFERO: initialization on going.")
                errNo = self.ids.system.startMeasurement()
                self.motor_console_message += f"> INTERFERO: distance measurement started with error ({errNo})\n"
                self.plainTextEditMotorConnexion.setPlainText(
                                            self.motor_console_message)
                while self.ids.system.getCurrentMode() != "measurement running":
                    time.sleep(0.5)
                msg = QtWidgets.QMessageBox()
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setText("Measurement mode is now running")
                msg.setInformativeText("Acquisition is starting soon.")
                msg.setWindowTitle("Measurement mode available.")
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()
                logging.info(f"INTERFERO: distance measurement started with error ({errNo})")
                if errNo is not None:
                    errNo2str = self.ids.system_service.errorNumberToString(1, errNo)
                    self.motor_console_message += f"> INTERFERO: {errNo2str}"
                    self.plainTextEditMotorConnexion.setPlainText(
                                                        self.motor_console_message)
                else:
                    self.init_abs_pos = self.ids.displacement.getAbsolutePosition(
                        self.ids.master_axis)
                    self.lbl_ref_position_value.setText(str(self.init_abs_pos[1]))
                    logging.info(f"INTERFERO: Initial absolute position: {self.init_abs_pos[1]} pm")
                    self.interfero_start_meas = True
                    self.pb_measure_start.setText("Stop measurement")
                    self.pb_measure_record.setEnabled(True)
                    self.interfero_recording_state = False
                    self.pb_measure_record.clicked.connect(
                                lambda: self.interfero_record_datastreaming())
                self.interfero_start_aquisition()
            elif current_mode == "measurement running":
                self.interfero_start_aquisition()
                self.interfero_recording_state = False
                self.interfero_start_meas = True
                self.pb_measure_start.setText("Stop measurement")
                self.pb_measure_record.setEnabled(True)
                self.pb_measure_record.clicked.connect(
                                lambda:self.interfero_record_datastreaming())
            elif current_mode in ["optics alignment starting",
                                  "optics alignment running"]:
                msg = QtWidgets.QMessageBox()
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setText("Alignment is running")
                msg.setInformativeText("Stop alignment before acquisition.")
                msg.setWindowTitle("Device unavailable.")
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()

        else:
            if self.mon_timer is not None:
                if self.interfero_recording_state:
                    reply = QtWidgets.QMessageBox.question(self,
                                               'Record on going...',
                                               'Stopping the measurement will also stop recording.\n Are you sure ?',
                                               QtWidgets.QMessageBox.Yes |
                                               QtWidgets.QMessageBox.No,
                                               QtWidgets.QMessageBox.No)
                    if reply == QtWidgets.QMessageBox.Yes:
                        self.ids_stream.stopRecording()
                        self.pb_measure_record.setStyleSheet("background-color: None")
                        self.pb_measure_record.setText("Start recording")
                        self.interfero_recording_state = False
                        logging.info("INTERFERO: stop recording stream")
                self.killTimer(self.mon_timer)
                self.mon_timer = None
                self.stopsig = True
                self.ids_stream.close()
                self.ids.system.stopMeasurement()
                self.pb_measure_record.setEnabled(False)
                self.pb_measure_start.setText("Start measurement")
                self.interfero_start_meas = False
                self.interfero_recording_state = False

    def interfero_init_for_record_cycle(self, specific_time = None):
        """
            Function to start and to sync the record of the displacement
            of the motor by the interferometer.
            
        """
        if not self.interfero_connected:
            self.init_interfero()
            self.action_connectInterfero(INTERFERO_IP)
            self.action_connect_interfero.setChecked(True)
            logging.info("INTERFERO: Device connected (cycle request).")
        else:
            logging.info("INTERFERO: Device already connected (cycle request).")

        if not self.interfero_start_meas:
            self.interfero_init_measurement()
            logging.info("INTERFERO: measurement started (cycle request).")
        else:
            logging.info("INTERFERO: measurement already started (cycle request).")

        if not self.interfero_recording_state:
            self.interfero_record_datastreaming(specific_time=specific_time)
            logging.info("INTERFERO: recording requested (cycle request).")
            time.sleep(3)
        else:
            logging.info("INTERFERO: recording already started (cycle request).")

    def interfero_restart_acq(self):
        if self.interfero_recording_state:
            reply = QtWidgets.QMessageBox.question(self,
                'Record on going...',
                'Initializing will also stop recording.\n Are you sure ?',
                QtWidgets.QMessageBox.Yes |
                QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No)
            if reply == QtWidgets.QMessageBox.Yes:
                # stop recording first
                self.ids_stream.stopRecording()
                self.pb_measure_record.setStyleSheet("background-color: None")
                self.pb_measure_record.setText("Start recording")
                self.interfero_recording_state = False
                logging.info("INTERFERO: Stop recording stream")
                self.motor_console_message += "> INTERFERO: Stop recording stream.\n"
                self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
                # stop measurement
        if self.mon_timer is not None:
            self.killTimer(self.mon_timer)
            self.mon_timer = None
        self.stopsig = True
        self.ids.system.stopMeasurement()
        logging.info("INTERFERO: Stop measurement.")
        self.motor_console_message += "> INTERFERO: Stop measurement.\n"
        self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
        self.pb_measure_start.setText("Start measurement")
        self.interfero_start_meas = False
        time.sleep(3)
        errNo = self.ids.system.startMeasurement()
        
        logging.info(f"INTERFERO: distance measurement started with error ({errNo})")
        self.motor_console_message += \
            f"> INTERFERO: distance measurement started with error ({errNo})\n"
        self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
        if errNo is not None:
            errNo2str = self.ids.system_service.errorNumberToString(1, errNo)
            self.motor_console_message += f"> INTERFERO: {errNo2str}"
            self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)

    def interfero_change_initialization(self):
        """
        Handler to change initialisation mode
        Two modes available:
            - Quick Initialization
            - High Accuracy Initialization

        Returns
        -------
        None.

        """
        initstatus = {"0": "High Accuracy Initialization",
                      "1": "Quick Initialization"}
        cb_initval = self.cb_init.currentIndex()
        if cb_initval in [0, 1]:
            self.ids.system.setInitMode(cb_initval)
            self.motor_console_message += \
                    f"> INTERFERO: initialization procedure -> {initstatus.get(str(cb_initval))}\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
        logging.info(f"INTERFERO: initialization procedure -> {initstatus.get(str(cb_initval))}")

    def interfero_read_streaming_data(self, buffersize):
        self.ids.master_axis = self.ids.axis.getMasterAxis()
        while not self.stopsig:
            _, axis0, axis1, axis2 = self.ids_stream.read(buffersize)
            if self.ids.master_axis == 0:
                axis = axis0
            elif self.ids.master_axis == 1:
                axis = axis1
            else:
                axis = axis2
            self.data = np.append(self.data, axis)

    def timerEvent(self, _):
        """
        Function executed every "period_timer"
        It updates the plot by comparing the size already plotted
        with the complete size of the data.
        """

        # ---------
        # Update interferometer data if start button pushed.
        if self.interfero_connected and self.interfero_start_meas:
            new_len_data = len(self.data)
            old_len_data = self.lendata_temp
            #print(new_len_data, old_len_data)
            # Version cumulative du plot... trop gourmand en memoire
            # abandonne dans un premier temps mais besoin de le mettre
            # en place
            # if new_len_data > old_len_data:
            #     for i in range(old_len_data, new_len_data):
            #         self.disp_vec[self.ptr] = float(self.data[i] / 1e9)
            #         self.ptr += 1
            #         if self.ptr >= self.disp_vec.shape[0]:
            #             tmp_pos = self.disp_vec
            #             self.disp_vec = np.empty(self.disp_vec.shape[0]*2)
            #             self.disp_vec[:tmp_pos.shape[0]] = tmp_pos
            #         self.curve_interfero.setData(self.disp_vec[:self.ptr],
            #                                      _callSync='off')
            #         self.curve_interfero.setPos(-self.ptr, 0)
            #     self.lendata_temp = new_len_data

            if new_len_data > old_len_data:
                for i in range(old_len_data, new_len_data):
                    self.disp_vec[:-1] = self.disp_vec[1:]  # shift data in the temporal mean 1 sample left
                    self.disp_vec[-1] = float(self.data[i] / 1e9)  # vector containing the instantaneous values
                    self.ptr -= 1
                self.curve_interfero.setData(self.disp_vec, _callSync='off')
                self.lendata_temp = new_len_data
            else:
                pass

        if self.agilent_cycle_running:
            new_len_data_agilent = len(self.agilent_position_vec.get("voltage"))
            old_len_data_agilent = self.lendata_temp_agilent

            if new_len_data_agilent > old_len_data_agilent:

                for i in range(old_len_data_agilent, new_len_data_agilent):
                    self.rt_voltage_agilent[self.ptr_agilent] = self.agilent_position_vec.get("voltage")[i]
                    self.rt_time_agilent[self.ptr_agilent] = self.agilent_position_vec.get("datetime")[i]
                    self.ptr_agilent += 1
                    if self.ptr_agilent >= self.rt_voltage_agilent.shape[0]:
                        tmp_pos_agilent = self.rt_voltage_agilent
                        self.rt_voltage_agilent = np.empty(self.rt_voltage_agilent.shape[0]*2)
                        self.rt_voltage_agilent[:tmp_pos_agilent.shape[0]] = tmp_pos_agilent
                        tmp_time_agilent = self.rt_time_agilent
                        self.rt_time_agilent = np.empty(self.rt_voltage_agilent.shape[0]*2)
                        self.rt_time_agilent[:tmp_time_agilent.shape[0]] = tmp_time_agilent
                    self.curve_motor.setData(
                        self.rt_time_agilent[:self.ptr_agilent] - self.rt_time_agilent[0],
                        self.rt_voltage_agilent[:self.ptr_agilent], _callSync='off')
                self.lendata_temp_agilent = new_len_data_agilent
            else:
                pass

        # ---------
        # Update motor data if start button pushed.
        if self.motor_cycle_running:
            new_len_datamotor = len(self.motor_position_vec.get("pos"))
            old_len_datamotor = self.lendata_temp_motor

            if new_len_datamotor > old_len_datamotor:
                for i in range(old_len_datamotor, new_len_datamotor):
                    self.rt_pos_motor[self.ptr_motor] = self.motor_position_vec.get("pos")[i]
                    self.rt_time_motor[self.ptr_motor] = self.motor_position_vec.get("datetime")[i]
                    self.ptr_motor += 1
                    if self.ptr_motor >= self.rt_pos_motor.shape[0]:
                        tmp_pos = self.rt_pos_motor
                        self.rt_pos_motor = np.empty(self.rt_pos_motor.shape[0]*2)
                        self.rt_pos_motor[:tmp_pos.shape[0]] = tmp_pos
                        tmp_time = self.rt_time_motor
                        self.rt_time_motor = np.empty.shape[0]*2
                        self.rt_time_motor[:tmp_time.shape[0]] = tmp_time
                    self.curve_motor.setData(self.rt_time_motor[:self.ptr_motor] - self.rt_time_motor[0],
                                             self.rt_pos_motor[:self.ptr_motor],
                                             _callSync='off')
                self.lendata_temp_motor = new_len_datamotor
            else:
                pass

    def interfero_start_aquisition(self):
        """
        Function to check if the interferometer is in
        the running mode or not.

        Returns
        -------
        None.

        """
        
        # Plot part
        self.windowWidth = int(self.rs_custom_pref["freq"]*self.rs_custom_pref["time_range"])
        # self.windowWidth = 10000
        self.disp_vec = np.linspace(0, 0, self.windowWidth)

        #self.disp_vec = np.array([])
        #self.disp_vec = np.repeat(self.init_abs_pos, 1)
        #self.displacement_interfero.clear()

        self.ptr = 0
        self.stopsig = False
        self.interfero_recording_state = False
        # Threads part
        self.threadpool = QThreadPool()
        if self.mon_timer is None:
            if self.ids.system.getCurrentMode() == "measurement running":
                self.mon_timer = self.startTimer(self.period_timer)
                axis0, axis1, axis2 = self.ids.master_axis == 0,\
                                    self.ids.master_axis == 1,\
                                    self.ids.master_axis == 2
                kwargs_stream = {"filePath": None,
                                 "axis0": axis0,
                                 "axis1": axis1,
                                 "axis2": axis2
                                 }
                interval_msec = int(1e6/self.rs_custom_pref["freq"])
                # Following buffersize provided by ATTOCUBE
                BUFFERSIZE = int((min(1023, max(1, 1000000/interval_msec/25))+1+2)*4)

                self.ids_stream = ids_stream.Stream(INTERFERO_IP, True,
                                                    interval_msec,
                                                    **kwargs_stream)
                self.ids_stream.open()

                logging.info(f"INTERFERO: start streaming @{interval_msec} Hz")
                worker = Worker(self.interfero_read_streaming_data,
                                BUFFERSIZE)
                self.threadpool.start(worker)
            else:
                msg = QtWidgets.QMessageBox()
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setText("Please wait, interfero not yet ready")
                msg.setInformativeText("Initialization on going")
                msg.setWindowTitle("Device unavailable.")
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()

    def interfero_record_datastreaming(self, specific_time=None):
        """
        Function to handle the recording ot the streaming
        into a file.
        Returns
        -------
        None.
        """
        if self.interfero_recording_state is not True:
            if specific_time is None:
                self.timenow = datetime.datetime.now().isoformat()
            else:
                self.timenow = specific_time

            self.timenow = self.timenow.replace(":", "_")
            self.timenow = self.timenow.replace("-", "_")
            self.timenow = self.timenow.replace(".", "_")
            self.interfero_record_fn = os.path.join(
                self.rs_custom_pref.get("record_dir"),
                f"{self.rs_custom_pref.get('record_prefix')}_{self.timenow}.aws")
            logging.info(f"INTERFERO: start recording stream to {self.interfero_record_fn}")
            self.motor_console_message += f"> INTERFERO: start recording stream to {self.interfero_record_fn}.\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
            self.ids_stream.startRecording(self.interfero_record_fn)
            self.pb_measure_record.setStyleSheet("background-color: red")
            self.pb_measure_record.setText("Stop recording")
            self.interfero_recording_state = True
        else:
            self.ids_stream.stopRecording()
            self.pb_measure_record.setStyleSheet("font-size: 13px")
            self.pb_measure_record.setText("Start recording")
            self.interfero_recording_state = False
            logging.info("INTERFERO: stop recording stream")
            self.motor_console_message += "> INTERFERO: stop recording.\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)

    def actionConnectMotor(self):
        """
        Function to start the motor, connected to the button
        action_connect_motor.

        Returns
        -------
        None.
        """
        self.motor_connect_device()

        # Motor / Setup tab
        self.btnApplyMotorDefault.clicked.connect(
                                        lambda: self.motor_set_default_setup())
        self.btnApplyMotorApply.clicked.connect(
                                        lambda: self.motor_apply_new_setup())

        self.rb_motor_jog.clicked.connect(
            lambda: self.motor_rb_motion_type_check("rb_motor_jog"))
        self.rb_motor_relative.clicked.connect(
            lambda: self.motor_rb_motion_type_check("rb_motor_relative"))

        self.rbPositionTarget.clicked.connect(
            lambda: self.motor_rb_target_type_check("rb_motor_pos_target"))
        self.rbRelativeTarget.clicked.connect(
            lambda: self.motor_rb_target_type_check("rb_motor_rel_target"))

        # Motor / Jog Tab
        self.lineEditrelativeStepNumber.setValidator(QtGui.QIntValidator())
        self.lineEditrelativeStepNumber.setText(
                                    str(self.motor_relative_step_number_value))

        self.le_motor_cycle_relative_step_nb.setValidator(
                                                        QtGui.QIntValidator())

    def motor_update_pref_jog_tab(self):
        """
        Function to update all the buttons in one time

        Returns
        -------
        None.

        """
        self.rb_motor_jog.setChecked(False)
        self.rb_motor_jog_is_checked = False
        self.rb_motor_relative.setChecked(True)
        self.rb_motor_relative_is_checked = True
        # self.rb_motor_cycle.setChecked(False)

    def motor_update_pref_cycle_tab(self):
        """
        Function to update all the buttons in one time

        Returns
        -------
        None.
        """

        self.rb_motor_jog.setChecked(False)
        self.rb_motor_jog_is_checked = False
        self.rb_motor_relative_is_checked = False
        self.rb_motor_relative.setChecked(False)
        # self.rb_motor_cycle.setChecked(True)

    def motor_connect_device(self):
        """
        Function to connect picomotor. It is instanciating the motor object
        After opening the USB connexion, the function read the default value
        (position, velocity and acceleration)
        """
        if self.motor_connexion_status == 0:
            # self.init_motor()
            # convert hex value in string to hex value
            self.motor_id_product = int(DEFAULTIDPRODUCT, 16)
            self.motor_id_vendor = int(DEFAULTIDVENDOR, 16)

            self.picomotor = Pico8742Ctrl(idProduct=self.motor_id_product,
                                          idVendor=self.motor_id_vendor)

            # If motor is connected, activate all the button to play with it
            if self.picomotor.message != "ERROR: Device not found":

                # MOTOR/JOG Panel Set default value
                self.motor_default_acc = self.picomotor.get_acceleration()
                pos = self.motor_default_acc.find(">")
                self.motor_default_acc = self.motor_default_acc[pos+1:]
                self.motor_acc = self.motor_default_acc

                self.motor_default_vel = self.picomotor.get_velocity()
                pos = self.motor_default_vel.find(">")
                self.motor_default_vel = self.motor_default_vel[pos+1:]

                self.motor_default_pos = self.picomotor.get_position()
                pos = self.motor_default_pos.find(">")
                self.motor_default_pos = self.motor_default_pos[pos+1:]

                self.lineEditacceleration.setText(self.motor_default_acc)
                self.lineEditvelocity.setText(self.motor_default_vel)
                self.lineEditpositionstatus.setText(self.motor_default_pos)

                # Activate all pushbuttons
                self.btnApplyMotorApply.setEnabled(True)
                self.btnApplyMotorDefault.setEnabled(True)

                # Update console message
                self.motor_console_message += f"> {self.picomotor.message}\n"
                self.plainTextEditMotorConnexion.setPlainText(
                                                self.motor_console_message)
                self.motor_connexion_status = 1
                self.motor_run_status = False
                self.statusBar().showMessage("MOTOR: Motor connected")
                logging.info("MOTOR: Motor connected.")
                self.motor_update_current_position()
                self.pbMotorJogRun.setEnabled(True)
                self.pbMotorJogRun.clicked.connect(
                                lambda: self.motor_run_jog_relative_style())

                self.pbMotorJogClockWise.setEnabled(True)
                self.pbMotorJogClockWise.clicked.connect(
                                lambda: self.motor_set_direction("+"))
                self.pbMotorJogAntiClockWise.setEnabled(True)
                self.pbMotorJogAntiClockWise.clicked.connect(
                                lambda: self.motor_set_direction("-"))
                self.pbMotorCycleRun.setEnabled(True)
                self.pbMotorCycleRun.clicked.connect(
                                lambda: self.motor_run_cycle_style())

                self.motor_load_last_session_param()
                self.cb_record_at_start.setEnabled(True)

            else:
                self.motor_console_message += f"> {self.picomotor.message}\n"
                self.plainTextEditMotorConnexion.setPlainText(
                                self.motor_console_message)

                self.statusBar().showMessage('Motor not connected')
                self.action_connect_motor.setChecked(False)
                #self.picomotor.close()
                del self.picomotor

        else:
            reply = QtWidgets.QMessageBox.question(self,
                                        'Do you want to disconnect motor ?',
                                        'Are you sure ?',
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        QtWidgets.QMessageBox.No)

            if reply == QtWidgets.QMessageBox.Yes:
                motorcmd = "ST"  # to send stop command to the motor
                self.picomotor.command(motorcmd)
                self.motor_connexion_status = 0
                self.motor_run_status = False
                self.motor_cycle_running = False
                self.picomotor.close()
                del self.picomotor
                self.pbMotorJogRun.setEnabled(False)
                self.pbMotorCycleRun.setEnabled(False)

                self.pbMotorJogRun.setChecked(False)
                self.pbMotorJogRun.setEnabled(False)
                self.pbMotorJogStop.setEnabled(False)

                self.pbMotorCycleRun.setChecked(False)
                self.pbMotorCycleStop.setChecked(False)
                self.pbMotorCycleRun.setEnabled(False)
                self.pbMotorCycleStop.setEnabled(False)

                self.pbMotorJogClockWise.setChecked(False)
                self.pbMotorJogAntiClockWise.setChecked(False)
                self.motor_console_message += f"> {MESSAGEMOTORDISCONNECTED}\n"
                self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
                self.statusBar().showMessage('Motor disconnected')
                logging.info("Motor disconnected by user.")
                # self.action_connect_motor.setChecked(False)
            else:
                pass

    def motor_load_last_session_param(self):
        """
        Function to load the parameters of the last session to avoid to refill
        all the fields each time.
        Returns
        -------
        None.
        """
        global PREFDIR
        listfilesession = glob.glob(os.path.join(PREFDIR, SESSIONFILENAME))
        if len(listfilesession) > 0:
            latest_file = max(listfilesession, key=os.path.getctime)
            with open(latest_file) as json_file:
                motor_cycle_param_dict = json.load(json_file)
                self.le_motor_cycle_dwell.setText(
                    str(motor_cycle_param_dict["dwell_time"]))
                self.le_motor_number_of_cycle.setText(
                    str(motor_cycle_param_dict["number_of_cycles"]))
                self.le_motor_cycle_relative_step_nb.setText(
                    str(motor_cycle_param_dict["number_of_steps"]))

                if motor_cycle_param_dict["direction"] == "up":
                    self.rb_motor_cycle_up.setChecked(True)
                elif motor_cycle_param_dict["direction"] == "down":
                    self.rb_motor_cycle_down.setChecked(True)
                else:
                    self.rb_motor_cycle_updown.setChecked(True)
                self.motor_console_message += "> Session parameters loaded.\n"
                self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
                logging.info("RATTLE SNAKE: Load parameters of the previous session.")
        else:
            self.motor_console_message += "> No session file found.\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
            logging.warning("No parameters files found.")

    def motor_set_direction(self, direction):
        """
        Function to set buttons and parameters with the motor direction
        Parameters
        ----------
        direction : str -> either "+" or "-": "+" if clockwise direction of
                    motor is selected. "-" if it is the anticlockwise direction
                    which has been choosen.
        Returns
        -------
        None.
        """
        if direction == "-":
            self.pbMotorJogAntiClockWise.setChecked(True)
            self.pbMotorJogAntiClockWise.setStyleSheet("background-color: Green")
            self.pbMotorJogClockWise.setStyleSheet("background-color: None")
            self.pbMotorJogClockWise.setChecked(False)
            self.motordirection = "-"

        else:
            self.pbMotorJogAntiClockWise.setChecked(False)
            self.pbMotorJogClockWise.setChecked(True)
            self.pbMotorJogClockWise.setStyleSheet("background-color: Green")
            self.pbMotorJogAntiClockWise.setStyleSheet("background-color: None")
            self.motordirection = "+"

    def motor_set_default_setup(self):
        """
        Function to set position, acceleration
        and velocity to the defaults values.
        """
        reply = QtWidgets.QMessageBox.question(self,
                                               'Set to default values',
                                               'Are you sure ?',
                        QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                        QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            self.lineEditacceleration.setValidator(QtGui.QIntValidator())
            self.lineEditacceleration.setText(self.motor_default_acc)
            self.motor_acc = self.motor_default_acc
            self.lineEditvelocity.setValidator(QtGui.QIntValidator())
            self.lineEditvelocity.setText(self.motor_default_vel)
            self.motor_vel = self.motor_default_vel
            self.lineEditpositionstatus.setValidator(QtGui.QIntValidator())
            self.lineEditpositionstatus.setText(self.motor_default_pos)

            self.motor_pos = self.motor_default_pos
        else:
            pass

    def motor_initialize_number_of_cycle(self):
        """
        Function to put the number of cycle on Motor Jog Tab

        Returns
        -------
        None.
        """
        self.le_motor_number_of_cycle.setValidator(
                                    QtGui.QIntValidator(0, MAXNUMBEROFCYCLE))

    def motor_update_current_position(self):
        """
        Function to update the Current motor position LCD. The function is
        sending a command to the motor to check the current position.

        Returns
        -------
        None.

        """
        self.motor_current_pos = self.picomotor.get_position()
        pos = self.motor_current_pos.find(">")
        self.motor_current_pos = self.motor_current_pos[pos+1:]
        self.lcdNumberCurrentPos.display(self.motor_current_pos)

    def motor_apply_new_setup(self):
        """
        Function to set position, acceleration
        and velocity with some new values.

        """
        reply = QtWidgets.QMessageBox.question(self, 'Save the new values',
                                               'Are you sure ?',
                                               QtWidgets.QMessageBox.Yes |
                                               QtWidgets.QMessageBox.No,
                                               QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            self.lineEditacceleration.setValidator(
                                    QtGui.QIntValidator(1, MAXVELOCITY, self))
            self.lineEditvelocity.setValidator(
                                    QtGui.QIntValidator(1, MAXACCELERATION,
                                                        self))
            self.lineEditpositionstatus.setValidator(QtGui.QIntValidator())
            if self.lineEditacceleration.text() != self.motor_acc:
                self.motor_acc = self.lineEditacceleration.text()
                cmd_2_motor = f"{self.picomotor.channel}AC{self.motor_acc}"
                self.picomotor.command(cmd_2_motor)
                self.motor_console_message += f"> {cmd_2_motor} (Set new acceleration)\n"
            if self.lineEditvelocity.text() != self.motor_vel:
                self.motor_vel = self.lineEditvelocity.text()
                cmd_2_motor = f"{self.picomotor.channel}VA{self.motor_vel}"
                self.picomotor.command(cmd_2_motor)
                self.motor_console_message += f"> {cmd_2_motor} (Set new velocity)\n"
            if self.lineEditpositionstatus.text() != self.motor_pos:
                self.motor_pos = self.lineEditpositionstatus.text()
                cmd_2_motor = f"{self.picomotor.channel}DH{self.motor_pos}"
                self.picomotor.command(cmd_2_motor)
                self.motor_console_message += f"> {cmd_2_motor} (Set new home position)\n"
                self.motor_update_current_position()
            self.plainTextEditMotorConnexion.setPlainText(self.motor_console_message)
        else:
            pass

    def motor_setdefault_status(self):
        """
        Function to set position, acceleration and velocity to the
        defaults values.
        """
        reply = QtWidgets.QMessageBox.question(self,
                                               "My title",
                                               "Set to default values",
                                               'Are you sure ?',
                                               QtWidgets.QMessageBox.Yes |
                                               QtWidgets.QMessageBox.No,
                                               QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            self.lineEditacceleration.setText(self.motor_default_acc)
            self.motor_acc = self.motor_default_acc
            self.lineEditvelocity.setText(self.motor_default_vel)
            self.motor_vel = self.motor_default_vel
            self.lineEditpositionstatus.setText(self.motor_default_pos)
            self.motor_pos = self.motor_default_pos
            self.motor_update_current_position()
            self.motor_console_message += "> ACC, VEL and POS - Set to default value\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
        else:
            pass

    def motor_run_jog_relative_style(self):
        """
        Action function associated to the "Go !" pushButton in Motor/Jog tab
        The function run the motor using the Jog (free motion) or Relative
        motion. In relative motion, user can choose a target distance or a
        target position. Both are expressed in number of steps whith must be
        a positive integer.

        While "Go !" pushButton is clicked, user can click again to abort the
        motion.

        The process is running in an independant thread.

        Returns
        -------
        None.
        """
        # whichtab = self.tabMotorConnexion.currentIndex()
        # print(whichtab)
        try:
            if self.motor_run_status is False:  # Check the motor not running
                self.pbMotorJogStop.clicked.connect(
                                lambda: self.motor_stop_jog_relative_style())
                self.pbMotorJogStop.setEnabled(True) 
                #  # Check direction
                if self.rb_motor_jog.isChecked():
                    if self.motordirection is not None:
                        self.motor_run_status = True
                        motorchannel = self.picomotor.channel
                        motorcmd = f"{motorchannel}MV{self.motordirection}"
                        # Thread part
                        kwargs = {"command": motorcmd}
                        worker = Worker(self.motor_run_single_command,
                                        **kwargs)
                        self.pbMotorJogRun.setChecked(True)
                        self.threadpool.start(worker)
                        self.motor_console_message += f"> Motor command: {motorcmd}\n"
                        self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
                    else:
                        self.pbMotorJogRun.setChecked(False)
                        self.motor_run_status = False
                        msg = QtWidgets.QMessageBox()
                        msg.setIcon(QtWidgets.QMessageBox.Warning)
                        msg.setText("Please select a direction first!")
                        msg.setWindowTitle("No motor direction selected.")
                        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                        msg.exec_()
                elif self.rb_motor_relative.isChecked():
                    if self.rbRelativeTarget.isChecked():
                        if self.motordirection is not None:
                            middle_cmd_text = "PR"  # Motor command xxPRnn
                            if int(self.lineEditrelativeStepNumber.text()) >= 0:
                                target = self.lineEditrelativeStepNumber.text()
                                self.motor_run_status = True
                                motorchannel = self.picomotor.channel
                                motorcmd = f"{motorchannel}{middle_cmd_text}{self.motordirection}{target}"
                                # Thread part
                                kwargs = {"command": motorcmd}
                                worker = Worker(self.motor_run_single_command, **kwargs)
                                self.pbMotorJogRun.setChecked(True)
                                self.threadpool.start(worker)
                                self.motor_console_message += f"> Motor command: {motorcmd}\n"
                                self.plainTextEditMotorConnexion.setPlainText(
                                                        self.motor_console_message)
                                time.sleep(2)
                                self.motor_update_current_position()
                            else:
                                self.pbMotorJogRun.setChecked(False)
                                self.motor_run_status = False
                                msg = QtWidgets.QMessageBox()
                                msg.setIcon(QtWidgets.QMessageBox.Warning)
                                msg.setText("Please enter the relative distance expected !")
                                msg.setInformativeText("This must be a positive integer.")
                                msg.setWindowTitle("No relative distance set")
                                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                                msg.exec_()
                        else:
                            self.pbMotorJogRun.setChecked(False)
                            self.motor_run_status = False
                            msg = QtWidgets.QMessageBox()
                            msg.setIcon(QtWidgets.QMessageBox.Warning)
                            msg.setText("Please select a direction first !")
                            msg.setWindowTitle("No motor direction selected.")
                            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                            msg.exec_()
                    else:
                        middle_cmd_text = "PA"  # Motor command xxPAnn
                        target = self.lineEditAbsolutePosition.text()
                        self.motor_run_status = True
                        motorchannel = self.picomotor.channel
                        motorcmd = f"{motorchannel}{middle_cmd_text}{target}"
                        # Thread part
                        kwargs = {"command": motorcmd}
                        worker = Worker(self.motor_run_single_command, **kwargs)
                        self.pbMotorJogRun.setChecked(True)
                        self.threadpool.start(worker)
                        self.motor_console_message += f"> Motor command: {motorcmd}\n"
                        self.plainTextEditMotorConnexion.setPlainText(
                                                self.motor_console_message)
                        time.sleep(2)
                        self.motor_update_current_position()

        except usb.core.USBError:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setText("Device unavailable")
            msg.setInformativeText("Restart program and make sure that the\
                                   motor is properly plugged.")
            msg.setWindowTitle("Device unavailable")
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()

    def motor_stop_jog_relative_style(self):
        """
        Handler to stop the motor

        Returns
        -------
        None.

        """
        if self.motor_run_status:
            motorcmd = "ST"  # to send stop command to the motor
            self.picomotor.command(motorcmd)
            time.sleep(2)
            #self.threadpool.clear()
            self.motor_console_message += \
                                f"> Motor command: {motorcmd} (STOP MOTOR)\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                self.motor_console_message)

            self.motor_run_status = False
            self.pbMotorJogRun.setChecked(False)
            self.pbMotorJogStop.setEnabled(True)

            self.motor_update_current_position()
            logging.info("MOTOR: Execution stopped.")

    def motor_run_cycle_style(self):
        """
        Action function associated to the "Go !" pushButton in Motor/Jog tab
        The function run the motor using the Jog (free motion) or Relative
        motion. In relative motion, user can choose a target distance or a
        target position. Both are expressed in number of steps which must be
        a positive integer.

        While "Go !" pushButton is clicked, user can click again to abort the
        motion.

        The process is running in an independant thread.

        Returns
        -------
        None.

        """
        self.stop_the_motor = False
        self.pbMotorCycleStop.setEnabled(True)
        self.pbMotorCycleStop.clicked.connect(self.motor_stop_cycle_style)

        # Empty the position dictionnary before start.
        self.motor_cycle_param_dict = {}
        self.motor_position_vec = {"time": np.array([]),
                                   "pos": np.array([]),
                                   "datetime": np.array([])}
        self.ptr_motor = 0

        logging.info(f"MOTOR: Setting-VELOCITY: {self.motor_default_vel}")
        logging.info(f"MOTOR: Setting-ACCELERATION: {self.motor_default_acc}")
        self.motor_update_current_position()
        logging.info(f"MOTOR: Setting-START POS: {self.picomotor.get_position()}")

        if self.save_data_from_motor_cycle:
            self.timenow = datetime.datetime.now().isoformat()
            self.timenow = self.timenow.replace(":", "_")
            self.timenow = self.timenow.replace("-", "_")
            self.timenow = self.timenow.replace(".", "_")
            self.motor_save_sequence_file = os.path.join(
                self.rs_custom_pref.get("record_dir"),
                f"{self.rs_custom_pref['record_prefix_motor']}_{self.timenow}.csv")
            logging.info(f"MOTOR: data saved in {self.motor_save_sequence_file}")
            self.motor_console_message +=\
                    f"> MOTOR: data saved in {self.motor_save_sequence_file}\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
            self.motor_file_instance = open(self.motor_save_sequence_file, "a")
            self.motor_file_instance_writer = csv.writer(
                                                    self.motor_file_instance)
        try:
            if not self.motor_run_status:
                if self.cb_record_at_start.isChecked():
                    logging.info("INTERFERO: Automatic starting before motor cycling.")
                    self.interfero_init_for_record_cycle(
                                                specific_time=self.timenow)

                logging.info("MOTOR: Cycle started...")
                dwelltime = int(self.le_motor_cycle_dwell.text())
                nbcycle = int(self.le_motor_number_of_cycle.text())
                nbstep = self.le_motor_cycle_relative_step_nb.text()

                # The motor is running #cycles times up (clockwise) then
                #                       cycles times down (anticlockwise)

                cycletype = None
                if self.rb_motor_cycle_updown.isChecked():
                    cycletype = "updown"
                elif self.rb_motor_cycle_up.isChecked():
                    cycletype = "up"
                elif self.rb_motor_cycle_down.isChecked():
                    cycletype = "down"
                else:
                    pass

                if cycletype is not None:
                    logging.info(f"MOTOR: Motor cycle direction: {cycletype}")
                    dictdirection = {}
                    dictdirection["up"] = ["+"]
                    dictdirection["down"] = ["-"]
                    dictdirection["updown"] = ["+", "-"]
                    self.motor_run_status = True
                    self.pbMotorCycleRun.setEnabled(False)
                    channel = self.picomotor.channel
                    kwargs = {"dwelltime": dwelltime, "nbcycle": nbcycle,
                              "nbstep": nbstep, "channel": channel,
                              "cycletype": cycletype}
                    worker = Worker(self.motor_run_cycle_command,
                                    **kwargs)
                    self.threadpool.start(worker)

        except usb.core.USBError:
            msg = QtWidgets.QMessageBox()
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setText("Device unavailable")
            msg.setInformativeText("Restart program and make sure that the\
                                   motor is properly plugged.")
            msg.setWindowTitle("MOTOR: Device unavailable")
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()

    def motor_stop_cycle_style(self):
        """
        Handler to stop a motor cycle on going.


        Returns
        -------
        None.

        """
        if self.motor_run_status:
            motorcmd = "ST"
            self.picomotor.command(motorcmd)  # Send command to stop motor
            self.stop_the_motor = True
            self.motor_run_status = False
            self.motor_cycle_running = False
            endtime = datetime.datetime.now()
            logging.info(f"{endtime}: Motor Stopped.")
            self.motor_console_message += f"> {motorcmd} (STOP MOTOR)\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                self.motor_console_message)
            if self.save_data_from_motor_cycle:
                self.motor_file_instance.close()
                self.save_data_from_motor_cycle = False

            self.pbMotorCycleStop.setEnabled(False)
            self.pbMotorCycleRun.setEnabled(True)
            self.pbMotorCycleRun.setChecked(False)

            self.motor_run_status = False
            self.motor_update_current_position()

    def motor_rb_target_type_check(self, tg_type):
        """
        Check and save the content of the radio button group Target
        to select absolute of relative motion.

        Parameters
        ----------
        tg_type: str - type of target, to specify which radiobutton has
                        been selected

        Returns
        ----------
        None
        """
        if tg_type == "rb_motor_pos_target":
            if self.rbPositionTarget.isChecked():
                self.lineEditAbsolutePosition.setEnabled(True)
                self.lineEditrelativeStepNumber.setEnabled(False)

        elif tg_type == "rb_motor_rel_target":
            if self.rb_motor_relative.isChecked():
                self.lineEditAbsolutePosition.setEnabled(False)
                self.lineEditrelativeStepNumber.setEnabled(True)

    def motor_rb_motion_type_check(self, rb_name):
        """
        Check and save the content of the radiobutton group
        to select relative or free run motion

        Parameters
        ----------
        rb_name : TYPE
            DESCRIPTION.

        Returns
        -------
        None.

        """
        if rb_name == "rb_motor_jog":
            if self.rb_motor_jog.isChecked():
                self.rb_motor_jog_is_checked = True
                self.rb_motor_relative_is_checked = False
                self.rbPositionTarget.setEnabled(False)
                self.rbRelativeTarget.setEnabled(False)
                self.lineEditAbsolutePosition.setEnabled(False)
                self.lineEditrelativeStepNumber.setEnabled(False)
            else:
                self.rb_motor_jog_is_checked = False
        elif rb_name == "rb_motor_relative":
            if self.rb_motor_relative.isChecked():
                self.rbPositionTarget.setEnabled(True)
                self.rbRelativeTarget.setEnabled(True)
                self.lineEditAbsolutePosition.setEnabled(True)
                self.lineEditrelativeStepNumber.setEnabled(True)
                self.rb_motor_relative_is_checked = True
                self.rb_motor_jog_is_checked = False
                self.rbRelativeTarget.setChecked(True)
            else:
                self.rb_motor_relative_is_checked = False

    def motor_relative_step_number(self):
        """
        Catch the relative step number value from the line Edit windows

        Returns
        -------
        None.

        """
        self.lineEditrelativeStepNumber.setValidator(QtGui.QIntValidator())
        self.motor_relative_step_number_value = \
            self.lself.lineEditrelativeStepNumber.text()

    def motor_run_single_command(self, *argv, **kwargs):
        """
        Function to send a single command to the motor

        Returns
        -------
        None.

        """
        command = kwargs.get("command")
        logging.info(f"MOTOR: Running single command of motor: {command}")
        self.picomotor.command(command)
        time.sleep(2)
        self.stop_the_motor = True
        self.motor_run_status = False
        self.motor_cycle_running = False

    def motor_run_cycle_command(self, *args, **kwargs):
        """
        Function to send a list of commands, one by one with a
        dwell time between them.

        Parameters
        ----------
        listmotorcmd : TYPE, optional
            DESCRIPTION. The default is None.
        channel : TYPE, optional
            DESCRIPTION. The default is 1.
        cycletype : TYPE, optional
            DESCRIPTION. The default is None.
        nbcycle : TYPE, optional
            DESCRIPTION. The default is 1.
        nbstep : TYPE, optional
            DESCRIPTION. The default is None.
        direction : TYPE, optional
            DESCRIPTION. The default is None.
        dwelltime : TYPE, optional
            DESCRIPTION. The default is None.

        Returns
        -------
        None.

        """
        logging.info("MOTOR: Running Motor cycle:")
        channel = int(kwargs.get("channel"))
        cycletype = kwargs.get("cycletype")
        nbcycle = int(kwargs.get("nbcycle"))
        dwelltime = int(kwargs.get("dwelltime"))
        nbstep = int(kwargs.get("nbstep"))

        dictdirection = {}
        dictdirection["up"] = ["+"]
        dictdirection["down"] = ["-"]
        dictdirection["updown"] = ["+", "-"]
        startpos = int(self.motor_current_pos)
        newpos = startpos

        self.motor_cycle_running = True
        self.motorwindowWidth = 100
        self.rt_pos_motor = np.array([])
        self.rt_time_motor = np.array([])
        self.motor_step_counter = 0
        self.ptr_motor = 0
        newdatetime = datetime.datetime.now().timestamp()
        self.motor_start_cycle_time = newdatetime  # Used in filename
        np.append(self.motor_position_vec["datetime"], newdatetime)
        np.append(self.motor_position_vec["pos"], newpos)
        self.rt_pos_motor = np.repeat(newpos, nbstep*len(dictdirection[cycletype]))
        self.rt_time_motor = np.repeat(0, nbstep*len(dictdirection[cycletype]))

        #if not self.stop_the_motor:
        for motordir in dictdirection[cycletype]:
            for _ in range(0, nbcycle):
                if not self.stop_the_motor:
                    self.motor_step_counter += 1
                    # Get time before motor command
                    self.motor_position_vec["datetime"] = \
                        np.append(self.motor_position_vec["datetime"],
                                  newdatetime)
                    self.motor_position_vec["pos"] = np.append(
                                            self.motor_position_vec["pos"],
                                            newpos)
                    if self.save_data_from_motor_cycle:
                        self.motor_file_instance_writer.writerow((newdatetime, newpos,
                                                           self.motor_step_counter))
                    # Motor command
                    motorcmd = f"{channel}PR{motordir}{nbstep}"
                    self.picomotor.command(motorcmd)

                    # Get time AFTER motor command
                    newdatetime = datetime.datetime.now().timestamp()
                    nbsteptoadd = f"{motordir}{nbstep}"
                    newpos = newpos + int(nbsteptoadd)
                    self.motor_position_vec["datetime"] = \
                        np.append(self.motor_position_vec["datetime"], newdatetime)
                    self.motor_position_vec["pos"]= np.append(
                                            self.motor_position_vec["pos"], newpos)
                    if self.save_data_from_motor_cycle:
                        self.motor_file_instance_writer.writerow((newdatetime, newpos,
                                                           self.motor_step_counter))
                    #Start pause
                    time.sleep(dwelltime)

                    # Get time after pause
                    newdatetime = datetime.datetime.now().timestamp()
                    self.motor_position_vec["datetime"] = \
                        np.append(self.motor_position_vec["datetime"], newdatetime)
                    self.motor_position_vec["pos"] = np.append(
                                        self.motor_position_vec["pos"], newpos)
                    if self.save_data_from_motor_cycle:
                        self.motor_file_instance_writer.writerow((newdatetime, newpos,
                                                           self.motor_step_counter))
                    logging.info(f"MOTOR: Command: {motorcmd} -> New positions: {newpos}")
                    # Update pos at each step
                    self.lcdNumberCurrentPos.display(newpos)

            if self.motor_step_counter >= nbcycle * len(dictdirection[cycletype]):
                self.motor_cycle_running = False
                self.pbMotorCycleRun.setChecked(False)
                self.pbMotorCycleRun.setEnabled(True)
                self.pbMotorCycleStop.setEnabled(False)
                self.motor_file_instance.close()
                self.stop_the_motor = True
                self.motor_run_status = False
                if self.interfero_recording_state:
                    self.interfero_record_datastreaming()
                    logging.info("INTERFERO: Recording ended.")
                logging.info("MOTOR: END motor cycle.")

        """
        Handler to interrupt the cycle of the power supply

        Returns
        -------
        None.

        """
        self.agilent_cycle_running = False
        self.pbAgilentCycleRun.setChecked(False)
        self.pbAgilentCycleRun.setEnabled(True)
        self.pbAgilentCycleStop.setEnabled(False)
        self.stop_agilent = True
        self.agilent_run_status = False
        if self.mon_timer is not None:
            self.mon_timer = None
        if self.agilent_param_dict["savedata"]:
            self.agilent_file_instance.close()
        if self.interfero_recording_state:
            self.interfero_record_datastreaming()
            logging.info("INTERFERO: Recording ended.")
        logging.info("AGILENT: STOP voltage cycle. (User request)")
    #
    # GUI functions to manange the power supply
    #
    #________________________________________________________
    def actionConnect_agilent(self):
        """
        Function to establish connexion with the Agilent power supply
    
        Returns
        -------
        None.
    
        """
        if not self.agilent_connected:
            rm = visa.ResourceManager()
            res = rm.list_resources()
            logging.info("AGILENT: Connexion to the power supply.")
            if len(res) != 0:
                try:
                    self.agilent_instance = rm.open_resource(res[-1])
                    try:
                        self.agilent_instance.query("*IDN?")
                        cmd = "".join([str(self.agilent_param_dict["mode"]), " V"])
                        if self.cb_agilent_voltage_setup.currentText() != cmd:
                            time.sleep(1)
                            cmd = cmd.replace("+", "P")
                            cmd = cmd.replace("-", "N")
                            cmd = cmd.replace(" ", "")
                            cmd =  "".join(["INST ", cmd])
                            print(cmd)
                            logging.info(f"AGILENT: mode changed to {cmd}")
                            self.motor_console_message += f"> AGILENT: mode changed to {cmd}.\n"
                            self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
                            self.agilent_instance.write(cmd)
                        logging.info("AGILENT: device connected.")
                        self.motor_console_message += "> AGILENT: device connected.\n"
                        self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
                        self.agilent_connected = True
                        self.agilent_run_status = False
                        self.ptr_agilent = 0
                        self.pbAgilentCycleRun.setEnabled(True)
                        self.pb_agilent_jog_apply_voltage.setEnabled(True)
                        self.cb_agilent_record_at_start.setEnabled(True)
                        self.pb_modify_filepath_agilent.setEnabled(True)
                        self.pb_agilent_apply_param.clicked.connect(self.agilent_apply_new_param)
                        # self.pb_agilent_default_param.clicked.connect(self.agilent_set_default_setup)
                        self.pb_agilent_apply_setup.clicked.connect(self.agilent_apply_new_setup)
                        self.rb_agilent_cycle_updown.setChecked(True)
                        self.rb_agilent_cycle_up.setEnabled(True)
                        self.rb_agilent_cycle_down.setEnabled(True)
                        self.pbAgilentCycleRun.clicked.connect(
                                                self.agilent_run_cycle_style)
                        self.displacement_motor.setTitle("AGILENT 3631E Power supply")
                        self.displacement_motor.setLabel('left',
                                         text="Voltage",
                                         units="Volts")
                        self.displacement_motor.setLabel('bottom',
                                         text="Time",
                                         units="s")
                        self.agilent_instance.write("OUTP ON")
                    except:
                        logging.info("AGILENT: ERROR - device probably off.")
                        self.motor_console_message += "> AGILENT: ERROR - device probably off.\n"
                        self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
                        self.action_connect_agilent.setChecked(False)
                        msg = QtWidgets.QMessageBox()
                        msg.setIcon(QtWidgets.QMessageBox.Warning)
                        msg.setText("AGILENT Device may be OFF")
                        msg.setInformativeText("Please switch on the device\
                                               then try connect it again.")
                        msg.setWindowTitle("AGILENT: Device unavailable")
                        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                        msg.exec_()
                except:
                    logging.info("AGILENT: ERROR - connexion impossible.")
                    self.motor_console_message += "> AGILENT: ERROR - connexion impossible.\n"
                    self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
                    self.action_connect_agilent.setChecked(False)
                    msg = QtWidgets.QMessageBox()
                    msg.setIcon(QtWidgets.QMessageBox.Warning)
                    msg.setText("AGILENT Device unavailable")
                    msg.setInformativeText("Restart program and make sure that the\
                                           power supply is properly plugged.")
                    msg.setWindowTitle("AGILENT: Device unavailable")
                    msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                    msg.exec_()
            else:
                logging.info("AGILENT: ERROR - connexion impossible.")
                self.motor_console_message += "> AGILENT: ERROR - connexion impossible.\n"
                self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
                self.action_connect_agilent.setChecked(False)
                msg = QtWidgets.QMessageBox()
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setText("AGILENT Device unavailable")
                msg.setInformativeText("Restart program and make sure that the\
                                       power supply is properly plugged.")
                msg.setWindowTitle("AGILENT: Device unavailable")
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()

    def agilent_apply_new_param(self):
        """
        Function to apply new parameters in Agilent/cycle tab
        To update the value Vmin, Vmax and Vstep
        Returns
        -------
        None.

        """
        # Get the voltage setup to determine the bounds
        voltage_mode = float(self.agilent_param_dict["mode"].replace("V", ""))
        # Voltage bounds
        max_voltage = max(0, voltage_mode)
        min_voltage = min(0, voltage_mode)
        # VMIN
        if float(self.le_agilent_vmin.text()) >= min_voltage:
            self.agilent_param_dict["vmin"] = float(self.le_agilent_vmin.text())
            logging.info(f"AGILENT: new Vmin: {self.agilent_param_dict['vmin']} V.\n")
            self.motor_console_message += f"> AGILENT: new Vmin: {self.agilent_param_dict['vmin']} V.\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
        else:
            logging.info("AGILENT: ERROR Vmin - Please verify your value.")
            self.motor_console_message += "> AGILENT: ERROR Vmin - Please verify your value.\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
        # VMAX
        if float(self.le_agilent_vmax.text()) <= max_voltage:
            self.agilent_param_dict["vmax"] = float(self.le_agilent_vmax.text())
            logging.info(f"AGILENT: new Vmax: {self.agilent_param_dict['vmax']} V.\n")
            self.motor_console_message += f"> AGILENT: new Vmax: {self.agilent_param_dict['vmax']} V.\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
        else:
            logging.info("AGILENT: ERROR Vmax - Please verify your value.")
            self.motor_console_message += "> AGILENT: ERROR Vmax - Please verify your value.\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
        # VSTEP
        if float(self.le_agilent_vstep.text()) > 0 and \
                float(self.le_agilent_vstep.text()) < float(self.agilent_param_dict["vmax"]):
            self.agilent_param_dict["vstep"] = float(self.le_agilent_vstep.text())
            logging.info(f"AGILENT: new Vstep: {self.agilent_param_dict['vstep']} V.\n")
            self.motor_console_message += f"> AGILENT: new Vstep: {self.agilent_param_dict['vstep']} V.\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
        else:
            logging.info("AGILENT: ERROR Vstep: INVALID VALUE.\n")
            self.motor_console_message += "> AGILENT: ERROR Vstep: INVALID VALUE.\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)


    def agilent_apply_new_setup(self):
        """
        Function to apply the new setup

        Returns
        -------
        None.

        """
        # Voltage mode
        self.agilent_param_dict["mode"] = self.cb_agilent_voltage_setup.currentText()
        # voltage_mode = float(self.agilent_param_dict["mode"].replace("V", ""))
        cmd = str(self.agilent_param_dict["mode"])
        cmd = cmd.replace("+", "P")
        cmd = cmd.replace("-", "N")
        cmd = cmd.replace(" ", "")

        cmd =  "".join(["INST ", cmd])
        self.agilent_instance.write(cmd)
        logging.info(f"AGILENT: set mode to {cmd}.\n")
        self.motor_console_message += f"> AGILENT: set mode to {cmd}.\n"
        self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
        self.agilent_instance.write("OUTP ON")

    def agilent_set_default_setup(self):
        """
        Function to set the default parameters back

        Returns
        -------
        None.

        """
        reply = QtWidgets.QMessageBox.question(self,
            'AGILENT: Set to default parameters...',
            'Are you sure ?',
            QtWidgets.QMessageBox.Yes |
            QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            self.agilent_param_dict["vmin"] = AGILENT_VOLT_MIN
            self.agilent_param_dict["vmax"] = AGILENT_VOLT_MAX
            self.agilent_param_dict["vstep"] = AGILENT_VOLT_STEP
            self.agilent_param_dict["current"] = AGILENT_CURRENT
            self.agilent_param_dict["mode"] = AGILENT_VOLT_SETUP
            self.cb_agilent_voltage_setup.setCurrentText(
                        "".join([self.agilent_param_dict.get("mode"), "V"]))
            self.le_agilent_vmin.setText(self.agilent_param_dict.get("vmin"))
            self.le_agilent_vmax.setText(self.agilent_param_dict.get("vmax"))
            self.le_agilent_vstep.setText(self.agilent_param_dict.get("vstep"))
            self.le_agilent_current.setText(
                                        self.agilent_param_dict.get("current"))
            cmd = str(self.agilent_param_dict["mode"])
            cmd = cmd.replace("+", "P")
            cmd = cmd.replace("-", "N")
            cmd = cmd.replace(" ", "")
            
            cmd =  "".join(["INST ", cmd])
            self.agilent_instance.write(cmd)
            
            #self.agilent_instance.write("OUTP OFF")
            self.agilent_instance.write("OUTP ON")

    def agilent_run_jog_style(self):
        """
        Function to apply a given voltage.
        It takes the voltage given in 

        Returns
        -------
        None.

        """
        if float(self.le_agilent_jog_voltage_value.text())<=float(self.agilent_param_dict["mode"])\
            and float(self.le_agilent_jog_voltage_value.text())>0.:
            self.agilent_jog_voltage_is_running = True
            voltage = float(self.le_agilent_jog_voltage_value.text())
            cmd = "VOLT {:.1f}".format(voltage)
            print(cmd)
            self.agilent_instance.write(cmd)
            self.pb_agilent_jog_stop_voltage.setEnabled(True)
            #self.agilent_instance.write("OUTP ON")
            logging.info(f"AGILENT: Jog Mode - voltage set to {cmd}")
            self.motor_console_message +=\
                        f"> AGILENT: Jog Mode - voltage set to {cmd}\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                        self.motor_console_message)
        else:
            self.agilent_jog_voltage_is_running = False

    def agilent_stop_jog_style(self):
        """
        Set the voltage to 0 Volt

        Returns
        -------
        None.

        """
        if self.agilent_jog_voltage_is_running:
            cmd = "VOLT {:.1f}".format(0)
            print(cmd)
            self.agilent_instance.write(cmd)
            logging.info(f"AGILENT: Jog Mode - voltage set to {cmd}")
            self.motor_console_message +=\
                        f"> AGILENT: Jog Mode - voltage set to {cmd}\n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                        self.motor_console_message)
            time.sleep(1)
            self.agilent_instance.write("OUTP ON")

    def agilent_jog_add_voltage(self):
        """
        Function to add a the step value to the current voltage
        it works only when the power supply is already providing
        the voltage with the value given in the lineEdit voltage

        Returns
        -------
        None.

        """
        if self.agilent_jog_voltage_is_running:
            new_voltage = float(self.le_agilent_jog_voltage_value.text())\
                + float(self.le_agilent_jog_step_value.text())
            if new_voltage <= float(self.agilent_param_dict["mode"])\
            and new_voltage>0.:
                self.le_agilent_jog_voltage_value.setText(str(new_voltage))
                cmd = "VOLT {:.1f}".format(new_voltage)
                print(cmd)
                self.agilent_instance.write(cmd)
                # self.agilent_instance.write("OUTP ON")
                logging.info(f"AGILENT: Jog Mode - voltage set to {cmd} V")
                self.motor_console_message +=\
                            f"> AGILENT: Jog Mode - voltage set to {cmd} V\n"
                self.plainTextEditMotorConnexion.setPlainText(
                                                            self.motor_console_message)
            else:
                self.agilent_instance.write("OUTP ON")
                logging.info("AGILENT: WARNING - Jog Mode - new voltage exceed bounds !")
                self.motor_console_message +=\
                            "> AGILENT: WARNING - Jog Mode - new voltage exceed bounds !\n"
                self.plainTextEditMotorConnexion.setPlainText(
                                                            self.motor_console_message)

    def agilent_jog_sub_voltage(self):
        """
        Function to add a the step value to the current voltage
        it works only when the power supply is already providing
        the voltage with the value given in the lineEdit voltage

        Returns
        -------
        None.

        """
        if self.agilent_jog_voltage_is_running:
            new_voltage = float(self.le_agilent_jog_voltage_value.text())\
                - float(self.le_agilent_jog_step_value.text())
            if new_voltage <= float(self.agilent_param_dict["mode"])\
            and new_voltage>0.:
                
                self.le_agilent_jog_voltage_value.setText(str(new_voltage)) 
                cmd = "VOLT {:.1f}".format(new_voltage)
                print(cmd)
                self.agilent_instance.write(cmd)
                logging.info(f"AGILENT: Jog Mode - voltage set to {cmd} V")
                self.motor_console_message +=\
                            f"> AGILENT: Jog Mode - voltage set to {cmd} V\n"
                self.plainTextEditMotorConnexion.setPlainText(
                                                            self.motor_console_message)
            else:
                self.agilent_instance.write("OUTP ON")
                logging.info("AGILENT: WARNING - Jog Mode - new voltage exceed bounds !")
                self.motor_console_message +=\
                            "> AGILENT: WARNING - Jog Mode - new voltage exceed bounds !\n"
                self.plainTextEditMotorConnexion.setPlainText(
                                                            self.motor_console_message)

    def agilent_run_cycle_style(self):
        """
        Handler called after "Start cycle" button pressed to start the 
        volatage cycle from Vmin to Vmax to Vmin with the option to come 
        back to Vmin each time.

        Returns
        -------
        None.

        """
        if not self.agilent_run_status:
            if self.agilent_jog_voltage_is_running:
                self.agilent_stop_jog_style()
                logging.info("AGILENT: WARNING - Jog Mode interrupted")
                self.motor_console_message +=\
                            "> AGILENT: WARNING - Jog Mode interrupted\n"
                self.plainTextEditMotorConnexion.setPlainText(
                                                            self.motor_console_message)
            self.stop_agilent = False
            self.pbAgilentCycleStop.setEnabled(True)
            self.pbAgilentCycleStop.clicked.connect(self.agilent_stop_cycle_style)
            self.ptr_agilent = 0

            if self.agilent_param_dict.get("savedata"):
                self.timenow_agilent = datetime.datetime.now().isoformat()
                self.timenow_agilent = self.timenow_agilent.replace(":", "_")
                self.timenow_agilent = self.timenow_agilent.replace("-", "_")
                self.timenow_agilent = self.timenow_agilent.replace(".", "_")
                self.agilent_save_sequence_file = os.path.join(
                    self.rs_custom_pref.get("record_dir"),
                    f"{self.rs_custom_pref['record_prefix_agilent']}_{self.timenow_agilent}.csv")
                logging.info(f"AGILENT: data saved in {self.agilent_save_sequence_file}")
                self.motor_console_message +=\
                        f"> AGILENT: data saved in {self.agilent_save_sequence_file}\n"
                self.plainTextEditMotorConnexion.setPlainText(
                                                        self.motor_console_message)
                self.agilent_file_instance = open(self.agilent_save_sequence_file, "a")
                self.agilent_file_instance_writer = csv.writer(
                                                        self.agilent_file_instance)
                logging.info("AGILENT: File opened...")
            try:
                if not self.agilent_run_status:
                    # self.data = np.array([])
                    self.agilent_position_vec = {"time": np.array([]),
                                                 "voltage": np.array([]),
                                                 "datetime": np.array([])}
                    self.rt_voltage_agilent = np.array([])
                    self.rt_time_agilent = np.array([])
                    self.ptr_agilent = 0
                    self.lendata_temp_agilent = 0
                    self.graphicsView.removeItem(self.displacement_motor)
                    self.graphicsView.nextRow()

                    self.displacement_motor = self.graphicsView.addPlot(
                                                    title="Device")
                    self.displacement_motor.setDownsampling(mode='peak')
                    self.displacement_motor.setClipToView(True)
                    self.displacement_motor.setTitle("AGILENT 3631E Power supply")
                    self.displacement_motor.setLabel('left',
                                     text="Voltage",
                                     units="Volts")
                    self.displacement_motor.setLabel('bottom',
                                     text="Time",
                                     units="s")
                    self.displacement_motor.showGrid(x=True, y=True)
                    
                    self.curve_motor = self.displacement_motor.plot()

                    if self.mon_timer is None:
                        self.mon_timer = self.startTimer(self.period_timer)
                    else:
                        logging.info("INTERFERO: Interfero already running")

                    if self.cb_agilent_record_at_start.isChecked():
                        logging.info("INTERFERO: Automatic starting before motor cycling.")
                        self.interfero_init_for_record_cycle(
                                                    specific_time=self.timenow_agilent)

                    logging.info("AGILENT: Voltage cycle started...")
                    dwelltime = int(self.le_agilent_cycle_dwell.text())
                    dwelltimelow = int(self.le_agilent_dwell_vmin.text())
                    vmin = float(self.le_agilent_vmin.text())
                    vmax = float(self.le_agilent_vmax.text())
                    vstep = float(self.le_agilent_vstep.text())
                    current = float(self.le_agilent_current.text())
                    back2vmin = self.cb_agilent_back2Vmin.isChecked()

                    logging.info(self.rb_agilent_cycle_updown.isChecked())
                    cycletype = None
                    if self.rb_agilent_cycle_updown.isChecked():
                        cycletype = "updown"
                        #logging.info("AGILENT: Before cycling...{cycletype}")
                    elif self.rb_agilent_cycle_up.isChecked():
                        cycletype = "up"
                        #logging.info("AGILENT: Before cycling...{cycletype}")
                    elif self.rb_agilent_cycle_down.isChecked():
                        cycletype = "down"
                        #logging.info("AGILENT: Before cycling...{cycletype}")
                    else:
                        #logging.info("AGILENT: No cycle choosed")
                        pass
                    if cycletype is not None:
                        logging.info(f"AGILENT: Power supply voltage cycle: {cycletype}")
                        dictdirection = {}
                        dictdirection["up"] = ["+"]
                        dictdirection["down"] = ["-"]
                        dictdirection["updown"] = ["+", "-"]
                        self.agilent_run_status = True
                        self.agilent_cycle_running = True
                        self.pbAgilentCycleRun.setEnabled(False)
                        kwargs = {"dwelltime": dwelltime, "vmin": vmin,
                                  "vmax": vmax, "vstep": vstep,
                                  "dwelltimelow": dwelltimelow,
                                  "current": current,
                                  "back2vmin": back2vmin,
                                  "cycletype":cycletype
                        }
                        logging.info(f"{kwargs}")
                        worker = Worker(self.agilent_run_cycle_command,
                                        **kwargs)
                        self.threadpool.start(worker)
            except:
                msg = QtWidgets.QMessageBox()
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setText("AGILENT: Device unavailable")
                msg.setInformativeText("Restart program and make sure that the\
                                       power supply is properly plugged.")
                msg.setWindowTitle("AGILENT: Device unavailable")
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()

    def agilent_run_cycle_command(self, *args, **kwargs):
        """
        Function to run a cycle of commands
    
        Parameters
        ----------
        *args : TYPE
            DESCRIPTION.
        **kwargs : TYPE
            DESCRIPTION.
    
        Returns
        -------
        None.
    
        """
        logging.info("AGILENT: Running Voltage cycle:")
        vmin = float(kwargs.get("vmin"))
        vmax = float(kwargs.get("vmax"))
        vstep = float(kwargs.get("vstep"))
        dwelltime = int(kwargs.get("dwelltime"))
        dwelltimelow = int(kwargs.get("dwelltimelow"))
        # current = int(kwargs.get("current"))
        back2vmin = True if kwargs.get("back2vmin") else False
        cycletype = kwargs.get("cycletype")
        dictdirection = {}
        dictdirection["up"] = ["+"]
        dictdirection["down"] = ["-"]
        dictdirection["updown"] = ["+", "-"]
        startpos = vmin
        newpos = startpos
        # Send output on command in case of restart another cycle
        self.agilent_instance.write("OUTP ON")

        self.agilent_cycle_running = True
        self.agilentwindowWidth = 100

        newdatetime = datetime.datetime.now().timestamp()
        self.motor_start_cycle_time = newdatetime  # Used in filename
        np.append(self.agilent_position_vec["datetime"], newdatetime)
        np.append(self.agilent_position_vec["voltage"], newpos)
        self.rt_voltage_agilent = np.repeat(newpos, int(((vmax-vmin)+2)/vstep))
        self.rt_time_agilent = np.repeat(0, int(((vmax-vmin)+2)/vstep))

        if not self.stop_agilent:
            if cycletype == "updown":
                for v in np.arange(vmin, vmax+vstep, vstep):
                    if not self.stop_agilent:
                        newdatetime = datetime.datetime.now().timestamp()
                        self.agilent_position_vec["datetime"] = \
                                np.append(self.agilent_position_vec["datetime"],
                                          newdatetime)
                        self.agilent_position_vec["voltage"] = np.append(
                                                self.agilent_position_vec["voltage"], v)
                        if self.agilent_param_dict["savedata"]:
                            try:
                                self.agilent_file_instance_writer.writerow(
                                                                (newdatetime, v))
                            except:
                                pass
    
                        cmd2ps = "VOLT {:.1f}".format(v)
                        self.agilent_instance.write(cmd2ps)
                        time.sleep(dwelltime)
                        # Save the data
                        newdatetime = datetime.datetime.now().timestamp()
                        self.agilent_position_vec["datetime"] = \
                                np.append(self.agilent_position_vec["datetime"], 
                                          newdatetime)
                        self.agilent_position_vec["voltage"] = np.append(
                                                self.agilent_position_vec["voltage"], v)
                        if self.agilent_param_dict["savedata"]:
                            try:
                                self.agilent_file_instance_writer.writerow(
                                                                (newdatetime, v))
                            except:
                                pass
                        logging.info(f"AGILENT: Command: {cmd2ps} -> New voltage: {v}")
                        if back2vmin and v != vmin:
                            self.agilent_position_vec["datetime"] = \
                                np.append(self.agilent_position_vec["datetime"], 
                                          newdatetime)
                            self.agilent_position_vec["voltage"] = np.append(
                                                self.agilent_position_vec["voltage"], vmin)
                            if self.agilent_param_dict["savedata"]:
                                try:
                                    self.agilent_file_instance_writer.writerow(
                                                                (newdatetime, vmin))
                                except:
                                    pass
                            cmd2psvmin = "VOLT {:.1f}".format(vmin)
                            self.agilent_instance.write(cmd2psvmin)
                            time.sleep(dwelltimelow)
                            logging.info(f"AGILENT: Command: {cmd2psvmin} -> New voltage: {vmin}")
                            newdatetime = datetime.datetime.now().timestamp()
                            self.agilent_position_vec["datetime"] = \
                                np.append(self.agilent_position_vec["datetime"], 
                                          newdatetime)
                            self.agilent_position_vec["voltage"] = np.append(
                                                self.agilent_position_vec["voltage"], vmin)
                            if self.agilent_param_dict["savedata"]:
                                try:
                                    self.agilent_file_instance_writer.writerow(
                                                                (newdatetime, vmin))
                                except:
                                    pass
                for v in np.arange(vmax-vstep, vmin-vstep, -vstep):
                    if not self.stop_agilent:
                        newdatetime = datetime.datetime.now().timestamp()
                        self.agilent_position_vec["datetime"] = \
                                np.append(self.agilent_position_vec["datetime"],
                                          newdatetime)
                        self.agilent_position_vec["voltage"] = np.append(
                                                self.agilent_position_vec["voltage"], v)
                        if self.agilent_param_dict["savedata"]:
                            try:
                                self.agilent_file_instance_writer.writerow(
                                                                (newdatetime, v))
                            except:
                                pass
                        cmd2ps = "VOLT {:.1f}".format(v)
                        self.agilent_instance.write(cmd2ps)
                        time.sleep(dwelltime)
                        logging.info(f"AGILENT: Command: {cmd2ps} -> New voltage: {v}")
                        newdatetime = datetime.datetime.now().timestamp()
                        self.agilent_position_vec["datetime"] = \
                                np.append(self.agilent_position_vec["datetime"], 
                                          newdatetime)
                        self.agilent_position_vec["voltage"] = np.append(
                                                self.agilent_position_vec["voltage"], v)
                        if self.agilent_param_dict["savedata"]:
                            try:
                                self.agilent_file_instance_writer.writerow(
                                                                (newdatetime, v))
                            except:
                                pass
                        if back2vmin and v != vmin:
                            self.agilent_position_vec["datetime"] = \
                                np.append(self.agilent_position_vec["datetime"], 
                                          newdatetime)
                            self.agilent_position_vec["voltage"] = np.append(
                                                self.agilent_position_vec["voltage"], vmin)
                            if self.agilent_param_dict["savedata"]:
                                try:
                                    self.agilent_file_instance_writer.writerow(
                                                                (newdatetime, vmin))
                                except:
                                    pass
                            cmd2psvmin = "VOLT {:.1f}".format(vmin)
                            self.agilent_instance.write(cmd2psvmin)
                            time.sleep(dwelltimelow)
                            logging.info(f"AGILENT: Command: {cmd2psvmin} -> New voltage: {vmin}")
                            newdatetime = datetime.datetime.now().timestamp()
                            self.agilent_position_vec["datetime"] = \
                                np.append(self.agilent_position_vec["datetime"], 
                                          newdatetime)
                            self.agilent_position_vec["voltage"] = np.append(
                                                self.agilent_position_vec["voltage"], vmin)
                            if self.agilent_param_dict["savedata"]:
                                try:
                                    self.agilent_file_instance_writer.writerow(
                                                                    (newdatetime, vmin))
                                except:
                                    pass
            # self.agilent_instance.write("OUTP OFF")
            elif cycletype == "up":
                for v in np.arange(vmin, vmax+vstep, vstep):
                    if not self.stop_agilent:
                        newdatetime = datetime.datetime.now().timestamp()
                        self.agilent_position_vec["datetime"] = \
                                np.append(self.agilent_position_vec["datetime"],
                                          newdatetime)
                        self.agilent_position_vec["voltage"] = np.append(
                                                self.agilent_position_vec["voltage"], v)
                        if self.agilent_param_dict["savedata"]:
                            try:
                                self.agilent_file_instance_writer.writerow(
                                                                (newdatetime, v))
                            except:
                                pass
                        cmd2ps = "VOLT {:.1f}".format(v)
                        self.agilent_instance.write(cmd2ps)
                        time.sleep(dwelltime)
                        # Save the data
                        newdatetime = datetime.datetime.now().timestamp()
                        self.agilent_position_vec["datetime"] = \
                                np.append(self.agilent_position_vec["datetime"], 
                                          newdatetime)
                        self.agilent_position_vec["voltage"] = np.append(
                                                self.agilent_position_vec["voltage"], v)
                        if self.agilent_param_dict["savedata"]:
                            try:
                                self.agilent_file_instance_writer.writerow(
                                                                (newdatetime, v))
                            except:
                                pass
                        logging.info(f"AGILENT: Command: {cmd2ps} -> New voltage: {v}")
                        if back2vmin and v != vmin:
                            self.agilent_position_vec["datetime"] = \
                                np.append(self.agilent_position_vec["datetime"], 
                                          newdatetime)
                            self.agilent_position_vec["voltage"] = np.append(
                                                self.agilent_position_vec["voltage"], vmin)
                            if self.agilent_param_dict["savedata"]:
                                try:
                                    self.agilent_file_instance_writer.writerow(
                                                                (newdatetime, vmin))
                                except:
                                    pass
                            cmd2psvmin = "VOLT {:.1f}".format(vmin)
                            self.agilent_instance.write(cmd2psvmin)
                            time.sleep(dwelltimelow)
                            logging.info(f"AGILENT: Command: {cmd2psvmin} -> New voltage: {vmin}")
                            newdatetime = datetime.datetime.now().timestamp()
                            self.agilent_position_vec["datetime"] = \
                                np.append(self.agilent_position_vec["datetime"],
                                          newdatetime)
                            self.agilent_position_vec["voltage"] = np.append(
                                                self.agilent_position_vec["voltage"], vmin)
                            if self.agilent_param_dict["savedata"]:
                                self.agilent_file_instance_writer.writerow(
                                                                (newdatetime, vmin))
            else:
                for v in np.arange(vmax-vstep, vmin-vstep, -vstep):
                    if not self.stop_agilent:
                        newdatetime = datetime.datetime.now().timestamp()
                        self.agilent_position_vec["datetime"] = \
                                np.append(self.agilent_position_vec["datetime"],
                                          newdatetime)
                        self.agilent_position_vec["voltage"] = np.append(
                                                self.agilent_position_vec["voltage"], v)
                        if self.agilent_param_dict["savedata"]:
                            try:
                                self.agilent_file_instance_writer.writerow(
                                                                (newdatetime, v))
                            except:
                                pass
                        cmd2ps = "VOLT {:.1f}".format(v)
                        self.agilent_instance.write(cmd2ps)
                        time.sleep(dwelltime)
                        logging.info(f"AGILENT: Command: {cmd2ps} -> New voltage: {v}")
                        newdatetime = datetime.datetime.now().timestamp()
                        self.agilent_position_vec["datetime"] = \
                                np.append(self.agilent_position_vec["datetime"], 
                                          newdatetime)
                        self.agilent_position_vec["voltage"] = np.append(
                                                self.agilent_position_vec["voltage"], v)
                        if self.agilent_param_dict["savedata"]:
                            try:
                                self.agilent_file_instance_writer.writerow(
                                                                (newdatetime, v))
                            except:
                                pass
                        if back2vmin and v != vmin:
                            self.agilent_position_vec["datetime"] = \
                                np.append(self.agilent_position_vec["datetime"], 
                                          newdatetime)
                            self.agilent_position_vec["voltage"] = np.append(
                                                self.agilent_position_vec["voltage"], vmin)
                            if self.agilent_param_dict["savedata"]:
                                try:
                                    self.agilent_file_instance_writer.writerow(
                                                                (newdatetime, vmin))
                                except:
                                    pass
                            cmd2psvmin = "VOLT {:.1f}".format(vmin)
                            self.agilent_instance.write(cmd2psvmin)
                            time.sleep(dwelltimelow)
                            logging.info(f"AGILENT: Command: {cmd2psvmin} -> New voltage: {vmin}")
                            newdatetime = datetime.datetime.now().timestamp()
                            self.agilent_position_vec["datetime"] = \
                                np.append(self.agilent_position_vec["datetime"], 
                                          newdatetime)
                            self.agilent_position_vec["voltage"] = np.append(
                                                self.agilent_position_vec["voltage"], vmin)
                            if self.agilent_param_dict["savedata"]:
                                try:
                                    self.agilent_file_instance_writer.writerow(
                                                                    (newdatetime, vmin))
                                except:
                                    pass

            # self.agilent_instance.write("OUTP OFF")
            self.agilent_cycle_running = False
            self.pbAgilentCycleRun.setChecked(False)
            self.pbAgilentCycleRun.setEnabled(True)
            self.pbAgilentCycleStop.setEnabled(False)
            # Close file
            self.agilent_file_instance.close()
            self.stop_agilent = True
            self.agilent_run_status = False
            # if self.mon_timer is not None:
            #    self.mon_timer = None
            if self.interfero_recording_state:
                self.interfero_record_datastreaming()
                logging.info("INTERFERO: Recording ended.")
                logging.info("AGILENT: END voltage cycle.")

    def agilent_stop_cycle_style(self):
        """
        Function to stop the power supply cycle

        Returns
        -------
        None.

        """
        reply = QtWidgets.QMessageBox.question(self,
                                               "Stop Power supply cycle",
                                               "Interrupt the cycle ?",
                                               QtWidgets.QMessageBox.Yes |
                                               QtWidgets.QMessageBox.No,
                                               QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            self.agilent_cycle_running = False
            self.pbAgilentCycleRun.setChecked(False)
            self.pbAgilentCycleRun.setEnabled(True)
            self.pbAgilentCycleStop.setEnabled(False)

            # Close file
            self.agilent_file_instance.close()
            self.stop_agilent = True #  Flag to stop the cycle
            self.agilent_run_status = False
            # if self.mon_timer is not None:
            #   self.mon_timer = None
            if self.interfero_recording_state:
                self.interfero_record_datastreaming()
                logging.info("INTERFERO: Recording ended.")
            logging.info("AGILENT: Cycle interrupted.")
            self.motor_console_message += "> AGILENT: cycle interrupted \n"
            self.plainTextEditMotorConnexion.setPlainText(
                                                    self.motor_console_message)
            self.agilent_instance.write("OUTP ON")
            self.threadpool.clear()

        else:
            pass


class RattleSnakeAboutWindows(QtWidgets.QDialog):
    """
    Class to open a windows "About". It's a basic QDialog.
    No return

    """

    def __init__(self, parent=None):
        """
        Constructor
        """
        QtWidgets.QMainWindow.__init__(self)
        self.setObjectName("About")
        self.user_interface = uic.loadUi(UI_ABOUT_WINDOW, self)
        self.pb_close.clicked.connect(lambda: self.close())
        self.lbl_version_nb.setText(VERSION)
        self.lbl_disclaimer.setText(GP_DISCLAIMER)


class IDS3010_preference_windows(QtWidgets.QDialog):
    def __init__(self, parent=None):
        QtWidgets.QMainWindow.__init__(self)
        self.setObjectName("Preferences")
        self.user_interface = uic.loadUi(UI_PREF_WINDOW, self)


def read_config_file(jsonfile):
    """
    Function to read the JSON config file

    Parameters
    ----------
    jsonfile : TYPE
        DESCRIPTION.

    Returns
    -------
    configdict : TYPE
        DESCRIPTION.

    """
    import json
    if os.path.exists(jsonfile):
        with open(jsonfile, "r") as jfile:
            configdict = json.load(jfile)
        logging.info("RATTLE SNAKE: Config file: read successful")
        return configdict
    else:
        logging.error(f"RATTLE SNAKE: {jsonfile} not found")
        return None


def main():
    """
    Main program to execute the graphical interface

    Returns
    -------
    None.

    """
    global SETUP_PARAM_FILE, CONFIG_DICT, VERSION, SESSIONFILENAME,\
        FILE_EXTENTION, FILESESSIONPREFIX, MAXACCELERATION, MAXVELOCITY, \
        MINDWELLTIME, MESSAGEMOTORDISCONNECTED, DEFAULTIDVENDOR, \
        DEFAULTIDPRODUCT, MAXNUMBEROFCYCLE, MAXNUMBEROFDWELL, GP_DISCLAIMER
    global MESSAGEMOTORDISCONNECTED, MESSAGEMOTORPERMISSIONERROR,\
        MESSAGEMOTORALREADYCONNECTED, DEFAULT_WAVE_LOCATION
    global INTERFERO_IP, INTERFERO_INTERVAL_MICROSEC,\
        INTERFERO_TIME_RANGE_PLOT, INTERFERO_XLABEL_PLOT,\
        INTERFERO_YLABEL_PLOT, DEFAULT_RECORD_DIR, DEFAULT_RECORD_PREFIX_FILE,\
        DEFAULT_RECORD_PREFIX_MOTOR_FILE

    # Agilent global variables
    global AGILENT_VOLT_SETUP, AGILENT_DWELL_TIME, AGILENT_VOLT_MIN,\
        AGILENT_VOLT_STEP, AGILENT_VOLT_MAX, AGILENT_CURRENT,\
        AGILENT_INSTR_RESSOURCE, DEFAULT_RECORD_PREFIX_AGILENT_FILE,\
        AGILENT_DWELL_TIME_LOW, AGILENT_JOG_STEP, AGILENT_JOG_VOLTAGE

    CONFIG_DICT = read_config_file(SETUP_PARAM_FILE)
    if CONFIG_DICT is not None:

        VERSION = CONFIG_DICT.get("VERSION")
        GP_DISCLAIMER = CONFIG_DICT.get("GP_DISCLAIMER")
        SESSIONFILENAME = CONFIG_DICT.get("SESSIONFILENAME")
        FILESESSIONPREFIX = CONFIG_DICT.get("FILESESSIONPREFIX")
        FILE_EXTENTION = CONFIG_DICT.get("FILE_EXTENTION")

        # Specific to the motor
        MAXNUMBEROFCYCLE = CONFIG_DICT.get("MAXNUMBEROFCYCLE")
        MAXNUMBEROFDWELL = CONFIG_DICT.get("MAXNUMBEROFDWELL")

        DEFAULTIDPRODUCT = CONFIG_DICT.get("DEFAULTIDPRODUCT")
        DEFAULTIDVENDOR = CONFIG_DICT.get("DEFAULTIDVENDOR")

        MINDWELLTIME = CONFIG_DICT.get("MINDWELLTIME")
        MAXVELOCITY = CONFIG_DICT.get("MAXVELOCITY")
        MAXACCELERATION = CONFIG_DICT.get("MAXACCELERATION")

        MESSAGEMOTORDISCONNECTED = CONFIG_DICT.get("MESSAGEMOTORDISCONNECTED")
        MESSAGEMOTORPERMISSIONERROR = CONFIG_DICT.get("MESSAGEMOTORPERMISSIONERROR")
        MESSAGEMOTORALREADYCONNECTED = CONFIG_DICT.get("MESSAGEMOTORALREADYCONNECTED")

        # Specific to the interferometer
        INTERFERO_IP = CONFIG_DICT.get("INTERFERO_IP")
        INTERFERO_INTERVAL_MICROSEC = int(CONFIG_DICT.get("INTERFERO_INTERVAL_MICROSEC"))
        INTERFERO_TIME_RANGE_PLOT = int(CONFIG_DICT.get("INTERFERO_TIME_RANGE_PLOT"))
        INTERFERO_XLABEL_PLOT = CONFIG_DICT.get("INTERFERO_XLABEL_PLOT")
        INTERFERO_YLABEL_PLOT = CONFIG_DICT.get("INTERFERO_YLABEL_PLOT")

        DEFAULT_WAVE_LOCATION = CONFIG_DICT.get("DEFAULT_WAVE_LOCATION")
        DEFAULT_RECORD_DIR = CONFIG_DICT.get("DEFAULT_RECORD_DIR")
        DEFAULT_RECORD_PREFIX_FILE = CONFIG_DICT.get("DEFAULT_RECORD_PREFIX_FILE")
        DEFAULT_RECORD_PREFIX_MOTOR_FILE = CONFIG_DICT.get("DEFAULT_RECORD_PREFIX_MOTOR_FILE")

        # AGILENT PARAMETERS
        AGILENT_INSTR_RESSOURCE = CONFIG_DICT.get("AGILENT_INSTR_RESSOURCE")
        AGILENT_VOLT_SETUP = CONFIG_DICT.get("AGILENT_VOLT_SETUP")
        AGILENT_DWELL_TIME = CONFIG_DICT.get("AGILENT_DWELL_TIME")
        AGILENT_DWELL_TIME_LOW = CONFIG_DICT.get("AGILENT_DWELL_TIME_LOW")
        AGILENT_VOLT_MIN = CONFIG_DICT.get("AGILENT_VOLT_MIN")
        AGILENT_VOLT_STEP = CONFIG_DICT.get("AGILENT_VOLT_STEP")
        AGILENT_VOLT_MAX = CONFIG_DICT.get("AGILENT_VOLT_MAX")
        AGILENT_CURRENT = CONFIG_DICT.get("AGILENT_CURRENT")
        DEFAULT_RECORD_PREFIX_AGILENT_FILE = CONFIG_DICT.get("DEFAULT_RECORD_PREFIX_AGILENT_FILE")
        AGILENT_JOG_STEP = CONFIG_DICT.get("AGILENT_JOG_STEP")
        AGILENT_JOG_VOLTAGE = CONFIG_DICT.get("AGILENT_JOG_VOLTAGE")
        # set an print the splash screen
        pixmap = QPixmap(os.path.join(
            CURRENT_FILE_DIR, 'images', "splash_guipionner.png"))

        splash = QtWidgets.QSplashScreen(pixmap, Qt.WindowStaysOnTopHint)
        splash.showMessage("Loading modules")
        splash.setMask(pixmap.mask())
        splash_font = splash.font()
        splash_font.setPixelSize(14)
        splash.setFont(splash_font)
        splash.show()
        app.processEvents()

        # Create a directory to save session preference
        global PREFDIR
        PREFDIR = os.path.join(CURRENT_FILE_DIR, SESSIONDIRNAME)

        try:
            os.makedirs(PREFDIR)
        except OSError:
            pass

    # Instantiate graphical interface in a dedicated thread
        guipioneers_mw = GuiPioneersMainWindow()
        splash.finish(guipioneers_mw.show())
        sys.exit(app.exec_())
    else:
        logging.error("Config file empty.")

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    main()
