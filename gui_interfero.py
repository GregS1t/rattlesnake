# -*- coding: utf-8 -*-
"""
Created on Tue Sep  7 15:23:25 2021

@author: cave

__author__ = "Grégory Sainton"
__email__="sainton@ipgp.fr"
__copyright= "IPGP France"
__purpose__ ="GUI to connect Attocube IDS3010 interferometer"
__licence__=""
__version__="0.0.1"
__status__="Development"

"""
import time
import IDS


CURRENT_MODES = ('system idle')

# Parameters
IDS3010ADDRESS = "172.27.36.217"
isMaster = True
intervalInMicroseconds = 10

class IDS_IPGP(IDS.Device):
    def __init__(self, idsipaddress):
        super().__init__(idsipaddress)
        self.ipaddress = idsipaddress 

    def connect(self):
        status = None
        try:
            super().connect()
            status = "OK"
        except:
            status = f"NO DEVICE FOUND AT THIS ADDRESS: {IDS3010ADDRESS} "
        return status

    def action_request_alignement(self, master_axis):
        """
            Function to handle aligment request from GUI

        """
        aligned_values = None
        current_mode = self.system.getCurrentMode()
        if current_mode == 'system idle':
            self.system.startOpticsAlignment()

            while current_mode != 'optics alignment running':
                time.sleep(1)
                current_mode = self.system.getCurrentMode()
            
            self.system.stopOpticsAlignment()
            time.sleep(5)
            aligned_values = self.adjustment.getContrastInPermille(master_axis)
        else:
            aligned_values = None
        return aligned_values

if __name__ == '__main__':

    ids = IDS_IPGP(IDS3010ADDRESS)
    status = ids.connect()
    print(status)
