#!/usr/bin/env python
#
# config.py
#
# Configuration for Flexi-loop
# 
# Copyright (C) 2023 by G3UKB Bob Cowdery
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
import copy

# PyQt5 imports
from PyQt5.QtWidgets import QMainWindow, QDialog, QApplication, QToolTip, QAbstractItemView
from PyQt5.QtGui import QPainter, QPainterPath, QColor, QPen, QFont
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QStatusBar, QTabWidget, QTableWidget, QInputDialog, QFileDialog, QFrame, QGroupBox, QMessageBox, QLabel, QSlider, QLineEdit, QTextEdit, QComboBox, QPushButton, QCheckBox, QRadioButton, QSpinBox, QAction, QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, QTableWidgetItem

# Application imports
from defs import *
from utils import *
import api

# Main config dialog        
class Config(QDialog):
    
    def __init__(self, model, msgs):
        super(Config, self).__init__()

        # Get root logger
        self.logger = logging.getLogger('root')
        
        self.__model = model
        self.__msgs = msgs
        
        # Local sets synced back to model on save
        # Sets are [[name, low_freq, high_freq, steps, position], [...], ...]
        self.__sets = {
            CAL_S1: copy.deepcopy(model[CONFIG][CAL][SETS][CAL_S1]),
            CAL_S2: copy.deepcopy(model[CONFIG][CAL][SETS][CAL_S2]),
            CAL_S3: copy.deepcopy(model[CONFIG][CAL][SETS][CAL_S3]),
        }
        self.__selected_loop = 1
        
        # Start idle processing
        QtCore.QTimer.singleShot(1000, self.__idleProcessing)
        
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
        self.__populate_ui()
        self.__populate_table()
        
    #=======================================================
    # PRIVATE
    #
    # Basic initialisation
    def __initUI(self):
        
        # Arrange window
        x,y,w,h = self.__model[STATE][WINDOWS][CONFIG_WIN]
        self.setGeometry(x,y,w,h)
                         
        self.setWindowTitle('Flexi-Loop Configuration')
        
    #=======================================================
    # Create all widgets
    def __populate_ui(self):
        #=======================================================
        
        # Set up the tabs
        self.top_tab_widget = QTabWidget()
           
        # Set main layout
        layout = QGridLayout()
        self.setLayout(layout)
        layout.addWidget(self.top_tab_widget, 0, 0)
        container = QWidget()
        common = QGridLayout()
        container.setLayout(common)
        layout.addWidget(container, 1, 0)
        
        # Arduino tab
        arduinotab = QWidget()
        self.top_tab_widget.addTab(arduinotab, "Arduino")
        arduinogrid = QGridLayout()
        arduinotab.setLayout(arduinogrid)
        self.__populate_arduino(arduinogrid)
        
        # Caibration tab
        calibrationab = QWidget()
        self.top_tab_widget.addTab(calibrationab, "Calibration")
        calobrationgrid = QGridLayout()
        calibrationab.setLayout(calobrationgrid)
        self.__populate_calibration(calobrationgrid)

        # Timeouts tab
        timeouttab = QWidget()
        self.top_tab_widget.addTab(timeouttab, "Timeouts")
        timeoutgrid = QGridLayout()
        timeouttab.setLayout(timeoutgrid)
        self.__populate_timeouts(timeoutgrid)
        
        # Action buttons
        self.__save = QPushButton("Save")
        self.__save.setMaximumWidth(30)
        self.__save.setToolTip('Save changes ...')
        common.addWidget(self.__save, 0, 0)
        self.__save.clicked.connect(self.__do_save)
        self.__cancel = QPushButton("Cancel")
        self.__cancel.setMaximumWidth(30)
        self.__cancel.setToolTip('Cancel changes ...')
        common.addWidget(self.__cancel, 0, 1)
        self.__cancel.clicked.connect(self.__do_cancel)
        self.__close = QPushButton("Close")
        self.__close.setMaximumWidth(30)
        self.__close.setToolTip('Close configuration')
        common.addWidget(self.__close, 0, 3)
        self.__close.clicked.connect(self.__do_close)
        
        gap = QWidget()
        common.addWidget(gap, 0, 2)
        common.setColumnStretch(2, 1)
        
    #=======================================================
    # Populate dialog
    def __populate_arduino(self, grid):
        # Serial port
        portlabel = QLabel('Arduino Port')
        grid.addWidget(portlabel, 0, 0)
        self.__serialporttxt = QLineEdit()
        self.__serialporttxt.setObjectName("dialog")
        self.__serialporttxt.setText(self.__model[CONFIG][ARDUINO][PORT])
        self.__serialporttxt.setToolTip('Set Arduino Port')
        self.__serialporttxt.setMaximumWidth(80)
        grid.addWidget(self.__serialporttxt, 0, 1)
        grid.setAlignment(QtCore.Qt.AlignLeft)
        
        slowlabel = QLabel('Slow Speed')
        grid.addWidget(slowlabel, 1, 0)
        self.__slowtxt = QSpinBox()
        self.__slowtxt.setObjectName("dialog")
        self.__slowtxt.setToolTip('Slow actuator speed')
        self.__slowtxt.setRange(0,500)
        self.__slowtxt.setValue(self.__model[CONFIG][ARDUINO][ACT_SPEED][ACT_SLOW])
        self.__slowtxt.setMinimumWidth(80)
        grid.addWidget(self.__slowtxt, 1, 1)
        
        slowlabel = QLabel('Medium Speed')
        grid.addWidget(slowlabel, 2, 0)
        self.__medtxt = QSpinBox()
        self.__medtxt.setObjectName("dialog")
        self.__medtxt.setToolTip('Medium actuator speed')
        self.__medtxt.setRange(0,500)
        self.__medtxt.setValue(self.__model[CONFIG][ARDUINO][ACT_SPEED][ACT_MED])
        self.__medtxt.setMinimumWidth(80)
        grid.addWidget(self.__medtxt, 2, 1)
        
        slowlabel = QLabel('Fast Speed')
        grid.addWidget(slowlabel, 3, 0)
        self.__fasttxt = QSpinBox()
        self.__fasttxt.setObjectName("dialog")
        self.__fasttxt.setToolTip('Fast actuator speed')
        self.__fasttxt.setRange(0,500)
        self.__fasttxt.setValue(self.__model[CONFIG][ARDUINO][ACT_SPEED][ACT_FAST])
        self.__fasttxt.setMinimumWidth(80)
        grid.addWidget(self.__fasttxt, 3, 1)
        
        # Close gaps
        grid.setRowStretch(4, 1)
        grid.setColumnStretch(4, 1)

    def __populate_calibration(self, grid):
        # Calibration data for each band covered by 
        # Loop select
        looplabel = QLabel('Select Loop')
        grid.addWidget(looplabel, 0, 0)
        self.__loop_sel = QComboBox()
        self.__loop_sel.addItem("1")
        self.__loop_sel.addItem("2")
        self.__loop_sel.addItem("3")
        self.__loop_sel.setMinimumHeight(20)
        grid.addWidget(self.__loop_sel, 0,1)
        self.__loop_sel.currentIndexChanged.connect(self.__loop_change)
        
        # Table area
        self.__table = QTableWidget()
        self.__table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.__table.setColumnCount(6)
        self.__table.setHorizontalHeaderLabels(('Name', 'LowFreq', 'PosLow', 'HighFreq', 'PosHigh', 'Steps'))
        self.__table.itemClicked.connect(self.__row_changed)
        grid.addWidget(self.__table, 1, 0, 1, 2)
        
        # Sub grid
        subgrid = QGridLayout()
        gb = QGroupBox()
        gb.setLayout(subgrid)
        grid.addWidget(gb, 2,0,1,2)

        # Name for band
        namelabel = QLabel('Name')
        subgrid.addWidget(namelabel, 0, 0)
        self.__nametxt = QLineEdit()
        self.__nametxt.setToolTip('Band bame')
        self.__nametxt.setMaximumWidth(80)
        subgrid.addWidget(self.__nametxt, 0, 1)
        
        # Lower/upper freq limit
        lowfreqlabel = QLabel('Low Freq')
        subgrid.addWidget(lowfreqlabel, 0, 2)
        self.__lowfreqtxt = QLineEdit()
        self.__lowfreqtxt.setInputMask('09.90')
        self.__lowfreqtxt.setToolTip('Low band frequency')
        self.__lowfreqtxt.setMaximumWidth(80)
        subgrid.addWidget(self.__lowfreqtxt, 0, 3)
        
        highfreqlabel = QLabel('High Freq')
        subgrid.addWidget(highfreqlabel, 0, 4)
        self.__highfreqtxt = QLineEdit()
        self.__highfreqtxt.setInputMask('09.90')
        self.__highfreqtxt.setToolTip('High band frequency')
        self.__highfreqtxt.setMaximumWidth(80)
        subgrid.addWidget(self.__highfreqtxt, 0, 5)
        
        # Number of steps
        steplabel = QLabel('Steps')
        subgrid.addWidget(steplabel, 1, 0)
        self.__steptxt = QSpinBox()
        self.__steptxt.setObjectName("dialog")
        self.__steptxt.setToolTip('Set number of calibration steps')
        self.__steptxt.setRange(0,50)
        self.__steptxt.setMinimumWidth(80)
        self.__steptxt.setValue(10)
        subgrid.addWidget(self.__steptxt, 1, 1)
        
        # Position
        poslowlabel = QLabel('PosLow%')
        subgrid.addWidget(poslowlabel, 1, 2)
        self.__poslowtxt = QSpinBox()
        self.__poslowtxt.setObjectName("dialog")
        self.__poslowtxt.setToolTip('Set actuator position for low frequency')
        self.__poslowtxt.setRange(0,100)
        self.__poslowtxt.setMinimumWidth(80)
        self.__poslowtxt.setValue(50)
        subgrid.addWidget(self.__poslowtxt, 1, 3)
        
        poshilabel = QLabel('PosHigh%')
        subgrid.addWidget(poshilabel, 1, 4)
        self.__poshitxt = QSpinBox()
        self.__poshitxt.setObjectName("dialog")
        self.__poshitxt.setToolTip('Set actuator position for high frequency')
        self.__poshitxt.setRange(0,100)
        self.__poshitxt.setMinimumWidth(80)
        self.__poshitxt.setValue(50)
        subgrid.addWidget(self.__poshitxt, 1, 5)
        
        # Button area
        # Sub grid
        subgrid1 = QGridLayout()
        gb1 = QGroupBox()
        gb1.setLayout(subgrid1)
        grid.addWidget(gb1, 3,0,1,2)

        self.__new = QPushButton("New")
        self.__new.setToolTip('Clear data')
        self.__new.clicked.connect(self.__do_new)
        self.__new.setMinimumHeight(20)
        subgrid1.addWidget(self.__new, 0, 0)
        
        self.__add = QPushButton("Add")
        self.__add.setToolTip('Add a new calibration item')
        self.__add.clicked.connect(self.__do_add)
        self.__add.setMinimumHeight(20)
        subgrid1.addWidget(self.__add, 0, 1)

        self.__remove = QPushButton("Remove")
        self.__remove.setToolTip('Remove calibration item')
        self.__remove.clicked.connect(self.__do_remove)
        self.__remove.setMinimumHeight(20)
        subgrid1.addWidget(self.__remove, 0, 2)
        
        # Close gaps
        grid.setRowStretch(1, 1)
        grid.setColumnStretch(2, 1)
        
        if self.__model[CONFIG][CAL][HOME] == -1 or self.__model[CONFIG][CAL][MAX] == -1:
            self.__add.setEnabled(False)
            self.__new.setEnabled(False)
        if self.__table.currentRow() == -1:
            self.__remove.setEnabled(False)
        
    
    def __populate_timeouts(self, grid):
        # Defaults for timeouts
        # Note values are configured in seconds
        # Working values depend on idle tick time
        # CALIBRATE_TIMEOUT = 120 * (1000/IDLE_TICKER)
        # TUNE_TIMEOUT = 120 * (1000/IDLE_TICKER)
        # RES_TIMEOUT = 60 * (1000/IDLE_TICKER)
        # MOVE_TIMEOUT = 30 * (1000/IDLE_TICKER)
        # SHORT_TIMEOUT = 2 * (1000/IDLE_TICKER)
        
        toinfolabel = QLabel('Timeouts for activities in seconds (waiting for Arduino response)')
        grid.addWidget(toinfolabel, 0, 0, 1, 3)
        
        caltolabel = QLabel('Calibration Timeout')
        grid.addWidget(caltolabel, 1, 0)
        self.__caltotxt = QSpinBox()
        self.__caltotxt.setObjectName("dialog")
        self.__caltotxt.setToolTip('Set number of seconds to wait for calibration to finish')
        self.__caltotxt.setRange(0,200)
        self.__caltotxt.setValue(self.__model[CONFIG][TIMEOUTS][CALIBRATE_TIMEOUT])
        self.__caltotxt.setMinimumWidth(80)
        grid.addWidget(self.__caltotxt, 1, 1)
    
        tunetolabel = QLabel('Tune Timeout')
        grid.addWidget(tunetolabel, 2, 0)
        self.__tunetotxt = QSpinBox()
        self.__tunetotxt.setObjectName("dialog")
        self.__tunetotxt.setToolTip('Set number of seconds to wait for tuning to finish')
        self.__tunetotxt.setRange(0,200)
        self.__tunetotxt.setValue(self.__model[CONFIG][TIMEOUTS][TUNE_TIMEOUT])
        self.__tunetotxt.setMinimumWidth(80)
        grid.addWidget(self.__tunetotxt, 2, 1)
        
        restolabel = QLabel('Resonance Timeout')
        grid.addWidget(restolabel, 3, 0)
        self.__restotxt = QSpinBox()
        self.__restotxt.setObjectName("dialog")
        self.__restotxt.setToolTip('Set number of seconds to wait for finding current resonance frequency')
        self.__restotxt.setRange(0,100)
        self.__restotxt.setValue(self.__model[CONFIG][TIMEOUTS][RES_TIMEOUT])
        self.__restotxt.setMinimumWidth(80)
        grid.addWidget(self.__restotxt, 3, 1)
        
        movetolabel = QLabel('Move Timeout')
        grid.addWidget(movetolabel, 4, 0)
        self.__movetotxt = QSpinBox()
        self.__movetotxt.setObjectName("dialog")
        self.__movetotxt.setToolTip('Set number of seconds to wait to move to extension %age')
        self.__movetotxt.setRange(0,60)
        self.__movetotxt.setValue(self.__model[CONFIG][TIMEOUTS][MOVE_TIMEOUT])
        self.__movetotxt.setMinimumWidth(80)
        grid.addWidget(self.__movetotxt, 4, 1)
        
        shorttolabel = QLabel('Short Timeout')
        grid.addWidget(shorttolabel, 5, 0)
        self.__shorttotxt = QSpinBox()
        self.__shorttotxt.setObjectName("dialog")
        self.__shorttotxt.setToolTip('Set number of seconds to wait for short running actions')
        self.__shorttotxt.setRange(0,10)
        self.__shorttotxt.setValue(self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT])
        self.__shorttotxt.setMinimumWidth(80)
        grid.addWidget(self.__shorttotxt, 5, 1)
        
        # Close gaps
        grid.setRowStretch(6, 1)
        grid.setColumnStretch(2, 1)
        
    #=======================================================
    # Window events
    def closeEvent(self, event):
        self.close()

    def resizeEvent(self, event):
        # Update config
        x,y,w,h = self.__model[STATE][WINDOWS][CONFIG_WIN]
        self.__model[STATE][WINDOWS][CONFIG_WIN] = [x,y,event.size().width(),event.size().height()]
        
    def moveEvent(self, event):
        # Update config
        x,y,w,h = self.__model[STATE][WINDOWS][CONFIG_WIN]
        self.__model[STATE][WINDOWS][CONFIG_WIN] = [event.pos().x(),event.pos().y(),w,h]
        
    #=======================================================
    # Calibration events

    #========================
    # Table events
    def __row_changed(self):
        if self.__table.currentRow() == -1:
            self.__remove.setEnabled(False)
        else:
            self.__remove.setEnabled(True)
            
    #========================
    # Combo box events
    def __loop_change(self, index):
        # Set loop selection needed by the callback as it cant access widgets
        # Index is zero based, loops are 1 based
        self.__selected_loop = index + 1
        self.__populate_table()
    
    #========================
    # Button events

    def __do_new(self):
        # Just clear the fields
        self.__nametxt.setText('')
        self.__lowfreqtxt.setText('')
        self.__highfreqtxt.setText('')
        self.__steptxt.setValue(10)
        self.__poslowtxt.setValue(50)
        self.__poshitxt.setValue(50)
    
    def __do_add(self):
        # Add current set to local sets
        key = self.__get_loop_item()
        self.__sets[key][self.__nametxt.text()] = [self.__lowfreqtxt.text(), str(self.__poslowtxt.value()), str(self.__highfreqtxt.text()), str(self.__poshitxt.value()), str(self.__steptxt.value())]
        self.__populate_table()
        
    def __do_remove(self):
        # Remove selected set from the local sets
        r = self.__table.currentRow()
        if r != -1:
            name = self.__table.item(r, 0).text()
            sets = self.__sets[self.__get_loop_item()]
            del sets[name]
            self.__table.removeRow(r);
            self.__populate_table()
            
    #=======================================================
    # Other events

    #=======================================================
    # Helpers
    def __populate_table(self):
        # Clear table
        row = 0
        while self.__table.rowCount() > 0:
            self.__table.removeRow(0);
        # Populate
        # Sets are {name: [low_freq, pos_low, high_freq, pos_high, steps], name:[...], ...}
        key = self.__get_loop_item()
        sets = self.__sets[key]
        if len(sets) > 0:
            for key, values in sets.items():
                self.__table.insertRow(row)
                self.__table.setItem(row, 0, QTableWidgetItem(str(key)))
                self.__table.setItem(row, 1, QTableWidgetItem(str(values[0])))
                self.__table.setItem(row, 2, QTableWidgetItem(str(values[1])))
                self.__table.setItem(row, 3, QTableWidgetItem(str(values[2])))
                self.__table.setItem(row, 4, QTableWidgetItem(str(values[3])))
                self.__table.setItem(row, 5, QTableWidgetItem(str(values[4])))
                row += 1
            if self.__table.rowCount() > 0:
                self.__table.selectRow(0)
        
    def __get_loop_item(self):
        if self.__selected_loop == 1:
           item = CAL_S1
        elif self.__selected_loop == 2:
           item = CAL_S2
        elif self.__selected_loop == 3:
           item = CAL_S3
        else:
            # Should not happen
            self.logger.warn("Invalid loop id %d" % self.__loop)
            item = CAL_S1
        return item
    
    def __do_save(self):
        # Move every field to the model
        # Changes take effect immediately as nothing uses cached values
        # Model is saved on exit
        self.__model[CONFIG][ARDUINO][PORT] = self.__serialporttxt.text()
        self.__model[CONFIG][ARDUINO][ACT_SPEED][ACT_SLOW] = self.__slowtxt.value()
        self.__model[CONFIG][ARDUINO][ACT_SPEED][ACT_MED] = self.__medtxt.value()
        self.__model[CONFIG][ARDUINO][ACT_SPEED][ACT_FAST] = self.__fasttxt.value()
        self.__model[CONFIG][CAL][SETS][CAL_S1] = self.__sets[CAL_S1]
        self.__model[CONFIG][CAL][SETS][CAL_S2] = self.__sets[CAL_S2]
        self.__model[CONFIG][CAL][SETS][CAL_S3] = self.__sets[CAL_S3]
        self.__model[CONFIG][TIMEOUTS][CALIBRATE_TIMEOUT] = self.__caltotxt.value()
        self.__model[CONFIG][TIMEOUTS][TUNE_TIMEOUT] = self.__tunetotxt.value()
        self.__model[CONFIG][TIMEOUTS][RES_TIMEOUT] = self.__restotxt.value()
        self.__model[CONFIG][TIMEOUTS][MOVE_TIMEOUT] = self.__movetotxt.value()
        self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT] = self.__shorttotxt.value()
        
    def __do_cancel(self):
        self.close()
    
    def __do_close(self):
        self.close()
    
    # =======================================================
    # Background activities
    def __idleProcessing(self):
    
        # Adjust buttons
        if self.__model[CONFIG][CAL][HOME] == -1 or self.__model[CONFIG][CAL][MAX] == -1:
            self.__add.setEnabled(False)
            self.__new.setEnabled(False)
        else:
            self.__new.setEnabled(True)
            if len(self.__nametxt.text()) > 0 and len(self.__lowfreqtxt.text()) > 0 and len(self.__highfreqtxt.text()) > 0 and self.__poslowtxt.value() > 0 and self.__poshitxt.value() > 0 and self.__steptxt.value() > 0:
                self.__add.setEnabled(True)
                
        if self.__table.currentRow() == -1:
            self.__remove.setEnabled(False)
        
        # Reset timer    
        QtCore.QTimer.singleShot(1000, self.__idleProcessing)
        