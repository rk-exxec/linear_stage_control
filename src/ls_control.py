#     Linear Stage Control is a program to control a single linear table via SMCI33-1
#     Copyright (C) 2021  Raphael Kriegl

#     This program is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.

#     This program is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#     GNU General Public License for more details.

#     You should have received a copy of the GNU General Public License
#     along with this program.  If not, see <https://www.gnu.org/licenses/>.

import functools
import serial
import time
import logging
from decimal import Decimal
import threading
import signal
import sys


from serial.tools.list_ports import comports


class MotorNotReferencedError(Exception):
    def __init__(self):
        super().__init__('Motor not referenced! Please call do_referencing()!')

class LinearStageControl(object):
    """ 
    This class contains all the control functions
    Create a new motor control object.

    :param portname: The Port for the serial connection (e.g. 'COM4' for Windows, '/dev/ttyS1' for Linux) or 'auto' for automatic discovery
    :param reference: Which limit switch will be used for referencing the motor, far means away from motor, near means near, coordinates are positive away from reference
    :param com_timeout: Timeout in sek for serial port
    """
    def __init__(self, portname='auto', reference='near', com_timeout=0.2):

        signal.signal(signal.SIGINT, self.sig_handler)
        signal.signal(signal.SIGTERM, self.sig_handler)
        self._serial_port = serial.Serial()
        if portname == 'auto':
            try:
                self._serial_port.port = self.find_com_port()
            except ConnectionError as ce:
                print('Stepper driver not found!')
                self._serial_port.port = None
        else:
            self._serial_port.port = portname
        self._serial_port.baudrate = 115200
        self._serial_port.timeout = com_timeout
        self._context_depth = 0
        self._debug = False
        self._connection_error = False
        self._substeps = 8 #does not do anything right now, for future
        self._reference_point = reference
        self._reference_changed = False
        self._status = 1
        self._positioning_error = 0
        self._killswitch_wait = False
        self._wait_mov_fin_thread = threading.Thread(target=self.wait_movement)
        #self.setup_defaults()
        # if not self.is_referenced():
        #     print('Referencing is required!')

    def __enter__(self):
        if not self._connection_error:
            try:
                if self._context_depth == 0 and self._serial_port.port is not None:
                    # self._serial_port.flushOutput()
                    # self._serial_port.flushInput()
                    self._serial_port.open()
            except Exception as ex:
                self._connection_error = True
                logging.error("stage control: error opening port: \n" + str(exc))
                raise  
            self._context_depth += 1
            return self
        else:
            return None

    def __exit__(self, exc, value, traceback):
        self._context_depth -= 1
        if self._context_depth == 0:
            self._serial_port.close()
        if exc:
            self._connection_error = True
            logging.error("stage control: error closing port: \n" + str(exc))
        return True

    def ErrorOutsideContext(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if args[0]._context_depth == 0:
                raise RuntimeError('Cannot use this Funtion outside of context').with_traceback(None)
            return func(*args, **kwargs)
        return wrapper

    def ErrorInsideContext(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if args[0]._context_depth != 0:
                raise RuntimeError('Cannot use this Funtion inside context').with_traceback(None)
            return func(*args, **kwargs)
        return wrapper

    @staticmethod
    def find_com_port() -> str:
        lst = comports()
        for port in lst:
            if port.manufacturer == 'Nanotec':
                return port.device
        else:
            raise ConnectionError('No Nanotec device found!')

    def has_connection_error(self):
        return self._connection_error

    @ErrorInsideContext
    def reset_connection(self) -> bool:
        """
        Try to reset connection if timeout has occured
        """
        try:
            with self:
                self.is_control_ready()
            self._connection_error = False
            return True
        except TimeoutError:
            self._connection_error = True
            return False

    # def __delete__(self, instance):
    #     if self._serial_port.is_open:
    #         self._serial_port.close()

    # def __del__(self):
    #     if self._serial_port.is_open:
    #         self._serial_port.close()

    def sig_handler(self, sig, fr):
        self.stop()
        print('Keyboard Interrupt: Motor stopped!')

    # def close(self):
    #     self._serial_port.close()

    def test_connection(self) -> bool:
        try:
            with self._serial_port:
                self._serial_port.is_open
            return True
        except TimeoutError as toe:
            return False

    @ErrorOutsideContext
    def query(self, message):
        """
        Send a message to the controller with newline char and reads response.

        :param message: The message to send, should be in proper syntax
        :returns: The response without newline
        :rtype: String
        """
        msg = message + '\r'
        if self._debug: print(message)
        #with self._serial_port:
        if not self._connection_error:
            self._serial_port.write(msg.encode())
            ans = self._serial_port.read_until(b'\r').decode('utf-8')
            if len(ans) == 0:
                raise TimeoutError('Port Timeout!')
            else:
                if self._debug: print(ans.strip())
                return ans.strip()
        else: return 0

    def command(self, message):
        """
        Send commands to controller. Check if write was successful.

        This is simply a query wrapper that does a validity check on the commandsand checks the response of the controller. 

        :param message: Query like string, following the proper syntax
        :returns: True if operation was successful, else False
        :rtype: Boolean
        """
        ans = self.query(message)
        if ans[-1] == '?':
            return False
        else:
            return True

    def is_referenced(self):
        """
        Check whether the motor is referenced.

        This is necessary after every loss of power to the controller
        :returns: True if motor is referenced
        :rtype: Boolean
        """
        ans = self.query('#1:is_referenced')
        if ans[-1] == '1' and not self._reference_changed:
            return True
        else:
            return False

    def setup_defaults(self):
        self.command(f'#1g{self._substeps}') # microstepping


    def fetch_status(self):
        """
        Fetch status from controller, extract integer value, save positioning error and state to internal variable for later use.
        
        :returns: The status value
        :rtype: int

        .. seealso:: :py:func:`is_control_ready`, :py:func:`has_positioning_error`
        """
        #extract int value and mask only useful 4 bits
        tmp = self.query('#1$')
        if tmp[-1] != '?':
            tmp = int(tmp[-3:])
            tmp = int(tmp)
            self._status = tmp & 0xF
            self._positioning_error = (self._status & 0b0100) >> 2
            return self._status

    def is_control_ready(self):
        """
        Check if the control is ready for movement

        :returns: True if control is ready
        :rtype: Boolean
        """
        ans = self.fetch_status()
        if ans & 1:
            return True
        else:
            return False

    def has_positioning_error(self):
        """
        Check control if a positioning error has occured since last call to :py:func:`clear_positioning_error`

        :returns: True if a positioning error has occured
        :rtype: Boolean

        .. seealso:: :py:func:`clear_positioning_error`
        """
        self.fetch_status()
        if self._positioning_error:
            return True
        else:
            return False

    def clear_positioning_error(self, reset_position=False):
        """
        Clear the positioning error to reenable movement.

        :param reset_postiton: False (default): Absolute position does not change, True: Set current absolute position to 0
        """
        self._positioning_error = 0
        if reset_position:
            self.query('#1D0')
        else:
            ans=self.query('#1C')
            ans = ans[2:] # extract position
            self.query('#1D' + ans) # clear error and set position

    def get_position(self):
        """
        Read the current position from the controller

        :returns: the position as int
        """
        ans = self.query('#1C')
        ans = ans[2:] # extract position
        if not self._reference_point == 'far':
            return ans + 50000
        else:
            return ans

    def set_soft_ramp(self):
        """
        Sets the accel and decel ramp do be softer
        """
        with self:
            self.command('#1:ramp_mode=+1') # sine ramp type
            self.command('#1:decelquick=+3000000') # quick stop Hz/s
            self.command('#1:accel=+10000') # accel Hz/s
            self.command('#1:decel=+10000') # brake Hz/s

    def set_quick_ramp(self):
        """
        Sets the accel and decel ramp do be abrupt
        """
        with self:
            self.command('#1:ramp_mode=+0') # trapez ramp type
            self.command('#1:decelquick=+3000000') # quick stop Hz/s
            self.command('#1:accel=+50000') # accel Hz/s
            self.command('#1:decel=+50000') # brake Hz/s

    def steps_to_mm(self, steps):
        """
        Converts the number of steps to distance in millimeters

        :param steps: The number of steps
        :returns: The distance in millimeters
        """
        steps_per_turn = self._substeps * 200
        return (1.25/steps_per_turn) * steps

    def mm_to_steps(self, mm):
        """
        Converts the distance in millimeters to number of steps

        :param mm: The distance in millimeters
        :returns: The number of steps
        """
        steps_per_turn = self._substeps * 200
        return int(round(Decimal((steps_per_turn/1.25) * mm)))

    def wait_movement(self):
        """
        Wait for movement ot finish.
        """
        while not self.is_control_ready():
            time.sleep(0.1)
        if self.has_positioning_error():
            # in endschalter gelaufen
            # reset position
            #self.stop()
            self.clear_positioning_error()
            #print('Movement ended prematurely!')

    def stop(self):
        """
        Immediately stops the motor
        """
        self.command('#1S')

    def stop_soft(self):
        """
        Stops the motor with brake ramp
        """
        self.command('#1S1')

    def set_reference_point(self, reference):
        """
        Redefine the reference point.

        :param reference: Which limit switch will be used for referencing the motor, 'far' means away from motor, 'near' means near, coordinates are positive away from reference
        """
        self._reference_point = reference
        self._reference_changed = True
        print('Please reference motor again!')

    def do_referencing(self):
        """
        Reference the motor to the limit switch defined by the reference
        point.
        """
        self.command('#1p4')
        self.command('#1l5154') # limit switch behaviour: slowly back off switch
        if self._reference_point == 'near':
            self.command('#1d1')
        else:
            self.command('#1d0')
        self.command('#1o4000')
        self.command('#1A')
        self._reference_changed = False
        
    def move_relative(self, steps, speed=4000):
        """Move the Stage relative to its current position.

        :param steps: number of steps to travel, max 50000
            steps < 0: Movement towards reference
            steps > 0: Movemento away from reference
        :param speed: Speed in steps/s (max 16000)
        """
        if abs(steps) > 50000:
            print("Relative Movement: Too many steps!")
            return
        if self._reference_point == 'far':
            self.command('#1d1')
        else:
            self.command('#1d0')
        self.command('#1p1')
        self.command('#1o' + str(speed))
        self.command('#1s' + str(steps))
        self.command('#1A')

    def move_absolute(self, steps, speed=4000):
        """Move the Stage to absolute position, 0 is opposite of motor.

        :param steps: Absolute position between 0 and 50000
        :param speed: Speed in steps/s
        """
        if not self.is_referenced():
            logging.error("lt_control: move_absolute(): not referenced!")
            return
        if abs(steps) > 50000:
            print('Absolute Movement: Too many steps!')
            return
        if not self._reference_point == 'far':
            steps = steps - 50000
        self.command('#1p2')
        self.command('#1o' + str(int(speed)))
        self.command('#1s' + str(int(steps)))
        self.command('#1A')

    def move_relative_mm(self, distance_mm, speed=3):
        """Move the Stage relative to its current position.

        :param distance_mm: travel distance in millimeters
            < 0: Movement away from motor
            > 0: Movement towards motor
        :param speed: Speed in mm/s
        """
        steps = self.mm_to_steps(distance_mm)
        speed = self.mm_to_steps(speed)
        self.move_relative(steps, speed)

    def move_absolute_mm(self, position_mm, speed=3):
        """Move the Stage to absolute position, 0 ist limit switch opposite of motor.

        :param position_mm: Absolute position between 0 and 39
        :param speed: Speed in mm/s
        """
        if not self.is_referenced():
            raise MotorNotReferencedError
        steps = self.mm_to_steps(position_mm)
        speed = self.mm_to_steps(speed)
        self.move_absolute(steps, speed)

    def move_inf_start(self, dest, speed=4000):
        """ Starts stage movement wit continous speed. Needs to be stopped with stop()

        :param dest: Movement direction, 0 towards, 1 away from motor
        :param speed: Speed in steps/s
        """
        self.command('#1d' + str(int(dest)))
        self.command('#1p5')
        self.command('#1o' + str(int(speed)))
        self.command('#1A')
        
    def get_position(self):
        """Return absolute position in steps.

        :returns: absolute position in steps
        """
        real_pos = int(self.query('#1C')[2:])
        if self._reference_point == 'far':
            disp_pos = real_pos
        else:
            disp_pos = real_pos + 50000
        return disp_pos