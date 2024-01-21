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

# PyQt5 imports
from PyQt5.QtWidgets import QMainWindow, QDialog, QApplication, QToolTip
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
        x,y,w,h = self.__model[STATE][WINDOWS][CONFIG_WIN]
        self.setGeometry(x,y,w,h)
                         
        self.setWindowTitle('Flexi-Loop Configuration')
        
    #=======================================================
    # Create all widgets
    def __populate(self):
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
    
        # VNA tab
        vnatab = QWidget()
        self.top_tab_widget.addTab(vnatab, "VNA")
        vnagrid = QGridLayout()
        vnatab.setLayout(vnagrid)
        self.__populate_vna(vnagrid)
        
        # Action buttons
        self.__save = QPushButton("Save")
        #self.__save.setObjectName("dialog")
        self.__save.setMaximumWidth(30)
        self.__save.setToolTip('Save changes ...')
        common.addWidget(self.__save, 0, 0)
        self.__save.clicked.connect(self.__do_save)
        self.__cancel = QPushButton("Cancel")
        #self.__cancel.setObjectName("dialog")
        self.__cancel.setMaximumWidth(30)
        self.__cancel.setToolTip('Cancel changes ...')
        common.addWidget(self.__cancel, 0, 1)
        self.__cancel.clicked.connect(self.__do_cancel)
        self.__close = QPushButton("Close")
        #self.__close.setObjectName("dialog")
        self.__close.setMaximumWidth(30)
        self.__close.setToolTip('Close configuration')
        common.addWidget(self.__close, 0, 2)
        self.__close.clicked.connect(self.__do_close)
        
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
        
        # Close gaps
        grid.setRowStretch(1, 1)
        grid.setColumnStretch(2, 1)

    def __populate_calibration(self, grid):
        # Default number of set points
        # ACTUATOR_STEPS = 10
        steplabel = QLabel('Calibration Steps')
        grid.addWidget(steplabel, 0, 0)
        self.__steptxt = QSpinBox()
        self.__steptxt.setObjectName("dialog")
        self.__steptxt.setToolTip('Set number of calibration steps')
        self.__steptxt.setRange(0,50)
        self.__steptxt.setValue(self.__model[CONFIG][CAL][ACTUATOR_STEPS])
        self.__steptxt.setMinimumWidth(80)
        grid.addWidget(self.__steptxt, 0, 1)
        
        # Close gaps
        grid.setRowStretch(1, 1)
        grid.setColumnStretch(2, 1)
    
    def __populate_timeouts(self, grid):
        # Defaults for timeouts
        # Note values are configured in seconds
        # Working values depend on idle tick time
        # CALIBRATE_TIMEOUT = 120 * (1000/IDLE_TICKER)
        # TUNE_TIMEOUT = 120 * (1000/IDLE_TICKER)
        # RES_TIMEOUT = 60 * (1000/IDLE_TICKER)
        # MOVE_TIMEOUT = 30 * (1000/IDLE_TICKER)
        # SHORT_TIMEOUT = 2 * (1000/IDLE_TICKER)
        
        caltolabel = QLabel('Calibration Timeout')
        grid.addWidget(caltolabel, 0, 0)
        self.__caltotxt = QSpinBox()
        self.__caltotxt.setObjectName("dialog")
        self.__caltotxt.setToolTip('Set number of seconds to wait for calibration to finish')
        self.__caltotxt.setRange(0,200)
        self.__caltotxt.setValue(self.__model[CONFIG][TIMEOUTS][CALIBRATE_TIMEOUT])
        self.__caltotxt.setMinimumWidth(80)
        grid.addWidget(self.__caltotxt, 0, 1)
    
        tunetolabel = QLabel('Tune Timeout')
        grid.addWidget(tunetolabel, 1, 0)
        self.__tunetotxt = QSpinBox()
        self.__tunetotxt.setObjectName("dialog")
        self.__tunetotxt.setToolTip('Set number of seconds to wait for tuning to finish')
        self.__tunetotxt.setRange(0,200)
        self.__tunetotxt.setValue(self.__model[CONFIG][TIMEOUTS][TUNE_TIMEOUT])
        self.__tunetotxt.setMinimumWidth(80)
        grid.addWidget(self.__tunetotxt, 1, 1)
        
        restolabel = QLabel('Resonance Timeout')
        grid.addWidget(restolabel, 2, 0)
        self.__restotxt = QSpinBox()
        self.__restotxt.setObjectName("dialog")
        self.__restotxt.setToolTip('Set number of seconds to wait for finding current resonance frequency')
        self.__restotxt.setRange(0,100)
        self.__restotxt.setValue(self.__model[CONFIG][TIMEOUTS][RES_TIMEOUT])
        self.__restotxt.setMinimumWidth(80)
        grid.addWidget(self.__restotxt, 2, 1)
        
        movetolabel = QLabel('Move Timeout')
        grid.addWidget(movetolabel, 3, 0)
        self.__movetotxt = QSpinBox()
        self.__movetotxt.setObjectName("dialog")
        self.__movetotxt.setToolTip('Set number of seconds to wait to move to extension %age')
        self.__movetotxt.setRange(0,60)
        self.__movetotxt.setValue(self.__model[CONFIG][TIMEOUTS][MOVE_TIMEOUT])
        self.__movetotxt.setMinimumWidth(80)
        grid.addWidget(self.__movetotxt, 3, 1)
        
        shorttolabel = QLabel('Short Timeout')
        grid.addWidget(shorttolabel, 4, 0)
        self.__shorttotxt = QSpinBox()
        self.__shorttotxt.setObjectName("dialog")
        self.__shorttotxt.setToolTip('Set number of seconds to wait for short running actions')
        self.__shorttotxt.setRange(0,10)
        self.__shorttotxt.setValue(self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT])
        self.__shorttotxt.setMinimumWidth(80)
        grid.addWidget(self.__shorttotxt, 4, 1)
        
        # Close gaps
        grid.setRowStretch(5, 1)
        grid.setColumnStretch(2, 1)
        
    def __populate_vna(self, grid):
        # VNA present?
        # Defaults
        # DRIVER_ID = 20  # MiniVNA Tiny
        # DRIVER_PORT = 'COM4'
        # CAL_FILE = '../VNAJ/vnaJ.3.3/calibration/REFL_miniVNA Tiny.cal'
        # SCAN_MODE = 'REFL' Fixed
        # EXPORTS = 'csv' Fixed
        # EXPORT_FILENAME = 'VNA_{0,date,yyMMdd}_{0,time,HHmmss}'
        # VNA_JAR = '../VNAJ/vnaJ.3.3/vnaJ-hl.3.3.3.jar'
        # Decoder defs
        # EXPORT_PATH = '../VNAJ/vnaJ.3.3/export'
        
        vnaavaillabel = QLabel('VNA Present?')
        grid.addWidget(vnaavaillabel, 0, 0)
        self.__vnaavailtog = QCheckBox('')
        self.__vnaavailtog.setToolTip('Set number of seconds to wait for short running actions')
        if self.__model[CONFIG][VNA_CONF][VNA_PRESENT] == VNA_YES:
            self.__vnaavailtog.setChecked(True)
        else:
            self.__vnaavailtog.setChecked(False)
        grid.addWidget(self.__vnaavailtog, 0, 1)
        
        vnadriverlabel = QLabel('VNA Driver')
        grid.addWidget(vnadriverlabel, 1, 0)    
        self.__vnadrivertxt = QSpinBox()
        self.__vnadrivertxt.setObjectName("dialog")
        self.__vnadrivertxt.setToolTip('Driver ID, default mini-VNA Tiny = 20')
        self.__vnadrivertxt.setRange(0,100)
        self.__vnadrivertxt.setValue(self.__model[CONFIG][VNA_CONF][DRIVER_ID])
        self.__vnadrivertxt.setMaximumWidth(80)
        grid.addWidget(self.__vnadrivertxt, 1, 1)
        
        vnaportlabel = QLabel('VNA Port')
        grid.addWidget(vnaportlabel, 2, 0)
        self.__vnaporttxt = QLineEdit()
        self.__vnaporttxt.setObjectName("dialog")
        self.__vnaporttxt.setText(self.__model[CONFIG][VNA_CONF][DRIVER_PORT])
        self.__vnaporttxt.setToolTip('Set VNA Port')
        self.__vnaporttxt.setMaximumWidth(80)
        grid.addWidget(self.__vnaporttxt, 2, 1)
        
        vnamodelabel = QLabel('Scan Mode')
        grid.addWidget(vnamodelabel, 4, 0)
        self.__vnamodetxt = QLabel(SCAN_MODE)
        self.__vnamodetxt.setToolTip('Fixed Scan Mode')
        self.__vnamodetxt.setMaximumWidth(80)
        grid.addWidget(self.__vnamodetxt, 4, 1)
        
        vnatypelabel = QLabel('Export File Type')
        grid.addWidget(vnatypelabel, 5, 0)
        self.__vnatypetxt = QLabel(EXPORTS)
        self.__vnatypetxt.setToolTip('Fixed export type')
        self.__vnatypetxt.setMaximumWidth(80)
        grid.addWidget(self.__vnatypetxt, 5, 1)
        
        vnanamelabel = QLabel('Export Filename')
        grid.addWidget(vnanamelabel, 6, 0)
        self.__vnanametxt = QLineEdit()
        self.__vnanametxt.setObjectName("dialog")
        self.__vnanametxt.setText(self.__model[CONFIG][VNA_CONF][EXPORT_FILENAME])
        self.__vnanametxt.setToolTip('Set export type')
        self.__vnanametxt.setMinimumWidth(300)
        grid.addWidget(self.__vnanametxt, 6, 1)
        
        vnacalpathlabel = QLabel('Calibration File Path')
        grid.addWidget(vnacalpathlabel, 7, 0)
        self.__vnacalpathtxt = QLineEdit()
        self.__vnacalpathtxt.setObjectName("dialog")
        self.__vnacalpathtxt.setText(self.__model[CONFIG][VNA_CONF][CAL_FILE])
        self.__vnacalpathtxt.setToolTip('Set calibration file path')
        self.__vnacalpathtxt.setMinimumWidth(300)
        grid.addWidget(self.__vnacalpathtxt, 7, 1)
        # Now we need a way to select a file
        self.__caldialog = QPushButton("...")
        self.__caldialog.setObjectName("dialog")
        #self.__caldialog.setMaximumWidth(10)
        self.__caldialog.setToolTip('Choose file...')
        grid.addWidget(self.__caldialog, 7, 2)
        self.__caldialog.clicked.connect(self.__do_cal_path)
        
        vnajarlabel = QLabel('VNA Jar Path')
        grid.addWidget(vnajarlabel, 8, 0)
        self.__vnajarpathtxt = QLineEdit()
        self.__vnajarpathtxt.setObjectName("dialog")
        self.__vnajarpathtxt.setText(self.__model[CONFIG][VNA_CONF][VNA_JAR])
        self.__vnajarpathtxt.setToolTip('Set JAR path')
        self.__vnajarpathtxt.setMinimumWidth(300)
        grid.addWidget(self.__vnajarpathtxt, 8, 1)
        # Now we need a way to select a file
        self.__jardialog = QPushButton("...")
        self.__jardialog.setObjectName("dialog")
        #self.__jardialog.setMaximumWidth(10)
        self.__jardialog.setToolTip('Choose file...')
        grid.addWidget(self.__jardialog, 8, 2)
        self.__jardialog.clicked.connect(self.__do_jar_path)
        
        vnaexportlabel = QLabel('Export Path')
        grid.addWidget(vnaexportlabel, 9, 0)
        self.__vnaexportpathtxt = QLineEdit()
        self.__vnaexportpathtxt.setObjectName("dialog")
        self.__vnaexportpathtxt.setText(self.__model[CONFIG][VNA_CONF][EXPORT_PATH])
        self.__vnaexportpathtxt.setToolTip('Set export file path')
        self.__vnaexportpathtxt.setMinimumWidth(300)
        grid.addWidget(self.__vnaexportpathtxt, 9, 1)
        # Now we need a way to select a file
        self.__exportdialog = QPushButton("...")
        self.__exportdialog.setObjectName("dialog")
        #self.__exportdialog.setMaximumWidth(10)
        self.__exportdialog.setToolTip('Choose file...')
        grid.addWidget(self.__exportdialog, 9, 2)
        self.__exportdialog.clicked.connect(self.__do_export_path)
        
        # Close gaps
        grid.setRowStretch(10, 1)
        grid.setColumnStretch(3, 1)
        
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
    def __do_save(self):
        # Move every field to the model
        # Changes take effect immediately as nothing uses cached values
        # Model is saved on exit
        self.__model[CONFIG][ARDUINO][PORT] = self.__serialporttxt.text()
        self.__model[CONFIG][CAL][ACTUATOR_STEPS] = self.__steptxt.value()
        self.__model[CONFIG][TIMEOUTS][CALIBRATE_TIMEOUT] = self.__caltotxt.value()
        self.__model[CONFIG][TIMEOUTS][TUNE_TIMEOUT] = self.__tunetotxt.value()
        self.__model[CONFIG][TIMEOUTS][RES_TIMEOUT] = self.__restotxt.value()
        self.__model[CONFIG][TIMEOUTS][MOVE_TIMEOUT] = self.__movetotxt.value()
        self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT] = self.__shorttotxt.value()
        if self.__vnaavailtog.isChecked():
            self.__model[CONFIG][VNA_CONF][VNA_PRESENT] = VNA_YES
        else:
            self.__model[CONFIG][VNA_CONF][VNA_PRESENT] = VNA_NO
        self.__model[CONFIG][VNA_CONF][DRIVER_ID] = self.__vnadrivertxt.value()
        self.__model[CONFIG][VNA_CONF][DRIVER_PORT] = self.__vnaporttxt.text()
        self.__model[CONFIG][VNA_CONF][EXPORT_FILENAME] = self.__vnanametxt.text()
        self.__model[CONFIG][VNA_CONF][CAL_FILE] = self.__vnacalpathtxt.text()
        self.__model[CONFIG][VNA_CONF][VNA_JAR] = self.__vnajarpathtxt.text()
        self.__model[CONFIG][VNA_CONF][EXPORT_PATH] = self.__vnaexportpathtxt.text()
        
    def __do_cancel(self):
        self.close()
    
    def __do_close(self):
        self.close()
    
    def __do_cal_path(self):
        file = QFileDialog.getOpenFileName(self, 'Open file')[0]
        if len(file) > 0:
            self.__vnacalpathtxt.setText(file)
        
    def __do_jar_path(self):
        file = QFileDialog.getOpenFileName(self, 'Open file')[0]
        if len(file) > 0:
            self.__vnajarpathtxt.setText(file)
        
    def __do_export_path(self):
        file = QFileDialog.getOpenFileName(self, 'Open file')[0]
        if len(file) > 0:
            self.__vnaexportpathtxt.setText(file)
    