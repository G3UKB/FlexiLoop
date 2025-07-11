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
from qt_inc import *

# Application imports
from defs import *
from utils import *
import api

# Setpoint config dialog        
class Calview(QDialog):
    
    def __init__(self, model, callback, msgs):
        super(Calview, self).__init__()

        # Get root logger
        self.logger = logging.getLogger('root')
        
        # Parameters
        self.__model = model
        # Callback for positioning and messages
        self.__cb = callback
        self.__msgs = msgs
        
        # Instance vars
        self.__loop = -1
        self.__pos_lookup = {}
     
        # Set the back colour
        palette = QPalette()
        palette.setColor(QPalette.Background, QColor(149,142,132))
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
        
        # Start idle processing
        QtCore.QTimer.singleShot(IDLE_LONG_TICKER, self.__idleProcessing)
        
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
        self.__moveto = QPushButton("Move to")
        self.__moveto.setToolTip('Move to selected frequency')
        self.__moveto.clicked.connect(self.__do_move)
        self.__moveto.setMinimumHeight(20)
        grid.addWidget(self.__moveto, 2, 1)
        
        self.__exit = QPushButton("Close")
        self.__exit.setToolTip('Close the application')
        self.__exit.clicked.connect(self.__do_close)
        self.__exit.setMinimumHeight(20)
        grid.addWidget(self.__exit, 2, 2)
    
    #=======================================================
    # PUBLIC
    #
    # Called to set current loop before showing dialog
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
    
    def moveEvent(self, event):
        # Update config
        x,y,w,h = self.__model[STATE][WINDOWS][CALVIEW_WIN]
        self.__model[STATE][WINDOWS][CALVIEW_WIN] = [event.pos().x(),event.pos().y(),w,h]
    
    #=======================================================
    # User events
    # Close dialog
    def __do_close(self):
        self.close()
    
    # Move to calibration point
    def __do_move(self):
        row = self.__table.currentRow()
        pos = float(self.__table.item(row, 1).text())
        if pos in self.__pos_lookup:
            abs_pos = self.__pos_lookup[pos]
            # Ask UI to move to pos
            self.__cb(abs_pos)
        else:
            self.logger.warn("Failed to lookup [{}] in lookup table [{}]".format(pos, self.__pos_lookup))
            
    #=======================================================
    # Helpers
    # Populate the table from model data for current loop
    def __populate_table(self):
        # Clear table
        row = 0
        while self.__table.rowCount() > 0:
            self.__table.removeRow(0);
        # Populate
        key = self.__get_loop_item()
        points = self.__model[CONFIG][CAL][key]
        for point in reversed(points):
            self.__table.insertRow(row)
            self.__table.setItem(row, 0, QTableWidgetItem(str(analog_pos_to_percent(self.__model, point[0]))))
            self.__table.setItem(row, 1, QTableWidgetItem(str(point[1])))
            self.__table.setItem(row, 2, QTableWidgetItem(str(point[2])))
            # Add to dict
            self.__pos_lookup[analog_pos_to_percent(self.__model, point[0])] = point[0] 
            row += 1
        if self.__table.rowCount() > 0:
            self.__table.selectRow(0)
        
    # Get key for loop    
    def __get_loop_item(self):
        if self.__loop == 1:
           item = CAL_L1
        elif self.__loop == 2:
           item = CAL_L2
        elif self.__loop == 3:
           item = CAL_L3
        else:
            # Should not happen
            self.logger.warn("Invalid loop id {}".format(self.__loop))
            item = CAL_L1
        return item

    
    # =======================================================
    # Background activities
    def __idleProcessing(self):
         
        # Adjust buttons       
        r = self.__table.currentRow()
        if r == -1 or not self.__model[STATE][ARDUINO][ONLINE]:
            # No row selected
            self.__moveto.setEnabled(False)
        else:
            self.__moveto.setEnabled(True) 
        
        # Reset timer    
        QtCore.QTimer.singleShot(IDLE_LONG_TICKER, self.__idleProcessing)
        