import serial
import time
from decimal import Decimal
import signal

class MotorNotReferencedError(Exception):
    def __init__(self):
        super().__init__('Motor not referenced! Please call do_referencing()!')

class LT(object):
    
    def __init__(self, portname, reference='near', com_timeout=1):
        """
        Create a new motor control object.

        :param portname: The Port for the serial connection (e.g. 'COM4' for Windows, '/dev/ttyS1' for Linux)
        :param reference: Which limit switch will be used for referencing the motor, far means away from motor, near means near, coordinates are positive away from reference
        :param com_timeout: Timeout in sek for serial port
        """
        signal.signal(signal.SIGINT, self.sig_handler)
        signal.signal(signal.SIGTERM, self.sig_handler)
        self.__serial_port = serial.Serial(portname, 115200, timeout=com_timeout)
        self.__debug = False
        self.__substeps = 8 #does not do anything right now, for future
        self.__reference_point = reference
        self.__reference_changed = False
        self.__status = 1
        self.__positioning_error = 0
        self.setup_defaults()
        if not self.is_referenced():
            print('Referencing is required!')

    def __delete__(self, instance):
        if self.__serial_port:
            self.__serial_port.close()

    def __del__(self):
        if self.__serial_port:
            self.__serial_port.close()

    def sig_handler(self, sig, fr):
        self.stop()
        print('Keyboard Interrupt: Motor stopped!')

    def close(self):
        self.__serial_port.close()

    def query(self, message):
        """
        Send a message to the controller with newline char and reads response.

        :param message: The message to send, should be in proper syntax
        :returns: The response without newline
        :rtype: String
        """
        msg = message + '\r'
        if self.__debug: print(message)
        self.__serial_port.write(msg.encode())
        ans = self.__serial_port.read_until(b'\r').decode('utf-8')
        if len(ans) == 0:
            raise TimeoutError
        else:
            if self.__debug: print(ans.strip())
            return ans.strip()

    def is_referenced(self):
        """
        Check whether the motor is referenced.

        This is necessary after every loss of power to the controller
        :returns: True if motor is referenced
        :rtype: Boolean
        """
        ans = self.query('#1:is_referenced')
        if ans[-1] == '1' and not self.__reference_changed:
            return True
        else:
            return False

    def setup_defaults(self):
        self.command('#1g8') # microstepping, 8 microsteps per step
    
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

    def fetch_status(self):
        """
        Fetch status from controller, extract integer value, save positioning error and state to internal variable for later use.
        
        :returns: The status value
        :rtype: int
        .. seealso:: is_control_ready(), has_position_error()
        """
        #extract int value and mask only useful 4 bits
        tmp = self.query('#1$')[-3:]
        tmp = int(tmp)
        self.__status = tmp & 0xF
        #self.__status = int(self.query('#1$')[-3:]) & 0xF
        self.__positioning_error = (self.__status & 0b0100) >> 2
        return self.__status

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
        Check control if a positioning error has occured since last clear_positioning_error()
        :returns: True if a positioning error has occured
        :rtype: Boolean
        .. seealso:: clear_position_error
        """
        self.fetch_status()
        if self.__positioning_error:
            return True
        else:
            return False

    def clear_positioning_error(self, reset_position=False):
        """
        Clear the positioning error to reenable movement.

        :param reset_postiton: False (default): Absolute position does not change, True: Set current absolute position to 0
        """
        self.__positioning_error = 0
        if reset_position:
            self.query('#1D0')
        else:
            ans=self.query('#1C')
            ans = ans[2:] # extract position
            self.query('#1D' + ans) # clear error and set position

    def steps_to_mm(self, steps):
        """
        Converts the number of steps to distance in millimeters

        :param steps: The number of steps
        :returns: The distance in millimeters
        """
        steps_per_turn = self.__substeps * 200
        return (1.25/steps_per_turn) * steps

    def mm_to_steps(self, mm):
        """
        Converts the distance in millimeters to number of steps

        :param mm: The distance in millimeters
        :returns: The number of steps
        """
        steps_per_turn = self.__substeps * 200
        return int(round(Decimal((steps_per_turn/1.25) * mm)))

    def wait_movement(self):
        """
        Wait for movement ot finish.
        """
        while not self.is_control_ready() and not self.has_positioning_error():
            time.sleep(0.1)       
        if self.has_positioning_error():
            # in endschalter gelaufen
            # reset position
            self.stop()
            self.clear_positioning_error()
            print('Movement ended prematurely!')

    def stop(self):
        """
        Immediately stops the motor
        """
        self.command('#1S')

    def set_reference_point(self, reference):
        """
        Redefine the reference point.

        :param reference: Which limit switch will be used for referencing the motor, 'far' means away from motor, 'near' means near, coordinates are positive away from reference
        """
        self.__reference_point = reference
        self.__reference_changed = True
        print('Please reference motor again!')

    def do_referencing(self):
        """
        Reference the motor to the limit switch defined by the reference
        point.
        """
        self.command('#1p4')
        self.command('#1l5154') # endschalterverhalten auf r�ckw�rts vom schalter runterfahren
        if self.__reference_point == 'near':
            self.command('#1d1')
        else:
            self.command('#1d0')
        self.command('#1o4000')
        self.command('#1A')
        self.wait_movement()
        self.__reference_changed = False
        
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
        if self.__reference_point == 'far':
            self.command('#1d1')
        else:
            self.command('#1d0')
        self.command('#1o' + str(speed))
        self.command('#1s' + str(steps))
        self.command('#1A')
        self.wait_movement()

    def move_absolute(self, steps, speed=4000):
        """Move the Stage to absolute position, 0 is opposite of motor.

        :param steps: Absolute position between 0 and 50000
        :param speed: Speed in steps/s
        """
        if not self.is_referenced():
            raise MotorNotReferencedError
        if abs(steps) > 50000:
            print('Absolute Movement: Too many steps!')
            return
        if not self.__reference_point == 'far':
            steps = steps - 50000
        self.command('#1p2')
        self.command('#1o' + str(int(speed)))
        self.command('#1s' + str(int(steps)))
        self.command('#1A')
        self.wait_movement()

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

    def get_position(self):
        """Return absolute position in steps.

        :returns: absolute position in steps
        """
        real_pos = int(self.query('#1C')[2:])
        if self.__reference_point == 'far':
            disp_pos = real_pos
        else:
            disp_pos = real_pos + 50000
        return disp_pos
