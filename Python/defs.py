#!/usr/bin/env python3
#
# defs.py
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
# Model defs
MIN_FREQ = 1800000
MAX_FREQ = 30000000
CONFIG = 'CONFIG'
STATE = 'STATE'
# Serial section
SERIAL = 'SERIAL'
PORT = 'PORT'
# Calibration section
CAL = 'CAL'
HOME = 'HOME'
MAX = 'MAX'
FREE = 'FREE'
LOOP_1 = 1
LOOP_2 = 2
LOOP_3 = 3
STEPS = 10
CAL_L1 = 'CAL_L1'
CAL_L2 = 'CAL_L2'
CAL_L3 = 'CAL_L3'
# State section
WINDOWS = 'WINDOWS'
MAIN_WIN = 'MAIN_WIN'
CONFIG_WIN = 'CONFIG_WIN'
MEM_WIN = 'MEM_WIN'
ARDUINO = 'ARDUINO'
ONLINE = 'ONLINE'
ACT_POS = 'ACT_POS'

#=======================================================================
# UI
CONFIG_PATH = '../config/auto_tuner.cfg'
IDLE_TICKER = 250
HEARTBEAT_TIMER = 10 # 10 * IDLE_TICKER = 1s ; heartbeats should be every 0.5s

# Current activities
NONE = 'None'
CALIBRATE = 'Calibrate'
SPEED = 'Speed'
HOME = 'Home'
MAX = 'Max'
POS = 'Pos'
NUDGEFWD = 'NudgeFwd'
NUDGEREV = 'NudgeRev'
MSFWD = 'msFwd'
MSREV = 'msRev'
MOVETO = 'MoveTo'
TUNE = 'Tune'
RESONANCE = 'Resonance'

STATUS = 'Status'
ABORT = 'Abort'

CALIBRATE_TIMEOUT = 120 * (1000/250)
TUNE_TIMEOUT = 120 * (1000/250)
RES_TIMEOUT = 60 * (1000/250)
MOVE_TIMEOUT = 30 * (1000/250)
SHORT_TIMEOUT = 2 * (1000/250)

#=======================================================================
# General
FWD = 'FWD'
REV = 'REV'

