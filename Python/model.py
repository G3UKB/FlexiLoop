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
            MOTOR_SPEED: {
                MINIMUM: SPEED_MIN,
                MAXIMUM: SPEED_MAX,
                DEFAULT: SPEED_DEF,
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
            # Feedback values for min and max
            HOME: -1,
            MAX: -1,
            # Frequency limits each loop
            # [Low, High]
            LIMITS: {
                LIM_1: [None, None],
                LIM_2: [None, None],
                LIM_3: [None, None],
            },
            # Number of steps for calibration of whole loop
            STEPS: {
                STEPS_1: 20,
                STEPS_2: 20,
                STEPS_3: 20,
            },
            # Loop 1-3 {name: [[abs feedback value, f, swr], [...], ...], name: [...]]
            CAL_L1: [],
            CAL_L2: [],
            CAL_L3: [],
        },
        SETPOINTS: {
            # Loop 1-3 {name: [[abs feedback value, f, swr], [...], ...], name: [...]]
            SP_L1: {},
            SP_L2: {},
            SP_L3: {},
        },
        VNA: {
            VNA_ENABLED: False,
        }
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
            MOTOR_POS: -1,
            MOTOR_FB: -1,
            SPEED: SPEED_DEF,
        },
        VNA: {
            VNA_OPEN: False,
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
