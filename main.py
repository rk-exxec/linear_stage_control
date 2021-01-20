#     this file provides gui functionality for lt_control
#     Copyright (C) 2020  Raphael Kriegl

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
import time
import sys
from enum import Enum, auto

from PySide2.QtCore import QCoreApplication, QRect, QSize, QTimer, Signal, Slot, Qt, QThread
from PySide2.QtGui import QIcon, QPaintEvent, QPainter, QShowEvent
from PySide2.QtWidgets import QAbstractSpinBox, QApplication, QCheckBox, QComboBox, QDoubleSpinBox, QGroupBox, QLabel, QMainWindow, QMessageBox, QPushButton, QSlider, QWidget

from lt_control import LT

class WaitMovementThread(QThread):
    """ Thread with callback function on exit """
    def __init__(self, target, slotOnFinished=None):
        super(WaitMovementThread, self).__init__()
        self.target = target
        if slotOnFinished:
            self.finished.connect(slotOnFinished)

    def run(self, *args, **kwargs):
        self.target(*args, **kwargs)

class CustomCallbackTimer(QTimer):
    """ Timer with custom callback function """
    def __init__(self, target, interval=500):
        super(CustomCallbackTimer, self).__init__()
        self.setInterval(interval)
        self.setSingleShot(False)
        self.timeout.connect(target)

class LightColor(Enum):
    RED = auto() #Qt.red
    GREEN = auto() #Qt.green
    ERROR = auto() #Qt.darkRed
    YELLOW = auto() #Qt.yellow
    OFF = auto()

class LightWidget(QWidget):
    """ a widget that displays a colored circle in the colors defined by LightEnum """
    def __init__(self, parent=None):
        super(LightWidget, self).__init__(parent)
        self._color = LightColor.OFF

    def set_red(self):
        self._color = LightColor.RED
        self.update()

    def set_green(self):
        self._color = LightColor.GREEN
        self.update()

    def set_error(self):
        self._color = LightColor.ERROR
        self.update()

    def set_yellow(self):
        self._color = LightColor.YELLOW
        self.update()

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        if self._color == LightColor.RED:
            painter.setBrush(Qt.red)
        elif self._color == LightColor.GREEN:
            painter.setBrush(Qt.green)
        elif self._color == LightColor.ERROR:
            painter.setBrush(Qt.darkRed)
        elif self._color == LightColor.YELLOW:
            painter.setBrush(Qt.yellow)
        else:
            painter.setBrush(Qt.gray)
        painter.drawEllipse(2,2,self.width()-4, self.height()-4)
        painter.end()


