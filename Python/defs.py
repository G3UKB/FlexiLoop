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
STATE = 'STATE'
# Serial section
SERIAL = 'SERIAL'
PORT = 'PORT'
# Calibration section
CAL = 'CAL'
HOME = 'HOME'
CAL_L1 = 'CAL_L1'
CAL_L2 = 'CAL_L2'
CAL_L3 = 'CAL_L3'
#======================================
# State
#
# Windows section
WINDOWS = 'WINDOWS'
MAIN_WIN = 'MAIN_WIN'
CONFIG_WIN = 'CONFIG_WIN'
MEM_WIN = 'MEM_WIN'
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

# Loop selection
LOOP_1 = 1
LOOP_2 = 2
LOOP_3 = 3

# Current activities
NONE = 'None'
CALIBRATE = 'Calibrate'
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
# Pseudo activities
STATUS = 'Status'
ABORT = 'Abort'
STOP = 'Stop'
NONE = 'None'

# Timeouts for the long running operations in seconds
# Adjusted for the idle tick rate to number of idle passes
CALIBRATE_TIMEOUT = 120 * (1000/250) #P
TUNE_TIMEOUT = 120 * (1000/250) #P
RES_TIMEOUT = 60 * (1000/250) #P
MOVE_TIMEOUT = 30 * (1000/250) #P
SHORT_TIMEOUT = 2 * (1000/250) #P

# Target selection dependent on relay on/off
TX = 'TX'
VNA = 'VNA'
# Relay used on 4 relay board
ANT_RLY = 'RELAY1'

# Hints to vna.py for simulation mode
VNA_HOME = 'HOME'
VNA_MAX = 'MAX'
VNA_MID = 'MID'
VNA_RANDOM = 'RANDOM'

# Number of steps for calibration
# Resonant frequency and feedback value at each step forms part of calibration
ACT_STEPS = 10 #P

# Direction of actuator motion
FWD = 'FWD'
REV = 'REV'

# Widget enable/disable states
W_DISABLE_ALL = 'WDisableAll'
W_LONG_RUNNING = 'WLongRunning'
W_FREE_RUNNING = 'WFreeRunning'
W_NORMAL = 'WNormal'
            
#=======================================================================
# VNA parameters
#

# Types
RQST_FRES = 'fres'
RQST_FSWR = 'fswr'
RQST_SCAN = 'scan'

# Freq inc between readings in Hz
INC_10K = 10000
INC_5K = 5000
INC_1K = 1000
INC_500 = 500
INC_250 = 250

# Driver
DRIVER_ID = 20  # MiniVNA Tiny
#DRIVER_PORT = 'ttyUSB0' #P
DRIVER_PORT = 'COM4' #P

# Scanner defs
#CAL_FILE = '/home/looppi/vnaJ.3.3/calibration/REFL_miniVNA Tiny.cal' #P
CAL_FILE = '../VNAJ/vnaJ.3.3/calibration/REFL_miniVNA Tiny.cal' #P
SCAN_MODE = 'REFL'
EXPORTS = 'csv'
EXPORT_FILENAME = 'VNA_{0,date,yyMMdd}_{0,time,HHmmss}' #P
#JAR = '/home/looppi/Projects/MiniVNA/VNAJ/vnaJ-hl.3.3.3.jar' #P
JAR = '../VNAJ/vnaJ.3.3/vnaJ-hl.3.3.3.jar' #P

# Decoder defs
LIN_EXPORT_PATH = '/home/looppi/vnaJ.3.3/export' #P
WIN_EXPORT_PATH = '../VNAJ/vnaJ.3.3/export' #P
DEC_FREQ = 0
DEC_SWR = 4




