#!/usr/bin/env python3
#
# defs.py
#
# Definitions for Flexi-Loop application
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

#=======================================================================
# Calibration
#======================================
MIN_FREQ = 1800000
MAX_FREQ = 30000000

#=======================================================================
# Model
#======================================
# Configutation
#
# Main section headers
CONFIG = 'CONFIG'

# Arduino section
ARDUINO = 'ARDUINO'
PORT = 'PORT'
ACT_SPEED = 'ACT_SPEED'
ACT_SLOW = 'ACT_SLOW'
ACT_MED = 'ACT_MED'
ACT_FAST = 'ACT_FAST'
# Timeout section
TIMEOUTS = 'TIMEOUTS'
# Calibration section
CAL = 'CAL'
HOME = 'HOME'
SETS = 'SETS'
CAL_S1 = 'CAL_S1'
CAL_S2 = 'CAL_S2'
CAL_S3 = 'CAL_S3'
CAL_L1 = 'CAL_L1'
CAL_L2 = 'CAL_L2'
CAL_L3 = 'CAL_L3'
# Setpoint section
SETPOINTS = 'SETPOINTS'
SP_L1 = 'SP_L1'
SP_L2 = 'SP_L2'
SP_L3 = 'SP_L3'
# VNA section
VNA_CONF = 'VNA_CONF'

#======================================
# State
#
STATE = 'STATE'
# Windows section
WINDOWS = 'WINDOWS'
MAIN_WIN = 'MAIN_WIN'
CONFIG_WIN = 'CONFIG_WIN'
SETPOINT_WIN = 'SETPOINT_WIN'
CALVIEW_WIN = 'CALVIEW_WIN'
# Arduino section
ARDUINO = 'ARDUINO'
ONLINE = 'ONLINE'
ACT_POS = 'ACT_POS'

#=======================================================================
# User Interface, Calibrate and Tuning
#
# Path to configuration file
CONFIG_PATH = '../config/flexi_loop.cfg'
# Run idle processing every IDLE_TICKER ms
IDLE_TICKER = 250
# Check Arduino every HEARTBEAT_TIMER ms
HEARTBEAT_TIMER = 5000

# Loop selection
LOOP_1 = 1
LOOP_2 = 2
LOOP_3 = 3

# Current activities
NONE = 'None'
CALIBRATE = 'Calibrate'
CONFIGURE = 'Configure'
SPEED = 'Speed'
HOME = 'Home'
MAX = 'Max'
POS = 'Pos'
RUNFWD = 'RunFwd'
RUNREV = 'RunRev'
STOPRUN = 'StopRun'
NUDGEFWD = 'NudgeFwd'
NUDGEREV = 'NudgeRev'
MSFWD = 'msFwd'
MSREV = 'msRev'
MOVETO = 'MoveTo'
TUNE = 'Tune'
RESONANCE = 'Resonance'
RLYON = 'RlyOn'
RLYOFF = 'RlyOff'
# Pseudo activities
STATUS = 'Status'
ABORT = 'Abort'
STOP = 'Stop'
NONE = 'None'

# Cal manual return values
CAL_SUCCESS = 'CalSuccess'
CAL_RETRY = 'CalRetry'
CAL_ABORT = 'CalAbort'

# Timeouts for the long running operations in seconds
# Adjusted for the idle tick rate to number of idle passes
CALIBRATE_TIMEOUT = 'CALIBRATE_TIMEOUT'
TUNE_TIMEOUT = 'TUNE_TIMEOUT'
RES_TIMEOUT = 'RES_TIMEOUT'
MOVE_TIMEOUT = 'MOVE_TIMEOUT'
SHORT_TIMEOUT = 'SHORT_TIMEOUT'

# Speed
SLOW = 100
MEDIUM = 200
FAST = 300

# Target selection dependent on relay on/off
RADIO = 'Radio'
ANALYSER = 'Analyser'

# Hints for manual calibration mode
MAN_NONE = 'MAN_NONE'
MAN_HOME = 'MAN_HOME'
MAN_MAX = 'MAN_MAX'
MAN_STEP = 'MAN_STEP'
HINT_MOVETO = 'MOVETO'
HINT_STEP = 'STEP'

# Direction of actuator motion
FWD = 'FWD'
REV = 'REV'

# Widget states
W_DISABLE_ALL = 'WDisableAll'
W_NO_CONFIG = 'WNoConfig'
W_LONG_RUNNING = 'WLongRunning'
W_FREE_RUNNING = 'WFreeRunning'
W_NORMAL = 'WNormal'

W_OFF_LINE = 'WOffLine'
W_LONG_RUNNING = 'WLongRunning'
W_FREE_RUNNING = 'WFreeRunning'
W_TRANSIENT = 'Transient'
W_NO_LIMITS = 'WNoLimits'
W_LIMITS_DELETE = 'WLimitsDelete'
W_CALIBRATED = 'WCalibrated'
W_OTHER_CALIBRATED = 'WOtherCalibrated'

# Manual calibration data states
MANUAL_IDLE = 0
MANUAL_DATA_REQD = 1
MANUAL_DATA_AVAILABLE = 2
MANUAL_NEXT = 3

# Hints for messages
MSG_INFO = 'MSG_INFO'
MSG_STATUS = 'MSG_STATUS'
MSG_ALERT = 'MSG_ALERT'

# Set types
SET_POS = 0
SET_FREQ = 1



