# GUI PIONEERS


## Versionning

- 0.1: Under development: GUI for the motor only 


## Purpose

User interface devoted to control NEWPORT PicoMotor 8742 and ATTOCUBE Interferometer IDS3010.


## Author / Contact
Grégory Sainton (sainton@ipgp.fr) on behalf IPGP and PIONEERS project


## Environment

I deeply encourage you to create a specific environment to install and run the code to avoid libraries conflicts with other programs and application

### OS 
Development under MacOS... Tested on Windows

### PYTHON

PYTHON 3.8

### USB port control
- pyusb

Under Windows, you may have some issue to connect the motor. This is related to the driver used to connect USB devices.



### Graphic Interface libraries
- PyQt5
- PyQtGraph
 

### Newport PicoMotor 8742 lib
This is an internal development. I didn't put the library in a devoted Git repository. 
It's saved in MOTOR directory 
 
## Run the GUI

So far, you just need to run $python guipioneers.py to run the interface.


## On going development
