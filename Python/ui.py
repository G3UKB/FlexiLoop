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

# Styles
BOXSTYLE = "QGroupBox {color: rgb(65,62,56); font: 16px}"
PBSTYLE = "QPushButton {min-height: 20px; min-width: 100px; background-color: rgb(131,124,114); color: rgb(24,74,101); border-style: outset; border-width: 1px; border-radius: 5px; font: 14px}"
DDSTYLE = "QComboBox {background-color: rgb(131,124,114); color: rgb(24,74,101); border-style: outset; border-width: 1px; border-radius: 5px; font: 14px}"
SBSTYLE = "QSpinBox {min-height: 20px; background-color: rgb(131,124,114); color: rgb(24,74,101); border-style: outset; border-width: 1px; border-radius: 5px; font: 14px}"
LESTYLE = "QLineEdit {min-height: 25px; background-color: rgb(131,124,114); color: rgb(24,74,101); border-style: outset; border-width: 1px; border-radius: 5px; font: 20px}"
LBL1STYLE = "QLabel {color: rgb(24,74,101); font: 14px}"
LBLSTSTYLE = "QLabel {color: rgb(191,13,13); font: 14px}"
LBLSTACSTYLE = "QLabel {color: rgb(33,82,3); font: 14px}"
ABORTSTYLEON = "QPushButton {min-height: 20px; min-width: 100px; background-color: rgb(191,13,13); color: rgb(0,0,0); border-style: outset; border-width: 1px; border-radius: 5px; font: 14px}"
ABORTSTYLEOFF = "QPushButton {min-height: 20px; min-width: 100px; background-color: rgb(131,124,114); color: rgb(180,180,180); border-style: outset; border-width: 1px; border-radius: 5px; font: 14px}"
FRAMESTYLE = "QLabel {color: rgb(33,82,3)}"

class VLine(QFrame):
    # a simple VLine, like the one you get from designer
    def __init__(self):
        super(VLine, self).__init__()
        self.setFrameShape(self.VLine|self.Sunken)
        self.setStyleSheet("background-color %s" % 'black')
        
