#!/usr/bin/env python
#
# ui.py
#
# User interface for Flexi-loop
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

# PyQt5 imports
from PyQt5.QtWidgets import QMainWindow, QApplication, QToolTip
from PyQt5.QtGui import QPainter, QPainterPath, QColor, QPen, QFont
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QStatusBar, QTableWidget, QInputDialog, QFrame, QGroupBox, QMessageBox, QLabel, QSlider, QLineEdit, QTextEdit, QComboBox, QPushButton, QCheckBox, QRadioButton, QSpinBox, QAction, QWidget, QGridLayout, QTableWidgetItem

# Application imports
from defs import *

class UI(QMainWindow):
    
    def __init__(self, model, qt_app):
        super(UI, self).__init__()

        self.__model = model 
        self.__qt_app = qt_app
    
        # Set the back colour
        palette = QtGui.QPalette()
        palette.setColor(QtGui.QPalette.Background,QtGui.QColor(195,195,195,255))
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
    # PUBLIC
    #
    # Run application
    def run(self, ):
        # Start idle processing
        QtCore.QTimer.singleShot(IDLE_TICKER, self.__idleProcessing)
        
        # Show the GUI
        self.show()
        self.repaint()
            
        # Enter event loop
        # Returns when GUI exits
        return self.__qt_app.exec_()
    
    #=======================================================
    # PRIVATE
    #
    # Basic initialisation
    def __initUI(self):
        
        """ Configure the GUI interface """
            
        self.setToolTip('Remote Auto-Tuner')
        
        # Arrange window
        x,y,w,h = self.__model[STATE][MAIN_WIN]
        self.setGeometry(x,y,w,h)
                         
        self.setWindowTitle('Flexi-Loop')
    
    #=======================================================
    # Create all widgets
    def __populate(self):
        #=======================================================
        # Set main layout
        w = QWidget()
        self.setCentralWidget(w)
        self.__grid = QGridLayout()
        w.setLayout(self.__grid)
        self.__grid.setColumnStretch(0,0)
        self.__grid.setColumnStretch(1,1)
        
        # -------------------------------------------
        # Selection area
        self.__selgrid = QGridLayout()
        w1 = QGroupBox('Selection')
        w1.setLayout(self.__selgrid)
        self.__grid.addWidget(w1, 0,1,2,1)
        
        self.__loop_sel = QComboBox()
        self.__loop_sel.addItem("1")
        self.__loop_sel.addItem("2")
        self.__loop_sel.addItem("3")
        self.__selgrid.addWidget(self.__loop_sel, 0,0)
        
        # -------------------------------------------
        # Button area
        self.__btngrid = QGridLayout()
        w2 = QGroupBox('Function')
        w2.setLayout(self.__btngrid)
        self.__grid.addWidget(w2, 0,0,2,1)
        
        self.__cal = QPushButton("(Re)Calibrate...")
        self.__cal.setToolTip('Calibrate for loop...')
        self.__btngrid.addWidget(self.__cal, 0,0)
        self.__cal.clicked.connect(self.__do_cal)
        self.__cal.setMaximumHeight(20)
        
        self.__tune = QPushButton("Tune...")
        self.__tune.setToolTip('Tune to frequency...')
        self.__btngrid.addWidget(self.__tune, 1,0)
        self.__tune.clicked.connect(self.__do_tune)
        self.__tune.setMaximumHeight(20)
    
    #=======================================================
    # Window events
    def closeEvent(self, event):
        self.__close()
    
    def __close(self):
        pass

    def resizeEvent(self, event):
        # Update config
        x,y,w,h = self.__model[STATE][MAIN_WIN]
        self.__model[STATE][MAIN_WIN] = [x,y,event.size().width(),event.size().height()]
        
    def moveEvent(self, event):
        # Update config
        x,y,w,h = self.__model[STATE][MAIN_WIN]
        self.__model[STATE][MAIN_WIN] = [event.pos().x(),event.pos().y(),w,h]
     
    #=======================================================
    # Button events
    def __do_cal(self):
        pass
    
    def __do_tune(self):
        pass
    
    #=======================================================
    # Background activities
    def __idleProcessing(self):
        
        # Set timer
        QtCore.QTimer.singleShot(IDLE_TICKER, self.__idleProcessing)
        