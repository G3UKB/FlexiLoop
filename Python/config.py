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
from PyQt5.QtWidgets import QStatusBar, QTabWidget, QTableWidget, QInputDialog, QFrame, QGroupBox, QMessageBox, QLabel, QSlider, QLineEdit, QTextEdit, QComboBox, QPushButton, QCheckBox, QRadioButton, QSpinBox, QAction, QWidget, QGridLayout, QVBoxLayout, QHBoxLayout, QTableWidgetItem

# Application imports
from defs import *
from utils import *
import api

# Main config dialog        
class Config(QDialog):
    
    def __init__(self, model):
        super(Config, self).__init__()

        # Get root logger
        self.logger = logging.getLogger('root')
        
        self.__model = model
     
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
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.top_tab_widget)
        
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
        
    #=======================================================
    # Populate dialog
    def __populate_arduino(self, grid):
        # Serial port
        pass

    def __populate_calibration(self, grid):
        # Default number of set points
        # ACTUATOR_STEPS = 10
        pass
    
    def __populate_timeouts(self, grid):
        # Defaults for timeouts
        # Note values are configured in seconds
        # Working values depend on idle tick time
        # CALIBRATE_TIMEOUT = 120 * (1000/IDLE_TICKER)
        # TUNE_TIMEOUT = 120 * (1000/IDLE_TICKER)
        # RES_TIMEOUT = 60 * (1000/IDLE_TICKER)
        # MOVE_TIMEOUT = 30 * (1000/IDLE_TICKER)
        # SHORT_TIMEOUT = 2 * (1000/IDLE_TICKER)
        pass
    
    def __populate_vna(self, grid):
        # VNA present?
        # Defaults
        # DRIVER_ID = 20  # MiniVNA Tiny
        # DRIVER_PORT = 'COM4'
        # CAL_FILE = '../VNAJ/vnaJ.3.3/calibration/REFL_miniVNA Tiny.cal'
        # SCAN_MODE = 'REFL'
        # EXPORTS = 'csv'
        # EXPORT_FILENAME = 'VNA_{0,date,yyMMdd}_{0,time,HHmmss}'
        # JAR = '../VNAJ/vnaJ.3.3/vnaJ-hl.3.3.3.jar' #P
        # Decoder defs
        # EXPORT_PATH = '../VNAJ/vnaJ.3.3/export'
        pass
        
    #=======================================================
    # Window events
    def closeEvent(self, event):
        pass
    
    def __close(self):
        pass

    def resizeEvent(self, event):
        # Update config
        x,y,w,h = self.__model[STATE][WINDOWS][CONFIG_WIN]
        self.__model[STATE][WINDOWS][CONFIG_WIN] = [x,y,event.size().width(),event.size().height()]
        
    def moveEvent(self, event):
        # Update config
        x,y,w,h = self.__model[STATE][WINDOWS][CONFIG_WIN]
        self.__model[STATE][WINDOWS][CONFIG_WIN] = [event.pos().x(),event.pos().y(),w,h]   