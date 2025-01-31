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
from qt_inc import *

# Application imports
from defs import *
from utils import *
import api
import persist

# Main config dialog        
class Config(QDialog):
    
    def __init__(self, model, msgs):
        super(Config, self).__init__()

        # Get root logger
        self.logger = logging.getLogger('root')
        
        # Parameters
        self.__model = model
        self.__msgs = msgs
        
        # Instance vars
        self.__selected_loop = 1
        
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
        self.__populate_ui()
        
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
        
        # VNA tab
        vnatab = QWidget()
        self.top_tab_widget.addTab(vnatab, "VNA")
        vnagrid = QGridLayout()
        vnatab.setLayout(vnagrid)
        self.__populate_vna(vnagrid)
        
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
        
        # Adjust layout
        gap = QWidget()
        common.addWidget(gap, 0, 2)
        common.setColumnStretch(2, 1)
        
    #=======================================================
    # Populate tabs
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
        
        minlabel = QLabel('Minimum Speed')
        grid.addWidget(minlabel, 1, 0)
        self.__mintxt = QSpinBox()
        self.__mintxt.setObjectName("dialog")
        self.__mintxt.setToolTip('Minimum motor speed')
        self.__mintxt.setRange(40,100)
        self.__mintxt.setValue(self.__model[CONFIG][ARDUINO][MOTOR_SPEED][MINIMUM])
        self.__mintxt.setMinimumWidth(80)
        grid.addWidget(self.__mintxt, 1, 1)
        
        maxlabel = QLabel('Maximum Speed')
        grid.addWidget(maxlabel, 2, 0)
        self.__maxtxt = QSpinBox()
        self.__maxtxt.setObjectName("dialog")
        self.__maxtxt.setToolTip('Maximum motor speed')
        self.__maxtxt.setRange(300,500)
        self.__maxtxt.setValue(self.__model[CONFIG][ARDUINO][MOTOR_SPEED][MAXIMUM])
        self.__maxtxt.setMinimumWidth(80)
        grid.addWidget(self.__maxtxt, 2, 1)
        
        deflabel = QLabel('Default Speed')
        grid.addWidget(deflabel, 3, 0)
        self.__deftxt = QSpinBox()
        self.__deftxt.setObjectName("dialog")
        self.__deftxt.setToolTip('Default motor speed')
        self.__deftxt.setRange(100,300)
        self.__deftxt.setValue(self.__model[CONFIG][ARDUINO][MOTOR_SPEED][DEFAULT])
        self.__deftxt.setMinimumWidth(80)
        grid.addWidget(self.__deftxt, 3, 1)
        
        # Close gaps
        grid.setRowStretch(4, 1)
        grid.setColumnStretch(4, 1)

    def __populate_calibration(self, grid):
        # Calibration data for each band covered by
        callabel = QLabel('Loops 1-3 calibration settings: ')
        grid.addWidget(callabel, 0, 0, 1,4)
        
        loop1label = QLabel('Name')
        grid.addWidget(loop1label, 1, 0)
        self.__loop1txt = QLineEdit(self.__model[CONFIG][CAL][NAMES][NAME_1])
        self.__loop1txt.setObjectName("dialog")
        self.__loop1txt.setToolTip('Loop 1 calibration name')
        self.__loop1txt.setMaximumWidth(80)
        grid.addWidget(self.__loop1txt, 1, 1)
        step1label = QLabel('Steps')
        grid.addWidget(step1label, 1, 2)
        self.__step1txt = QSpinBox()
        self.__step1txt.setObjectName("dialog")
        self.__step1txt.setToolTip('Loop 1 number of calibration steps')
        self.__step1txt.setRange(5,50)
        self.__step1txt.setMinimumWidth(80)
        self.__step1txt.setValue(self.__model[CONFIG][CAL][STEPS][STEPS_1])
        grid.addWidget(self.__step1txt, 1, 3)
        
        loop2label = QLabel('Name')
        grid.addWidget(loop2label, 2, 0)
        self.__loop2txt = QLineEdit(self.__model[CONFIG][CAL][NAMES][NAME_2])
        self.__loop2txt.setObjectName("dialog")
        self.__loop2txt.setToolTip('Loop 2 calibration name')
        self.__loop2txt.setMaximumWidth(80)
        grid.addWidget(self.__loop2txt, 2, 1)
        step2label = QLabel('Steps')
        grid.addWidget(step2label, 2, 2)
        self.__step2txt = QSpinBox()
        self.__step2txt.setObjectName("dialog")
        self.__step2txt.setToolTip('Loop 2 number of calibration steps')
        self.__step2txt.setRange(5,50)
        self.__step2txt.setMinimumWidth(80)
        self.__step2txt.setValue(self.__model[CONFIG][CAL][STEPS][STEPS_2])
        grid.addWidget(self.__step2txt, 2, 3)
        
        loop3label = QLabel('Name')
        grid.addWidget(loop3label, 3, 0)
        self.__loop3txt = QLineEdit(self.__model[CONFIG][CAL][NAMES][NAME_3])
        self.__loop3txt.setObjectName("dialog")
        self.__loop3txt.setToolTip('Loop 3 calibration name')
        self.__loop3txt.setMaximumWidth(80)
        grid.addWidget(self.__loop3txt, 3, 1)
        step3label = QLabel('Steps')
        grid.addWidget(step3label, 3, 2)
        self.__step3txt = QSpinBox()
        self.__step3txt.setObjectName("dialog")
        self.__step3txt.setToolTip('Loop 3 number of calibration steps')
        self.__step3txt.setRange(5,50)
        self.__step3txt.setMinimumWidth(80)
        self.__step3txt.setValue(self.__model[CONFIG][CAL][STEPS][STEPS_3])
        grid.addWidget(self.__step3txt, 3, 3)
        
         # Close gaps
        grid.setRowStretch(4, 1)
        grid.setColumnStretch(4, 1)
        
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
    # Populate VNA
    def __populate_vna(self, grid):
        # VNA enable
        vnalabel = QLabel('VNA Enable')
        grid.addWidget(vnalabel, 0, 0)
        self.__vnacb = QCheckBox('')
        grid.addWidget(self.__vnacb, 0, 1)
        self.__vnacb.stateChanged.connect(self.__vna_state_changed)
        
        if self.__model[CONFIG][VNA][VNA_ENABLED]:
            self.__vnacb.setChecked(True)
        else:
            self.__vnacb.setChecked(False)
            
        # Close gaps
        grid.setRowStretch(1, 1)
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
    # User events

    #===========================
    # Arduino tab events
    # None
    
    #===========================
    # Calibration tab events
    # Target loop changed
    def __loop_change(self, index):
        # Set loop selection needed by the callback as it cant access widgets
        # Index is zero based, loops are 1 based
        self.__selected_loop = index + 1
        self.__populate_table()
        
    # New table row selected
    def __row_changed(self):
        if self.__table.currentRow() == -1:
            self.__remove.setEnabled(False)
        else:
            self.__remove.setEnabled(True)
            
    # Button events
    def __do_new(self):
        # Just clear the fields
        self.__nametxt.setText('')
        self.__lowfreqtxt.setText('')
        self.__highfreqtxt.setText('')
        self.__steptxt.setValue(10)
        self.__poslowtxt.setText('')
        self.__poshitxt.setText('')
    
    # Add current set to local sets
    def __do_add(self):
        key = self.__get_loop_item()
        self.__sets[key][self.__nametxt.text()] = [float(self.__lowfreqtxt.text()), float(self.__poslowtxt.text()), float(self.__highfreqtxt.text()), float(self.__poshitxt.text()), int(self.__steptxt.value())]
        self.__populate_table()
    
    # Remove selected set from the local sets    
    def __do_remove(self):
        r = self.__table.currentRow()
        if r != -1:
            name = self.__table.item(r, 0).text()
            sets = self.__sets[self.__get_loop_item()]
            del sets[name]
            self.__table.removeRow(r);
            self.__populate_table()
    
    #===========================
    # Timeout tab events
    # None
    
    #===========================
    # VNA tab events
    def __vna_state_changed(self):
        if self.__vnacb.isChecked():
            self.__model[STATE][VNA_ENABLED] = True
        else:
            self.__model[STATE][VNA_ENABLED] = False
    
    #===========================
    # Common button events
    # Save the changes to the model
    def __do_save(self):
        # Move every field to the model
        # Changes take effect immediately as nothing uses cached values
        # Model is saved on exit
            
        # Save any updates    
        self.__model[CONFIG][ARDUINO][PORT] = self.__serialporttxt.text()
        self.__model[CONFIG][ARDUINO][MOTOR_SPEED][MINIMUM] = self.__mintxt.value()
        self.__model[CONFIG][ARDUINO][MOTOR_SPEED][MAXIMUM] = self.__maxtxt.value()
        self.__model[CONFIG][ARDUINO][MOTOR_SPEED][DEFAULT] = self.__deftxt.value()
        
        self.__model[CONFIG][CAL][NAMES][NAME_1] = self.__loop1txt.text()
        self.__model[CONFIG][CAL][NAMES][NAME_2] = self.__loop2txt.text()
        self.__model[CONFIG][CAL][NAMES][NAME_3] = self.__loop3txt.text()
        self.__model[CONFIG][CAL][STEPS][STEPS_1] = self.__step1txt.value()
        self.__model[CONFIG][CAL][STEPS][STEPS_2] = self.__step2txt.value()
        self.__model[CONFIG][CAL][STEPS][STEPS_3] = self.__step3txt.value()
                                         
        self.__model[CONFIG][TIMEOUTS][CALIBRATE_TIMEOUT] = self.__caltotxt.value()
        self.__model[CONFIG][TIMEOUTS][TUNE_TIMEOUT] = self.__tunetotxt.value()
        self.__model[CONFIG][TIMEOUTS][RES_TIMEOUT] = self.__restotxt.value()
        self.__model[CONFIG][TIMEOUTS][MOVE_TIMEOUT] = self.__movetotxt.value()
        self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT] = self.__shorttotxt.value()
        
        if self.__vnacb.isChecked():
            self.__model[CONFIG][VNA][VNA_ENABLED] = True
        else:
            self.__model[CONFIG][VNA][VNA_ENABLED] = False
        
        # Save model
        persist.saveCfg(CONFIG_PATH, self.__model)
    
    # Cancel changes    
    def __do_cancel(self):
        self.close()
    
    # Close
    def __do_close(self):
        self.close()
        
        