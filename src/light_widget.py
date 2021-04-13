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

from enum import Enum, auto
from PySide2.QtWidgets import QWidget
from PySide2.QtCore import Signal, Slot, Qt
from PySide2.QtGui import QPaintEvent, QPainter
 
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
