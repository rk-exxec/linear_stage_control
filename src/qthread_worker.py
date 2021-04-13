
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

from PySide2.QtCore import QThread,Slot

class Worker(QThread):
    """executes function in qthread
    """
    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()
        self.args = args
        self.kwargs = kwargs
        self.fn = fn

    @Slot()
    def run(self):
        self.fn(*self.args, **self.kwargs)


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