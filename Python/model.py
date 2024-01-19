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

# -----------------------------------------------------------
# IP helper
import socket
def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

flexi_loop_model = {
    CONFIG: {
        ARDUINO: {
            PORT: 'COM5',
        },
        TIMEOUTS: {
            CALIBRATE_TIMEOUT: 120,
            TUNE_TIMEOUT: 120,
            RES_TIMEOUT: 60,
            MOVE_TIMEOUT: 30,
            SHORT_TIMEOUT: 2,
        },
        CAL: {
            # Number of steps for set points
            ACTUATOR_STEPS: 10,
            # Feedback values for min and max
            HOME: -1,
            MAX: -1,
            # Loop 1-3 [f at home (highest f), f at max extension (lowest f), [[f, feedback value], [...], ...]]
            CAL_L1: [],
            CAL_L2: [],
            CAL_L3: [],
        },
        SETPOINTS: {
            SP_L1: {},
            SP_L2: {},
            SP_L3: {},
        },
        VNA_CONF: {
            VNA_PRESENT: VNA_YES,
            DRIVER_ID: 20,
            DRIVER_PORT: 'COM4',
            CAL_FILE: '../VNAJ/vnaJ.3.3/calibration/REFL_miniVNA Tiny.cal',
            EXPORT_FILENAME: 'VNA_{0,date,yyMMdd}_{0,time,HHmmss}',
            VNA_JAR: '../VNAJ/vnaJ.3.3/vnaJ-hl.3.3.3.jar',
            EXPORT_PATH: '../VNAJ/vnaJ.3.3/export',
        },
    },
    STATE: {
        WINDOWS: {
            MAIN_WIN: [300,300,500,200],
            CONFIG_WIN: [300,300,300,300],
            SETPOINT_WIN: [300,300,520,300],
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
