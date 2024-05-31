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
    return round_sig(((float(offset)/float(span))*100.0))

# Round a floating pint number to n significant digits 
def round_sig(x, sig=2):
    return round(x, sig)

# Find the best match (interpolate if necessary) frequency for a given absolute position
def find_from_position(model, loop, pos):
    # Get the data set
    sets = model_for_loop(model, loop)
    # If we have data look for a match
    if len(sets) == 0:
        # Failed to find a candidate
        return False, 'No currebnt sets for loop %d!' % loop, (None, None, None)
    # A set is a dictionary of name:[[pos, freq, swr], [...], ...]
    # We first determine the best set to look for a match.
    # Sets can overlap so we want the minimum span set as the best candidate
    candidate = find_candidate(sets, pos, SET_POS)
    '''
    candidate = None
    lastlow = None
    lasthi = None
    for name, pset in sets:
        low = pset[0][0]
        high = pset[-1][0]
        if pos >= low and pset <= high:
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
    '''
    if candidate == None:
        # Failed to find a candidate
        return False, 'No candidate found for position %d!' % pos, (None, None, None)
        
    # We need to find best match for the curent position.
    pset = sets[candidate]
    index = 0
    offset = 7
    idx_low = -1
    idx_high = -1
    # The list is not necessarily in any order as could cover multiple bands
    # Also the position could be increasing or decreasing
    # Also they are not inclusive due to slight drift in the analog value
    # Iterate through in pairs
    for index in range(1, len(pset)-1, 2):
        # See if apos lies between values
        if pset[index][0] <= pos and pset[index+1][0] >= pos:
            idx_low = index
            idx_high = index+1
            break
        elif pset[index][0] >= pos and pset[index+1][0] <= pos:
            idx_low = index+1
            idx_high = index
            break
        # If not are we close enough to one value
        elif abs(pset[index][0] - pos) < offset:
            idx_low = index
            idx_high = index
            break
        elif abs(pset[index+1][0] - pos) < offset:
            idx_low = index
            idx_high = index
            break 
        
    if idx_low == -1 or  idx_high ==-1:
        # Failed to find a match in candidate set
        return False, 'No match found in candidate %d!' % candidate, (None, None, None)
    else:
        # The feedback values and frequencies above and below the required position
        fb_high = pset[idx_high][0]
        fb_low = pset[idx_low][0]
        frq_high = pset[idx_high][1]
        frq_low = pset[idx_low][1]
        # We now need to calculate the frequency value for the required position
        # Span between positions
        fb_span = fb_high - fb_low
        if fb_span < 0:
            fb_span = fb_low - fb_high
        if fb_span == 0: fb_span = 1
        # Increment from low to actual position
        fb_inc = pos - fb_low
        # Fraction to be applied to frequency
        fb_frac = fb_inc/fb_span
        # Same for frequency
        frq_span = frq_high - frq_low
        if frq_span < 0:
            frq_span = frq_low - frq_high 
        frq_frac = fb_frac * frq_span
        
        # Interpolate target frequency
        target_freq = frq_low - frq_frac
        # Return (pos, freq, swr)
        return True, '', (pset[idx_low][0], target_freq, pset[idx_low][2] )
    
# Find candidate for given position
def find_candidate(sets, pos, qual):
    candidate = None
    lastlow = None
    lasthi = None
    for name, pset in sets.items():
        low = pset[0][qual]
        high = pset[-1][qual]
        if pos >= low and pos <= high:
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