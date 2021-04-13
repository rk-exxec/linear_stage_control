# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'form.ui'
##
## Created by: Qt User Interface Compiler version 5.15.1
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import *
from PySide2.QtGui import *
from PySide2.QtWidgets import *

from light_widget import LightWidget


class Ui_ctl_widget(object):
    def setupUi(self, ctl_widget):
        if not ctl_widget.objectName():
            ctl_widget.setObjectName(u"ctl_widget")
        ctl_widget.resize(309, 202)
        self.magnetControl = QGroupBox(ctl_widget)
        self.magnetControl.setObjectName(u"magnetControl")
        self.magnetControl.setGeometry(QRect(10, 0, 291, 191))
        self.jogUpBtn = QPushButton(self.magnetControl)
        self.jogUpBtn.setObjectName(u"jogUpBtn")
        self.jogUpBtn.setGeometry(QRect(10, 30, 71, 23))
        self.jogUpBtn.setLayoutDirection(Qt.LeftToRight)
        icon = QIcon()
        icon.addFile(u"../../../qt_resources/qt_resources/up.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.jogUpBtn.setIcon(icon)
        self.jogDownBtn = QPushButton(self.magnetControl)
        self.jogDownBtn.setObjectName(u"jogDownBtn")
        self.jogDownBtn.setGeometry(QRect(10, 60, 71, 23))
        icon1 = QIcon()
        icon1.addFile(u"../../../qt_resources/qt_resources/down.svg", QSize(), QIcon.Normal, QIcon.Off)
        self.jogDownBtn.setIcon(icon1)
        self.stopBtn = QPushButton(self.magnetControl)
        self.stopBtn.setObjectName(u"stopBtn")
        self.stopBtn.setGeometry(QRect(10, 90, 71, 23))
        self.pushButton_12 = QPushButton(self.magnetControl)
        self.pushButton_12.setObjectName(u"pushButton_12")
        self.pushButton_12.setGeometry(QRect(10, 160, 71, 23))
        self.referenceBtn = QPushButton(self.magnetControl)
        self.referenceBtn.setObjectName(u"referenceBtn")
        self.referenceBtn.setGeometry(QRect(10, 130, 71, 23))
        self.lamp = LightWidget(self.magnetControl)
        self.lamp.setObjectName(u"lamp")
        self.lamp.setGeometry(QRect(120, 160, 21, 21))
        self.softRampChk = QCheckBox(self.magnetControl)
        self.softRampChk.setObjectName(u"softRampChk")
        self.softRampChk.setGeometry(QRect(210, 110, 70, 17))
        self.softRampChk.setChecked(False)
        self.groupBox_2 = QGroupBox(self.magnetControl)
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
        self.unitComboBox.addItem("")
        self.unitComboBox.setObjectName(u"unitComboBox")
        self.unitComboBox.setGeometry(QRect(60, 20, 51, 23))
        self.statusLabel = QLabel(self.magnetControl)
        self.statusLabel.setObjectName(u"statusLabel")
        self.statusLabel.setGeometry(QRect(150, 160, 131, 21))

        self.retranslateUi(ctl_widget)

        QMetaObject.connectSlotsByName(ctl_widget)
    # setupUi

    def retranslateUi(self, ctl_widget):
        ctl_widget.setWindowTitle(QCoreApplication.translate("ctl_widget", u"ctl_widget", None))
        self.magnetControl.setTitle(QCoreApplication.translate("ctl_widget", u"Motor Control", None))
        self.jogUpBtn.setText(QCoreApplication.translate("ctl_widget", u" Jog up   ", None))
        self.jogDownBtn.setText(QCoreApplication.translate("ctl_widget", u" Jog down", None))
        self.stopBtn.setText(QCoreApplication.translate("ctl_widget", u"STOP", None))
        self.pushButton_12.setText(QCoreApplication.translate("ctl_widget", u"Cal. B-Field", None))
        self.referenceBtn.setText(QCoreApplication.translate("ctl_widget", u"Reference", None))
        self.softRampChk.setText(QCoreApplication.translate("ctl_widget", u"Soft Ramp", None))
        self.groupBox_2.setTitle(QCoreApplication.translate("ctl_widget", u"Manual Positioning", None))
        self.goBtn.setText(QCoreApplication.translate("ctl_widget", u"Go", None))
        self.unitComboBox.setItemText(0, QCoreApplication.translate("ctl_widget", u"steps", None))
        self.unitComboBox.setItemText(1, QCoreApplication.translate("ctl_widget", u"mm", None))
        self.unitComboBox.setItemText(2, QCoreApplication.translate("ctl_widget", u"mT", None))

        self.statusLabel.setText("")
    # retranslateUi

