#!/usr/bin/env python
#
# calview.py
#
# View calibration points for Flexi-loop
# 
# Copyright (C) 2024 by G3UKB Bob Cowdery
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#    
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#    
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#    
#  The author can be reached by email at:   
#     bob@bobcowdery.plus.com
#

# Python imports
import sys
import traceback
import logging

# PyQt5 imports
from PyQt5.QtWidgets import QMainWindow, QDialog, QApplication, QToolTip, QAbstractItemView
from PyQt5.QtGui import QPainter, QPainterPath, QColor, QPen, QFont
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QStatusBar, QTabWidget, QTableWidget, QInputDialog, QFileDialog, QFrame, QGroupBox, QMessageBox, QLabel, QSlider, QLineEdit, QTextEdit, QComboBox, QPushButton, QCheckBox, QRadioButton, QSpinBox, QAction, QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, QTableWidgetItem

# Application imports
from defs import *
from utils import *
import api

# Setpoint config dialog        
class Calview(QDialog):
    
    def __init__(self, model, msgs):
        super(Calview, self).__init__()

        # Get root logger
        self.logger = logging.getLogger('root')
        
        self.__model = model
        self.__msgs = msgs
        
        # Local vars
        self.__loop = -1
     
        # Set the back colour
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Background,QtGui.QColor(149,142,132))
        self.setPalette(palette)

        # Set the tooltip style
        QToolTip.setFont(QFont('SansSerif', 10))
        self.setStyleSheet('''QToolTip { 
                           background-color: darkgray; 
                           color: black; 
                           border: #8ad4ff solid 1px
                           }''')
        
        # Initialise the GUI
        self.__initUI()
        
        # Populate
        self.__populate()
        
    #=======================================================
    # PRIVATE
    #
    # Basic initialisation
    def __initUI(self):
        # Arrange window
        x,y,w,h = self.__model[STATE][WINDOWS][CALVIEW_WIN]
        self.setGeometry(x,y,w,h)
                         
        self.setWindowTitle('Flexi-Loop Calibration View')
        
        
    #=======================================================
    # Create all widgets
    def __populate(self):
        # Set main layout
        grid = QGridLayout()
        self.setLayout(grid)
    
        # Heading
        heading = QGroupBox('')
        headbox = QHBoxLayout()
        heading.setLayout(headbox)
        self.__looplabel = QLabel('Calibration points for loop [%d]' % self.__loop)
        headbox.addWidget(self.__looplabel)
        grid.addWidget(heading,0, 0, 1, 3)
        
        # Table area
        self.__table = QTableWidget()
        self.__table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.__table.setColumnCount(3)
        self.__table.setHorizontalHeaderLabels(('Position %', 'Freq', 'SWR',))
        grid.addWidget(self.__table, 1, 0, 1, 3)
        
        # Button area
        self.__exit = QPushButton("Close")
        self.__exit.setToolTip('Close the application')
        self.__exit.clicked.connect(self.__do_close)
        self.__exit.setMinimumHeight(20)
        grid.addWidget(self.__exit, 2, 2)     
    
    #=======================================================
    # PUBLIC
    #
    def set_loop(self, loop):
        self.__loop = loop
        self.__looplabel.setText('Calibration points for loop [%d]' % self.__loop)
        self.__populate_table()
    
    #=======================================================
    # Window events
    def closeEvent(self, event):
        self.close()

    def resizeEvent(self, event):
        # Update config
        x,y,w,h = self.__model[STATE][WINDOWS][CALVIEW_WIN]
        self.__model[STATE][WINDOWS][CALVIEW_WIN] = [x,y,event.size().width(),event.size().height()]
        pass
    
    def moveEvent(self, event):
        # Update config
        x,y,w,h = self.__model[STATE][WINDOWS][CALVIEW_WIN]
        self.__model[STATE][WINDOWS][CALVIEW_WIN] = [event.pos().x(),event.pos().y(),w,h]
        pass
    
    #=======================================================
    # User events
    def __do_close(self):
        self.close()
    
    #=======================================================
    # Helpers
    def __populate_table(self):
        key = self.__get_loop_item()
        cps = self.__model[CONFIG][CAL][key]
        if len(cps) > 0:
            row = 0
            while self.__table.rowCount() > 0:
                self.__table.removeRow(0);
    
            for item in cps[2]:
                self.__table.insertRow(row)
                self.__table.setItem(row, 0, QTableWidgetItem(self.__pos_to_percent(item[0])))
                self.__table.setItem(row, 1, QTableWidgetItem(str(item[1])))
                self.__table.setItem(row, 2, QTableWidgetItem(str(item[2])))
                row += 1
            if self.__table.rowCount() > 0:
                self.__table.selectRow(0)
        
    def __get_loop_item(self):
        if self.__loop == 1:
           item = CAL_L1
        elif self.__loop == 2:
           item = CAL_L2
        elif self.__loop == 3:
           item = CAL_L3
        else:
            # Should not happen
            self.logger.warn("Invalid loop id %d" % self.__loop)
            item = SP_L1
        return item

    def __pos_to_percent(self, pos):
        home = self.__model[CONFIG][CAL][HOME]
        maximum = self.__model[CONFIG][CAL][MAX]
        span = maximum - home
        offset = pos - home
        return str(int((offset/span)*100))
    