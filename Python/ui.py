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
import logging
import queue

# PyQt5 imports
from PyQt5.QtWidgets import QMainWindow, QApplication, QToolTip
from PyQt5.QtGui import QPainter, QPainterPath, QColor, QPen, QFont
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QStatusBar, QTableWidget, QInputDialog, QFrame, QGroupBox, QListWidget, QMessageBox, QLabel, QSlider, QLineEdit, QTextEdit, QComboBox, QPushButton, QCheckBox, QRadioButton, QSpinBox, QAction, QWidget, QGridLayout, QHBoxLayout, QTableWidgetItem

# Application imports
from defs import *
from utils import *
import api
import config
import setpoints

# Vertical line
class VLine(QFrame):
    # A simple VLine, like the one you get from designer
    def __init__(self):
        super(VLine, self).__init__()
        self.setFrameShape(self.VLine|self.Sunken)
        self.setObjectName("maninner")

# Main window        
class UI(QMainWindow):
    
    def __init__(self, model, qt_app, port):
        super(UI, self).__init__()

        # Get root logger
        self.logger = logging.getLogger('root')
        
        # Create message q
        self.__msgq = queue.Queue(100)
        
        self.__model = model
        self.__qt_app = qt_app
        
        # Create the API instance
        self.__api = api.API(model, port, self.callback, self.msg_callback)
        self.__api.init_comms()
        
        # Create the config dialog
        self.__config_dialog = config.Config(self.__model, self.msg_callback)
        
        # Create the setpoint dialog
        self.__sp_dialog = setpoints.Setpoint(self.__model, self.msg_callback)
        
        #Loop status
        self.__selected_loop = 1
        self.__loop_status = [False, False, False]
        self.__last_widget_status = None
    
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
        self.__free_running = False
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT]*(1000/IDLE_TICKER)
        self.__switch_mode = TX
        self.__last_switch_mode= self.__switch_mode
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
        self.__auto_swr = '_._'
        self.__man_swr = '_._'
        
        # Default to TX side
        self.__relay_state = TX
        
        # Manual calibration status
        self.__man_hint = MAN_NONE
        self.__man_cal_state = MANUAL_IDLE
        self.__man_cal_freq = 0.0
        self.__man_cal_swr = 1.0
        
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
    # CALLBACKS
    #
    # Note this can be called from any thread to output messages to the transcript
    def msg_callback(self, data, msgtype=MSG_INFO):
        self.__msgq.put((data, msgtype))
    
    # This is called when doing a manual calibration to set the hint and get the next data items.
    # This is called on the calibration thread so will not interrupt the UI
    def man_cal_callback(self, hint):
        # We set the hint and set data required flag and wait for the state to go to data available
        self.__man_cal_state = MANUAL_DATA_REQD
        while self.__man_cal_state != MANUAL_DATA_AVAILABLE:
            sleep (0.2)
        r = (self.__man_cal_freq, self.__man_cal_swr)
        self.__man_cal_freq = 0.0
        self.__man_cal_swr = 1.0
        while self.__man_cal_state != MANUAL_NEXT:
            sleep (0.2)
        self.__man_cal_state = MANUAL_IDLE
        return r    
        
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
            self.__activity_timer = self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT]*(1000/IDLE_TICKER)
        else:
            # Activity in progress
            self.__activity_timer -= 1
            if self.__activity_timer <= 0:
                self.logger.info ('Timed out waiting for activity %s to complete. Maybe the Arduino has gone off-line!' % (self.__current_activity))
                self.__current_activity == NONE
                self.__activity_timer = self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT]*(1000/IDLE_TICKER)
                return
            
            # Get current event data
            (name, (success, msg, args)) = data
            if name == self.__current_activity:
                if success:
                    # Action any data
                    if name == POS:
                        # Update position
                        self.__current_pos = args[0]
                    elif name == CALIBRATE:
                        # Update the loop status
                        if self.__selected_loop != -1:
                            self.__loop_status[self.__selected_loop-1] = True
                    elif name == TUNE:
                        self.__swr = args[0]
                    self.logger.info ('Activity %s completed successfully' % (self.__current_activity))
                    self.__current_activity = NONE
                    self.__activity_timer = self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT]*(1000/IDLE_TICKER)
                else:
                    self.logger.info ('Activity %s completed but failed!' % (self.__current_activity))
            elif name == STATUS:
                # We expect status at any time
                self.__current_pos = args[0]
                self.__model[STATE][ARDUINO][ACT_POS] = self.__current_pos
            elif name == ABORT:
                # User hit the abort button
                self.__current_activity = NONE
                self.__activity_timer = self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT]*(1000/IDLE_TICKER)
                self.logger.info("Activity aborted by user!")
            else:
                self.logger.info ('Waiting for activity %s to completed but got activity %s! Continuing to wait' % (self.__current_activity, name))
                
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
        
        # VNA status
        self.st_lb0 = QLabel()
        self.st_lb0.setText('VNA: ')
        self.statusBar.addPermanentWidget(self.st_lb0)
        self.__st_vna = QLabel()
        if self.__model[CONFIG][VNA_CONF][VNA_PRESENT] == VNA_YES:
            self.__st_vna.setText('present')
            self.__st_vna.setObjectName("stgreen")
        else:
            self.__st_vna.setText('absent')
            self.__st_vna.setObjectName("stred")
        self.__st_vna.setStyleSheet(self.__st_vna.styleSheet())
        self.statusBar.addPermanentWidget(self.__st_vna)
        
        self.statusBar.addPermanentWidget(VLine())
        
        # Arduino status
        self.st_lbl = QLabel()
        self.st_lbl.setText('Arduino: ')
        self.statusBar.addPermanentWidget(self.st_lbl)
        self.__st_ard = QLabel()
        self.__st_ard.setText('off-line')
        self.__st_ard.setObjectName("stred")
        self.__st_ard.setStyleSheet(self.__st_ard.styleSheet())
        self.statusBar.addPermanentWidget(self.__st_ard)
        
        self.statusBar.addPermanentWidget(VLine())

        # Target status
        self.tg_lbl = QLabel()
        self.tg_lbl.setText('Target: ')
        self.statusBar.addPermanentWidget(self.tg_lbl)
        self.__tg_ard = QLabel()
        self.__tg_ard.setText('TX')
        self.__tg_ard.setObjectName("stred")
        self.__tg_ard.setStyleSheet(self.__tg_ard.styleSheet())
        self.statusBar.addPermanentWidget(self.__tg_ard)
        
        self.statusBar.addPermanentWidget(VLine())
        
        # Activity Status
        self.st_lblact= QLabel()
        self.st_lblact.setText('Activity: ')
        self.statusBar.addPermanentWidget(self.st_lblact)
        self.__st_act = QLabel()
        self.__st_act.setText(NONE)
        self.__st_act.setObjectName("stred")
        self.__st_act.setStyleSheet(self.__st_act.styleSheet())
        self.statusBar.addPermanentWidget(self.__st_act)
        
        self.statusBar.addPermanentWidget(VLine())
        
        # Buttons
        self.__abort = QPushButton("Abort!")
        self.__abort.setEnabled(False)
        self.__abort.setObjectName("abort")
        self.__abort.setToolTip('Abort the current operation!')
        self.__abort.clicked.connect(self.__do_abort)
        self.__abort.setMinimumHeight(20)
        self.statusBar.addPermanentWidget(self.__abort)
        
        self.statusBar.addPermanentWidget(VLine())
        
        self.__exit = QPushButton("Close")
        self.__exit.setToolTip('Close the application')
        self.__exit.clicked.connect(self.__do_close)
        self.__exit.setMinimumHeight(20)
        self.statusBar.addPermanentWidget(self.__exit)       
        
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
        # Menu type area
        self.__menugrid = QGridLayout()
        wmen = QGroupBox('')
        wmen.setLayout(self.__menugrid)
        self.__grid.addWidget(wmen, 0,0,1,4)
        
        self.__config = QPushButton("Config")
        self.__config.setEnabled(True)
        self.__config.setToolTip('Manage configuration...')
        self.__config.clicked.connect(self.__do_config)
        self.__config.setMinimumHeight(20)
        self.__menugrid.addWidget(self.__config, 0,0)
        
        # -------------------------------------------
        # Loop area
        self.__loopgrid = QGridLayout()
        w1 = QGroupBox('Loop')
        w1.setLayout(self.__loopgrid)
        self.__grid.addWidget(w1, 1,0,1,4)
        
        looplabel = QLabel('Select Loop')
        self.__loopgrid.addWidget(looplabel, 0, 0)
        self.__loop_sel = QComboBox()
        self.__loop_sel.addItem("1")
        self.__loop_sel.addItem("2")
        self.__loop_sel.addItem("3")
        self.__loop_sel.setMinimumHeight(20)
        self.__loopgrid.addWidget(self.__loop_sel, 0,1)
        self.__loop_sel.currentIndexChanged.connect(self.__loop_change)
        
        minlabel = QLabel('Min freq')
        self.__loopgrid.addWidget(minlabel, 0, 2)
        minlabel.setAlignment(QtCore.Qt.AlignCenter)
        self.__minvalue = QLabel('0.0')
        self.__minvalue.setAlignment(QtCore.Qt.AlignCenter)
        self.__minvalue.setObjectName("minmax")
        self.__loopgrid.addWidget(self.__minvalue, 0, 3)
        maxlabel = QLabel('Max freq')
        self.__loopgrid.addWidget(maxlabel, 0, 4)
        maxlabel.setAlignment(QtCore.Qt.AlignCenter)
        self.__maxvalue = QLabel('0.0')
        self.__maxvalue.setAlignment(QtCore.Qt.AlignCenter)
        self.__maxvalue.setObjectName("minmax")
        self.__loopgrid.addWidget(self.__maxvalue, 0, 5)
        
        # Calibration
        self.__cal = QPushButton("(Re)Calibrate...")
        self.__cal.setToolTip('Calibrate for loop...')
        self.__loopgrid.addWidget(self.__cal, 1, 0)
        self.__cal.clicked.connect(self.__do_cal)
        
        self.__calview = QPushButton("...")
        self.__calview.setToolTip('View calibrations')
        self.__calview.setObjectName("view")
        self.__loopgrid.addWidget(self.__calview, 1, 1)
        self.__calview.clicked.connect(self.__do_cal_view)
        
        s = QGroupBox('Calibrate Status')
        hbox = QHBoxLayout()
        self.__l1label = QLabel('Loop-1')
        hbox.addWidget(self.__l1label)
        self.__l1label.setObjectName("stred")
        self.__l1label.setStyleSheet(self.__l1label.styleSheet())
        self.__l1label.setAlignment(QtCore.Qt.AlignCenter)
        self.__l2label = QLabel('Loop-2')
        hbox.addWidget(self.__l2label)
        self.__l2label.setObjectName("stred")
        self.__l2label.setStyleSheet(self.__l2label.styleSheet())
        self.__l2label.setAlignment(QtCore.Qt.AlignCenter)
        self.__l3label = QLabel('Loop-3')
        hbox.addWidget(self.__l3label)
        self.__l3label.setObjectName("stred")
        self.__l3label.setStyleSheet(self.__l3label.styleSheet())
        self.__l3label.setAlignment(QtCore.Qt.AlignCenter)
        s.setLayout(hbox)
        self.__loopgrid.addWidget(s, 1, 2, 1, 3)
        
        # Set points
        self.__sp = QPushButton("Setpoints...")
        self.__sp.setToolTip('Manage setpoints for loop...')
        self.__loopgrid.addWidget(self.__sp, 1, 5)
        self.__sp.clicked.connect(self.__do_sp)
        
        sps = QGroupBox('Setpoint Status')
        hbox1 = QHBoxLayout()
        self.__l4label = QLabel('Loop-1')
        hbox1.addWidget(self.__l4label)
        self.__l4label.setObjectName("stred")
        self.__l4label.setStyleSheet(self.__l4label.styleSheet())
        self.__l4label.setAlignment(QtCore.Qt.AlignCenter)
        self.__l5label = QLabel('Loop-2')
        hbox1.addWidget(self.__l5label)
        self.__l5label.setObjectName("stred")
        self.__l5label.setStyleSheet(self.__l5label.styleSheet())
        self.__l5label.setAlignment(QtCore.Qt.AlignCenter)
        self.__l6label = QLabel('Loop-3')
        hbox1.addWidget(self.__l6label)
        self.__l6label.setObjectName("stred")
        self.__l6label.setStyleSheet(self.__l6label.styleSheet())
        self.__l6label.setAlignment(QtCore.Qt.AlignCenter)
        sps.setLayout(hbox1)
        self.__loopgrid.addWidget(sps, 1, 6, 1, 3)
        
        # If no VNA we can put up the manual calibration box
        self.__manualcal = QGroupBox('Manual Input')
        manualgrid = QGridLayout()
        self.__manualcal.setLayout(manualgrid)
        
        gap = QWidget()
        manualgrid.addWidget(gap, 0, 0)
        
        # Data entry
        freqlabel = QLabel('Freq')
        manualgrid.addWidget(freqlabel, 0, 1)
        self.__manfreqtxt = QLineEdit()
        self.__manfreqtxt.setInputMask('000.000;0')
        self.__manfreqtxt.setToolTip('Resonant frequency')
        self.__manfreqtxt.setMaximumWidth(80)
        manualgrid.addWidget(self.__manfreqtxt, 0, 2)
        
        swrlabel = QLabel('SWR')
        manualgrid.addWidget(swrlabel, 0, 3)
        self.__manswrtxt = QLineEdit()
        self.__manswrtxt.setInputMask('0.0;0')
        self.__manswrtxt.setToolTip('SWR at resonance')
        self.__manswrtxt.setMaximumWidth(80)
        manualgrid.addWidget(self.__manswrtxt, 0, 4)
        
        gap = QWidget()
        manualgrid.addWidget(gap, 0, 5)
        
        # Button area
        self.__save = QPushButton("Save")
        self.__save.setToolTip('Use the current values for this calibration point')
        self.__save.clicked.connect(self.__do_man_save)
        self.__save.setMinimumHeight(20)
        manualgrid.addWidget(self.__save, 0, 6)
        
        self.__next = QPushButton("Next")
        self.__next.setToolTip('Move to next calibration point')
        self.__next.clicked.connect(self.__do_man_next)
        self.__next.setMinimumHeight(20)
        manualgrid.addWidget(self.__next, 0, 7)
        
        self.__loopgrid.addWidget(self.__manualcal, 2, 0, 1, 8)
        
        # Space out
        manualgrid.setColumnStretch(0, 1)
        manualgrid.setColumnStretch(5, 2)
        
        # Unhide for testing
        self.__manualcal.hide()
        
        # -------------------------------------------
        # Auto area
        self.__autogrid = QGridLayout()
        w2 = QGroupBox('Auto')
        w2.setLayout(self.__autogrid)
        self.__grid.addWidget(w2, 2,0,1,4)
        self.__autogrid.setColumnMinimumWidth(5,300)
        
        freqlabel = QLabel('Freq')
        self.__autogrid.addWidget(freqlabel, 0, 0)
        self.__freqtxt = QLineEdit()
        self.__freqtxt.setToolTip('Set tune frequency')
        self.__freqtxt.setInputMask('000.000;0')
        self.__freqtxt.setMaximumWidth(80)
        self.__autogrid.addWidget(self.__freqtxt, 0, 1)
        
        swrlabel = QLabel('SWR')
        self.__autogrid.addWidget(swrlabel, 0, 2)
        swrlabel.setAlignment(QtCore.Qt.AlignCenter)
        self.__auto_swrval = QLabel('-.-')
        self.__auto_swrval.setObjectName("minmax")
        self.__autogrid.addWidget(self.__auto_swrval, 0, 3)
        
        self.__tune = QPushButton("Tune...")
        self.__tune.setToolTip('Tune to freq...')
        self.__autogrid.addWidget(self.__tune, 0,4)
        self.__tune.clicked.connect(self.__do_tune)
        
        # -------------------------------------------
        # Manual area
        self.__mangrid = QGridLayout()
        w3 = QGroupBox('Manual')
        w3.setLayout(self.__mangrid)
        self.__grid.addWidget(w3, 3,0,1,4)
        
        # Sub grid
        self.__subgrid = QGridLayout()
        w4 = QGroupBox()
        w4.setLayout(self.__subgrid)
        self.__mangrid.addWidget(w4, 0,0,1,6)
        
        #----------------------------------
        # Target select
        relaylabel = QLabel('Target (TX/VNA)')
        self.__subgrid.addWidget(relaylabel, 0, 0)
        self.__relay_sel = QComboBox()
        self.__relay_sel.setMinimumHeight(20)
        self.__relay_sel.setMaximumWidth(70)
        self.__relay_sel.setMinimumWidth(70)
        self.__relay_sel.addItem("TX")
        self.__relay_sel.addItem("VNA")
        self.__subgrid.addWidget(self.__relay_sel, 0, 1)
        self.__relay_sel.currentIndexChanged.connect(self.__relay_change)
        
        speedlabel = QLabel('Speed')
        self.__subgrid.addWidget(speedlabel, 0, 2)
        self.__speed_sel = QComboBox()
        self.__speed_sel.setMinimumHeight(20)
        self.__speed_sel.setMaximumWidth(70)
        self.__speed_sel.setMinimumWidth(70)
        self.__speed_sel.addItem("Slow")
        self.__speed_sel.addItem("Med")
        self.__speed_sel.addItem("Fast")
        self.__subgrid.addWidget(self.__speed_sel, 0, 3)
        self.__speed_sel.currentIndexChanged.connect(self.__speed_change)
        
        self.__runrev = QPushButton("<< Run Rev")
        self.__runrev.setToolTip('Run actuator reverse...')
        self.__subgrid.addWidget(self.__runrev, 0,4)
        self.__runrev.clicked.connect(self.__do_run_rev)
        
        self.__stopact = QPushButton("Stop")
        self.__stopact.setToolTip('Stop actuator')
        self.__subgrid.addWidget(self.__stopact, 0,5)
        self.__stopact.clicked.connect(self.__do_stop_act)
        
        self.__runfwd = QPushButton("Run Fwd >>")
        self.__runfwd.setToolTip('Run actuator forward...')
        self.__subgrid.addWidget(self.__runfwd, 0,6)
        self.__runfwd.clicked.connect(self.__do_run_fwd)    
        
        #----------------------------------
        # Get current
        res1label = QLabel('SWR')
        self.__mangrid.addWidget(res1label, 1, 0)
        self.__swrres = QLabel('-.-')
        self.__swrres.setObjectName("minmax")
        self.__swrres.setMaximumWidth(100)
        self.__mangrid.addWidget(self.__swrres, 1, 1)
        
        res2label = QLabel('Freq')
        self.__mangrid.addWidget(res2label, 1, 2)
        self.__freqval = QLabel('-.-')
        self.__freqval.setObjectName("minmax")
        self.__freqval.setMaximumWidth(100)
        self.__mangrid.addWidget(self.__freqval, 1, 3)
        
        self.__getres = QPushButton("Get Current")
        self.__getres.setToolTip('Get current SWR and Frequency...')
        self.__mangrid.addWidget(self.__getres, 1,4)
        self.__getres.clicked.connect(self.__do_res)
        
        #----------------------------------
        # Move position
        movelabel = QLabel('Move to (%)')
        self.__mangrid.addWidget(movelabel, 2, 0)
        self.__movetxt = QSpinBox()
        self.__movetxt.setToolTip('Move position 0-100%')
        self.__movetxt.setRange(0,100)
        self.__movetxt.setValue(50)
        self.__movetxt.setMaximumWidth(80)
        self.__mangrid.addWidget(self.__movetxt, 2, 1)
        
        self.__movepos = QPushButton("Move")
        self.__movepos.setToolTip('Move to given position 0-100%...')
        self.__mangrid.addWidget(self.__movepos, 2,2)
        self.__movepos.clicked.connect(self.__do_pos)
        
        curr1label = QLabel('Current Pos')
        self.__mangrid.addWidget(curr1label, 2, 3)
        self.__currpos = QLabel('-')
        self.__currpos.setStyleSheet("QLabel {color: rgb(65,62,56); font: 20px}")
        self.__currpos.setMaximumWidth(100)
        self.__mangrid.addWidget(self.__currpos, 2, 4)
        
        #----------------------------------
        # Increment
        inclabel = QLabel('Inc (ms)')
        self.__mangrid.addWidget(inclabel, 3, 0)
        self.__inctxt = QSpinBox()
        self.__inctxt.setToolTip('Increment time in ms')
        self.__inctxt.setRange(0,1000)
        self.__inctxt.setValue(500)
        self.__inctxt.setMaximumWidth(80)
        self.__mangrid.addWidget(self.__inctxt, 3, 1)
        
        self.__mvfwd = QPushButton("Move Forward")
        self.__mvfwd.setToolTip('Move forward for given ms...')
        self.__mangrid.addWidget(self.__mvfwd, 3,2)
        self.__mvfwd.clicked.connect(self.__do_move_fwd)
        
        self.__mvrev = QPushButton("Move Reverse")
        self.__mvrev.setToolTip('Move reverse for given ms...')
        self.__mangrid.addWidget(self.__mvrev, 3,3)
        self.__mvrev.clicked.connect(self.__do_move_rev)
        
        self.__nudgefwd = QPushButton("Nudge Forward")
        self.__nudgefwd.setToolTip('Nudge forward...')
        self.__mangrid.addWidget(self.__nudgefwd, 3,4)
        self.__nudgefwd.clicked.connect(self.__do_nudge_fwd)
        
        self.__nudgerev = QPushButton("Nudge Reverse")
        self.__nudgerev.setToolTip('Nudge reverse...')
        self.__mangrid.addWidget(self.__nudgerev, 3,5)
        self.__nudgerev.clicked.connect(self.__do_nudge_rev)
        
        # Message area
        self.__msglist = QListWidget()
        self.__grid.addWidget(self.__msglist, 4, 0, 1, 4)
        
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
    # Configuration
    def __do_config(self):
        self.__config_dialog.show()
    
    #=======================================================
    # Button events
    def __do_close(self):
        self.__close()
        self.__qt_app.quit()
        
    def __do_abort(self):
        self.__api.abort_activity()
    
    def __do_cal(self):
        manual = False
        # VNA check
        if self.__model[CONFIG][VNA_CONF][VNA_PRESENT] == VNA_NO:
            # No VNA present so we do a manual config
            manual = True
        
        # Switch to auto or manual VNA
        self.__switch_mode = VNA
        # Do the calibrate sequence
        loop = int(self.__loop_sel.currentText())
        self.__selected_loop = loop
        self.__current_activity = CALIBRATE
        print("Set CALIBRATE")
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][CALIBRATE_TIMEOUT]*(1000/IDLE_TICKER)
        self.__st_act.setText(CALIBRATE)
        self.__long_running = True
        if self.__api.calibrate(loop, manual, self.man_cal_callback):
            if loop == 1:
                self.__l1label.setObjectName("stgreen")
                self.__l1label.setStyleSheet(self.__l1label.styleSheet())
                self.__loop_status[0] = True
            elif loop == 2:
                self.__l2label.setObjectName("stgreen")
                self.__l2label.setStyleSheet(self.__l2label.styleSheet())
                self.__loop_status[1] = True
            elif loop == 3:
                self.__l3label.setObjectName("stgreen")
                self.__l3label.setStyleSheet(self.__l3label.styleSheet())
                self.__loop_status[2] = True
        self.__switch_mode = TX
    
    def __do_cal_view(self):
        pass
    
    def __do_sp(self):
        # Invoke the setpoint dialog
        # This allows setting and navigating setpoints.
        self.__sp_dialog.set_loop(self.__selected_loop)
        self.__sp_dialog.show()
    
    def __do_tune(self):
        self.__switch_mode = VNA
        loop = int(self.__loop_sel.currentText())
        freq = float(self.freqtxt.displayText())
        self.__st_act.setText(TUNE)
        self.__current_activity = TUNE
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][TUNE_TIMEOUT]*(1000/IDLE_TICKER)
        self.__long_running = True
        self.__api.move_to_freq(loop, freq)
        self.__switch_mode = TX
        
    def __relay_change(self):
        target = self.__relay_sel.currentText()
        if target == TX:
            self.__set_tx_mode()
        else:
            self.__set_vna_mode()
    
    def __speed_change(self):
        pass
    
    def __do_run_fwd(self):
        self.__current_activity = RUNFWD
        self.__st_act.setText(RUNFWD)
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][MOVE_TIMEOUT]*(1000/IDLE_TICKER)
        self.__free_running = True
        self.__api.free_fwd()
    
    def __do_run_rev(self):
        self.__current_activity = RUNREV
        self.__st_act.setText(RUNREV)
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][MOVE_TIMEOUT]*(1000/IDLE_TICKER)
        self.__free_running = True
        self.__api.free_rev()
    
    def __do_stop_act(self):
        self.__api.free_stop()
    
    def __do_res(self):
        self.__switch_mode = VNA
        self.__tg_ard.setText(VNA)
        self.__relay_sel.setCurrentText(VNA)
        self.__relay_state = VNA
        self.__current_activity = RESONANCE
        self.__st_act.setText(RESONANCE)
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][RES_TIMEOUT]*(1000/IDLE_TICKER)
        r, (f,swr) = self.__api.get_current_res(self.__selected_loop)
        if r:
            self.__freqval.setText(f)
            self.__swrres.setText(swr)
        self.__current_activity = NONE
        self.__switch_mode = TX
    
    def __do_pos(self):
        self.__current_activity = MOVETO
        self.__st_act.setText(MOVETO)
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][MOVE_TIMEOUT]*(1000/IDLE_TICKER)
        self.__long_running = True
        self.__api.move_to_position(self.__movetxt.value())
    
    def __do_move_fwd(self):
        self.__current_activity = MSFWD
        self.__st_act.setText(MSFWD)
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT]*(1000/IDLE_TICKER)
        self.__api.move_fwd_for_ms(self.__inctxt.value())
    
    def __do_move_rev(self):
        self.__current_activity = MSREV
        self.__st_act.setText(MSREV)
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT]*(1000/IDLE_TICKER)
        self.__api.move_rev_for_ms(self.__inctxt.value())
    
    def __do_nudge_fwd(self):
        self.__current_activity = NUDGEFWD
        self.__st_act.setText(NUDGEFWD)
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT]*(1000/IDLE_TICKER)
        self.__api.nudge_fwd()
    
    def __do_nudge_rev(self):
        self.__current_activity = NUDGEREV
        self.__st_act.setText(NUDGEREV)
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT]*(1000/IDLE_TICKER)
        self.__api.nudge_rev()

    #=======================================================
    # Combo box events
    def __loop_change(self, index):
        # Set loop selection needed by the callback as it cant access widgets
        # Index is zero based, loops are 1 based
        self.__selected_loop = index + 1
        # Set the min/max frequencies
        loop = model_for_loop(self.__model, self.__selected_loop)
        if len(loop) > 0:
            self.__minvalue.setText(str(loop[0]))
            self.__maxvalue.setText(str(loop[1]))
        else:
            self.__minvalue.setText('0.0')
            self.__maxvalue.setText('0.0')
    
    
    #=======================================================
    # Manual calibration events
    def __do_man_save(self):
        self.__man_cal_freq = self.__manfreqtxt.text()
        self.__man_cal_swr = self.__manswrtxt.text()
        self.__man_cal_state = MANUAL_DATA_AVAILABLE
    
    def __do_man_next(self):
        self.__manfreqtxt.setText('')
        self.__manswrtxt.setText('')
        self.__man_cal_state = MANUAL_NEXT
    
    #=======================================================
    # Helpers
    def __set_tx_mode(self):
        self.__current_activity = RLYOFF
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT]*(1000/IDLE_TICKER)
        self.__api.tx_mode()
        self.__tg_ard.setText(TX)
        self.__relay_sel.setCurrentText(TX)
        self.__relay_state = TX
            
    def __set_vna_mode(self):
        self.__current_activity = RLYON
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT]*(1000/IDLE_TICKER)
        self.__api.vna_mode()
        self.__tg_ard.setText(VNA)
        self.__relay_sel.setCurrentText(VNA)
        self.__relay_state = VNA
        
    #=======================================================
    # Background activities
    def __idleProcessing(self):
        # Here we update the UI according to current activity and the status set by the callback
        if self.__model[STATE][ARDUINO][ONLINE]:
            # on-line indicator
            self.__st_ard.setText('on-line')
            self.__st_ard.setObjectName("stgreen")
            self.__st_ard.setStyleSheet(self.__st_ard.styleSheet())
            
            # Update current position
            self.__currpos.setText(str(self.__current_pos) + '%')
            widget_state = None  
            # Check activity state
            if self.__current_activity != NONE:
                # Activity current
                if self.__long_running:
                    widget_state = W_LONG_RUNNING
                elif self.__free_running:
                    widget_state = W_FREE_RUNNING
                else:
                    widget_state = W_DISABLE_ALL
            else:
                # No activity
                widget_state = W_NORMAL
                self.__long_running = False
                self.__free_running = False
                if self.__relay_state == TX:
                    self.__tg_ard.setText(TX)
                    self.__relay_sel.setCurrentText(TX)
                elif self.__relay_state == VNA:
                    self.__tg_ard.setText(VNA)
                    self.__relay_sel.setCurrentText(VNA)
                # Check relay status
                if self.__switch_mode != self.__last_switch_mode:
                    self.__last_switch_mode = self.__switch_mode
                    if self.__switch_mode == VNA:
                        self.__set_vna_mode()
                    else:
                        self.__set_tx_mode()
                    
            self.__st_act.setText(self.__current_activity)
            
            # Show manual entry if required
            if self.__current_activity == CALIBRATE:
                if self.__model[CONFIG][VNA_CONF][VNA_PRESENT] == VNA_NO:
                    # No VNA present so we do a manual config
                    self.__manualcal.show()
            else:
                self.__manualcal.hide()
        else:
            # Try to bring on-line
            self.__api.init_comms()
            # Not online yet so we can't do anything except exit
            widget_state = W_DISABLE_ALL
            # off-line indicator
            self.__st_ard.setText('off-line')
            self.__st_ard.setObjectName("stred")
            self.__st_ard.setStyleSheet(self.__st_ard.styleSheet())
        
        # Update loop status for configured loops
        if self.__loop_status[0]:
            self.__l1label.setObjectName("stgreen")
            self.__l1label.setStyleSheet(self.__l1label.styleSheet())
        if self.__loop_status[1]:
            self.__l2label.setObjectName("stgreen")
            self.__l2label.setStyleSheet(self.__l2label.styleSheet())
        if self.__loop_status[2]:
            self.__l3label.setObjectName("stgreen")
            self.__l3label.setStyleSheet(self.__l3label.styleSheet())
        
        # Adjust buttons for loop status
        if self.__model[STATE][ARDUINO][ONLINE]:
            if not self.__loop_status[self.__selected_loop-1]:
                # Current loop is not configured
                widget_state = W_NO_CONFIG
        
        # Update min/max frequencies
        loop = model_for_loop(self.__model, self.__selected_loop)
        if len(loop) > 0:
            self.__minvalue.setText(str(loop[1]))
            self.__maxvalue.setText(str(loop[0]))
        # Update SWR
        self.__auto_swrval.setText(str(self.__auto_swr))
        
        # Update VNA status
        if self.__model[STATE][ARDUINO][ONLINE]:
            if self.__model[CONFIG][VNA_CONF][VNA_PRESENT] == VNA_YES:
                self.__st_vna.setText('present')
                self.__st_vna.setObjectName("stgreen")
            else:
                self.__st_vna.setText('absent')
                self.__st_vna.setObjectName("stred")
            self.__st_vna.setStyleSheet(self.__st_vna.styleSheet())
        
        # Set widgets
        self.__set_widget_state(widget_state)
        
        # Output any messages
        if self.__msgq.qsize() > 0:
            while self.__msgq.qsize() > 0:
                msg, msgtype = self.__msgq.get()
                self.__msglist.insertItem(0, msg)
                if msgtype == MSG_INFO:
                    self.__msglist.item(0).setForeground(QColor(60,60,60))
                elif msgtype == MSG_STATUS:
                    self.__msglist.item(0).setForeground(QColor(33,82,3))
                elif msgtype == MSG_ALERT:
                    self.__msglist.item(0).setForeground(QColor(191,13,13))
                else:
                    self.__msglist.item(0).setForeground(QColor(60,60,60))
            # Cull messages?
            if self.__msglist.count() > 100:
                # Keep history between 50 and 100
                for n in range(0, 50):
                    self.__msglist.takeitem(n)
        
        # Manage manual data entry state
        if self.__man_cal_state == MANUAL_IDLE:
            self.__manfreqtxt.setEnabled(False)
            self.__manswrtxt.setEnabled(False)
            self.__save.setEnabled(False)
            self.__next.setEnabled(False)
        elif self.__man_cal_state == MANUAL_DATA_REQD:
            self.__manfreqtxt.setEnabled(True)
            self.__manswrtxt.setEnabled(True)
            if len(self.__manfreqtxt.text()) > 0 and len(self.__manswrtxt.text()) > 0: 
                self.__save.setEnabled(True)
            self.__next.setEnabled(False)
        elif self.__man_cal_state == MANUAL_DATA_AVAILABLE:
            self.__manfreqtxt.setEnabled(False)
            self.__manswrtxt.setEnabled(False)
            self.__save.setEnabled(False)
            self.__next.setEnabled(True)
        
        # Reset timer
        QtCore.QTimer.singleShot(IDLE_TICKER, self.__idleProcessing)
 
    # Enable/disable according to state
    def __set_widget_state(self, state):
        if not self.__last_widget_status == state:
            self.__last_widget_status = state
            if state == W_DISABLE_ALL:
                # All disable except close
                self.__w_enable_disable(False)
                self.__stopact.setEnabled(False)
                self.__abort.setEnabled(False)
            
            elif state == W_NO_CONFIG:
                # All disable except close and config
                self.__w_enable_disable(False)
                self.__stopact.setEnabled(False)
                self.__abort.setEnabled(False)
                self.__loop_sel.setEnabled(True)
                self.__cal.setEnabled(True)
                self.__sp.setEnabled(True)
                
            elif state == W_LONG_RUNNING:
                # All disable except close and abort
                self.__w_enable_disable(False)
                self.__stopact.setEnabled(False)
                self.__abort.setEnabled(True)
                
            elif state == W_FREE_RUNNING:
                # All disable except close and stop
                self.__w_enable_disable(False)
                self.__stopact.setEnabled(True)
                self.__abort.setEnabled(False)
                
            elif state == W_NORMAL:
                # All enable except abort and stop
                self.__w_enable_disable(True)
                self.__stopact.setEnabled(False)
                self.__abort.setEnabled(False)
            else:
                # All disable except close
                self.__w_enable_disable(False)
                self.__stopact.setEnabled(False)
                self.__abort.setEnabled(False)
    
        # Do additive states
        if self.__model[STATE][ARDUINO][ONLINE]:
            if self.__model[CONFIG][VNA_CONF][VNA_PRESENT] == VNA_YES:
                self.__w_vna_enable_disable(True)
            else:
                self.__w_vna_enable_disable(False)
        
    # All enabled (True) or disabled (False)
    def __w_enable_disable(self, state):
        self.__loop_sel.setEnabled(state)
        self.__cal.setEnabled(state)
        self.__sp.setEnabled(state)
        self.__freqtxt.setEnabled(state)
        self.__tune.setEnabled(state)
        self.__relay_sel.setEnabled(state)
        self.__speed_sel.setEnabled(state)
        self.__mvrev.setEnabled(state)
        self.__mvfwd.setEnabled(state)
        self.__getres.setEnabled(state)
        self.__movetxt.setEnabled(state)
        self.__runfwd.setEnabled(state)
        self.__runrev.setEnabled(state)
        self.__inctxt.setEnabled(state)
        self.__movepos.setEnabled(state)
        self.__nudgefwd.setEnabled(state)
        self.__nudgerev.setEnabled(state)
    
    # Additive state for VNA    
    def __w_vna_enable_disable(self, state):
        self.__getres.setEnabled(state)
        