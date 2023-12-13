#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Created on Wed Jun 9 11:41:04 2021

@project : PIONEERS
@author  : Grégory SAINTON (IPGP)
@mail    : sainton@ipgp.fr
@version : 1.0 - creation

Based on https://github.com/bdhammel/python_newport_controller
In a Terminal window:

$ system_profiler SPUSBDataType

Picomotor Controller:

  Product ID: 0x4000
  Vendor ID: 0x104d
  ...

"""

try:
    import usb
except ModuleNotFoundError:
    print("Module 'usb' is not installed")
    print("Please install it by typing 'conda install pyusb' in a Terminal.")

import re
import logging


NEWFOCUS_COMMAND_REGEX = re.compile("([0-9]{0,1})([a-zA-Z?]{2,})([0-9+-]*)")
MOTOR_TYPE = {
        "0":"No motor connected",
        "1":"Motor Unknown",
        "2":"'Tiny' Motor",
        "3":"'Standard' Motor"
        }

class Pico8742Ctrl(object):
    def __init__(self, idProduct, idVendor):
        """
        Initialize the Picomotor class with the spec's of the attached device
        
        
        ----
        INPUT:
            idProduct (hex): Product ID of picomotor controller
            idVendor (hex): Vendor ID of picomotor controller
        """
        self.channel = None
        self.idProduct = idProduct
        self.idVendor = idVendor
        self.message = self.usbconnect()
        self.status  = 0
        #self.ep_out = None
        #self.ep_in = None


    def usbconnect(self):
        """
        Connect class to USB device 
        Find device from Vendor ID and Product ID
        Setup taken from [1]
        Raises:
            ValueError: if the device cannot be found by the Vendor ID and Product
                ID
            Assert False: if the input and outgoing endpoints can't be established
        """
        # find the device
        try: 
            self.dev = usb.core.find(
                            idProduct=self.idProduct,
                            idVendor=self.idVendor
                            )
           
            if self.dev is not None:
                #raise ValueError('Device not found')
    
                # set the active configuration. With no arguments, the first
                # configuration will be the active one
                self.dev.set_configuration()

                # get an endpoint instance
                cfg = self.dev.get_active_configuration()
                intf = cfg[(0, 0)]

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

                if  self.ep_out is not None and self.ep_in is not None:
                    # Confirm connection to user
                    resp = self.command('VE?')
                    outmessage = "Connected to Motor Controller Model {}. Firmware {} {} {}\n".format(
                                                                *resp.split(' '))
                    logging.info(f"{outmessage}")
                    for m in range(1,5):
                        resp = self.command("{}QM?".format(m))

                        #print(f"Port {m} - status {resp}")
                        #print("Motor #{motor_number}: {status}".format(
                        #                                        motor_number=m,
                        #                                        status=MOTOR_TYPE[resp[-1]]))
                        if resp[-1] == "3":
                            self.channel = m
                            outmessage += f"Default motor found on port {m}\n"
                            logging.info(f"{outmessage}")
                    self.status = 1
                    return outmessage
                else:
                    return "ERROR: Device not found"
            else:
                return "ERROR: Device not found"
        except usb.core.USBError:
            return "WARNING: Motor already connected"

    def close(self):
        usb.util.dispose_resources(self.dev)

    def send_command(self, usb_command, get_reply=False):
        """
        Send command to USB device
        ----
        INPUT
            @usb_command (str): Correctly formated command for USB driver
            @get_reply (bool) : query the IN endpoint after sending command, to
                                      get controller's reply
        ----
        RETURN:
            Character representation of returned hex values if a reply is
                requested
        """
        self.ep_out.write(usb_command)

        if get_reply:
            return self.ep_in.read(100)

    def parse_command(self, newfocuscmd):
        """
        Convert a NewFocus style command into a USB command
        ------
        INPUT:
            newfocuscmd (str): of the form xxAAnn
                xx> it the device number
                AA> the command
                nn> a parameter
            eg. 2AC150000 -> set motor 2 acceleration at 150,000 steps/sec^2

            For more information see the Picomotor Controler/Driver user's manual

        """

        parsed_cmd = NEWFOCUS_COMMAND_REGEX.match(newfocuscmd)

        # Check to see if a regex match was found in the user submitted command
        if parsed_cmd:
            # Extract matched components of the command
            driver_number, command, parameter = parsed_cmd.groups()
            
            usb_command = command

            # Construct USB safe command
            if driver_number:
                usb_command = '1>{driver_number} {command}'.format(
                                                    driver_number=driver_number,
                                                    command=usb_command
                                                    )
            if parameter:
                usb_command = '{command} {parameter}'.format(
                                                    command=usb_command,
                                                    parameter=parameter
                                                    )

            usb_command += '\r'

            return usb_command
        else:
            print("ERROR! Command {} was not a valid format".format(
                                                            newfocuscmd))


    def parse_reply(self, reply):
        """
        Retrieve the controller's answer and make it readable

        ----
        INPUT
            @ans (list): list of bytes returns from controller in hex format

        ----
        RETURN
            @ans (str): Cleaned string of controller reply
        """

        ans = ''.join([chr(x) for x in reply])
        return ans.rstrip()

    def command(self, newfocuscmd):
        """
        Send NewFocus formated command
        ----
        INPUT
            newfocuscmd (str): Legal command listed in usermanual [2 - 6.2]

        ----
        RETURN
            reply (str): Human readable reply from controller
        """
        # print(f"In pico8742: {newfocuscmd}")
        usb_command = self.parse_command(newfocuscmd)

        # if there is a '?' in the command, the user expects a response from
        # the driver
        if '?' in newfocuscmd:
            get_reply = True
        else:
            get_reply = False

        reply = self.send_command(usb_command, get_reply)

        # if a reply is expected, parse it
        if get_reply:
            return self.parse_reply(reply)

    def get_velocity(self, channel="1"):
        """
            Returns velocity for a given channel
        """
        cmd = channel+"VA?"
        return self.command(cmd)

    def set_velocity(self, channel="1", value=None):
        """
            Set velocity for a given channel with value
        """
        if value is not None:
            cmd = channel+"VA"+str(value)
            self.command(cmd)

    def get_acceleration(self, channel=None):
        """
        Returns acceleration for a given channel
        ----
        INPUT
            @channel (int): Channel number

        ----
        RETURN
            result of the acceleration
        """

        if channel is None:
            channel = str(self.channel)

        cmd = channel+"AC?"
        return self.command(cmd)

    def set_acceleration(self, channel=None, value=None):
        """
        Set velocity for a given channel with value

        ----
        INPUT:
            @channel (int) : channel number
            @value (int) : new value of the acceleration in step/sec^2

        """
        if channel is None:
            channel = self.channel

        if value is not None: 
            cmd = channel+"AC"+str(value)
            self.command(cmd)

    def get_position(self, channel=None):
        """
        Returns current position for a given channel
        ----
        INPUT
            @channel (int): Channel number
        ----
        RETURN
            result of the position
        """

        if channel is None:
            channel = str(self.channel)

        cmd = channel+"TP?"
        return self.command(cmd)

    def start_console(self):
        """Continuously ask user for a command
        """
        print('''
        Picomotor Command Line
        ---------------------------
        Enter a valid NewFocus command, or 'quit' to exit the program.
        Common Commands:
            xMV[+-]: .....Indefinitely move motor 'x' in + or - direction
                 ST: .....Stop all motor movement
              xPRnn: .....Move motor 'x' 'nn' steps
        \n
        ''')

        while True:
            command = input("Command>")
            if command.lower() in ['q', 'quit', 'exit']:
                break
            else:
                rep = self.command(command)
                if rep:
                    print("Output: {}".format(rep))


if __name__ == '__main__':

    # Default value of idProduct and idVendor
    idProduct = '0x4000'  # '0x4000'
    idVendor = '0x104d'  # '0x104d'

    if not (idProduct or idVendor):
        print('Run the following command in a new terminal window:')
        print('\t$ system_profiler SPUSBDataType\n')
        print('Enter Product ID: (0x4000)')
        idProduct = input('> ')
        print('Enter Vendor ID: (0x104d)')
        idVendor = input('> ')
        print('\n')

    # convert hex value in string to hex value
    idProduct = int(idProduct, 16)
    idVendor = int(idVendor, 16)

    # Initialize controller
    controller = Pico8742Ctrl(idProduct=idProduct, idVendor=idVendor)
    # controller.start_console()
