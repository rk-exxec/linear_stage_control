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

# TODO expose more settings of lt_control, reference side, etc.

import functools
import pathlib
import logging
from enum import Enum, auto

from PySide6.QtCore import QTimer, QThread, QRect, QSize, Qt, QCoreApplication, Slot
from PySide6.QtGui import QPainter, QPaintEvent, QIcon, QFont, QShowEvent
from PySide6.QtWidgets import (
    QWidget, QGroupBox, QPushButton, QCheckBox, QSlider, QDoubleSpinBox, QAbstractSpinBox,
    QComboBox, QLabel, QFrame, QMessageBox
)

from .LinearStageControl import LinearStageControl


class CustomCallbackTimer(QTimer):
    """ Timer with custom callback function """
    def __init__(self, target, interval=500):
        super(CustomCallbackTimer, self).__init__()
        self.setInterval(interval)
        self.setSingleShot(False)
        self.timeout.connect(target)

class CallbackWorker(QThread):
    """ Thread with callback function on exit """
    def __init__(self, target, *args, slotOnFinished=None, **kwargs):
        super(CallbackWorker, self).__init__()
        self.args = args
        self.kwargs = kwargs
        self.target = target
        if slotOnFinished:
            self.finished.connect(slotOnFinished)

    def run(self):
        self.target(*self.args, **self.kwargs)

class LightColor(Enum):
    """ helper class to enumerate colors for lamp widget

    .. seealso:: :class:`LightWidget`
    """
    RED = auto() #Qt.red
    GREEN = auto() #Qt.green
    ERROR = auto() #Qt.darkRed
    YELLOW = auto() #Qt.yellow
    OFF = auto()

class LightWidget(QWidget):
    """
    provides a round status lamp as widget with 4 colors to indicate status ok, warning, stop and error

    .. seealso:: :class:`LightColor`
    """
    def __init__(self, parent=None):
        super(LightWidget, self).__init__(parent)
        self._color = LightColor.OFF

    def set_red(self):
        """ set lamp color to red """
        self._color = LightColor.RED
        self.update()

    def set_green(self):
        """ set lamp color to green """
        self._color = LightColor.GREEN
        self.update()

    def set_error(self):
        """ set lamp color to dark red """
        self._color = LightColor.ERROR
        self.update()

    def set_yellow(self):
        """ set lamp color to yellow """
        self._color = LightColor.YELLOW
        self.update()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._color == LightColor.RED:
            painter.setBrush(Qt.GlobalColor.red)
        elif self._color == LightColor.GREEN:
            painter.setBrush(Qt.GlobalColor.green)
        elif self._color == LightColor.ERROR:
            painter.setBrush(Qt.GlobalColor.darkRed)
        elif self._color == LightColor.YELLOW:
            painter.setBrush(Qt.GlobalColor.yellow)
        else:
            painter.setBrush(Qt.GlobalColor.gray)
        painter.drawEllipse(2,2,self.width()-4, self.height()-4)
        painter.end()

