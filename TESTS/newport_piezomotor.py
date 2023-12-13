
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Created on Wed Jun 9 11:41:04 2021

@project : PIONEERS
@author  : Grégory SAINTON (IPGP)
@mail    : sainton@ipgp.fr
@version : 1.0 - creation


"""

try:
    import usb
    print("Module 'usb' found")
except ModuleNotFoundError:
    print("Module 'usb' is not installed")
    print("Please install it by typing 'conda install pyusb' in a Terminal.")

import re

NEWFOCUS_COMMAND_REGEX = re.compile("([0-9]{0,1})([a-zA-Z?]{2,})([0-9+-]*)")
MOTOR_TYPE = {
        "0":"No motor connected",
        "1":"Motor Unknown",
        "2":"'Tiny' Motor",
        "3":"'Standard' Motor"
        }


class Controller(object):
    def __init__(self, idProduct, idVendor):
        """Initialize the Picomotor class with the spec's of the attached device
        Call self._connect to set up communication with usb device and endpoints 
        
        Args:
            idProduct (hex): Product ID of picomotor controller
            idVendor (hex): Vendor ID of picomotor controller
        """
        self.idProduct = idProduct
        self.idVendor = idVendor
        self._connect()
        
    
    def _connect(self):
        """Connect class to USB device 
        Find device from Vendor ID and Product ID
        Setup taken from [1]
        Raises:
            ValueError: if the device cannot be found by the Vendor ID and Product
                ID
            Assert False: if the input and outgoing endpoints can't be established
        """
        # find the device
        self.dev = usb.core.find(
                        idProduct=self.idProduct,
                        idVendor=self.idVendor
                        )
       
        if self.dev is None:
            raise ValueError('Device not found')

        # set the active configuration. With no arguments, the first
        # configuration will be the active one
        self.dev.set_configuration()

        # get an endpoint instance
        cfg = self.dev.get_active_configuration()
        intf = cfg[(0,0)]

        self.ep_out = usb.util.find_descriptor(
            intf,
            # match the first OUT endpoint
            custom_match = \
            lambda e: \
                usb.util.endpoint_direction(e.bEndpointAddress) == \
                usb.util.ENDPOINT_OUT)

        self.ep_in = usb.util.find_descriptor(
            intf,
            # match the first IN endpoint
            custom_match = \
            lambda e: \
                usb.util.endpoint_direction(e.bEndpointAddress) == \
                usb.util.ENDPOINT_IN)

        assert (self.ep_out and self.ep_in) is not None
        
        # Confirm connection to user
        resp = self.command('VE?')
        print("Connected to Motor Controller Model {}. Firmware {} {} {}\n".format(
                                                    *resp.split(' ')
                                                    ))
        for m in range(1,5):
            resp = self.command("{}QM?".format(m))
            print("Motor #{motor_number}: {status}".format(
                                                    motor_number=m,
                                                    status=MOTOR_TYPE[resp[-1]]
                                                    ))

if __name__ == '__main__':
    print('\n\n')
    print('#'*80)
    print('#\tPython controller for NewFocus Picomotor Controller')
    print('#'*80)
    print('\n')

    idProduct = None # '0x4000'
    idVendor = None  # '0x104d'

    if not (idProduct or idVendor):
        print('Run the following command in a new terminal window:')
        print('\t$ system_profiler SPUSBDataType\n')
        print('Enter Product ID:')
        idProduct = raw_input('> ') 
        print('Enter Vendor ID:')
        idVendor = raw_input('> ') 
        print('\n')

    # convert hex value in string to hex value
    idProduct = int(idProduct, 16)
    idVendor = int(idVendor, 16)

    # Initialize controller and start console
    controller = Controller(idProduct=idProduct, idVendor=idVendor)
    #controller.start_console()
            
            
    