class StageControl(QMainWindow):
    """
    A widget to control the motor via lt_control
    """
    def __init__(self, parent=None) -> None:
        super(StageControl, self).__init__(parent)
        self._lt_ctl = LT()
        self.workerThread = QThread(self)
        #self: Ui_stage_ctl = self.window().ui
        self.setCentralWidget(QWidget(self))
        self.setupUi(self.centralWidget())
        self._shown = False
        self._mov_dist: float = 0
        self._mov_unit: str = 'steps'
        self._old_unit: str = 'steps'
        self._invalid = False
        self.wait_movement_thread = WaitMovementThread(self.wait_movement, self.finished_moving)
        self.update_pos_timer = CustomCallbackTimer(self.update_pos, 250)

    def __del__(self):
        #self._lt_ctl.close()
        del self._lt_ctl

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
            try:
                self.load_calib_file('./MagnetCalibration.csv')
                #self.unlock_mag_unit()
            except Exception as ex:
                self.lock_mag_unit()
            self._shown = True

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
        with self._lt_ctl:
            try:
                if not self._lt_ctl.is_referenced():
                    self.lamp.set_yellow()
                    self.set_status_message('Referencing needed!')
                    self.unlock_movement_buttons()
                    self.lock_abs_pos_buttons()
                else:
                    self.lamp.set_green()
                    self.set_status_message('')
                    self.unlock_movement_buttons()
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
                self.posSpinBox.setValue(self._lt_ctl.steps_to_mm(self.posSpinBox.value()))
            elif self._old_unit == 'mT':
                #/1000 bc interpolation works with tesla, while we work with mT
                self.posSpinBox.setValue(self.mag_to_mm_interp(self.posSpinBox.value()/1000))
        elif unit == 'steps':
            self.posSlider.setMaximum(50000)
            self.posSlider.setTickInterval(1000)
            self.posSpinBox.setDecimals(0)
            if self._old_unit == 'mm':
                self.posSpinBox.setValue(self._lt_ctl.mm_to_steps(self.posSpinBox.value()))
            elif self._old_unit == 'mT':
                self.posSpinBox.setValue(self._lt_ctl.mm_to_steps(self.mag_to_mm_interp(self.posSpinBox.value()/1000)))
        elif unit == 'mT':
            self.posSlider.setMaximum(max(self._calibration_table['Field(T)'])*1000)
            self.posSlider.setTickInterval(10)
            self.posSpinBox.setDecimals(0)
            if self._old_unit == 'mm':
                self.posSpinBox.setValue(self.mm_to_mag_interp(self.posSpinBox.value())*1000)
            elif self._old_unit == 'steps':
                self.posSpinBox.setValue(self.mm_to_mag_interp(self._lt_ctl.steps_to_mm(self.posSpinBox.value()))*1000)

        self._old_unit = self._mov_unit

    @Slot(float)
    def spin_box_val_changed(self, value: float):
        """ update internal variable and slider if spin box value changed """
        if self.unitComboBox.currentText() == 'steps':
            self._mov_dist = int(value)
            self.posSlider.setValue(int(value))
        elif self.unitComboBox.currentText() == 'mm':
            self._mov_dist = value
            self.posSlider.setValue(int(value*100))
        elif self.unitComboBox.currentText() == 'mT':
            self._mov_dist = value
            self.posSlider.setValue(int(value))

    @Slot(int)
    def slider_moved(self, value: int):
        """ update spin box if slider moved """
        if self.unitComboBox.currentText() == 'steps':
            self.posSpinBox.setValue(float(value))
        elif self.unitComboBox.currentText() == 'mm':
            self.posSpinBox.setValue(float(value/100))
        elif self.unitComboBox.currentText() == 'mT':
            self.posSpinBox.setValue(float(value))

    @Slot(int)
    @OnlyIfPortActive
    def change_ramp_type(self, state: Qt.CheckState):
        """ set motor brake and accel ramp on check changed """
        if state == Qt.Checked:
            with self._lt_ctl:
                self._lt_ctl.set_soft_ramp()
        elif state == Qt.Unchecked:
            with self._lt_ctl:
                self._lt_ctl.set_quick_ramp()
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
        with self._lt_ctl:
            if self._mov_unit == 'steps':
                return self._lt_ctl.get_position()
            elif self._mov_unit == 'mm':
                return self._lt_ctl.steps_to_mm(self._lt_ctl.get_position())
            elif self._mov_unit == 'mT':
                return self.mm_to_mag_interp(self._lt_ctl.steps_to_mm(self._lt_ctl.get_position()))*1000

    @Slot()
    def jog_up_start(self):
        """ start motor movement away from motor """
        with self._lt_ctl:
            self._lt_ctl.move_inf_start(0)
        self.update_pos_timer.start()

    @Slot()
    def jog_down_start(self):
        """ start motor movement towards motor """
        with self._lt_ctl:
            self._lt_ctl.move_inf_start(1)
        self.update_pos_timer.start()

    @Slot()
    def move_pos(self):
        """ move motor to specified position """
        with self._lt_ctl:
            if self._mov_unit == 'mm':
                self._lt_ctl.move_absolute_mm(self._mov_dist)
            elif self._mov_unit == 'steps':
                self._lt_ctl.move_absolute(int(self._mov_dist))
            elif self._mov_unit == 'mT':
                self._lt_ctl.move_absolute_mm(self.mag_to_mm_interp(self._mov_dist/1000))
        self.lock_movement_buttons()
        self.wait_movement_thread.start()

    @Slot()
    def motor_stop(self):
        """ stop motor immediately"""
        with self._lt_ctl:
            self._lt_ctl.stop()
        if self.update_pos_timer.isActive():
            self.update_pos_timer.stop()
        self.update_pos()
        self.update_motor_status()

    @Slot()
    def motor_stop_soft(self):
        """ stops motor with brake ramp """
        with self._lt_ctl:
            self._lt_ctl.stop_soft()
        if self.update_pos_timer.isActive():
            self.update_pos_timer.stop()
        self.lock_movement_buttons()
        self.wait_movement_thread.start()

    def wait_movement(self):
        """ wait unitl movement stops """
        with self._lt_ctl:
            self._lt_ctl.wait_movement()

    def finished_moving(self):
        """ update ui position displays when movement finishes """
        # callback for when the motor stops moving (only absolute and relative, and jogging with soft stop)
        self.update_pos()
        self.update_motor_status()

    @Slot()
    def reference(self):
        """ execute referencing process """
        self.lamp.set_yellow()
        with self._lt_ctl:
            self._lt_ctl.do_referencing()
        self.lock_movement_buttons()
        self.wait_movement_thread.start()

    def is_driver_ready(self) -> bool:
        """ check if the motor drive is ready for movement """
        with self._lt_ctl:
            return self._lt_ctl.test_connection()

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

    def setupUi(self, main):
        if not self.objectName():
            self.setObjectName(u"ctl")
        self.resize(309, 178)
        self.stageControl = QGroupBox(main)
        self.stageControl.setGeometry(QRect(10, 10, 291, 161))
        self.stageControl.setObjectName(u"stageControl")
        self.jogUpBtn = QPushButton(self.stageControl)
        self.jogUpBtn.setObjectName(u"jogUpBtn")
        self.jogUpBtn.setGeometry(QRect(10, 30, 71, 23))
        self.jogUpBtn.setLayoutDirection(Qt.LeftToRight)
        icon = QIcon()
        icon.addFile(u"qt_resources/up.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.jogUpBtn.setIcon(icon)
        self.jogDownBtn = QPushButton(self.stageControl)
        self.jogDownBtn.setObjectName(u"jogDownBtn")
        self.jogDownBtn.setGeometry(QRect(10, 60, 71, 23))
        icon1 = QIcon()
        icon1.addFile(u"qt_resources/down.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.jogDownBtn.setIcon(icon1)
        self.stopBtn = QPushButton(self.stageControl)
        self.stopBtn.setObjectName(u"stopBtn")
        self.stopBtn.setGeometry(QRect(10, 90, 71, 23))
        self.referenceBtn = QPushButton(self.stageControl)
        self.referenceBtn.setObjectName(u"referenceBtn")
        self.referenceBtn.setGeometry(QRect(10, 130, 71, 23))
        self.lamp = LightWidget(self.stageControl)
        self.lamp.setObjectName(u"lamp")
        self.lamp.setGeometry(QRect(120, 130, 21, 21))
        self.softRampChk = QCheckBox(self.stageControl)
        self.softRampChk.setObjectName(u"softRampChk")
        self.softRampChk.setGeometry(QRect(210, 110, 70, 17))
        self.softRampChk.setChecked(False)
        self.groupBox_2 = QGroupBox(self.stageControl)
        self.groupBox_2.setObjectName(u"groupBox_2")
        self.groupBox_2.setGeometry(QRect(120, 30, 161, 80))
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
        self.unitComboBox.setObjectName(u"unitComboBox")
        self.unitComboBox.setGeometry(QRect(60, 20, 51, 23))
        self.statusLabel = QLabel(self.stageControl)
        self.statusLabel.setObjectName(u"statusLabel")
        self.statusLabel.setGeometry(QRect(150, 130, 131, 21))

        self.retranslateUi()
    # setupUi

    def retranslateUi(self):
        self.setWindowTitle(QCoreApplication.translate("ctl", u"Stage Control", None))
        self.stageControl.setTitle(QCoreApplication.translate("ctl", u"Motor Control", None))
        self.jogUpBtn.setText(QCoreApplication.translate("ctl", u" Jog up   ", None))
        self.jogDownBtn.setText(QCoreApplication.translate("ctl", u" Jog down", None))
        self.stopBtn.setText(QCoreApplication.translate("ctl", u"STOP", None))
        self.referenceBtn.setText(QCoreApplication.translate("ctl", u"Reference", None))
        self.softRampChk.setText(QCoreApplication.translate("ctl", u"Soft Ramp", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("ctl", u"Manual Positioning", None))
        self.goBtn.setText(QCoreApplication.translate("ctl", u"Go", None))
        self.unitComboBox.setItemText(0, QCoreApplication.translate("ctl", u"steps", None))
        self.unitComboBox.setItemText(1, QCoreApplication.translate("ctl", u"mm", None))

        self.statusLabel.setText("")

if __name__ == "__main__":
    # init application
    app = QApplication(sys.argv)
    widget = StageControl()
    widget.show()
    # execute qt main loop
    sys.exit(app.exec_())