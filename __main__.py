#     Linear Stage Control is a program to control a single linear table via SMCI33-1
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

import sys

from PySide6.QtCore import QFile
from PySide6.QtWidgets import QMainWindow, QApplication
from PySide6.QtUiTools import QUiLoader



from ls_control import LinearStageControlGUI


def load_ui(ui_file, parent=None):
    loader = QUiLoader()
    file = QFile(ui_file)
    file.open(QFile.ReadOnly)
    myWidget = loader.load(file, None)
    myWidget.show()
    file.close()
    myWidget.show()
    return myWidget

if __name__ == "__main__":
    # init application
    app = QApplication(sys.argv)
    widget = QMainWindow()
    widget.setWindowTitle("Linear Stage Control")
    widget.resize(309, 202)
    widget.ui = LinearStageControlGUI(widget)
    widget.show()
    # execute qt main loop
    sys.exit(app.exec())