class LinearStageControlGUI(QGroupBox):
    """
    A widget to control the motor via the module :class:`LinearStageControl`.

    """
    def __init__(self, parent=None) -> None:
        super(LinearStageControlGUI, self).__init__(parent)
        self.logger = logging.getLogger()
        self.setupUI()
        self._shown = False
        self._mov_dist: float = 0
        self._mov_unit: str = 'steps'
        self._mov_speed: int = 4000 # steps/s
        self._mov_speed_mm: float = 3.0 # mm/s
        self._old_unit: str = 'steps'
        self._invalid = False
        self.wait_movement_thread = CallbackWorker(self.wait_movement, slotOnFinished=self.finished_moving)
        self.update_pos_timer = CustomCallbackTimer(self.update_pos, 250)
        self.ls_ctl: LinearStageControl = None
        self.initialize()
        self.logger.debug("initialized stage control")

    def __del__(self):
        del self.ls_ctl

    def connect_signals(self):
        self.jogUpBtn.pressed.connect(self.jog_up_start)
        self.jogDownBtn.pressed.connect(self.jog_down_start)
        self.jogUpBtn.released.connect(self.motor_stop_soft)
        self.jogDownBtn.released.connect(self.motor_stop_soft)
        self.referenceBtn.clicked.connect(self.reference)
        self.goBtn.clicked.connect(self.move_pos)
        self.stopBtn.clicked.connect(self.motor_stop)
        self.posSpinBox.valueChanged.connect(self.pos_spin_box_val_changed) #lambda pos: self.magnet_ctl.set_mov_dist(int(pos)) or self.posSlider.setValue(int(pos))
        self.unitComboBox.currentTextChanged.connect(self.mag_mov_unit_changed)
        self.posSlider.sliderMoved.connect(self.pos_slider_moved) # only fires with user input lambda pos: self.posLineEdit.setText(str(pos)) or self.posSpinBox.setValue(float(pos))
        self.softRampChk.stateChanged.connect(self.change_ramp_type)
        self.speedSlider.sliderMoved.connect(self.speed_slider_moved)
        self.speedSpinBox.valueChanged.connect(self.speed_spin_box_val_changed)

    
    def if_port_is_active(func):
        """ Decorator that only executes fcn if serial port is open, otherwise it fails silently """
        def null(*args, **kwargs):
            pass

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if args[0].ls_ctl.has_connection_error():
                args[0].logger.debug("Device not ready")
                return null(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        return wrapper

    def showEvent(self, event: QShowEvent):
        if not self._shown:
            self.connect_signals()
            self.mag_mov_unit_changed('mm')
            self.update_motor_status()
            self.update_pos()
            # self.change_ramp_type(self.softRampChk.isChecked())
            self._shown = True
            return True
        
    def initialize(self):
        """ Create control instance and check for status """
        if self.ls_ctl is not None: 
            self.ls_ctl.close_port()
            del self.ls_ctl
            self.ls_ctl = None
        self.lamp.set_error()
        self.set_status_message('Not connected!')
        self.ls_ctl = LinearStageControl()
        if self.ls_ctl.has_connection_error():
            self.logger.error("Motor not found!")
            return
        
        with self.ls_ctl:
            self.ls_ctl.read_substeps()
        self.change_ramp_type(self.softRampChk.isChecked())
        self.update_motor_status()
        self.update_pos()

    @if_port_is_active
    def update_pos(self):
        """ update spin box with current pos"""
        try:
            pos = float(self.get_position())
        except Exception as toe:
            pos = 45100
        self.posSpinBox.setValue(pos)

    @if_port_is_active
    def update_motor_status(self):
        """ Get motor status and display it """
        with self.ls_ctl:
            try:
                if not self.ls_ctl.is_referenced():
                    self.lamp.set_yellow()
                    self.set_status_message('Referencing needed!')
                    self.unlock_movement_buttons()
                    self.lock_abs_pos_buttons()
                    self.logger.info("stage control: no reference! locking absolute movement")
                    return True
                elif self.ls_ctl.is_control_ready():
                    self.lamp.set_green()
                    self.set_status_message('Ready')
                    self.unlock_movement_buttons()
                    self.logger.info("stage control: has reference! unlocking absolute movement")
                    return True
                else:
                    self.lamp.set_red()
                    self.set_status_message('Connection Error!')
                    self.logger.warning("stage control: connection error")
                    self.lock_movement_buttons()
                    return False
            except TimeoutError as te:
                self.lamp.set_red()
                self.set_status_message('Connection Timeout!')
                self.lock_movement_buttons()
                return False

    @Slot(str)
    def mag_mov_unit_changed(self, unit: str):
        """ update slider and spin box if the movement units has changes """
        self._mov_unit = unit.strip()
        old_val = self.posSpinBox.value()
        if unit == 'mm':
            self.posSlider.setMaximum(3906) #max mm are 39.0625
            self.posSlider.setTickInterval(100)
            self.posSpinBox.setDecimals(2)
            if self._old_unit == 'steps':
                self.posSpinBox.setValue(self.ls_ctl.steps_to_mm(old_val))
        elif unit == 'steps':
            self.posSlider.setMaximum(50000)
            self.posSlider.setTickInterval(1000)
            self.posSpinBox.setDecimals(0)
            if self._old_unit == 'mm':
                self.posSpinBox.setValue(self.ls_ctl.mm_to_steps(old_val))
        else:
            return
        self.logger.info(f"stage control: movement unit changed from {self._old_unit} to {self._mov_unit}")
        self._old_unit = self._mov_unit

    @Slot(float)
    def pos_spin_box_val_changed(self, value: float):
        """ update internal variable and slider if spin box value changed """
        self._mov_dist = int(value)
        if self.unitComboBox.currentText() == 'mm':
            value = value*100
        self.posSlider.setValue(int(value))

    @Slot(int)
    def pos_slider_moved(self, value: int):
        """ update spin box if slider moved, this causes the spin box valueChanged signal to fire """
        if self.unitComboBox.currentText() == 'mm':
            self.posSpinBox.setValue(float(value/100))
        else:
            self.posSpinBox.setValue(float(value))

    @Slot(float)
    def speed_spin_box_val_changed(self, value: float):
        """ update internal variable and slider if spin box value changed """
        self.set_speed(value)
        self.speedSlider.setValue(int(value*10))

    @Slot(int)
    def speed_slider_moved(self, value: int):
        """ update spin box if slider moved, this causes the spin box valueChanged signal to fire """
        self.speedSpinBox.setValue(float(value)/10)

    def set_speed(self, value):
        """set the speed of the motor

        :param value: speed in mm/s
        """
        self._mov_speed = self.ls_ctl.mm_to_steps(value)
        self._mov_speed_mm = value

    @if_port_is_active
    def update_speed(self, value):
        """live update the speed of the motor

        :param value: speed in mm/s
        """
        # self._mov_speed = self.ls_ctl.mm_to_steps(value)
        # self._mov_speed_mm = value
        with self.ls_ctl:
            self.ls_ctl.command('#1o' + str(self.ls_ctl.mm_to_steps(value)))


    @Slot(Qt.CheckState)
    @if_port_is_active
    def change_ramp_type(self, state: Qt.CheckState):
        """ set motor brake and accel ramp on check changed """
        if state == Qt.CheckState.Checked:
            with self.ls_ctl:
                self.ls_ctl.set_soft_ramp()
            self.logger.info("stage control: set soft ramp")
        elif state == Qt.CheckState.Unchecked:
            with self.ls_ctl:
                self.ls_ctl.set_quick_ramp()
                self.logger.info("stage control: set quick ramp")
        else:
            pass


    def do_timeout_dialog(self) -> bool:
        """ display a dialog if the connection timed out """
        ret = QMessageBox.critical(self, "Connection timeout!", "Could not connect ot the stepper driver! Retry?", buttons=QMessageBox.StandardButton.Abort|QMessageBox.StandardButton.Retry)
        if ret == QMessageBox.StandardButton.Retry:
            return True
        else:
            return False

    def get_position(self, unit=None):
        """ return the motor position in the current unit """
        if not unit:
            unit = self._mov_unit
        with self.ls_ctl:
            if unit == 'steps':
                return self.ls_ctl.get_position()
            elif unit == 'mm':
                return self.ls_ctl.steps_to_mm(self.ls_ctl.get_position())
            else:
                raise ValueError(f"Unsupported unit: {unit}")

    @Slot()
    @if_port_is_active
    def jog_up_start(self):
        """ start motor movement away from motor """
        self.logger.info("stage control: start jog up")
        self.set_status_message('Jogging')
        with self.ls_ctl:
            self.ls_ctl.move_inf_start(0, speed=self._mov_speed)
        self.update_pos_timer.start()

    @Slot()#
    @if_port_is_active
    def jog_down_start(self):
        """ start motor movement towards motor """
        self.logger.info("stage control: start jog down")
        self.set_status_message('Jogging')
        with self.ls_ctl:
            self.ls_ctl.move_inf_start(1, speed=self._mov_speed)
        self.update_pos_timer.start()

    @Slot()
    @if_port_is_active
    def move_pos(self):
        """ move motor to specified position """
        with self.ls_ctl:
            if self._mov_unit == 'mm':
                self.ls_ctl.move_absolute_mm(self._mov_dist, speed=self._mov_speed_mm)
            elif self._mov_unit == 'steps':
                self.ls_ctl.move_absolute(int(self._mov_dist), speed=self._mov_speed)
        self.lock_movement_buttons()
        self.logger.info(f"stage control: start movement to {self._mov_dist} {self._mov_unit}")
        self.set_status_message(f'Moving to {self._mov_dist} {self._mov_unit}')
        self.wait_movement_thread.start()

    @Slot()
    @if_port_is_active
    def motor_stop(self):
        """ stop motor immediately"""
        with self.ls_ctl:
            self.ls_ctl.stop()
        if self.update_pos_timer.isActive():
            self.update_pos_timer.stop()
        self.logger.info("stage control: stop")
        self.set_status_message('Stop')
        self.update_pos()
        self.update_motor_status()

    @Slot()
    @if_port_is_active
    def motor_stop_soft(self):
        """ stops motor with brake ramp """
        with self.ls_ctl:
            self.ls_ctl.stop_soft()
        if self.update_pos_timer.isActive():
            self.update_pos_timer.stop()
        self.logger.info("stage control: stop")
        self.set_status_message('Stop')
        self.lock_movement_buttons()
        self.wait_movement_thread.start()

    def wait_movement(self):
        """ wait unitl movement stops """
        with self.ls_ctl:
            self.ls_ctl.wait_movement()

    def finished_moving(self):
        """ update ui position displays when movement finishes """
        # callback for when the motor stops moving (only absolute and relative, and jogging with soft stop)
        self.logger.info("stage control: reached pos")
        self.update_pos()
        self.update_motor_status()

    @Slot()
    @if_port_is_active
    def reference(self):
        """ execute referencing process """
        self.lamp.set_yellow()
        self.logger.info("stage control: referencing")
        self.set_status_message('Referencing')
        with self.ls_ctl:
            self.ls_ctl.do_referencing()
        self.lock_movement_buttons()
        self.wait_movement_thread.start()

    def is_driver_ready(self) -> bool:
        """ check if the motor drive is ready for movement """
        with self.ls_ctl:
            return self.ls_ctl.test_connection()

    def unlock_mag_unit(self):
        """ mag unit is now available """
        self.unitComboBox.addItem('mT')

    def lock_mag_unit(self):
        """ mag unit is not available """
        self.unitComboBox.clear()
        self.unitComboBox.addItems(['steps','mm'])

    def lock_movement_buttons(self):
        """ lock buttons if movemnt shouldn't be possible """
        self.jogUpBtn.setEnabled(False)
        self.jogDownBtn.setEnabled(False)
        self.jogUpBtn.setEnabled(False)
        self.jogDownBtn.setEnabled(False)
        self.referenceBtn.setEnabled(False)
        self.goBtn.setEnabled(False)
        self.posSpinBox.setEnabled(False)
        self.unitComboBox.setEnabled(False)
        self.posSlider.setEnabled(False)
        self.softRampChk.setEnabled(False)

    def lock_abs_pos_buttons(self):
        self.goBtn.setEnabled(False)

    def unlock_movement_buttons(self):
        self.jogUpBtn.setEnabled(True)
        self.jogDownBtn.setEnabled(True)
        self.jogUpBtn.setEnabled(True)
        self.jogDownBtn.setEnabled(True)
        self.referenceBtn.setEnabled(True)
        self.goBtn.setEnabled(True)
        self.posSpinBox.setEnabled(True)
        self.unitComboBox.setEnabled(True)
        self.posSlider.setEnabled(True)
        self.softRampChk.setEnabled(True)

    def set_status_message(self, text: str = ''):
        """ set the message that is displayed on the motor control label """
        self.statusLabel.setText(text)

    def setupUI(self):
        self.setObjectName(u"magnetControl")
        self.setGeometry(QRect(10, 0, 291, 191))
        font = QFont()
        font.setFamily(u"Segoe UI")
        font.setPointSize(8)
        self.setFont(font)
        self.jogUpBtn = QPushButton(self)
        self.jogUpBtn.setObjectName(u"jogUpBtn")
        self.jogUpBtn.setGeometry(QRect(10, 20, 71, 23))
        self.jogUpBtn.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
        icon = QIcon()
        path = pathlib.Path(__file__).parent.absolute().resolve()
        icon.addFile(f"{path}/../qt/up.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.jogUpBtn.setIcon(icon)
        self.jogDownBtn = QPushButton(self)
        self.jogDownBtn.setObjectName(u"jogDownBtn")
        self.jogDownBtn.setGeometry(QRect(10, 50, 71, 23))
        icon1 = QIcon()
        icon1.addFile(f"{path}/../qt/down.svg", QSize(), QIcon.Mode.Normal, QIcon.State.Off)
        self.jogDownBtn.setIcon(icon1)
        self.stopBtn = QPushButton(self)
        self.stopBtn.setObjectName(u"stopBtn")
        self.stopBtn.setGeometry(QRect(10, 80, 71, 23))
        self.referenceBtn = QPushButton(self)
        self.referenceBtn.setObjectName(u"referenceBtn")
        self.referenceBtn.setGeometry(QRect(10, 130, 71, 23))
        self.lamp = LightWidget(self)
        self.lamp.setObjectName(u"lamp")
        self.lamp.setGeometry(QRect(120, 160, 21, 21))
        self.softRampChk = QCheckBox(self)
        self.softRampChk.setObjectName(u"softRampChk")
        self.softRampChk.setGeometry(QRect(10, 110, 75, 17))
        self.softRampChk.setChecked(True)
        self.groupBox_2 = QGroupBox(self)
        self.groupBox_2.setObjectName(u"groupBox_2")
        self.groupBox_2.setGeometry(QRect(120, 20, 161, 80))
        self.goBtn = QPushButton(self.groupBox_2)
        self.goBtn.setObjectName(u"goBtn")
        self.goBtn.setGeometry(QRect(120, 20, 31, 23))
        self.posSlider = QSlider(self.groupBox_2)
        self.posSlider.setObjectName(u"posSlider")
        self.posSlider.setGeometry(QRect(10, 50, 141, 22))
        self.posSlider.setMaximum(50000)
        self.posSlider.setTracking(True)
        self.posSlider.setOrientation(Qt.Orientation.Horizontal)
        self.posSlider.setTickPosition(QSlider.TickPosition.TicksAbove)
        self.posSlider.setTickInterval(1000)
        self.posSpinBox = QDoubleSpinBox(self.groupBox_2)
        self.posSpinBox.setObjectName(u"posSpinBox")
        self.posSpinBox.setGeometry(QRect(10, 20, 41, 21))
        self.posSpinBox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.posSpinBox.setAccelerated(False)
        self.posSpinBox.setDecimals(0)
        self.posSpinBox.setMaximum(50000.000000000000000)
        self.unitComboBox = QComboBox(self.groupBox_2)
        self.unitComboBox.addItem("")
        self.unitComboBox.addItem("")
        self.unitComboBox.addItem("")
        self.unitComboBox.setObjectName(u"unitComboBox")
        self.unitComboBox.setGeometry(QRect(60, 20, 51, 23))
        self.statusLabel = QLabel(self)
        self.statusLabel.setObjectName(u"statusLabel")
        self.statusLabel.setGeometry(QRect(150, 160, 131, 21))
        self.statusLabel.setFrameShape(QFrame.Shape.Box)
        self.statusLabel.setFrameShadow(QFrame.Shadow.Plain)
        self.speedSlider = QSlider(self)
        self.speedSlider.setObjectName(u"speedSlider")
        self.speedSlider.setGeometry(QRect(130, 120, 91, 22))
        self.speedSlider.setMinimum(0)
        self.speedSlider.setMaximum(120)
        self.speedSlider.setPageStep(10)
        self.speedSlider.setValue(30)
        self.speedSlider.setOrientation(Qt.Orientation.Horizontal)
        self.speedSlider.setInvertedAppearance(False)
        self.speedSlider.setInvertedControls(False)
        self.speedSlider.setTickPosition(QSlider.TickPosition.TicksAbove)
        self.label = QLabel(self)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(130, 100, 71, 16))
        self.speedSpinBox = QDoubleSpinBox(self)
        self.speedSpinBox.setObjectName(u"speedSpinBox")
        self.speedSpinBox.setGeometry(QRect(230, 120, 41, 21))
        self.speedSpinBox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.speedSpinBox.setAccelerated(False)
        self.speedSpinBox.setDecimals(2)
        self.speedSpinBox.setMinimum(0.000000000000000)
        self.speedSpinBox.setMaximum(12.500000000000000)
        self.speedSpinBox.setValue(3.000000000000000)

        self.retranslateUi()
    
    def retranslateUi(self):
        self.setTitle(QCoreApplication.translate("ctl_widget", u"Motor Control", None))
        self.jogUpBtn.setText(QCoreApplication.translate("ctl_widget", u" Jog up   ", None))
        self.jogDownBtn.setText(QCoreApplication.translate("ctl_widget", u" Jog down", None))
        self.stopBtn.setText(QCoreApplication.translate("ctl_widget", u"STOP", None))
        self.referenceBtn.setText(QCoreApplication.translate("ctl_widget", u"Reference", None))
        self.softRampChk.setText(QCoreApplication.translate("ctl_widget", u"Soft Ramp", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("ctl_widget", u"Manual Positioning", None))
        self.goBtn.setText(QCoreApplication.translate("ctl_widget", u"Go", None))
        self.unitComboBox.setItemText(0, QCoreApplication.translate("ctl_widget", u"mm", None))
        self.unitComboBox.setItemText(1, QCoreApplication.translate("ctl_widget", u"steps", None))
        self.unitComboBox.setItemText(2, QCoreApplication.translate("ctl_widget", u"mT", None))
        self.label.setText(QCoreApplication.translate("ctl_widget", u"Speed (mm/s):", None))

        self.statusLabel.setText("")

