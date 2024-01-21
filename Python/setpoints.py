#!/usr/bin/env python
#
# setpoints.py
#
# Setpoint dialog for Flexi-loop
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
class Setpoint(QDialog):
    
    def __init__(self, model, msgs):
        super(Setpoint, self).__init__()

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
        x,y,w,h = self.__model[STATE][WINDOWS][SETPOINT_WIN]
        self.setGeometry(x,y,w,h)
                         
        self.setWindowTitle('Flexi-Loop Setpoint Management')
        
        # Start idle processing
        QtCore.QTimer.singleShot(IDLE_TICKER, self.__idleProcessing)
        
    #=======================================================
    # Create all widgets
    def __populate(self):
        #=======================================================
           
        # Set main layout
        grid = QGridLayout()
        self.setLayout(grid)
    
        # Heading
        heading = QGroupBox('')
        headbox = QHBoxLayout()
        heading.setLayout(headbox)
        self.__looplabel = QLabel('Setpoints for loop [%d]' % self.__loop)
        headbox.addWidget(self.__looplabel)
        grid.addWidget(heading,0, 0, 1, 3)
        
        # Table area
        self.__table = QTableWidget()
        self.__table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.__table.setColumnCount(4)
        self.__table.setHorizontalHeaderLabels(('Name','Freq','SWR','Position'))
        grid.addWidget(self.__table, 1, 0, 1, 3)
        self.__table.currentItemChanged.connect(self.__row_click)
        self.__table.doubleClicked.connect(self.__row_double_click)
        
        # Button area
        self.__moveto = QPushButton("Move to")
        self.__moveto.setToolTip('Move to selected setpoint')
        self.__moveto.clicked.connect(self.__do_moveto)
        self.__moveto.setMinimumHeight(20)
        grid.addWidget(self.__moveto, 2, 0)
        
        self.__remove = QPushButton("Remove")
        self.__remove.setToolTip('Remove selected setpoint')
        self.__remove.clicked.connect(self.__do_remove)
        self.__remove.setMinimumHeight(20)
        grid.addWidget(self.__remove, 2, 1)
        
        self.__exit = QPushButton("Close")
        self.__exit.setToolTip('Close the application')
        self.__exit.clicked.connect(self.__do_close)
        self.__exit.setMinimumHeight(20)
        grid.addWidget(self.__exit, 2, 2)     
        
        # New entry area
        new_entry = QGroupBox('New')
        hbox = QHBoxLayout()
        new_entry.setLayout(hbox)
        
        namelabel = QLabel('Name')
        hbox.addWidget(namelabel)
        self.__nametxt = QLineEdit()
        self.__nametxt.setToolTip('Name the setpoint')
        self.__nametxt.setMaximumWidth(80)
        hbox.addWidget(self.__nametxt)

        freqlabel = QLabel('Freq')
        hbox.addWidget(freqlabel)
        self.__freqtxt = QLineEdit()
        self.__freqtxt.setToolTip('Record frequency')
        self.__freqtxt.setInputMask('000.000;0')
        self.__freqtxt.setMaximumWidth(80)
        hbox.addWidget(self.__freqtxt)
        
        swrlabel = QLabel('SWR')
        hbox.addWidget(swrlabel)
        self.__swrtxt = QLineEdit()
        self.__swrtxt.setToolTip('Record SWR')
        self.__swrtxt.setInputMask('0.0;0')
        self.__swrtxt.setMaximumWidth(80)
        hbox.addWidget(self.__swrtxt)
        
        self.__add = QPushButton("Add")
        self.__add.setToolTip('Add new setpoint')
        self.__add.clicked.connect(self.__do_add)
        self.__add.setMinimumHeight(20)
        hbox.addWidget(self.__add)
        
        grid.addWidget(new_entry, 3, 0, 1, 3)
    
    #=======================================================
    # PUBLIC
    #
    def set_loop(self, loop):
        self.__loop = loop
        self.__looplabel.setText('Setpoints for loop [%d]' % self.__loop)
        self.__populate_table()
    
    #=======================================================
    # Window events
    def closeEvent(self, event):
        self.close()

    def resizeEvent(self, event):
        # Update config
        x,y,w,h = self.__model[STATE][WINDOWS][SETPOINT_WIN]
        self.__model[STATE][WINDOWS][SETPOINT_WIN] = [x,y,event.size().width(),event.size().height()]
        
    def moveEvent(self, event):
        # Update config
        x,y,w,h = self.__model[STATE][WINDOWS][SETPOINT_WIN]
        self.__model[STATE][WINDOWS][SETPOINT_WIN] = [event.pos().x(),event.pos().y(),w,h]
        
    #=======================================================
    # User events
    def __do_close(self):
        self.close()

    def __row_click(self):
        pass
    
    def __row_double_click(self):
        pass
    
    def __do_moveto(self):
        pass
    
    def __do_remove(self):
        r = self.__table.currentRow()
        if r != -1:
            name = self.__table.item(r, 0).text()
            sps = self.__model[CONFIG][SETPOINTS][self.__get_loop_item()]
            del sps[name]
            self.__table.removeRow(r);
            self.__populate_table()
    
    def __do_add(self):
        # Get data
        name = self.__nametxt.text()
        freq = self.__freqtxt.text()
        swr = self.__swrtxt.text()
        pos = self.__model[STATE][ARDUINO][ACT_POS]
        if pos != -1:
            # Create new row
            rowPosition = self.__table.rowCount()
            self.__table.insertRow(rowPosition)
            self.__table.setItem(rowPosition, 0, QTableWidgetItem(name))
            self.__table.setItem(rowPosition, 1, QTableWidgetItem(freq))
            self.__table.setItem(rowPosition, 2, QTableWidgetItem(swr))
            self.__table.setItem(rowPosition, 3, QTableWidgetItem(str(pos)))
            # Manage model
            self.__update_model()
        else:
            self.logger.warn("No loop position available for add()")
    
    #=======================================================
    # Helpers
    def __populate_table(self):
        key = self.__get_loop_item()
        sps = self.__model[CONFIG][SETPOINTS][key]
        row = 0
        while self.__table.rowCount() > 0:
            self.__table.removeRow(0);

        for item in sps.items():
            self.__table.insertRow(row)
            self.__table.setItem(row, 0, QTableWidgetItem(item[0]))
            self.__table.setItem(row, 1, QTableWidgetItem(item[1][0]))
            self.__table.setItem(row, 2, QTableWidgetItem(item[1][1]))
            self.__table.setItem(row, 3, QTableWidgetItem(item[1][2]))
            row += 1
        if self.__table.rowCount() > 0:
            self.__table.selectRow(0)
        
    def __update_model(self):
        item = self.__get_loop_item()    
        self.__model[CONFIG][SETPOINTS][item].clear()    
        for r in range(0, self.__table.rowCount()):
            name = self.__table.item(r, 0).text()
            freq = self.__table.item(r, 1).text()
            swr = self.__table.item(r, 2).text() 
            pos = self.__table.item(r, 3).text()
            self.__model[CONFIG][SETPOINTS][item][name] = [freq, swr, pos]
            
    def __get_loop_item(self):
        if self.__loop == 1:
           item = SP_L1
        elif self.__loop == 2:
           item = SP_L2
        elif self.__loop == 3:
           item = SP_L3
        else:
            # Should not happen
            self.logger.warn("Invalid loop id %d" % self.__loop)
            item = SP_L1
        return item
    
    #=======================================================
    # Idle time
    def __idleProcessing(self):
        QtCore.QTimer.singleShot(IDLE_TICKER, self.__idleProcessing)
        
        if len(self.__nametxt.text()) > 0 and len(self.__freqtxt.text()) and len(self.__swrtxt.text()) > 0:
            self.__add.setEnabled(True)
        else:
            self.__add.setEnabled(False)
            
        r = self.__table.currentRow()
        if r == -1:
            # No row selected
            self.__moveto.setEnabled(False)
            self.__remove.setEnabled(False)
        else:
            self.__moveto.setEnabled(True)
            self.__remove.setEnabled(True) 
        