class UI(QMainWindow):
    
    def __init__(self, model, qt_app, port):
        super(UI, self).__init__()

        self.__model = model
        self.__qt_app = qt_app
        
        # Create the API instance
        self.__api = api.API(model, port, self.callback)
        
        #Loop status
        self.__selected_loop = 1
        self.__loop_status = [False, False, False]
    
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
        
        # Local state holders
        # Current (long running) activity
        self.__current_activity = NONE
        self.__long_running = False
        self.__activity_timer = SHORT_TIMEOUT
        # Loop status
        home = self.__model[CONFIG][CAL][HOME]
        maximum = self.__model[CONFIG][CAL][MAX]
        if home != -1 and maximum != -1:
            # Something has been configured
            # Check loops
            if len(self.__model[CONFIG][CAL][CAL_L1]) > 0:
                self.__loop_status[0] = True
            if len(self.__model[CONFIG][CAL][CAL_L2]) > 0:
                self.__loop_status[1] = True
            if len(self.__model[CONFIG][CAL][CAL_L3]) > 0:
                self.__loop_status[2] = True
        # Last actuator position (may not be correct if its been moved outside app)
        pos = self.__model[STATE][ARDUINO][ACT_POS]
        if pos == -1:
            pos = '-'
        self.__current_pos = pos
        # SWR
        self.__swr = '_._'
        
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
    # CALLBACK
    #
    def callback(self, data):
        # We get callbacks here from calibration, tuning and serial comms
        # Everything south of the API is threaded so as not to block
        # the UI. That means event callbacks must be managed to update the UI
        # and prevent invalid commands being issues during long running
        # operations, except for ABORT to stop the current operation.
        #
        # Callback format is:
        #   (command-name, (success, failure-message, [response data for command]))
        #
        # Callbacks are on the thread of the caller and cannot directly call UI methods
        # which must be called on the main thread. Therefore flags are set which are
        # interpreted by the idle time function to manage the UI state.
        # print("UI callback: ", data)
        
        # Are we waiting for an activity to complete
        if self.__current_activity == NONE:
            self.__activity_timer = SHORT_TIMEOUT
        else:
            # Activity in progress
            self.__activity_timer -= 1
            if self.__activity_timer <= 0:
                print ('Timed out waiting for activity %s to complete. Maybe the Arduino has gone off-line!' % (self.__current_activity))
                self.__current_activity == NONE
                self.__activity_timer = SHORT_TIMEOUT
                return
            
            # Get current event data
            (name, (success, msg, args)) = data
            if name == self.__current_activity:
                if success:
                    # Action any data
                    if name == 'Pos':
                        # Update position
                        self.__current_pos = args[0]
                    elif name == CALIBRATE:
                        # Update the loop status
                        if self.__selected_loop != -1:
                            self.__loop_status[self.__selected_loop-1] = True
                    elif name == TUNE:
                        self.__swr = args[0]
                    print ('Activity %s completed successfully' % (self.__current_activity))
                    self.__current_activity = NONE
                    self.__activity_timer = SHORT_TIMEOUT
                else:
                    print ('Activity %s completed but failed!' % (self.__current_activity))
            elif name == STATUS:
                # We expect status at any time
                self.__current_pos = args[0]
                self.__model[STATE][ARDUINO][ACT_POS] = self.__current_pos
            elif name == ABORT:
                # User hit the abort button
                self.__current_activity = NONE
                self.__activity_timer = SHORT_TIMEOUT
                print("Activity aborted by user!")
            else:
                print ('Waiting for activity %s to completed but got activity %s! Contibuing to wait' % (self.__current_activity, name))
                
    #=======================================================
    # PRIVATE
    #
    # Basic initialisation
    def __initUI(self):
        
        # Arrange window
        x,y,w,h = self.__model[STATE][WINDOWS][MAIN_WIN]
        self.setGeometry(x,y,w,h)
                         
        self.setWindowTitle('Flexi-Loop Controller')
        
        #======================================================================================
        # Configure the status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
        # Arduino status
        self.st_lbl = QLabel()
        self.st_lbl.setText('Arduino: ')
        self.st_lbl.setStyleSheet(LBL1STYLE)
        self.statusBar.addPermanentWidget(self.st_lbl)
        self.__st_ard = QLabel()
        self.__st_ard.setText('off-line')
        self.__st_ard.setStyleSheet(LBLSTSTYLE)
        self.statusBar.addPermanentWidget(self.__st_ard)
        
        self.statusBar.addPermanentWidget(VLine())

        # Activity Status
        self.st_lblact= QLabel()
        self.st_lblact.setText('Activity: ')
        self.st_lblact.setStyleSheet(LBL1STYLE)
        self.statusBar.addPermanentWidget(self.st_lblact)
        self.__st_act = QLabel()
        self.__st_act.setText(NONE)
        self.__st_act.setStyleSheet(LBLSTSTYLE)
        self.statusBar.addPermanentWidget(self.__st_act)
        
        self.statusBar.addPermanentWidget(VLine())
        
        # Buttons
        self.__abort = QPushButton("Abort!")
        self.__abort.setStyleSheet(ABORTSTYLEOFF)
        self.__abort.setToolTip('Abort the current operation!')
        self.__abort.clicked.connect(self.__do_abort)
        self.statusBar.addPermanentWidget(self.__abort)
        #self.__abort.setVisible(False)
        
        self.statusBar.addPermanentWidget(VLine())
        
        self.__exit = QPushButton("Close")
        self.__exit.setStyleSheet(PBSTYLE)
        self.__exit.setToolTip('Close the application')
        self.__exit.clicked.connect(self.__do_close)
        self.statusBar.addPermanentWidget(self.__exit)
        
        self.statusBar.setStyleSheet("QStatusBar::item{border: none;}")       
        
    #=======================================================
    # Create all widgets
    def __populate(self):
        #=======================================================
        # Set main layout
        self.__central_widget = QWidget()
        self.setCentralWidget(self.__central_widget)
        self.__grid = QGridLayout()
        self.__central_widget.setLayout(self.__grid)
        
        # -------------------------------------------
        # Loop area
        self.__loopgrid = QGridLayout()
        w1 = QGroupBox('Loop')
        w1.setStyleSheet(BOXSTYLE)
        w1.setLayout(self.__loopgrid)
        self.__grid.addWidget(w1, 0,0,1,4)
        
        looplabel = QLabel('Select Loop')
        looplabel.setStyleSheet(LBL1STYLE)
        self.__loopgrid.addWidget(looplabel, 0, 0)
        self.__loop_sel = QComboBox()
        self.__loop_sel.setStyleSheet(DDSTYLE)
        self.__loop_sel.addItem("1")
        self.__loop_sel.addItem("2")
        self.__loop_sel.addItem("3")
        self.__loop_sel.setMinimumHeight(30)
        self.__loopgrid.addWidget(self.__loop_sel, 0,1)
        self.__loop_sel.currentIndexChanged.connect(self.__loop_change)
        
        minlabel = QLabel('Min freq')
        minlabel.setStyleSheet(LBL1STYLE)
        self.__loopgrid.addWidget(minlabel, 0, 2)
        minlabel.setAlignment(QtCore.Qt.AlignCenter)
        self.__minvalue = QLabel('0.0')
        self.__minvalue.setAlignment(QtCore.Qt.AlignCenter)
        self.__minvalue.setStyleSheet("QLabel {color: rgb(65,62,56); font: 20px}")
        self.__loopgrid.addWidget(self.__minvalue, 0, 3)
        maxlabel = QLabel('Max freq')
        maxlabel.setStyleSheet(LBL1STYLE)
        self.__loopgrid.addWidget(maxlabel, 0, 4)
        maxlabel.setAlignment(QtCore.Qt.AlignCenter)
        self.__maxvalue = QLabel('0.0')
        self.__maxvalue.setAlignment(QtCore.Qt.AlignCenter)
        self.__maxvalue.setStyleSheet("QLabel {color: rgb(65,62,56); font: 20px}")
        self.__loopgrid.addWidget(self.__maxvalue, 0, 5)
        
        self.__cal = QPushButton("(Re)Calibrate...")
        self.__cal.setStyleSheet(PBSTYLE)
        self.__cal.setToolTip('Calibrate for loop...')
        self.__loopgrid.addWidget(self.__cal, 1, 0)
        self.__cal.clicked.connect(self.__do_cal)
        
        s = QGroupBox('Status')
        s.setStyleSheet("QGroupBox {color: rgb(65,62,56); font: 14px}")
        hbox = QHBoxLayout()
        self.__l1label = QLabel('Loop-1')
        hbox.addWidget(self.__l1label)
        self.__l1label.setStyleSheet(LBLSTSTYLE)
        self.__l1label.setAlignment(QtCore.Qt.AlignCenter)
        self.__l2label = QLabel('Loop-2')
        hbox.addWidget(self.__l2label)
        self.__l2label.setStyleSheet(LBLSTSTYLE)
        self.__l2label.setAlignment(QtCore.Qt.AlignCenter)
        self.__l3label = QLabel('Loop-3')
        hbox.addWidget(self.__l3label)
        self.__l3label.setStyleSheet(LBLSTSTYLE)
        self.__l3label.setAlignment(QtCore.Qt.AlignCenter)
        s.setLayout(hbox)
        self.__loopgrid.addWidget(s, 1, 1, 1, 3)
        
        # -------------------------------------------
        # Auto area
        self.__autogrid = QGridLayout()
        w2 = QGroupBox('Auto')
        w2.setStyleSheet(BOXSTYLE)
        w2.setLayout(self.__autogrid)
        self.__grid.addWidget(w2, 1,0,1,4)
        self.__autogrid.setColumnMinimumWidth(5,300)
        
        freqlabel = QLabel('Freq')
        freqlabel.setStyleSheet(LBL1STYLE)
        self.__autogrid.addWidget(freqlabel, 0, 0)
        self.freqtxt = QLineEdit()
        self.freqtxt.setStyleSheet(LESTYLE)
        self.freqtxt.setToolTip('Set tune frequency')
        self.freqtxt.setInputMask('000.000;0')
        self.freqtxt.setMaximumWidth(80)
        self.__autogrid.addWidget(self.freqtxt, 0, 1)
        
        swrlabel = QLabel('SWR')
        swrlabel.setStyleSheet(LBL1STYLE)
        self.__autogrid.addWidget(swrlabel, 0, 2)
        swrlabel.setAlignment(QtCore.Qt.AlignCenter)
        self.__swrval = QLabel('-.-')
        self.__swrval.setStyleSheet("QLabel {color: rgb(65,62,56); font: 20px}")
        self.__autogrid.addWidget(self.__swrval, 0, 3)
        
        self.__tune = QPushButton("Tune...")
        self.__tune.setStyleSheet(PBSTYLE)
        self.__tune.setToolTip('Tune to freq...')
        self.__autogrid.addWidget(self.__tune, 0,4)
        self.__tune.clicked.connect(self.__do_tune)
        
        # -------------------------------------------
        # Manual area
        self.__mangrid = QGridLayout()
        w3 = QGroupBox('Manual')
        w3.setStyleSheet(BOXSTYLE)
        w3.setLayout(self.__mangrid)
        self.__grid.addWidget(w3, 2,0,1,4)
        
        #----------------------------------
        # Target select
        relaylabel = QLabel('Select TX/VNA')
        relaylabel.setStyleSheet(LBL1STYLE)
        self.__mangrid.addWidget(relaylabel, 0, 0)
        self.__relay_sel = QComboBox()
        self.__relay_sel.setStyleSheet(DDSTYLE)
        self.__relay_sel.setMinimumHeight(30)
        self.__relay_sel.addItem("TX")
        self.__relay_sel.addItem("VNA")
        self.__mangrid.addWidget(self.__relay_sel, 0, 2, 1, 1)
        
        #----------------------------------
        # Get current
        res1label = QLabel('SWR')
        res1label.setStyleSheet(LBL1STYLE)
        self.__mangrid.addWidget(res1label, 1, 0)
        self.__swrres = QLabel('-.-')
        self.__swrres.setStyleSheet("QLabel {color: rgb(65,62,56); font: 20px}")
        self.__swrres.setMaximumWidth(100)
        self.__mangrid.addWidget(self.__swrres, 1, 2)
        
        res2label = QLabel('Freq')
        res2label.setStyleSheet(LBL1STYLE)
        res2label.setAlignment(QtCore.Qt.AlignCenter)
        self.__mangrid.addWidget(res2label, 1, 3)
        self.__freqval = QLabel('-.-')
        self.__freqval.setStyleSheet("QLabel {color: rgb(65,62,56); font: 20px}")
        self.__freqval.setMaximumWidth(100)
        self.__mangrid.addWidget(self.__freqval, 1, 4)
        
        self.__getres = QPushButton("Get Current")
        self.__getres.setStyleSheet(PBSTYLE)
        self.__getres.setToolTip('Get current SWR and Frequency...')
        self.__mangrid.addWidget(self.__getres, 1,5)
        self.__getres.clicked.connect(self.__do_res)
        
        #----------------------------------
        # Move position
        movelabel = QLabel('Move to (%)')
        movelabel.setStyleSheet(LBL1STYLE)
        self.__mangrid.addWidget(movelabel, 2, 0)
        self.movetxt = QSpinBox()
        self.movetxt.setStyleSheet(SBSTYLE)
        self.movetxt.setToolTip('Move position 0-100%')
        self.movetxt.setRange(0,100)
        self.movetxt.setValue(50)
        self.movetxt.setMaximumWidth(80)
        self.__mangrid.addWidget(self.movetxt, 2, 2)
        
        self.__movepos = QPushButton("Move")
        self.__movepos.setStyleSheet(PBSTYLE)
        self.__movepos.setToolTip('Move to given position 0-100%...')
        self.__mangrid.addWidget(self.__movepos, 2,3)
        self.__movepos.clicked.connect(self.__do_pos)
        
        curr1label = QLabel('Current Pos')
        curr1label.setStyleSheet(LBL1STYLE)
        self.__mangrid.addWidget(curr1label, 2, 4)
        self.__currpos = QLabel('-')
        self.__currpos.setStyleSheet("QLabel {color: rgb(65,62,56); font: 20px}")
        self.__currpos.setMaximumWidth(100)
        self.__mangrid.addWidget(self.__currpos, 2, 5)
        
        #----------------------------------
        # Increment
        inclabel = QLabel('Increment (ms)')
        inclabel.setStyleSheet(LBL1STYLE)
        self.__mangrid.addWidget(inclabel, 3, 0)
        self.inctxt = QSpinBox()
        self.inctxt.setStyleSheet(SBSTYLE)
        self.inctxt.setToolTip('Increment time in ms')
        self.inctxt.setRange(0,1000)
        self.inctxt.setValue(500)
        self.inctxt.setMaximumWidth(80)
        self.__mangrid.addWidget(self.inctxt, 3, 2)
        
        self.__runpos = QPushButton("Move Forward")
        self.__runpos.setStyleSheet(PBSTYLE)
        self.__runpos.setToolTip('Move forward for given ms...')
        self.__mangrid.addWidget(self.__runpos, 3,3)
        self.__runpos.clicked.connect(self.__do_move_fwd)
        
        self.__runrev = QPushButton("Move Reverse")
        self.__runrev.setStyleSheet(PBSTYLE)
        self.__runrev.setToolTip('Move reverse for given ms...')
        self.__mangrid.addWidget(self.__runrev, 3,4)
        self.__runrev.clicked.connect(self.__do_move_rev)
        
        self.__nudgefwd = QPushButton("Nudge Forward")
        self.__nudgefwd.setStyleSheet(PBSTYLE)
        self.__nudgefwd.setToolTip('Nudge forward...')
        self.__mangrid.addWidget(self.__nudgefwd, 3,5)
        self.__nudgefwd.clicked.connect(self.__do_nudge_fwd)
        
        self.__nudgerev = QPushButton("Nudge Reverse")
        self.__nudgerev.setStyleSheet(PBSTYLE)
        self.__nudgerev.setToolTip('Nudge reverse...')
        self.__mangrid.addWidget(self.__nudgerev, 3,6)
        self.__nudgerev.clicked.connect(self.__do_nudge_rev)
        
    #=======================================================
    # Window events
    def closeEvent(self, event):
        self.__close()
    
    def __close(self):
        self.__api.terminate()

    def resizeEvent(self, event):
        # Update config
        x,y,w,h = self.__model[STATE][WINDOWS][MAIN_WIN]
        self.__model[STATE][WINDOWS][MAIN_WIN] = [x,y,event.size().width(),event.size().height()]
        
    def moveEvent(self, event):
        # Update config
        x,y,w,h = self.__model[STATE][WINDOWS][MAIN_WIN]
        self.__model[STATE][WINDOWS][MAIN_WIN] = [event.pos().x(),event.pos().y(),w,h]
     
    #=======================================================
    # Button events
    def __do_close(self):
        self.__close()
        self.__qt_app.quit()
        
    def __do_abort(self):
        self.__api.abort_activity()
    
    def __do_cal(self):
        loop = int(self.__loop_sel.currentText())
        self.__selected_loop = loop
        self.__current_activity = CALIBRATE
        self.__activity_timer = CALIBRATE_TIMEOUT
        self.__st_act.setText(CALIBRATE)
        self.__long_running = True
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
        freq = float(self.freqtxt.displayText())
        self.__st_act.setText(TUNE)
        self.__current_activity = TUNE
        self.__activity_timer = TUNE_TIMEOUT
        self.__long_running = True
        self.__api.move_to_freq(loop, freq)
    
    def __do_res(self):
        self.__current_activity = RESONANCE
        self.__st_act.setText(RESONANCE)
        self.__activity_timer = RES_TIMEOUT
        self.__api.get_current_res()
    
    def __do_pos(self):
        self.__current_activity = MOVETO
        self.__st_act.setText(MOVETO)
        self.__activity_timer = MOVE_TIMEOUT
        self.__long_running = True
        self.__api.move_to_position(self.movetxt.value())
    
    def __do_move_fwd(self):
        self.__current_activity = MSFWD
        self.__st_act.setText(MSFWD)
        self.__activity_timer = SHORT_TIMEOUT
        self.__api.move_fwd_for_ms(self.inctxt.value())
    
    def __do_move_rev(self):
        self.__current_activity = MSREV
        self.__st_act.setText(MSREV)
        self.__activity_timer = SHORT_TIMEOUT
        self.__api.move_rev_for_ms(self.inctxt.value())
    
    def __do_nudge_fwd(self):
        self.__current_activity = NUDGEFWD
        self.__st_act.setText(NUDGEFWD)
        self.__activity_timer = SHORT_TIMEOUT
        self.__api.nudge_fwd()
    
    def __do_nudge_rev(self):
        self.__current_activity = NUDGEREV
        self.__st_act.setText(NUDGEREV)
        self.__activity_timer = SHORT_TIMEOUT
        self.__api.nudge_rev()

    #=======================================================
    # Combo box events
    def __loop_change(self, index):
        # Set loop selection needed by the callback as it cant access widgets
        # Index is zero based, loops are 1 based
        self.__selected_loop = index + 1
        # Set the min/max frequencies
        loop = self.__model_for_loop(self.__selected_loop)
        if len(loop) > 0:
            self.__minvalue.setText(str(loop[0]))
            self.__maxvalue.setText(str(loop[1]))
        else:
            self.__minvalue.setText('0.0')
            self.__maxvalue.setText('0.0')
        
    #=======================================================
    # Background activities
    def __idleProcessing(self):
        # Here we update the UI according to current activity and the status set by the callback
        if self.__model[STATE][ARDUINO][ONLINE]:
            # on-line indicator
            self.__st_ard.setText('on-line')
            self.__st_ard.setStyleSheet(LBLSTACSTYLE)
            self.__central_widget.setEnabled(True)
            
            # Update current position
            self.__currpos.setText(str(self.__current_pos) + '%')
              
            # Check activity state
            if self.__current_activity != NONE:
                # Activity current
                self.__central_widget.setEnabled(False)
                if self.__long_running:
                    self.__abort.setStyleSheet(ABORTSTYLEON)
            else:
                self.__central_widget.setEnabled(True)
                self.__long_running = False
                self.__abort.setStyleSheet(ABORTSTYLEOFF)
            self.__st_act.setText(self.__current_activity)
        else:
            # Not online so we can't do anything except exit
            self.__central_widget.setEnabled(False)
            # off-line indicator
            self.__st_ard.setText('off-line')
            self.__st_ard.setStyleSheet(LBLSTSTYLE)
        
        # Update loop status for configured loops
        if self.__loop_status[0]:
            self.__l1label.setStyleSheet(LBLSTACSTYLE)
        if self.__loop_status[1]:
            self.__l2label.setStyleSheet(LBLSTACSTYLE)
        if self.__loop_status[2]:
            self.__l3label.setStyleSheet(LBLSTACSTYLE)
        # Update min/max frequencies
        loop = self.__model_for_loop(self.__selected_loop)
        if len(loop) > 0:
            self.__minvalue.setText(str(loop[1]))
            self.__maxvalue.setText(str(loop[0]))
        # Update SWR
        self.__swrval.setText(str(self.__swr))
            
        # Reset timer
        QtCore.QTimer.singleShot(IDLE_TICKER, self.__idleProcessing)
 
    #=======================================================
    # Utils
    def __model_for_loop(self, loop):
        
        if loop == 1:
            return self.__model[CONFIG][CAL][CAL_L1]
        elif loop == 2:
            return self.__model[CONFIG][CAL][CAL_L2]
        elif loop == 3:
            return self.__model[CONFIG][CAL][CAL_L3]
        else:
            return []
            