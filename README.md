# Linear Stage Control

A python class to control a single axis translation table with two limit switches via the SMCI33-1 controller  
Tested with the movetec L60 and L65 linear stages.

[![Documentation Status](https://readthedocs.org/projects/linear-stage-control/badge/?version=latest)](https://linear-stage-control.readthedocs.io/en/latest/?badge=latest)

## Installation

1. clone or download this repository
2. install python 3.8.x, make sure it is added to your PATH variable
3. install packages `pip install -r requirements.txt`

## GUI Usage 

![grafik](https://user-images.githubusercontent.com/40037381/105205492-9d02a780-5b45-11eb-8d78-1439f3895b21.png)

Connect controller via USB.  
Execute program via command line `python -m linear_stage_control`  


### Controls
- Jog Up / Down moves the motor in the specified direction while the buttons are held
- STOP will stop the motor immediately
- Slider/TextBox: You can also specify a location to travel to via the slider or the text box. You can choose between mm and steps as as unit. To start travel, press GO.
- Soft Ramp: checkbox causes the motor to accelerate more softly, reducing jerking movements to protect sensitive equipment
- Reference: this button will start the referencing sequence to enable the afore mentioned location travel ability.
- The Lamp will indicate the status:
    - Red: serial connection failed / ERROR
    - Yellow: not referenced
    - Green: all ok

### Referencing

To move to absolute coordinates, the motor must be referenced.  
For that, press the Reference button.   

**The motor will start moving immediately!**  

**The motor moves until it hits the limit switch! Make sure nothing is in the way!**  

**If the motor does not stop at the limit switch, press STOP!**  
Check your connections or make sure the voltage level of your switches is 5-24V!

## Troubleshooting

The Serial Port of the controller should be detected automatically, but this will only work reliably if no other Nanotec controller is plugged in!  
If it doesnt work, open `ls_gui.py` and alter this line:  
`self.ls_ctl = LinearStageControl()`  
to  
`self.ls_ctl = LinearStageControl(portname="COM4")`  
replace *"COM4"* with the portname of your device, this supports linux ports.  
Then restart the program.

## API Documentation

https://linear-stage-control.readthedocs.io
