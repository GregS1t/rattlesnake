# -*- coding: utf-8 -*-
"""
Created on Fri Jul 30 15:34:58 2021

@author=  cave

__author__ = "Grégory Sainton"
__email__="sainton@ipgp.fr"
__copyright= "IPGP France"
__purpose__ ="GUI to connect Attocube IDS3010 interferometer"
__licence__=""
__version__="0.0.1"
__status__="Development"

"""
import os
import sys
import time
import datetime
import numpy as np
import ATTOCUBE.IDS as IDS


current_dir = os.getcwd()
print(f"Current directory: {current_dir}")


CURRENT_MODES = ('system idle')

# Parameters
IDS3010ADDRESS = "172.27.36.217"
isMaster = True
intervalInMicroseconds = 10

filePath = os.path.join(current_dir, "IDS3010_Data_Acquisition_test0.txt")
print(filePath)


# connecting to IDS and reset axes
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
            ids.system.startMeasurement()
            current_mode = ids.system.getCurrentMode()
            while current_mode != 'measurement running':
                time.sleep(1)
                current_mode = ids.system.getCurrentMode()
            print(f" Status: {ids.system.getCurrentMode()}")


if __name__ == '__main__':

    ids = IDS_IPGP(IDS3010ADDRESS)
    ids.connect()

    current_mode = ids.system.getCurrentMode()
    print(current_mode)
    master_axis = ids.axis.getMasterAxis()
    print(f"Master axis : {ids.axis.getMasterAxis()}")
    ids.action_request_alignement()

    ids.action_request_start_measurement()


    master_axis = ids.axis.getMasterAxis()
    axis0, axis1, axis2 = False, False, False
    if master_axis == 0:
        axis0 = True
    elif master_axis == 1:
        axis1 = True
    elif master_axis == 2:
        axis2 = True
    print(f"Master axis: {master_axis}")
    
    # Start measurement
    erroNo, position = ids.displacement.getAbsolutePosition(master_axis)
    
    print("Start acquisition:")
    ids_stream = ids.streaming.startBackgroundStreaming(True,
                                                        intervalInMicroseconds,
                                                        filePath, bufferSize=1024,
                                                        axis0=axis0, axis1=axis1, 
                                                        axis2=axis2)

    time.sleep(20)
    ids.streaming.stopBackgroundStreaming()
    print("Fin")
    freq = 20  # frequency in Hz
    # print("Start measuring")
    # for i in range(0, 100000):
    #     time_meas = np.append(time_meas,
    #                          int(datetime.datetime.now().timestamp()))
    #     displac_meas = np.append(displac_meas,
    #                              ids.displacement.getAbsolutePosition(
    #                                  master_axis)[1])
    #     time.sleep(1/float(freq))
    #     # print(time_meas, displac_meas)
    # print(len(time_meas), len(displac_meas))
    # time_meas = np.subtract(time_meas, time_meas[0])
    # displac_meas = np.divide(displac_meas, 1e10)
    # plt.plot(time_meas, displac_meas)
    # plt.ylabel("displacement (m)")
    # plt.xlabel("time (s)")
    # plt.show()

# =============================================================================
#
# if current_mode == 'system idle':
#
#     ids.system.startOpticsAlignment()
#
#     while current_mode !='optics alignment running':
#         time.sleep(1)
#         current_mode = ids.system.getCurrentMode()
#
#     print(f"IDS aligned with contrast equal to {ids.adjustment.getContrastInPermille(1)} per mille")
#     ids.system.stopOpticsAlignment()
#     print("Alignement stopped")
#     time.sleep(10)
#     current_mode = ids.system.getCurrentMode()
#     print(current_mode)
#
#
#
#
#
# if current_mode == "system idle":
#
#     current_mode = ids.system.getCurrentMode()
#     print(current_mode)
#
#     ids.system.startMeasurement()
#     current_mode = ids.system.getCurrentMode()
#     print(current_mode)
#     while current_mode !='measurement running':
#         time.sleep(1)
#         current_mode = ids.system.getCurrentMode()
#
# print(f" Status: {current_mode}")
#
# master_axis = ids.axis.getMasterAxis()
# axis0, axis1, axis2 = False, False, False
# if master_axis == 0:
#     axis0 = True
# elif master_axis == 1:
#     axis1 = True
# elif master_axis == 2:
#     axis2 = True
# print(f"Master axis: {master_axis}")
#
# # Start measurements
#
# erroNo, position = ids.displacement.getAbsolutePosition(master_axis)
#
# print("Start acquisition:")
# ids_stream = ids.streaming.startBackgroundStreaming(True,
#                                                    intervalInMicroseconds,
#                                                    filePath, bufferSize=1024,
#                                                    axis0=axis0, axis1=axis1, 
#                                                    axis2=axis2)
# print(position)
#
# #ids.streaming.stopBackgroundStreaming()
# print("fin")
#
# ids.system.stopMeasurement()
# time.sleep(5)
# current_mode = ids.system.getCurrentMode()
# print(current_mode)
# =============================================================================
