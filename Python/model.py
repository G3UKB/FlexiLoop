#!/usr/bin/env python3
#
# model.py
#
# Flexi-loop persistent model
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

# Applicaion imports
from defs import *

# The application model contains persisted configuration and state data
flexi_loop_model = {
    CONFIG: {
        ARDUINO: {
            PORT: 'COM5',
            ACT_SPEED: {
                ACT_SLOW: SLOW,
                ACT_MED: MEDIUM,
                ACT_FAST: FAST,
            },
        },
        TIMEOUTS: {
            CALIBRATE_TIMEOUT: 180,
            TUNE_TIMEOUT: 120,
            RES_TIMEOUT: 60,
            MOVE_TIMEOUT: 30,
            SHORT_TIMEOUT: 2,
        },
        CAL: {
            # Number of steps for set points
            SETS: {
                CAL_S1: {},
                CAL_S2: {},
                CAL_S3: {},
            },
            # Feedback values for min and max
            HOME: -1,
            MAX: -1,
            # Loop 1-3 [[feedback value, f, swr], [...], ...]]
            CAL_L1: [],
            CAL_L2: [],
            CAL_L3: [],
        },
        SETPOINTS: {
            SP_L1: {},
            SP_L2: {},
            SP_L3: {},
        },
    },
    STATE: {
        WINDOWS: {
            MAIN_WIN: [300,300,500,200],
            CONFIG_WIN: [300,300,300,300],
            SETPOINT_WIN: [300,300,520,300],
            CALVIEW_WIN: [300,300,300,200],
        },
        ARDUINO: {
            ONLINE: False,
            ACT_POS: -1,
        }
    }
}

# Manage model
flexi_loop_model_clone = None

def copy_model(model):
    global flexi_loop_model_clone
    flexi_loop_model_clone = copy.deepcopy(model)
    
def restore_model(model):
    global flexi_loop_model_clone
    if flexi_loop_model_clone != None:
        model = copy.deepcopy(flexi_loop_model_clone)
