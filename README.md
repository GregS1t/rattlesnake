# GUI PIONEERS
![Pioneers image](./images/splash_guipionner.png)

## Versionning

- 0.1: Under development.
	 


## Purpose

User interface devoted to control NEWPORT PicoMotor 8742 and ATTOCUBE Interferometer IDS3010.


## Author / Contact
Grégory Sainton on behalf IPGP and PIONEERS project


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
 
### Dependances
All the necessary packages are listed in requirement.txt 
You need in particular : 
- pyqtgraph
- pyusb
- pyvisa

### Newport PicoMotor 8742 lib
This is an internal development. I didn't put the library in a devoted Git repository. 
It's saved in MOTOR directory 
 
## Run the GUI

So far, you just need to run $python guipioneers.py to run the interface.


## On going development

![main_window](./images/rattlesnakemain.png)


