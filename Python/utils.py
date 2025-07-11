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
from math import log10, floor

# Application imports
from defs import *

# ***********************************************
# NOTE - functions are NOT re-entrant
# If calling from more than one thread add protection
# ***********************************************

# Return the loop config for loop id
def model_for_loop(model, loop):
        
    if loop == 1:
        return model[CONFIG][CAL][CAL_L1]
    elif loop == 2:
        return model[CONFIG][CAL][CAL_L2]
    elif loop == 3:
        return model[CONFIG][CAL][CAL_L3]
    else:
        return None

# Return the %age relative position for an absolute feedback offset    
def percent_pos_to_analog(model, pos):
    # pos is given as 0.0-100.0%
    # convert this into the corresponding analog value
    # home and max are the analog feedback values 
    home = model[CONFIG][CAL][HOME]
    maximum = model[CONFIG][CAL][MAX]
    if home == -1 or maximum == -1:
        return None
    fspan = float(maximum - home)
    return int(((float(pos)/100.0)*fspan) + float(home))

# Return the absolute analog value given the % extension   
def analog_pos_to_percent(model, pos):
    # pos is given as the absolute analog value
    # convert this into the corresponding relative percentage
    # home and max are the analog feedback values 
    home = model[CONFIG][CAL][HOME]
    maximum = model[CONFIG][CAL][MAX]
    if home == -1 or maximum == -1:
        return None
    span = maximum - home
    offset = pos - home
    val = round_sig(((float(offset)/float(span))*100.0))
    # Due to slight variation in the feedback value we can go slightly over limits.
    if val < 0.0: val = 0.0
    if val > 100.0: val = 100.0
    return val

# Round a floating pint number to n significant digits 
def round_sig(x, sig=2):
    return round(x, sig)
    
# Find candidate for given position
def find_pos_candidate(sets, pos):
    candidate = None
    lastlow = None
    lasthi = None
    for name, pset in sets.items():
        low = pset[0][0]
        high = pset[-1][0]
        if pos <= low and pos >= high:
            # Our position lies within this set
            if candidate == None:
                candidate = name
                lastlow = low
                lasthi = high
            else:
                if low - high < lastlow - lasthi:
                    candidate = name
                lastlow = low
                lasthi = high   
    return candidate
    
#=================================================
# Testing
def sim_steps(model):
    low_pos = 30.0
    high_pos = 20.0
    steps = 10
    
    low_pos_abs = percent_pos_to_analog(model, low_pos)
    high_pos_abs = percent_pos_to_analog(model, high_pos)
    span = low_pos_abs - high_pos_abs
    fb_inc = float(span)/float(steps)
    print(low_pos_abs, high_pos_abs, span, fb_inc)
    
    next_inc = round(float(low_pos_abs) - fb_inc, 0)
    counter = 0
    print(low_pos_abs, high_pos_abs, span, fb_inc, next_inc)
    print('Low ', low_pos_abs)
    while next_inc > high_pos_abs:
        print('Counter: %d, Next: %d' % (counter, int(next_inc)))
        next_inc -= fb_inc
        counter += 1
    print('High ', high_pos_abs)
    
def self_test():
    
    model = {
        CONFIG: {
            CAL: {
                # Calibration sets for each loop
                # {name: [low_freq, low_pos, high_freq, high_pos, steps], name:[...], ...}
                SETS: {
                    CAL_S1: {},
                    CAL_S2: {},
                    CAL_S3: {},
                },
                # Feedback values for min and max
                HOME: 508,
                MAX: 779,
                # Loop 1-3 [[feedback value, f, swr], [...], ...]]
                CAL_L1: {},
                CAL_L2: {},
                CAL_L3: {},
            },
            SETPOINTS: {
                # Loop 1-3 [...?]
                SP_L1: {},
                SP_L2: {},
                SP_L3: {},
            },
        }
    }
    
    val = percent_pos_to_analog(model, 50.0)
    print('%->an ', val)
    
    print('an->% home ', analog_pos_to_percent(model, 508))
    print('an->% max ', analog_pos_to_percent(model, (779-508) + 508))
    
    arg = ((779-508)/2.0) + 508
    print('an arg ', arg)
    val = analog_pos_to_percent(model, arg)
    print('an->% ', val)
    
    sim_steps(model)

