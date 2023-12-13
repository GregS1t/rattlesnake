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
import matplotlib.pyplot as plt
import ATTOCUBE.IDS as IDS

current_dir = os.getcwd()
print(f"Current directory: {current_dir}")


CURRENT_MODES = ('system idle')

# Parameters
IDS3010ADDRESS = "172.27.36.212"
isMaster = True
intervalInMicroseconds = 10

class IDS_IPGP(IDS.Device):
    def __init__(self, idsipaddress):
        super().__init__(idsipaddress)

if __name__ == '__main__':

    ids = IDS_IPGP(IDS3010ADDRESS)
    
    try:
        ids.connect()
    except:
        print(f"NO DEVICE FOUND AT THIS ADDRESS: {IDS3010ADDRESS}")
    