#=========================================================================================
'''
def __idleProcessing(self):
    QtCore.QTimer.singleShot(IDLE_TICKER, self.__idleProcessing)
    
    if len(self.__nametxt.text()) > 0 and len(self.__freqtxt.text()) > 0:
        self.__nametxt.setEnabled(True)
        self.__freqtxt.setEnabled(True)
        
def __do_add_mem(self):
    # Get data
    name = self.__nametxt.text()
    freq = self.__freqtxt.text()
    low,high,tx,ant = self.__settings()
    if low: ind = 'low-range'
    else: ind = 'high-range'
    # Create new row
    rowPosition = self.__table.rowCount()
    self.__table.insertRow(rowPosition)
    self.__table.setItem(rowPosition, 0, QTableWidgetItem(name))
    self.__table.setItem(rowPosition, 1, QTableWidgetItem(freq))
    self.__table.setItem(rowPosition, 2, QTableWidgetItem(ind))
    self.__table.setItem(rowPosition, 3, QTableWidgetItem(str(tx)))
    self.__table.setItem(rowPosition, 4, QTableWidgetItem(str(ant)))
    # Add to model
    self.__update_model()

def __do_update_mem(self):
    # Get data
    name = self.__nametxt.text()
    freq = self.__freqtxt.text()
    low,high,tx,ant = self.__settings()
    if low: ind = 'low-range'
    else: ind = 'high-range'
    # Update row
    rowPosition = self.__table.currentRow()
    self.__table.setItem(rowPosition, 0, QTableWidgetItem(name))
    self.__table.setItem(rowPosition, 1, QTableWidgetItem(freq))
    self.__table.setItem(rowPosition, 2, QTableWidgetItem(ind))
    self.__table.setItem(rowPosition, 3, QTableWidgetItem(str(tx)))
    self.__table.setItem(rowPosition, 4, QTableWidgetItem(str(ant)))
    # Update model
    self.__update_model()
    
def __do_run_mem(self):
    r = self.__table.currentRow()
    ind = self.__table.item(r, 2).text()
    tx = self.__table.item(r, 3).text()
    ant = self.__table.item(r, 4).text()
    # Execute tuner commands
    self.__callback(ind, tx, ant)
        
def __do_remove_mem(self):
    r = self.__table.currentRow()
    self.__table.removeRow(r)
    # Remove from model
    self.__update_model()

def __row_click(self):
    r = self.__table.currentRow()
    if r != -1:
        self.__nametxt.setText(self.__table.item(r, 0).text())
        self.__freqtxt.setText(self.__table.item(r, 1).text())
    
def __row_double_click(self):
    self.__do_run_mem
    
def __do_save(self):
    # Save model
    persist.saveCfg(CONFIG_PATH, self.__model)
    # and hide window
    self.hide()
'''