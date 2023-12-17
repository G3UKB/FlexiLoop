#!/usr/bin/env python
#
# utils.py
#
# Utility functions for Flexi Loop Controller
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
import os,sys
from time import sleep

# Application imports
from defs import *

# Return the loop config for loop id
def model_for_loop(model, loop):
        
    if loop == 1:
        return model[CONFIG][CAL][CAL_L1]
    elif loop == 2:
        return model[CONFIG][CAL][CAL_L2]
    elif loop == 3:
        return model[CONFIG][CAL][CAL_L3]
    else:
        return []

# Return the %age relative position for an absolute feedback offset    
def absolute_pos_to_relative(model, pos):
    # pos is given as 0-100%
    # convert this into the corresponding analog value
    home = model[CONFIG][CAL][HOME]
    maximum = model[CONFIG][CAL][MAX]
    if home == -1 or max == -1:
        print("Failed to move as limits are not set!")
        return 0
    span = maximum - home
    return (int(pos)/100)*span
    