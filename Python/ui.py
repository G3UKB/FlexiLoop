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
from PyQt5.QtWidgets import QStatusBar, QTableWidget, QInputDialog, QFrame, QGroupBox, QMessageBox, QLabel, QSlider, QLineEdit, QTextEdit, QComboBox, QPushButton, QCheckBox, QRadioButton, QSpinBox, QAction, QWidget, QGridLayout, QHBoxLayout, QTableWidgetItem

# Application imports
from defs import *
import api

class UI(QMainWindow):
    
    def __init__(self, model, qt_app, api, port):
        super(UI, self).__init__()

        self.__model = model
        self.__api = api
        
        self.__qt_app = qt_app
        
        #Loop status
        self.__loop_status = [False, False, False]
    
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
        
        # Get loop status
        home = self.__model[CONFIG][CAL][HOME]
        maximum = self.__model[CONFIG][CAL][MAX]
        if home != -1 and maximum != -1:
            # Something has been configured
            # Check loops
            if len(self.__model[CONFIG][CAL][CAL_L1]) > 0:
                self.__loop_status[0] = True
            elif len(self.__model[CONFIG][CAL][CAL_L2]) > 0:
                self.__loop_status[1] = True
            elif len(self.__model[CONFIG][CAL][CAL_L3]) > 0:
                self.__loop_status[2] = True 
        
    #=======================================================
    # PUBLIC
    #
    # Run application
    def run(self, ):
        
        # Show the GUI
        self.show()
        self.repaint()
            
        # Start idle processing
        QtCore.QTimer.singleShot(1000, self.__idleProcessing)
        
        # Enter event loop
        # Returns when GUI exits
        return self.__qt_app.exec_()
    
    #=======================================================
    # PRIVATE
    #
    # Basic initialisation
    def __initUI(self):
        
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
        
        # -------------------------------------------
        # Loop area
        self.__loopgrid = QGridLayout()
        w1 = QGroupBox('Loop')
        w1.setLayout(self.__loopgrid)
        self.__grid.addWidget(w1, 0,0,1,4)
        
        looplabel = QLabel('Select Loop')
        self.__loopgrid.addWidget(looplabel, 0, 0)
        self.__loop_sel = QComboBox()
        self.__loop_sel.addItem("1")
        self.__loop_sel.addItem("2")
        self.__loop_sel.addItem("3")
        self.__loop_sel.setMinimumHeight(30)
        self.__loopgrid.addWidget(self.__loop_sel, 0,1)
        
        minlabel = QLabel('Min freq')
        self.__loopgrid.addWidget(minlabel, 0, 2)
        minlabel.setAlignment(QtCore.Qt.AlignCenter)
        self.__minvalue = QLabel('0.0')
        self.__minvalue.setAlignment(QtCore.Qt.AlignCenter)
        self.__minvalue.setStyleSheet("QLabel {color: rgb(255,100,0); font: 20px}")
        self.__loopgrid.addWidget(self.__minvalue, 0, 3)
        maxlabel = QLabel('Max freq')
        self.__loopgrid.addWidget(maxlabel, 0, 4)
        maxlabel.setAlignment(QtCore.Qt.AlignCenter)
        self.__maxvalue = QLabel('0.0')
        self.__maxvalue.setAlignment(QtCore.Qt.AlignCenter)
        self.__maxvalue.setStyleSheet("QLabel {color: rgb(255,100,0); font: 20px}")
        self.__loopgrid.addWidget(self.__maxvalue, 0, 5)
        
        self.__cal = QPushButton("(Re)Calibrate...")
        self.__cal.setToolTip('Calibrate for loop...')
        self.__loopgrid.addWidget(self.__cal, 1, 0)
        self.__cal.clicked.connect(self.__do_cal)
        self.__cal.setMinimumHeight(30)
        self.__cal.setMinimumWidth(100)
        
        w2 = QGroupBox('Status')
        hbox = QHBoxLayout()
        self.__l1label = QLabel('Loop-1')
        hbox.addWidget(self.__l1label)
        self.__l1label.setStyleSheet("QLabel {color: rgb(255,0,0); font: 12px}")
        self.__l1label.setAlignment(QtCore.Qt.AlignCenter)
        self.__l2label = QLabel('Loop-2')
        hbox.addWidget(self.__l2label)
        self.__l2label.setStyleSheet("QLabel {color: rgb(255,0,0); font: 12px}")
        self.__l2label.setAlignment(QtCore.Qt.AlignCenter)
        self.__l3label = QLabel('Loop-3')
        hbox.addWidget(self.__l3label)
        self.__l3label.setStyleSheet("QLabel {color: rgb(255,0,0); font: 12px}")
        self.__l3label.setAlignment(QtCore.Qt.AlignCenter)
        w2.setLayout(hbox)
        self.__loopgrid.addWidget(w2, 1, 1, 1, 3)
        
        # -------------------------------------------
        # Auto area
        self.__autogrid = QGridLayout()
        w1 = QGroupBox('Auto')
        w1.setLayout(self.__autogrid)
        self.__grid.addWidget(w1, 1,0,1,4)
        self.__autogrid.setColumnMinimumWidth(5,300)
        
        freqlabel = QLabel('Freq')
        self.__autogrid.addWidget(freqlabel, 0, 0)
        self.freqtxt = QLineEdit()
        self.freqtxt.setToolTip('Set tune frequency')
        self.freqtxt.setInputMask('000.000;_')
        self.freqtxt.setStyleSheet("QLineEdit {color: rgb(255,100,0); font: 20px}")
        self.freqtxt.setMaximumWidth(80)
        self.__autogrid.addWidget(self.freqtxt, 0, 1)
        
        swrlabel = QLabel('SWR')
        self.__autogrid.addWidget(swrlabel, 0, 2)
        swrlabel.setAlignment(QtCore.Qt.AlignCenter)
        self.__swrval = QLabel('?.?')
        self.__swrval.setStyleSheet("QLabel {color: rgb(255,100,0); font: 20px}")
        self.__autogrid.addWidget(self.__swrval, 0, 3)
        
        self.__tune = QPushButton("Tune...")
        self.__tune.setToolTip('Tune to freq...')
        self.__autogrid.addWidget(self.__tune, 0,4)
        self.__tune.clicked.connect(self.__do_tune)
        self.__tune.setMinimumHeight(30)
        self.__tune.setMinimumWidth(100)
        self.__tune.setMaximumWidth(100)
        
        # -------------------------------------------
        # Manual area
        self.__mangrid = QGridLayout()
        w1 = QGroupBox('Manual')
        w1.setLayout(self.__mangrid)
        self.__grid.addWidget(w1, 2,0,1,4)
        
        #----------------------------------
        # Target select
        relaylabel = QLabel('Select TX/VNA')
        self.__mangrid.addWidget(relaylabel, 0, 0)
        self.__relay_sel = QComboBox()
        self.__relay_sel.setMinimumHeight(30)
        self.__relay_sel.addItem("TX")
        self.__relay_sel.addItem("VNA")
        self.__mangrid.addWidget(self.__relay_sel, 0, 2, 1, 1)
        
        #----------------------------------
        # Get current
        res1label = QLabel('SWR')
        self.__mangrid.addWidget(res1label, 1, 0)
        self.__swrres = QLabel('?.?')
        self.__swrres.setStyleSheet("QLabel {color: rgb(255,100,0); font: 20px}")
        self.__swrres.setMaximumWidth(100)
        self.__mangrid.addWidget(self.__swrres, 1, 2)
        
        res2label = QLabel('Freq')
        res2label.setAlignment(QtCore.Qt.AlignCenter)
        self.__mangrid.addWidget(res2label, 1, 3)
        self.__freqval = QLabel('?.?')
        self.__freqval.setStyleSheet("QLabel {color: rgb(255,100,0); font: 20px}")
        self.__freqval.setMaximumWidth(100)
        self.__mangrid.addWidget(self.__freqval, 1, 4)
        
        self.__getres = QPushButton("Get Current")
        self.__getres.setToolTip('Get current SWR and Frequency...')
        self.__mangrid.addWidget(self.__getres, 1,5)
        self.__getres.clicked.connect(self.__do_res)
        self.__getres.setMinimumHeight(30)
        self.__getres.setMinimumWidth(100)
        self.__getres.setMaximumWidth(100)
        
        #----------------------------------
        # Move position
        movelabel = QLabel('Move to')
        self.__mangrid.addWidget(movelabel, 2, 0)
        self.movetxt = QLineEdit()
        self.movetxt.setToolTip('Move position 0-100%')
        self.movetxt.setInputMask('000;_')
        self.movetxt.setStyleSheet("QLineEdit {color: rgb(255,100,0); font: 20px}")
        self.movetxt.setMaximumWidth(80)
        self.__mangrid.addWidget(self.movetxt, 2, 2)
        
        self.__movepos = QPushButton("Move")
        self.__movepos.setToolTip('Move to given position 0-100%...')
        self.__mangrid.addWidget(self.__movepos, 2,3)
        self.__movepos.clicked.connect(self.__do_pos)
        self.__movepos.setMinimumHeight(30)
        self.__movepos.setMinimumWidth(100)
        self.__movepos.setMaximumWidth(100)
        
        curr1label = QLabel('Current Pos')
        self.__mangrid.addWidget(curr1label, 2, 4)
        self.__currpos = QLabel('???')
        self.__currpos.setStyleSheet("QLabel {color: rgb(255,100,0); font: 20px}")
        self.__currpos.setMaximumWidth(100)
        self.__mangrid.addWidget(self.__currpos, 2, 5)
        
        #----------------------------------
        # Increment
        inclabel = QLabel('Increment ms')
        self.__mangrid.addWidget(inclabel, 3, 0)
        self.inctxt = QLineEdit()
        self.inctxt.setToolTip('Increment time in ms')
        self.inctxt.setInputMask('0000;_')
        self.inctxt.setStyleSheet("QLineEdit {color: rgb(255,100,0); font: 20px}")
        self.inctxt.setMaximumWidth(80)
        self.__mangrid.addWidget(self.inctxt, 3, 2)
        
        self.__movepos = QPushButton("Move")
        self.__movepos.setToolTip('Move to given position 0-100%...')
        self.__mangrid.addWidget(self.__movepos, 3 ,3)
        self.__movepos.clicked.connect(self.__do_pos)
        self.__movepos.setMinimumHeight(30)
        self.__movepos.setMinimumWidth(100)
        self.__movepos.setMaximumWidth(100)
        
        self.__runpos = QPushButton("Move Forward")
        self.__runpos.setToolTip('Move forward for given ms...')
        self.__mangrid.addWidget(self.__runpos, 3,3)
        self.__runpos.clicked.connect(self.__do_move_fwd)
        self.__runpos.setMinimumHeight(30)
        self.__runpos.setMinimumWidth(100)
        self.__runpos.setMaximumWidth(100)
        
        self.__runrev = QPushButton("Move Reverse")
        self.__runrev.setToolTip('Move reverse for given ms...')
        self.__mangrid.addWidget(self.__runrev, 3,4)
        self.__runrev.clicked.connect(self.__do_move_rev)
        self.__runrev.setMinimumHeight(30)
        self.__runrev.setMinimumWidth(100)
        self.__runrev.setMaximumWidth(100)
        
        self.__nudgefwd = QPushButton("Nudge Forward")
        self.__nudgefwd.setToolTip('Nudge forward...')
        self.__mangrid.addWidget(self.__nudgefwd, 3,5)
        self.__nudgefwd.clicked.connect(self.__do_nudge_fwd)
        self.__nudgefwd.setMinimumHeight(30)
        self.__nudgefwd.setMinimumWidth(100)
        self.__nudgefwd.setMaximumWidth(100)
        
        self.__nudgerev = QPushButton("Nudge Reverse")
        self.__nudgerev.setToolTip('Nudge reverse...')
        self.__mangrid.addWidget(self.__nudgerev, 3,6)
        self.__nudgerev.clicked.connect(self.__do_nudge_rev)
        self.__nudgerev.setMinimumHeight(30)
        self.__nudgerev.setMinimumWidth(100)
        self.__nudgerev.setMaximumWidth(100)
        
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
        loop = int(self.__loop_sel.currentText())
        if self.__api.calibrate(loop):
            if loop == 1:
                self.__l1label.setStyleSheet("QLabel {color: rgb(0,255,0); font: 12px}")
                self.__loop_status[0] = True
            elif loop == 2:
                self.__l2label.setStyleSheet("QLabel {color: rgb(0,255,0); font: 12px}")
                self.__loop_status[1] = True
            elif loop == 3:
                self.__l3label.setStyleSheet("QLabel {color: rgb(0,255,0); font: 12px}")
                self.__loop_status[2] = True
    
    def __do_tune(self):
        loop = int(self.__loop_sel.currentText())
        freq = self.freqtxt.displayText()
        self.__api.move_to_freq(loop, freq)
    
    def __do_res(self):
        pos = self.__api.get_pos()
        self.__currpos.setText(str(pos))
    
    def __do_pos(self):
        self.__api.move_to_position(self.movetxt.displayText())
    
    def __do_move_fwd(self):
        self.__api.move_fwd(self.inctxt.displayText())
    
    def __do_move_rev(self):
        self.__api.move_rev(self.inctxt.displayText())
    
    def __do_nudge_fwd(self):
        self.__api.nudge_fwd()
    
    def __do_nudge_rev(self):
        self.__api.nudge_rev()

    #=======================================================
    # Background activities
    def __idleProcessing(self):
        
        # Update current position
        pos = self.__api.get_pos()
        self.__currpos.setText(str(pos))
        
        # Update loop status
        if self.__loop_status[0]:
            self.__l1label.setStyleSheet("QLabel {color: rgb(0,255,0); font: 12px}")
        elif self.__loop_status[1]:
            self.__l2label.setStyleSheet("QLabel {color: rgb(0,255,0); font: 12px}")
        elif self.__loop_status[2]:
            self.__l3label.setStyleSheet("QLabel {color: rgb(0,255,0); font: 12px}")
                
        # Reset timer
        QtCore.QTimer.singleShot(IDLE_TICKER, self.__idleProcessing)
        