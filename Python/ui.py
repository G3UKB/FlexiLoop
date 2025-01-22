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
from qt_inc import *

# Application imports
from defs import *
from utils import *
import api
import config
import setpoints
import calview
sys.path.append('../NanoVNA')
import vna_api

# Vertical line
class VLine(QFrame):
    # A simple VLine, like the one you get from designer
    def __init__(self):
        super(VLine, self).__init__()
        self.setFrameShape(self.VLine|self.Sunken)
        self.setObjectName("maninner")

# Main window        
class UI(QMainWindow):
    
    def __init__(self, model, qt_app):
        super(UI, self).__init__()

        # Get root logger
        self.logger = logging.getLogger('root')
        
        # Create message q
        self.__msgq = queue.Queue(100)
        
        self.__model = model
        self.__qt_app = qt_app
        
        # Create the VNA instance
        self.__vna_open = False
        self.__vna_api = vna_api.VNAApi(model)
        if self.__model[CONFIG][VNA][VNA_ENABLED]:
            if not self.__vna_api.open():
                self.logger.warn ('Failed to open VNA device! Trying periodically.')
            
        # Create the API instance
        self.__api = api.API(model, self.__vna_api, self.callback, self.msg_callback)
        self.__api.init_comms()
        
        # Create the config dialog
        self.__config_dialog = config.Config(self.__model, self.__diff_callback, self.msg_callback)
        
        # Create the setpoint dialog
        self.__sp_dialog = setpoints.Setpoint(self.__model, self.msg_callback, self.__move_callback)
        
        # Create the calibration view dialog
        self.__calview_dialog = calview.Calview(self.__model, self.__move_callback, self.msg_callback)
        
        #Loop status
        self.__selected_loop = 1
        self.__loop_status = [False, False, False]
        self.__last_widget_status = None
    
        # Set the back colour
        palette = QPalette()
        palette.setColor(QPalette.Background,QColor(158,152,143))
        self.setPalette(palette)

        # Set the tooltip style
        QToolTip.setFont(QFont('SansSerif', 10))
        self.setStyleSheet('''QToolTip { 
                           background-color: darkgray; 
                           color: black; 
                           border: #8ad4ff solid 1px
                           }''')   
        
        # Local state holders
        self.__selected_loop = 1
        self.__tune_freq = 0.0
        self.__current_activity = NONE
        self.__long_running = False
        self.__free_running = False
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT]*(1000/IDLE_TICKER)
        self.__switch_mode = RADIO
        self.__last_switch_mode= self.__switch_mode
        self.__saved_mode = self.__switch_mode
        self.__deferred_activity = None
        self.__current_speed = self.__model[STATE][ARDUINO][SPEED]
        self.__aborting = False
        self.__tracking_update = 8
        self.__tracking_counter = self.__tracking_update
        # Of form for loops 1-3 [[added, removed, modified],[...],[...]]
        self.__cal_diff = [[],[],[]]
        
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
                
        # Last saved motor position
        self.__current_pos = self.__model[STATE][ARDUINO][MOTOR_POS]
        self.__fb_pos = self.__model[STATE][ARDUINO][MOTOR_FB]
        self.__moved = True
        # Flag to initiate a position refresh at SOD
        self.__init_pos = True
        # We must wait a little to make sure Arduino has initialised
        self.__init_pos_dly = 10
        
        # Default to radio side
        self.__relay_state = RADIO
        
        # Manual calibration status
        self.__man_hint = MAN_NONE
        self.__man_cal_state = MANUAL_IDLE
        self.__man_cal_freq = 0.0
        self.__man_cal_swr = 1.0
        
        # Initialise the GUI
        self.__initUI()
        
        # Populate controls
        self.__populate()
        
        # Get calibrate differences
        self.__config_dialog.cal_init()
        
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
    
    # Called from calview and setpoints dialog to move to a position.
    # Called on main thread so we can do UI stuff
    def __move_callback(self, pos):
        # pos is expected to be the feedback value
        self.__current_activity = MOVETO
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][MOVE_TIMEOUT]*(1000/IDLE_TICKER)
        self.__long_running = True
        self.__api.move_to_position(pos)
    
    # Called by configuration dialog to highlight differences between config and calibration
    def __diff_callback(self, diff):
        self.__cal_diff = diff
        
    # This is called when doing a manual calibration to set the hint and get the next data items.
    # This is called on the calibration thread so will not interrupt the UI
    def man_cal_callback(self):
        # We set the data required flag and wait for the state to go to data available
        self.__man_cal_state = MANUAL_DATA_REQD
        while self.__man_cal_state != MANUAL_DATA_AVAILABLE:
            if self.__aborting:
                self.__aborting = False
                # Let calibration do the actual abort
                return CAL_ABORT, (None, None, None)
            sleep (0.2)
        
        if self.__is_float(self.__man_cal_freq) and self.__is_float(self.__man_cal_swr):
            result = (self.__man_cal_freq, self.__man_cal_swr, self.__fb_pos)
            self.__man_cal_freq = 0.0
            self.__man_cal_swr = 1.0
            while self.__man_cal_state != MANUAL_NEXT:
                sleep (0.2)
            self.__man_cal_state = MANUAL_IDLE
            return CAL_SUCCESS, result
        else:
            self.__man_cal_state = MANUAL_DATA_REQD
            return CAL_RETRY, (None, None, None)
    
    # Main callback    
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
        
        # Are we waiting for an activity to complete
        if self.__current_activity == NONE:
            self.__activity_timer = self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT]*(1000/IDLE_TICKER)
        else:
            # Activity in progress
            self.__activity_timer -= 1
            if self.__activity_timer <= 0:
                self.logger.info ('Timed out waiting for activity {} to complete. Maybe the Arduino has gone off-line!'.format(self.__current_activity))
                self.__current_activity = NONE
                self.__activity_timer = self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT]*(1000/IDLE_TICKER)
                return
            
            # Get current event data
            (name, (success, msg, args)) = data
            if len(msg) > 0 and not success:
                self.msg_callback(msg, MSG_ALERT)
                
            if name == self.__current_activity:
                if success:
                    self.__current_activity = NONE
                    # Action any data
                    if name == POS:
                        # Update position
                        self.__current_pos = args[0]
                        self.__fb_pos = args[1]
                        self.__moved = True
                    elif name == CONFIGURE:
                        pass
                    elif name == CALIBRATE:
                        # Update the loop status
                        if self.__selected_loop != -1:
                            self.__loop_status[self.__selected_loop-1] = True
                        # Switch mode back to what is was before any change for long running activities
                        self.__switch_mode = self.__saved_mode
                        self.__moved = True
                    elif name == FREQLIMITS:
                        # Switch mode back to what is was before any change for long running activities
                        self.__switch_mode = self.__saved_mode
                        self.__moved = True
                    elif name == TUNE:
                        # Switch mode back to what is was before any change for long running activities
                        self.__switch_mode = self.__saved_mode
                        self.__moved = True
                    self.logger.info ('Activity {} completed successfully'.format(self.__current_activity))
                    # Do we have a deferred activity
                    if self.__deferred_activity != None:
                        self.__deferred_activity()
                        self.__deferred_activity = None
                else:
                    self.logger.info ('Activity {} completed but failed!'.format(self.__current_activity))
                    self.__current_activity = NONE
                    # Switch mode back to what is was before any change for long running activities
                    self.__switch_mode = self.__saved_mode
            elif name == STATUS:
                # We expect status at any time
                self.__current_pos = args[0]
                self.__fb_pos = args[1]
                self.__moved = True
                self.__model[STATE][ARDUINO][MOTOR_POS] = float(self.__current_pos)
                self.__model[STATE][ARDUINO][MOTOR_FB] = float(self.__fb_pos)
            elif name == LIMIT:
                # No action required as the current activity will complete
                pass
            elif name == ABORT:
                # User hit the abort button
                self.__current_activity = NONE
                # Switch mode back to what is was before any change for long running activities
                self.__switch_mode = self.__saved_mode
                self.logger.info("Activity aborted by user!")
            elif name == DEBUG:
                self.logger.info(args[0])
            else:
                # Treat this as an abort because it will probably lock us up otherwise
                self.logger.info ('Waiting for activity {} to completed but got activity {}! Aborting, please restart the activity.'.format(self.__current_activity, name))
                self.__aborting = True
                self.__api.abort_activity()
                
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
        # Configure the menu bar
        self.menubar = QMenuBar(self)
        self.setMenuBar(self.menubar)
        
        self.filemenu = QMenu("&File", self)
        self.menubar.addMenu(self.filemenu)
        self.exitaction = QAction(self)
        self.exitaction.setText("&Exit")
        self.filemenu.addAction(self.exitaction)
        self.exitaction.triggered.connect(self.__do_close)
        
        self.editmenu = QMenu("&Edit", self)
        self.menubar.addMenu(self.editmenu)
        self.configaction = QAction(self)
        self.configaction.setText("&Config")
        self.editmenu.addAction(self.configaction)
        self.configaction.triggered.connect(self.__do_config)
        
        #======================================================================================
        # Configure the status bar
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        
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
        self.__tg_ard.setText(RADIO)
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
        
        # VNA Status
        self.st_lblvna= QLabel()
        self.st_lblvna.setText('VNA')
        self.statusBar.addPermanentWidget(self.st_lblvna)
        self.st_lblvna.setObjectName("stred")
        self.st_lblvna.setStyleSheet(self.st_lblvna.styleSheet())
        
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
    # Create and position all widgets
    def __populate(self):
        #=======================================================
        # Set main layout
        self.__central_widget = QWidget()
        self.setCentralWidget(self.__central_widget)
        self.__grid = QGridLayout()
        self.__central_widget.setLayout(self.__grid)
        
        # -------------------------------------------
        # Feedback area
        self.__fbgrid = QGridLayout()
        gb_fb = QGroupBox('Feedback system')
        gb_fb.setLayout(self.__fbgrid)
        self.__grid.addWidget(gb_fb, 0,0)
        self.__pop_feedback(self.__fbgrid)
        
        # -------------------------------------------
        # Loop area
        self.__loopgrid = QGridLayout()
        gb_loop = QGroupBox('Mag loops')
        gb_loop.setLayout(self.__loopgrid)
        self.__grid.addWidget(gb_loop, 1,0)
        self.pop_loop(self.__loopgrid)
        
        # -------------------------------------------
        # Auto area
        self.__autogrid = QGridLayout()
        gb_auto = QGroupBox('Auto')
        gb_auto.setLayout(self.__autogrid)
        self.__grid.addWidget(gb_auto, 2,0)
        self.__autogrid.setColumnMinimumWidth(5,300)
        self.__pop_auto(self.__autogrid)
        
        # -------------------------------------------
        # Manual area
        self.__mangrid = QGridLayout()
        gb_man = QGroupBox('Manual')
        gb_man.setLayout(self.__mangrid)
        self.__grid.addWidget(gb_man, 3,0)
        self.__pop_man(self.__mangrid)
        
        # -------------------------------------------
        # Message area
        self.__msglist = QListWidget()
        self.__grid.addWidget(self.__msglist, 4, 0)
    
    # Populate feedback zone
    def __pop_feedback(self, grid):
        # Configure
        self.__pot = QPushButton("Set Limits...")
        self.__pot.setToolTip('Set limits...')
        grid.addWidget(self.__pot, 0, 0)
        self.__pot.clicked.connect(self.__do_pot)
        
        # Delete
        self.__potdel = QPushButton("Delete")
        self.__potdel.setToolTip('Delete limits...')
        grid.addWidget(self.__potdel, 0, 1)
        self.__potdel.clicked.connect(self.__do_pot_del)
        
        # Limits
        gb_lim = QGroupBox('Feedback limits')
        hbox_lim = QHBoxLayout()
        
        potminlabel = QLabel('Home')
        hbox_lim.addWidget(potminlabel)
        potminlabel.setAlignment(QtCore.Qt.AlignCenter)
        self.__potminvalue = QLabel('0.0')
        self.__potminvalue.setAlignment(QtCore.Qt.AlignCenter)
        self.__potminvalue.setObjectName("minmax")
        hbox_lim.addWidget(self.__potminvalue)
        
        self.__reshome = QPushButton("Reset")
        self.__reshome.setToolTip('Reset home from curren pos')
        hbox_lim.addWidget(self.__reshome)
        self.__reshome.clicked.connect(self.__do_reshome)
        
        maxpotlabel = QLabel('Max')
        hbox_lim.addWidget(maxpotlabel)
        maxpotlabel.setAlignment(QtCore.Qt.AlignCenter)
        self.__potmaxvalue = QLabel('0.0')
        self.__potmaxvalue.setAlignment(QtCore.Qt.AlignCenter)
        self.__potmaxvalue.setObjectName("minmax")
        hbox_lim.addWidget(self.__potmaxvalue)
        
        self.__resmax = QPushButton("Reset")
        self.__resmax.setToolTip('Reset max from curren pos')
        hbox_lim.addWidget(self.__resmax)
        self.__resmax.clicked.connect(self.__do_resmax)
        
        gb_lim.setLayout(hbox_lim)
        grid.addWidget(gb_lim, 0, 2)
        
        # Space out
        grid.setColumnStretch(2, 2)
        grid.setColumnStretch(3, 1)
    
    # Populate loop zone
    def pop_loop(self, grid):
        
        # ====================================================================
        # Select section
        looplabel = QLabel('Select Loop')
        grid.addWidget(looplabel, 0, 0)
        self.__loop_sel = QComboBox()
        self.__loop_sel.addItem("1")
        self.__loop_sel.addItem("2")
        self.__loop_sel.addItem("3")
        self.__loop_sel.setMinimumHeight(20)
        grid.addWidget(self.__loop_sel, 0, 1)
        self.__loop_sel.currentIndexChanged.connect(self.__loop_change)
        
        s = QGroupBox('Calibrate Status')
        hbox = QHBoxLayout()
        
        self.__l1label = QLabel('1')
        hbox.addWidget(self.__l1label)
        self.__l1label.setObjectName("stred")
        self.__l1label.setStyleSheet(self.__l1label.styleSheet())
        self.__l1label.setAlignment(QtCore.Qt.AlignCenter)
        self.__l2label = QLabel('2')
        hbox.addWidget(self.__l2label)
        self.__l2label.setObjectName("stred")
        self.__l2label.setStyleSheet(self.__l2label.styleSheet())
        self.__l2label.setAlignment(QtCore.Qt.AlignCenter)
        self.__l3label = QLabel('3')
        hbox.addWidget(self.__l3label)
        self.__l3label.setObjectName("stred")
        self.__l3label.setStyleSheet(self.__l3label.styleSheet())
        self.__l3label.setAlignment(QtCore.Qt.AlignCenter)
        s.setLayout(hbox)
        grid.addWidget(s, 0, 2, 1, 2)
        
        self.__span = QPushButton("Set Span")
        self.__span.setToolTip('Set the upper and lower frequency limits for this loop')
        grid.addWidget(self.__span, 0, 4)
        self.__span.clicked.connect(self.__do_span)
        
        minf, maxf = self.__model[CONFIG][CAL][LIMITS][LIM_1]
        if minf != None:
            self.__fminvalue = QLabel(str(round(minf, 1)))
        else:
            self.__fminvalue = QLabel('-.-')
        self.__fminvalue.setAlignment(QtCore.Qt.AlignCenter)
        self.__fminvalue.setObjectName("minmax")
        grid.addWidget(self.__fminvalue, 0, 5)
        
        mhz = QLabel('MHz - ')
        grid.addWidget(mhz, 0, 6)
        
        if maxf != None:
            self.__fmaxvalue = QLabel(str(round(maxf, 1)))
        else:
            self.__fmaxvalue = QLabel('-.-')
        self.__fmaxvalue.setAlignment(QtCore.Qt.AlignCenter)
        self.__fmaxvalue.setObjectName("minmax")
        grid.addWidget(self.__fmaxvalue, 0, 7)
        
        mhz1 = QLabel('MHz')
        grid.addWidget(mhz1, 0, 8)
            
        # ====================================================================
        # Calibration section
        self.__cal = QPushButton("Calibrate...")
        self.__cal.setToolTip('Calibrate for loop...')
        self.__loopgrid.addWidget(self.__cal, 1, 0)
        self.__cal.clicked.connect(self.__do_cal)
        
        self.__caldel = QPushButton("Delete")
        self.__caldel.setToolTip('Delete calibration for loop')
        self.__loopgrid.addWidget(self.__caldel, 1, 2)
        self.__caldel.clicked.connect(self.__do_cal_del)
        
        self.__calview = QPushButton("Calibration...")
        self.__calview.setToolTip('View calibrations')
        grid.addWidget(self.__calview, 1, 3)
        self.__calview.clicked.connect(self.__do_cal_view)

        # Set points
        self.__sp = QPushButton("Setpoints...")
        self.__sp.setToolTip('Manage setpoints for loop...')
        self.__sp.setObjectName("calchange")
        grid.addWidget(self.__sp, 2, 0)
        self.__sp.clicked.connect(self.__do_sp)
        
        sps = QGroupBox('Setpoint Status')
        hbox1 = QHBoxLayout()
        
        count = len(self.__model[CONFIG][SETPOINTS][SP_L1])
        self.__l4label = QLabel('1 [%d]' % count)
        hbox1.addWidget(self.__l4label)
        self.__l4label.setObjectName("storange")
        self.__l4label.setStyleSheet(self.__l4label.styleSheet())
        self.__l4label.setAlignment(QtCore.Qt.AlignCenter)
        
        count = len(self.__model[CONFIG][SETPOINTS][SP_L2])
        self.__l5label = QLabel('2 [%d]' % count)
        hbox1.addWidget(self.__l5label)
        self.__l5label.setObjectName("storange")
        self.__l5label.setStyleSheet(self.__l5label.styleSheet())
        self.__l5label.setAlignment(QtCore.Qt.AlignCenter)
        
        count = len(self.__model[CONFIG][SETPOINTS][SP_L3])
        self.__l6label = QLabel('3 [%d]' % count)
        hbox1.addWidget(self.__l6label)
        self.__l6label.setObjectName("storange")
        self.__l6label.setStyleSheet(self.__l6label.styleSheet())
        self.__l6label.setAlignment(QtCore.Qt.AlignCenter)
        sps.setLayout(hbox1)
        grid.addWidget(sps, 2, 1, 1, 3)
        
        # ====================================================================
        # Manual layout
        self.__manualcal = QGroupBox('Entry')
        manualgrid = QGridLayout()
        self.__manualcal.setLayout(manualgrid)
        
        gap = QWidget()
        manualgrid.addWidget(gap, 0, 0)
        
        # Dynamic data entry area for manual calibration
        freqlabel = QLabel('Freq')
        manualgrid.addWidget(freqlabel, 0, 1)
        self.__manfreqtxt = QLineEdit()
        self.__manfreqtxt.setInputMask('09.9000')
        self.__manfreqtxt.setToolTip('Resonant frequency')
        self.__manfreqtxt.setMaximumWidth(80)
        manualgrid.addWidget(self.__manfreqtxt, 0, 2)
        
        swrlabel = QLabel('SWR')
        manualgrid.addWidget(swrlabel, 0, 3)
        self.__manswrtxt = QLineEdit()
        self.__manswrtxt.setInputMask('D.9')
        self.__manswrtxt.setToolTip('SWR at resonance')
        self.__manswrtxt.setMaximumWidth(80)
        manualgrid.addWidget(self.__manswrtxt, 0, 4)
        
        gap = QWidget()
        manualgrid.addWidget(gap, 0, 5)
        
        # Dynamic data entry buttons for manual calibration
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
        
        grid.addWidget(self.__manualcal, 3, 0, 1, 8)
        
        # Normally hidden
        self.__manualcal.hide()
    
    # Populate auto zone    
    def __pop_auto(self, grid):
        
        # Move to frequency
        freqlabel = QLabel('Tune to Freq')
        self.__autogrid.addWidget(freqlabel, 0, 0)
        self.__freqtxt = QLineEdit()
        self.__freqtxt.setToolTip('Set tune frequency')
        self.__freqtxt.setInputMask('09.9000')
        self.__freqtxt.setMaximumWidth(80)
        self.__freqtxt.textChanged.connect(self.__auto_text)
        grid.addWidget(self.__freqtxt, 0, 1)
        
        self.__tune = QPushButton("Tune...")
        self.__tune.setToolTip('Tune to freq...')
        self.__autogrid.addWidget(self.__tune, 0, 2)
        self.__tune.clicked.connect(self.__do_tune)
        
        # Tracking
        # Sub grid
        tracksubgrid = QGridLayout()
        sg_track = QGroupBox()
        sg_track.setLayout(tracksubgrid)
        grid.addWidget(sg_track, 1,0,1,3)
        
        tracklabel = QLabel('Tracking')
        tracksubgrid.addWidget(tracklabel, 1, 0)
        
        res2label = QLabel('Freq')
        tracksubgrid.addWidget(res2label, 1, 1)
        self.__freqval = QLabel('-.-')
        self.__freqval.setObjectName("minmax")
        self.__freqval.setMaximumWidth(100)
        tracksubgrid.addWidget(self.__freqval, 1, 2)
        
        res1label = QLabel('SWR')
        tracksubgrid.addWidget(res1label, 1, 3)
        self.__swrres = QLabel('-.-')
        self.__swrres.setObjectName("minmax")
        self.__swrres.setMaximumWidth(100)
        tracksubgrid.addWidget(self.__swrres, 1, 4)
    
    # Populate manual zone
    def __pop_man(self, grid):
        
        # Sub grid
        self.__subgrid = QGridLayout()
        w4 = QGroupBox()
        w4.setLayout(self.__subgrid)
        grid.addWidget(w4, 0,0,1,6)
        
        # Target select
        relaylabel = QLabel('Target')
        self.__subgrid.addWidget(relaylabel, 0, 0)
        self.__relay_sel = QComboBox()
        self.__relay_sel.setMinimumHeight(20)
        self.__relay_sel.setMaximumWidth(70)
        self.__relay_sel.setMinimumWidth(70)
        self.__relay_sel.addItem(RADIO)
        self.__relay_sel.addItem(ANALYSER)
        self.__subgrid.addWidget(self.__relay_sel, 0, 1)
        self.__relay_sel.currentIndexChanged.connect(self.__relay_change)
        
        gap = QWidget()
        self.__subgrid.addWidget(gap, 0, 2)
        self.__subgrid.setColumnStretch(2, 1)
        
        self.__runrev = QPushButton("<< Run Rev")
        self.__runrev.setToolTip('Run actuator reverse...')
        self.__subgrid.addWidget(self.__runrev, 0,3)
        self.__runrev.clicked.connect(self.__do_run_rev)
        
        self.__stopact = QPushButton("Stop")
        self.__stopact.setToolTip('Stop actuator')
        self.__subgrid.addWidget(self.__stopact, 0,4)
        self.__stopact.clicked.connect(self.__do_stop_act)
        
        self.__runfwd = QPushButton("Run Fwd >>")
        self.__runfwd.setToolTip('Run actuator forward...')
        self.__subgrid.addWidget(self.__runfwd, 0,5)
        self.__runfwd.clicked.connect(self.__do_run_fwd)
        
        gap = QWidget()
        self.__subgrid.addWidget(gap, 0, 6)
        self.__subgrid.setColumnStretch(6, 1)
        
         # Speed
        speedtag = QLabel('Speed')
        self.__subgrid.addWidget(speedtag, 1, 0)
        self.__speed_sld = QSlider()
        self.__speed_sld.setGeometry(QtCore.QRect(190, 100, 160, 16))
        self.__speed_sld.setOrientation(QtCore.Qt.Horizontal)
        self.__speed_sld.setMinimum(SPEED_MIN)
        self.__speed_sld.setMaximum(SPEED_MAX)
        self.__speed_sld.setTickInterval(50)
        self.__speed_sld.setTickPosition(QSlider.TicksBelow )
        self.__speed_sld.setValue(SPEED_DEF)
        self.__subgrid.addWidget(self.__speed_sld, 1, 1, 1, 3)
        self.__speed_sld.valueChanged.connect(self.__speed_changed)
        
        # Move position
        movelabel = QLabel('Move to (%)')
        grid.addWidget(movelabel, 1, 0)
        self.__movetxt = QSpinBox()
        self.__movetxt.setToolTip('Move position 0-100%')
        self.__movetxt.setRange(0,100)
        self.__movetxt.setValue(50)
        self.__movetxt.setMaximumWidth(80)
        self.__mangrid.addWidget(self.__movetxt, 1, 1)
        
        self.__movepos = QPushButton("Move")
        self.__movepos.setToolTip('Move to given position 0-100%...')
        self.__mangrid.addWidget(self.__movepos, 1,2)
        self.__movepos.clicked.connect(self.__do_pos)
        
        curr1label = QLabel('Current Position')
        grid.addWidget(curr1label, 1, 3)
        self.__currpos = QLabel('-')
        self.__currpos.setStyleSheet("QLabel {color: rgb(65,62,56); font: 20px}")
        self.__currpos.setMaximumWidth(100)
        grid.addWidget(self.__currpos, 1, 4)
        self.__currposfb = QLabel('-')
        self.__currposfb.setStyleSheet("QLabel {color: rgb(65,62,56); font: 20px}")
        self.__currposfb.setMaximumWidth(100)
        grid.addWidget(self.__currposfb, 1, 5)
        
        # Increment
        inclabel = QLabel('Inc (ms)')
        grid.addWidget(inclabel, 2, 0)
        self.__inctxt = QSpinBox()
        self.__inctxt.setToolTip('Increment time in ms')
        self.__inctxt.setRange(0,1000)
        self.__inctxt.setValue(500)
        self.__inctxt.setMaximumWidth(80)
        grid.addWidget(self.__inctxt, 2, 1)
        
        self.__mvfwd = QPushButton("Move Forward")
        self.__mvfwd.setToolTip('Move forward for given ms...')
        grid.addWidget(self.__mvfwd, 2,2)
        self.__mvfwd.clicked.connect(self.__do_move_fwd)
        
        self.__mvrev = QPushButton("Move Reverse")
        self.__mvrev.setToolTip('Move reverse for given ms...')
        grid.addWidget(self.__mvrev, 2,3)
        self.__mvrev.clicked.connect(self.__do_move_rev)
        
        self.__nudgefwd = QPushButton("Nudge Forward")
        self.__nudgefwd.setToolTip('Nudge forward...')
        grid.addWidget(self.__nudgefwd, 2,4)
        self.__nudgefwd.clicked.connect(self.__do_nudge_fwd)
        
        self.__nudgerev = QPushButton("Nudge Reverse")
        self.__nudgerev.setToolTip('Nudge reverse...')
        grid.addWidget(self.__nudgerev, 2,5)
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
    # Menu events
    def __do_config(self):
        self.__config_dialog.cal_init()
        self.__config_dialog.show()
    
    #=======================================================
    # Main buttons events
    def __do_close(self):
        self.__close()
        self.__qt_app.quit()
        
    def __do_abort(self):
        self.__aborting = True
        self.__api.abort_activity()
    
    #=======================================================
    # Feedback zone events
    def __do_pot(self):
        # Do the configure sequence
        self.__current_activity = CONFIGURE
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][CALIBRATE_TIMEOUT]*(1000/IDLE_TICKER)
        self.__long_running = True
        # Dispatches on separate thread
        self.__api.configure()
    
    def __do_pot_del(self):
        # Ask user if they really want to delete the calibration
        qm = QMessageBox
        ret = qm.question(self,'', "Do you want to delete the feedback positions?", qm.Yes | qm.No)

        if ret == qm.Yes:
            self.__model[CONFIG][CAL][HOME] = -1
            self.__model[CONFIG][CAL][MAX] = -1
            self.__model[STATE][ARDUINO][MOTOR_POS] = -1
            self.__current_pos = -1
            # Set to reinit position
            self.__init_pos = True
    
    def __do_reshome(self):
        self.__model[CONFIG][CAL][HOME] = int(self.__fb_pos)
    
    def __do_resmax(self):
        self.__model[CONFIG][CAL][MAX] = int(self.__fb_pos)
        
    #=======================================================
    # Calibrate zone events
    def __loop_change(self, index):
        # Set loop selection needed by the callback as it cant access widgets
        # Index is zero based, loops are 1 based
        self.__selected_loop = index + 1
        ls = (LIM_1, LIM_2, LIM_3)
        minf, maxf = self.__model[CONFIG][CAL][LIMITS][ls[index]]
        if minf != None:
            self.__fminvalue.setText(str(round(minf, 1)))
        else:
            self.__fminvalue.setText('-.-')
        if maxf != None:
            self.__fmaxvalue.setText(str(round(maxf, 1)))
        else:
            self.__fmaxvalue.setText('-.-')
        
    def __do_cal(self):
        
        if self.__relay_state == RADIO:
            # Switch to ANALYSER, switch back is done in the callback
            self.__saved_mode = self.__last_switch_mode
            self.__switch_mode = ANALYSER
            
            # This will kick off when the callback from the relay change arrives
            self.__st_act.setText(CALIBRATE)
            self.__deferred_activity = self.__do_cal_deferred
        else:
            # Already in analyser mode. Just start calibrate run
            self.__st_act.setText(CALIBRATE)
            self.__do_cal_deferred()
            
    def __do_cal_deferred(self):
        # Do the calibrate sequence
        self.__current_activity = CALIBRATE
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][CALIBRATE_TIMEOUT]*(1000/IDLE_TICKER)
        self.__long_running = True
        # Dispatches on separate thread
        if self.__loop_status[self.__selected_loop-1] and len(self.__cal_diff[self.__selected_loop-1]) > 0:
            # We need to sync the new calibration data
            self.__api.sync(self.__selected_loop, self.man_cal_callback, self.__cal_diff[self.__selected_loop-1])
            # Did we succeed
            # This will get us the current differences and set the status
            self.__config_dialog.cal_init()
        else:
            # Just calibrate
            self.__api.calibrate(self.__selected_loop, self.man_cal_callback)
    
    def __do_cal_view(self):
        # Invoke the calview dialog
        self.__calview_dialog.set_loop(self.__selected_loop)
        self.__calview_dialog.show()
    
    def __do_cal_del(self):
        loop = self.__selected_loop
        
        # Ask user if they really want to delete the calibration
        qm = QMessageBox
        ret = qm.question(self,'', "Do you want to delete the calibration data for loop %d?" % loop, qm.Yes | qm.No)

        if ret == qm.Yes:
            # Delete calibration for this loop
            
            if loop == 1:
                self.__loop_status[0] = False
                self.__l1label.setObjectName("stred")
                self.__l1label.setStyleSheet(self.__l1label.styleSheet())
                self.__model[CONFIG][CAL][CAL_L1].clear()
            elif loop == 2:
                self.__loop_status[1] = False
                self.__l2label.setObjectName("stred")
                self.__l2label.setStyleSheet(self.__l1label.styleSheet())
                self.__model[CONFIG][CAL][CAL_L2].clear()
            elif loop == 3:
                self.__loop_status[2] = False
                self.__l3label.setObjectName("stred")
                self.__l3label.setStyleSheet(self.__l1label.styleSheet())
                self.__model[CONFIG][CAL][CAL_L3].clear()
        
    def __do_sp(self):
        # Invoke the setpoint dialog
        # This allows setting and navigating setpoints.
        self.__sp_dialog.set_loop(self.__selected_loop)
        self.__sp_dialog.show()
    
    def __do_span(self):
        
        if self.__relay_state == RADIO:
            # Switch to ANALYSER, switch back is done in the callback
            self.__saved_mode = self.__last_switch_mode
            self.__switch_mode = ANALYSER
            
            # This will kick off when the callback from the relay change arrives
            self.__st_act.setText(FREQLIMITS)
            self.__deferred_activity = self.__do_span_deferred
        else:
            # Already in analyser mode. Just start calibrate run
            self.__st_act.setText(FREQLIMITS)
            self.__do_span_deferred()
            
    def __do_span_deferred(self):
        self.__current_activity = FREQLIMITS
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][CALIBRATE_TIMEOUT]*(1000/IDLE_TICKER)
        self.__long_running = True
        self.__api.set_limits(self.__selected_loop, self.man_cal_callback)
    
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
    # Auto zone events
    def __auto_text(self, text):
        try:
            self.__tune_freq = float(text)
        except:
            self.__tune_freq = 0.0
        
    def __do_tune(self):
        self.__current_activity = TUNE
        self.__st_act.setText(TUNE)
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][TUNE_TIMEOUT]*(1000/IDLE_TICKER)
        self.__long_running = True
        self.__api.move_to_freq(self.__selected_loop, self.__tune_freq)
    
    #=======================================================
    # Manual zone events    
    def __relay_change(self):
        target = self.__relay_sel.currentText()
        if target == RADIO:
            self.__switch_mode = RADIO
        else:
            self.__switch_mode = ANALYSER
    
    def __speed_changed(self):
        self.__current_speed = self.__speed_sld.value()
        self.__current_activity = SPEED
        self.__st_act.setText(SPEED)
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT]*(1000/IDLE_TICKER)
        self.__api.speed_change(self.__current_speed)
        self.__model[STATE][ARDUINO][SPEED] = self.__current_speed
        
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
    
    def __do_pos(self):
        self.__current_activity = MOVETO
        self.__st_act.setText(MOVETO)
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][MOVE_TIMEOUT]*(1000/IDLE_TICKER)
        self.__long_running = True
        self.__api.move_to_position(self.__movetxt.value(), MOVE_PERCENT)
    
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
    # Helpers
    def __set_radio_mode(self):
        self.__current_activity = RLYOFF
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT]*(1000/IDLE_TICKER)
        self.__api.radio_mode()
        self.__tg_ard.setText(RADIO)
        self.__relay_sel.setCurrentText(RADIO)
        self.__relay_state = RADIO
            
    def __set_analyser_mode(self):
        self.__current_activity = RLYON
        self.__activity_timer = self.__model[CONFIG][TIMEOUTS][SHORT_TIMEOUT]*(1000/IDLE_TICKER)
        self.__api.analyser_mode()
        self.__tg_ard.setText(ANALYSER)
        self.__relay_sel.setCurrentText(ANALYSER)
        self.__relay_state = ANALYSER
     
    def __is_float(self, value):
        if value is None:
            return False
        try:
            float(value)
            return True
        except:
            return False

    #=======================================================
    # Idle processing called every IDLE_TICKER secs when no UI activity
    def __idleProcessing(self):
        
        #=======================================================
        # Here we update the UI according to current activity and the status set by the callbacks
        fb_config = False
        if self.__model[STATE][ARDUINO][ONLINE]:
            # Update the on-line indicators
            self.__st_ard.setText('on-line')
            self.__st_ard.setObjectName("stgreen")
            self.__st_ard.setStyleSheet(self.__st_ard.styleSheet())
            
            # Check feedback status
            if self.__model[CONFIG][CAL][HOME] != -1 and self.__model[CONFIG][CAL][MAX] != -1:
                fb_config = True
            # Update current motor position
            if self.__current_pos == -1:
                self.__currpos.setText('-')
                self.__currposfb.setText('-')
            else:
                self.__currpos.setText(str(self.__current_pos) + '%')
                self.__currposfb.setText(str(self.__fb_pos))
                # and tracking
                if self.__moved and self.__current_activity == NONE:
                    if self.__tracking_update <= 0:
                        self.__tracking_update = self.__tracking_counter
                        self.__moved = False
                        self.__update_tracking(self.__selected_loop, self.__fb_pos)
                    else:
                        self.__tracking_update -= 1
            # Is this first run after feedback configuration   
            if self.__init_pos and fb_config:
                self.__init_pos_dly -= 1
                if self.__init_pos_dly <= 0:
                    self.__init_pos = False
                    # Initialte a get pos so current values reflected at startup
                    if self.__model[STATE][ARDUINO][MOTOR_POS] == -1:
                        self.__api.get_pos()
                        self.__current_activity = POS
                        self.__st_act.setText(POS)
                 
            # Check activity state
            if self.__current_activity == NONE:
                # No current activity so do some housekeeping
                
                # Do we need to change relay state
                if self.__switch_mode != self.__last_switch_mode:
                    # Yes
                    self.__last_switch_mode = self.__switch_mode
                    if self.__switch_mode == ANALYSER:
                        self.__set_analyser_mode()
                    else:
                        self.__set_radio_mode()
                # Set target indicators
                if self.__relay_state == RADIO:
                    self.__tg_ard.setText(RADIO)
                    self.__relay_sel.setCurrentText(RADIO)
                elif self.__relay_state == ANALYSER:
                    self.__tg_ard.setText(ANALYSER)
                    self.__relay_sel.setCurrentText(ANALYSER)
                    
                # Clear running indicators
                self.__long_running = False
                self.__free_running = False
            
            # Update activity indicator    
            self.__st_act.setText(self.__current_activity)
            
            # Show manual entry if calibration required and no VNA
            if self.__current_activity == CALIBRATE:
                self.__manualcal.show()
            else:
                self.__manualcal.hide()
        else:
            # off-line indicator
            self.__st_ard.setText('off-line')
            self.__st_ard.setObjectName("stred")
            self.__st_ard.setStyleSheet(self.__st_ard.styleSheet())
            # Arduino is off-line so try and bring on-line
            self.__api.init_comms()
        
        # =======================================================
        # Update other fields that do not depend on Arduino state
        # Loop status for configured loops
        if self.__loop_status[0]:
            self.__l1label.setObjectName("stgreen")
            self.__l1label.setStyleSheet(self.__l1label.styleSheet())
        if self.__loop_status[1]:
            self.__l2label.setObjectName("stgreen")
            self.__l2label.setStyleSheet(self.__l2label.styleSheet())
        if self.__loop_status[2]:
            self.__l3label.setObjectName("stgreen")
            self.__l3label.setStyleSheet(self.__l3label.styleSheet())
            
        # Setpoint counts
        count = len(self.__model[CONFIG][SETPOINTS][SP_L1])
        self.__l4label.setText('1 [%d]' % count)
        count = len(self.__model[CONFIG][SETPOINTS][SP_L2])
        self.__l5label.setText('2 [%d]' % count)
        count = len(self.__model[CONFIG][SETPOINTS][SP_L3])
        self.__l6label.setText('3 [%d]' % count)
        
        # Update min/max pot values
        if fb_config:
            self.__potminvalue.setText(str(self.__model[CONFIG][CAL][HOME]))
            self.__potmaxvalue.setText(str(self.__model[CONFIG][CAL][MAX]))
        else:
            self.__potminvalue.setText('-')
            self.__potmaxvalue.setText('-')
        
        # Update freq limits
        ls = (LIM_1, LIM_2, LIM_3)
        minf, maxf = self.__model[CONFIG][CAL][LIMITS][ls[self.__selected_loop-1]]
        if minf != None:
            self.__fminvalue.setText(str(round(minf, 1)))
        else:
            self.__fminvalue.setText('-.-')
        if maxf != None:
            self.__fmaxvalue.setText(str(round(maxf, 1)))
        else:
            self.__fmaxvalue.setText('-.-')
        
        # Update VNA flag
        if self.__model[CONFIG][VNA][VNA_ENABLED]:
            if not self.__model[STATE][VNA][VNA_OPEN]:
                self.__vna_api.open()
        elif self.__model[STATE][VNA][VNA_OPEN]:
            # Has been disabled but still open
            self.__vna_api.close()
            
        if self.__model[STATE][VNA][VNA_OPEN]:
            self.st_lblvna.setObjectName("stgreen")
        else:
            self.st_lblvna.setObjectName("stred")
        self.st_lblvna.setStyleSheet(self.st_lblvna.styleSheet())
        
        # =======================================================
        # Output any queued messages
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
                    self.__msglist.takeItem(n)
        
        # =======================================================
        # Set general widget state
        self.__set_widgets(self.__set_widget_state())
        # Manage manual data entry state
        self.__manage_manual_widgets()
        
        # =======================================================
        # Reset timer
        QtCore.QTimer.singleShot(IDLE_TICKER, self.__idleProcessing)
    
    #========================================================================================
    # Set the widget state according to current context
    def __set_widget_state(self):
        widget_state = W_OFF_LINE    # Fall-back to disable everything except close
        # Check activity state
        if self.__current_activity != NONE:
            # Activity in progress, so we must be operational
            if self.__long_running:
                # Long running such as calibration etc
                widget_state = W_LONG_RUNNING
            elif self.__free_running:
                # Free running such as manual forward/reverse
                widget_state = W_FREE_RUNNING
            else:
                # Almost instant such as nudge, relay change etc
                widget_state = W_TRANSIENT
        else:
            # No activity
            # widget_state depends on application state
            if self.__model[STATE][ARDUINO][ONLINE]:
                # Arduino on-line
                if self.__model[CONFIG][CAL][HOME] > 0 and self.__model[CONFIG][CAL][MAX] > 0:
                    # We have feedback limits set
                    if self.__loop_status == [False, False, False]:
                        # There are no loops configured so allow delete for limita
                        widget_state = W_LIMITS_DELETE
                    elif self.__loop_status[self.__selected_loop-1]:
                        # The selected loop is calibrated
                        widget_state = W_CALIBRATED
                    else:
                        # A loop is calibrated but not the selected one
                        widget_state = W_OTHER_CALIBRATED
                else:
                    # The feedback limits are not set so can only configure these
                    widget_state = W_NO_LIMITS
            else:
                # Arduino off-line
                widget_state = W_OFF_LINE
        return widget_state
    
    # Enable/disable according to state
    def __set_widgets(self, state):
        if not self.__last_widget_status == state:
            # We have a state change
            self.__last_widget_status = state
            # Always allow exit and abort usually off
            self.__exit.setEnabled(True)
            self.__abort.setEnabled(False)
            # Set according to state
            if state == W_OFF_LINE:
                # Everything off except exit
                self.__exit.setEnabled(True)
                self.__abort.setEnabled(False)
                self.__enable_disable_feedback(False)
                self.__enable_disable_loop(False)
                self.__loop_sel.setEnabled(True)
                self.__calview.setEnabled(True)
                self.__enable_disable_auto(False)
                self.__enable_disable_manual(False)
            elif state == W_NO_LIMITS:
                # Everything off except exit and configure
                self.__exit.setEnabled(True)
                self.__abort.setEnabled(False)
                self.__enable_disable_feedback(True)
                self.__potdel.setEnabled(False)
                self.__enable_disable_loop(False)
                self.__enable_disable_auto(False)
                self.__enable_disable_manual(False)
            elif state == W_LIMITS_DELETE:
                # We have limits but no calibration for any loop
                # We allow delete for limits and all manual controls except get current and stop.
                self.__exit.setEnabled(True)
                self.__abort.setEnabled(False)
                self.__enable_disable_feedback(True)
                self.__pot.setEnabled(False)
                self.__enable_disable_loop(False)
                self.__cal.setEnabled(True)
                self.__loop_sel.setEnabled(True)
                if self.__model[STATE][VNA][VNA_OPEN]:
                    self.__enable_disable_auto(True)
                else:
                    self.__enable_disable_auto(False)
                self.__enable_disable_manual(True)
                self.__stopact.setEnabled(False)
            elif state == W_CALIBRATED:
                # We have calibration for the selected loop
                # Allow all except configure or delete limits
                self.__exit.setEnabled(True)
                self.__abort.setEnabled(False)
                self.__enable_disable_feedback(False)
                self.__enable_disable_loop(True)
                self.__cal.setEnabled(False)
                self.__enable_disable_auto(True)
                self.__enable_disable_manual(True)
                self.__stopact.setEnabled(False)
            elif state == W_OTHER_CALIBRATED:
                # We have calibration for not the selected loop
                # Allow all except configure or delete limits
                self.__exit.setEnabled(True)
                self.__abort.setEnabled(False)
                self.__enable_disable_feedback(False)
                self.__enable_disable_loop(True)
                self.__enable_disable_auto(True)
                self.__enable_disable_manual(True)
                self.__stopact.setEnabled(False)
            elif state == W_LONG_RUNNING:
                # All off for long running except abort and special case
                self.__exit.setEnabled(False)
                self.__abort.setEnabled(True)
                self.__enable_disable_feedback(False)
                self.__enable_disable_loop(False)
                self.__enable_disable_auto(False)
                self.__enable_disable_manual(False)
                self.__stopact.setEnabled(False)
            elif state == W_FREE_RUNNING:
                self.__exit.setEnabled(True)
                self.__abort.setEnabled(False)
                self.__enable_disable_feedback(False)
                self.__enable_disable_loop(False)
                self.__enable_disable_auto(False)
                self.__enable_disable_manual(False)
                self.__stopact.setEnabled(True)
            elif state == W_TRANSIENT:
                self.__exit.setEnabled(True)
                self.__abort.setEnabled(False)
                self.__enable_disable_feedback(False)
                self.__enable_disable_loop(True)
                self.__enable_disable_auto(True)
                self.__enable_disable_manual(True)
                self.__stopact.setEnabled(False)
            else:
                # Default all disable
                self.__exit.setEnabled(True)
                self.__abort.setEnabled(False)
                self.__enable_disable_feedback(False)
                self.__enable_disable_loop(False)
                self.__enable_disable_auto(False)
                self.__enable_disable_manual(False)
        
        # Anything that needs to be done even if state does not change
        self.__cal.setText('Calibrate...')
        if state == W_CALIBRATED:
            loop = self.__selected_loop-1
            if len(self.__cal_diff[loop][0]) > 0 or len(self.__cal_diff[loop][1]) > 0 or len(self.__cal_diff[loop][2]) > 0:
                self.__cal.setEnabled(True)
                self.__cal.setText('Sync...')
            else:
                self.__cal.setEnabled(False)
        
        # Update span enable        
        if self.__model[STATE][VNA][VNA_OPEN] and (state != W_OFF_LINE or state != W_NO_LIMITS):
            self.__span.setEnabled(True)
        else:
            self.__span.setEnabled(False)
                
    # All enabled (True) or disabled (False)
    def __enable_disable_feedback(self, state):
        # Feedback sectiom
        self.__pot.setEnabled(state)
        self.__potdel.setEnabled(state)
        self.__reshome.setEnabled(state)
        self.__resmax.setEnabled(state)
    
    def __enable_disable_loop(self, state):    
        # Loop section
        self.__loop_sel.setEnabled(state)
        self.__cal.setEnabled(state)
        self.__caldel.setEnabled(state)
        self.__calview.setEnabled(state)
        self.__sp.setEnabled(state)
        # Miss out manual entry as hidden when not required
    
    def __enable_disable_auto(self, state):    
        # Auto section
        self.__freqtxt.setEnabled(state)
        self.__tune.setEnabled(state)
    
    def __enable_disable_manual(self, state):    
        # Manual section
        self.__relay_sel.setEnabled(state)
        self.__speed_sld.setEnabled(state)
        self.__runfwd.setEnabled(state)
        self.__stopact.setEnabled(state)
        self.__runrev.setEnabled(state)
        self.__movetxt.setEnabled(state)
        self.__movepos.setEnabled(state)
        self.__inctxt.setEnabled(state)
        self.__mvfwd.setEnabled(state)
        self.__mvrev.setEnabled(state)
        self.__nudgefwd.setEnabled(state)
        self.__nudgerev.setEnabled(state)
    
    # Manage manual data entry state   
    def __manage_manual_widgets(self):
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
    
    def __update_tracking(self, loop, pos):
        # Get current absolute position
        if self.__model[STATE][VNA][VNA_OPEN]:
            # We have an active VNA so can ask it where we are
            lc = (LIM_1, LIM_2, LIM_3)
            start, end = self.__model[CONFIG][CAL][LIMITS][lc[self.__selected_loop-1]]
            if start != None and end != None:
                r, f, swr = self.__api.get_resonance(start, end)
            else:
                r = False
        else:
            # We can only get a good approximation if we are within a frequency set
            r, msg, (pos, f, swr) = find_from_position(self.__model, loop, pos)
        if r:
            self.__freqval.setText(str(round(f, 4)))
            self.__swrres.setText(str(swr))
        else:
            self.__freqval.setText('?.?')
            self.__swrres.setText('?.?')

        