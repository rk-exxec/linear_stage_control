#     MAEsure is a program to measure the surface energy of MAEs via contact angle
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

# TODO maybe do StageControl class and expand it with the magnet stuff??

import functools
import pathlib
import logging

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from .light_widget import LightWidget
from .ls_control import LinearStageControl

from .qthread_worker import CallbackWorker

class CustomCallbackTimer(QTimer):
    """ Timer with custom callback function """
    def __init__(self, target, interval=500):
        super(CustomCallbackTimer, self).__init__()
        self.setInterval(interval)
        self.setSingleShot(False)
        self.timeout.connect(target)

class LinearStageControlGUI(QGroupBox):
    """
    A widget to control the motor via the module `lt_control`_.

    .. seealso:: :class:`LT<lt_control.LT>`
    """
    def __init__(self, parent=None) -> None:
        super(LinearStageControlGUI, self).__init__(parent)
        self.ls_ctl = LinearStageControl()
        self.setupUI()
        self._shown = False
        self._mov_dist: float = 0
        self._mov_unit: str = 'steps'
        self._old_unit: str = 'steps'
        self._invalid = False
        self.wait_movement_thread = CallbackWorker(self.wait_movement, slotOnFinished=self.finished_moving)
        self.update_pos_timer = CustomCallbackTimer(self.update_pos, 250)
        logging.debug("initialized stage control")

    def __del__(self):
        #self._lt_ctl.close()
        del self.ls_ctl

    def connect_signals(self):
        self.jogUpBtn.pressed.connect(self.jog_up_start)
        self.jogDownBtn.pressed.connect(self.jog_down_start)
        self.jogUpBtn.released.connect(self.motor_stop_soft)
        self.jogDownBtn.released.connect(self.motor_stop_soft)
        self.referenceBtn.clicked.connect(self.reference)
        self.goBtn.clicked.connect(self.move_pos)
        self.stopBtn.clicked.connect(self.motor_stop)
        self.posSpinBox.valueChanged.connect(self.spin_box_val_changed) #lambda pos: self.magnet_ctl.set_mov_dist(int(pos)) or self.posSlider.setValue(int(pos))
        self.unitComboBox.currentTextChanged.connect(self.mag_mov_unit_changed)
        self.posSlider.sliderMoved.connect(self.slider_moved) # only fires with user input lambda pos: self.posLineEdit.setText(str(pos)) or self.posSpinBox.setValue(float(pos))
        self.softRampChk.stateChanged.connect(self.change_ramp_type)

    def OnlyIfPortActive(func):
        """ Decorator that only executes fcn if serial port is open, otherwise it fails silently """
        def null(*args, **kwargs):
            pass

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if args[0]._lt_ctl.has_connection_error():
                logging.warning("stage control: device not ready")
                return null(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        return wrapper

    def showEvent(self, event: QShowEvent):
        if not self._shown:
            self.connect_signals()
            self.update_motor_status()
            self.update_pos()
            self.change_ramp_type(self.softRampChk.isChecked())
            self._shown = True
            return True

    @OnlyIfPortActive
    def update_pos(self):
        """ update spin box with current pos"""
        try:
            pos = float(self.get_position())
        except Exception as toe:
            pos = 45100
        self.posSpinBox.setValue(pos)

    @OnlyIfPortActive
    def update_motor_status(self):
        """ Get motor status and display it """
        with self.ls_ctl:
            try:
                if not self.ls_ctl.is_referenced():
                    self.lamp.set_yellow()
                    self.set_status_message('Referencing needed!')
                    self.unlock_movement_buttons()
                    self.lock_abs_pos_buttons()
                    logging.info("stage control: no reference! locking absolute movement")
                else:
                    self.lamp.set_green()
                    self.set_status_message('')
                    self.unlock_movement_buttons()
                    logging.info("stage control: has reference! unlocking absolute movement")
                return True
            except TimeoutError as te:
                self.lamp.set_red()
                self.set_status_message('Connection Timeout!')
                self.lock_movement_buttons()
                return False

    @Slot(str)
    def mag_mov_unit_changed(self, unit: str):
        """ update slider and spin box if the movement units has changes """
        self._mov_unit = unit.strip()
        if unit == 'mm':
            self.posSlider.setMaximum(3906) #max mm are 39.0625
            self.posSlider.setTickInterval(100)
            self.posSpinBox.setDecimals(2)
            if self._old_unit == 'steps':
                self.posSpinBox.setValue(self.ls_ctl.steps_to_mm(self.posSpinBox.value()))
        elif unit == 'steps':
            self.posSlider.setMaximum(50000)
            self.posSlider.setTickInterval(1000)
            self.posSpinBox.setDecimals(0)
            if self._old_unit == 'mm':
                self.posSpinBox.setValue(self.ls_ctl.mm_to_steps(self.posSpinBox.value()))
        else:
            return
        logging.info(f"stage control: movement unit changed from {self._old_unit} to {self._mov_unit}")
        self._old_unit = self._mov_unit

    @Slot(float)
    def spin_box_val_changed(self, value: float):
        """ update internal variable and slider if spin box value changed """
        self._mov_dist = int(value)
        self.posSlider.setValue(int(value))

    @Slot(int)
    def slider_moved(self, value: int):
        """ update spin box if slider moved """
        if self.unitComboBox.currentText() == 'mm':
            self.posSpinBox.setValue(float(value/100))
        else:
            self.posSpinBox.setValue(float(value))

    @Slot(int)
    @OnlyIfPortActive
    def change_ramp_type(self, state: Qt.CheckState):
        """ set motor brake and accel ramp on check changed """
        if state == Qt.Checked:
            with self.ls_ctl:
                self.ls_ctl.set_soft_ramp()
            logging.info("stage control: set soft ramp")
        elif state == Qt.Unchecked:
            with self.ls_ctl:
                self.ls_ctl.set_quick_ramp()
                logging.info("stage control: set quick ramp")
        else:
            pass


    def do_timeout_dialog(self) -> bool:
        """ display a dialog if the connection timed out """
        msgBox = QMessageBox()
        msgBox.setText("The connection timed out")
        msgBox.setInformativeText("Could not connect ot the stepper driver!")
        msgBox.setStandardButtons(QMessageBox.Retry | QMessageBox.Abort | QMessageBox.Close)
        msgBox.setDefaultButton(QMessageBox.Retry)
        ret = msgBox.exec_()
        if ret == QMessageBox.Retry:
            return True
        elif ret == QMessageBox.Abort:
            return False
        elif ret == QMessageBox.Close:
            return False

    def get_position(self):
        """ return the motor position in the current unit """
        with self.ls_ctl:
            if self._mov_unit == 'steps':
                return self.ls_ctl.get_position()
            elif self._mov_unit == 'mm':
                return self.ls_ctl.steps_to_mm(self.ls_ctl.get_position())

    @Slot()
    def jog_up_start(self):
        """ start motor movement away from motor """
        logging.info("stage control: start jog up")
        with self.ls_ctl:
            self.ls_ctl.move_inf_start(0)
        self.update_pos_timer.start()

    @Slot()
    def jog_down_start(self):
        """ start motor movement towards motor """
        logging.info("stage control: start jog down")
        with self.ls_ctl:
            self.ls_ctl.move_inf_start(1)
        self.update_pos_timer.start()

    @Slot()
    def move_pos(self):
        """ move motor to specified position """
        with self.ls_ctl:
            if self._mov_unit == 'mm':
                self.ls_ctl.move_absolute_mm(self._mov_dist)
            elif self._mov_unit == 'steps':
                self.ls_ctl.move_absolute(int(self._mov_dist))
        self.lock_movement_buttons()
        logging.info(f"stage control: start movement to {self._mov_dist}{self._mov_unit}")
        self.wait_movement_thread.start()

    @Slot()
    def motor_stop(self):
        """ stop motor immediately"""
        with self.ls_ctl:
            self.ls_ctl.stop()
        if self.update_pos_timer.isActive():
            self.update_pos_timer.stop()
        logging.info("stage control: stop")
        self.update_pos()
        self.update_motor_status()

    @Slot()
    def motor_stop_soft(self):
        """ stops motor with brake ramp """
        with self.ls_ctl:
            self.ls_ctl.stop_soft()
        if self.update_pos_timer.isActive():
            self.update_pos_timer.stop()
        logging.info("stage control: stop")
        self.lock_movement_buttons()
        self.wait_movement_thread.start()

    def wait_movement(self):
        """ wait unitl movement stops """
        with self.ls_ctl:
            self.ls_ctl.wait_movement()

    def finished_moving(self):
        """ update ui position displays when movement finishes """
        # callback for when the motor stops moving (only absolute and relative, and jogging with soft stop)
        logging.info("stage control: reached pos")
        self.update_pos()
        self.update_motor_status()

    @Slot()
    def reference(self):
        """ execute referencing process """
        self.lamp.set_yellow()
        logging.info("stage control: referencing")
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
        self.jogUpBtn = QPushButton(self)
        self.jogUpBtn.setObjectName(u"jogUpBtn")
        self.jogUpBtn.setGeometry(QRect(10, 20, 71, 23))
        self.jogUpBtn.setLayoutDirection(Qt.LeftToRight)
        icon = QIcon()
        path = pathlib.Path(__file__).parent.absolute()
        icon.addFile(f"{path}/qt_resources/up.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.jogUpBtn.setIcon(icon)
        self.jogDownBtn = QPushButton(self)
        self.jogDownBtn.setObjectName(u"jogDownBtn")
        self.jogDownBtn.setGeometry(QRect(10, 50, 71, 23))
        icon1 = QIcon()
        icon1.addFile(f"{path}/qt_resources/down.svg", QSize(), QIcon.Normal, QIcon.Off)
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
        self.softRampChk.setGeometry(QRect(l10, 110, 70, 17))
        self.softRampChk.setChecked(False)
        self.groupBox_2 = QGroupBox(self)
        self.groupBox_2.setObjectName(u"groupBox_2")
        self.groupBox_2.setGeometry(QRect(120, 10, 161, 80))
        self.goBtn = QPushButton(self.groupBox_2)
        self.goBtn.setObjectName(u"goBtn")
        self.goBtn.setGeometry(QRect(120, 20, 31, 23))
        self.posSlider = QSlider(self.groupBox_2)
        self.posSlider.setObjectName(u"posSlider")
        self.posSlider.setGeometry(QRect(10, 50, 141, 22))
        self.posSlider.setMaximum(50000)
        self.posSlider.setTracking(True)
        self.posSlider.setOrientation(Qt.Horizontal)
        self.posSlider.setTickPosition(QSlider.TicksAbove)
        self.posSlider.setTickInterval(1000)
        self.posSpinBox = QDoubleSpinBox(self.groupBox_2)
        self.posSpinBox.setObjectName(u"posSpinBox")
        self.posSpinBox.setGeometry(QRect(10, 20, 41, 21))
        self.posSpinBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
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
        self.speedSlider = QSlider(self)
        self.speedSlider.setObjectName(u"speedSlider")
        self.speedSlider.setGeometry(QRect(130, 110, 91, 22))
        self.speedSlider.setMinimum(0)
        self.speedSlider.setMaximum(120)
        self.speedSlider.setPageStep(10)
        self.speedSlider.setValue(30)
        self.speedSlider.setOrientation(Qt.Horizontal)
        self.speedSlider.setInvertedAppearance(False)
        self.speedSlider.setInvertedControls(False)
        self.speedSlider.setTickPosition(QSlider.TicksAbove)
        self.label = QLabel(self)
        self.label.setObjectName(u"label")
        self.label.setGeometry(QRect(130, 90, 71, 16))
        self.speedSpinBox = QDoubleSpinBox(self)
        self.speedSpinBox.setObjectName(u"speedSpinBox")
        self.speedSpinBox.setGeometry(QRect(230, 110, 41, 21))
        self.speedSpinBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.speedSpinBox.setAccelerated(False)
        self.speedSpinBox.setDecimals(1)
        self.speedSpinBox.setMinimum(1.000000000000000)
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
        self.unitComboBox.setItemText(0, QCoreApplication.translate("ctl_widget", u"steps", None))
        self.unitComboBox.setItemText(1, QCoreApplication.translate("ctl_widget", u"mm", None))
        self.unitComboBox.setItemText(2, QCoreApplication.translate("ctl_widget", u"mT", None))
        self.label.setText(QCoreApplication.translate("ctl_widget", u"Speed (mm/s):", None))

        self.statusLabel.setText("")