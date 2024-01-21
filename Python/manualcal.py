#!/usr/bin/env python
#
# manual.py
#
# Manual entry in lieu of VNA for Flexi-loop
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

# Manual input dialog        
class ManualInput(QDialog):
    
    def __init__(self):
        super(ManualInput, self).__init__()

        # Get root logger
        self.logger = logging.getLogger('root')
        
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
    def run(self, hint):          
        self.setWindowTitle('Flexi-Loop Manual Calibration [%s]' % hint)
        self.__freqtxt.setText('')
        self.__swrtxt.setText('')
    
    def results(self):
        return (self.__swrtxt.text(), self.__freqtxt.text())
    
    #=======================================================
    # Create all widgets
    def __populate(self):
        #=======================================================
           
        # Set main layout
        grid = QGridLayout()
        self.setLayout(grid)
    
        # Data entry
        freqlabel = QLabel('Frequency')
        grid.addWidget(freqlabel ,0 ,0)
        self.__freqtxt = QLineEdit()
        self.__freqtxt.setToolTip('Resonant frequency')
        self.__freqtxt.setMaximumWidth(80)
        grid.addWidget(self.__freqtxt ,0 ,1)
        
        swrlabel = QLabel('SWR')
        grid.addWidget(swrlabel ,1 ,0)
        self.__swrtxt = QLineEdit()
        self.__swrtxt.setToolTip('SWR at resonance')
        self.__swrtxt.setMaximumWidth(80)
        grid.addWidget(self.__swrtxt ,1 ,1)
        
        # Button area
        self.__close = QPushButton("Close")
        self.__close.setToolTip('Close to use values')
        self.__close.clicked.connect(self.__do_close)
        self.__close.setMinimumHeight(20)
        grid.addWidget(self.__close, 2, 0)
    
    #=======================================================
    # PUBLIC
    #
    
    #=======================================================
    # Window events
    def closeEvent(self, event):
        self.hide()

    #=======================================================
    # User events
    def __do_close(self):
        self.hide()
