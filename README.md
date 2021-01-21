# movtec L60 Control

A python class to control the L60 translation table from movtec.de with two limit switches via the SMCI33-1 controller

## Installation

1. clone repo
2. install python 3.8.x, make sure it is added to your PATH variable
3. install packages `pip install -r requirements.txt`

## GUI Usage 

![grafik](https://user-images.githubusercontent.com/40037381/105205492-9d02a780-5b45-11eb-8d78-1439f3895b21.png)

Connect controller via USB.  
Execute program via command line `python main.py`  


### Controls
- Jog Up / Down moves the motor in the specified direction while the buttons are held
- STOP will stop the motor immediately
- You can also specify a location to travel to via the slider or the text box. You can choose between mm and steps as as unit. To start travel, press GO.
- The Soft Ramp checkbox causes the motor to accelerate more softly, reducing jerking movements to protect snsitive equipment
- The Reference button will start the referencing sequence to enable the afore mentioned location travel ability.
- The Lamp will indicate the status:
    - Red: serial connection failed / ERROR
    - Yellow: not referenced
    - Green: all ok

### Referencing

To move to absolute coordinates, the motor must be referenced.  
For that, press the Reference button.   
**The motor will start moving immediately!**  
**If the motor does not stop at the limit switch, press STOP!**  
Check your connections or make sure the voltage level of your switches is 5-24V!

## Troubleshooting

The Serial Port of the controller should be detected automatically, but this will only work reliably if no other Nanotec controller is plugged in!  
If it doesnt work, open `main.py` and alter this line:  
`self._lt_ctl = LT()`  
to  
`self._lt_ctl = LT(portname="COM4")`  
replace *"COM4"* with the portname of your device, this supports linux ports.  
Then restart the program.
