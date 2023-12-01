#!/usr/bin/env python
#
# api.py
#
# Abstraction between UI and low level modules
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

# Application imports
from defs import *
import model
import persist
import serialcomms
import calibrate
import vna

MODE = SIMULATE
# MODE = NORMAL

# Verbose flag
VERB = False

#=====================================================
# The Programming Interface class
#===================================================== 
class API:
    
    # Initialisation
    def __init__(self, model, port):
        
        self.__model = model
        
        # Create a SerialComms instance
        self.__serial_comms = serialcomms.SerialComms(port)
        
        # Create a VNA instance
        self.__vna = vna.VNA(MODE)
        
        # Create a Calibration instance
        self.__cal = calibrate.Calibrate(self.__serial_comms, self.__vna, model)
    
    # Perform a calibration for the given loop    
    def calibrate(self, loop):
        print("Calibrating loop: {}. This may take a while...".format(loop))
        r, m, cal = self.__cal.calibrate(loop, STEPS)
        if r:
            print("Calibration complete: {}".format(cal))
            return True, m
        else:
            print("Calibration failed! {}".format(cal))
            return False, m
        
    # Perform a re-calibration for the given loop    
    def re_calibrate(self, loop):
        print("Calibrating loop: {}. This may take a while...".format(loop))
        r, m, cal = self.__cal.re_calibrate(loop, STEPS)
        if r:
            print("Re-calibration complete: {}".format(cal))
            return True, m
        else:
            print("Re-calibration failed! {}".format(cal))
            return False, m
    
    # Get position as a %age of full travel
    def get_pos(self):
        pos = self.__serial_comms.pos()
        # Get calibration
        home = self.__model[CONFIG][CAL][HOME]
        maximum = self.__model[CONFIG][CAL][MAX]
        if home == -1 or max == -1:
            if VERB: print("Failed to get position as limits are not set!")
            return '???'
        span = maximum - home
        offset = pos - home
        return int(offset/span)
        
    # Move to lowest SWR for loop on given frequency
    def move_to_freq(self, loop, freq):
        # Get calibration
        cal = self.__model[CONFIG][CAL][loop]
        if freq < cal[0] or freq > cal[1]:
            # Not covered by this loop
            print ("Requested freq {} is outside limits for this loop [{},{}]".format(loop, cal[0], cal[1]))
            return False, "Requested freq {} is outside limits for this loop [{},{}]".format(loop, cal[0], cal[1])
        
        # Stage 1: move as close to frequency as possible
        # Find the two points this frequency falls between
        index = 0
        low = 0
        high = 0
        # The list is in high to low frequency order as home is fully retracted
        for f in cal[2]:
            if f[1] < freq:
                # Lower than target
                high = index-1
                low = index
            else:
                index += 1
        # Calculate where between these points the frequency should be
        higher = high - f
        span = high - low
        frac = higher/span
        # Offsets
        high_offset = cal[2][high][0]
        low_offset = cal[2][low][0]
        # Amount to add
        offset_span = high_offset - low_offset
        offset_frac = offset_span*frac
        target_pos = high_offset + offset_frac
        # We now have a position to move to
        self.__serial_comms.move(pos)
        
        # Stage 2 tweak SWR
        r, swr = self.__vna.fswr(freq)
        last_swr = swr
        try_for = 10
        dir = FWD
        if r:
            # Tweek if necessary
            while swr > 1.5:
                if try_for <= 0:
                    print("Unable to reduce SWR to less than 1.5 {}".format(swr))
                    return True, "Unable to reduce SWR to less than 1.5 {}".format(swr)
                if dir == FWD:
                    self.__serial_comms.nudge_fwd()
                else:
                    self.__serial_comms.nudge_rev()
                r, swr = self.__vna.fswr(freq)
                if swr < last_swr:
                    last_swr = swr
                    try_for -= 1
                    continue
                else:
                    dir = REV
                    last_swr = swr
                    try_for -= 1
                    continue               
            return True, "", swr
        else:
            print("Failed to obtain a SWR reading for freq {}".format(freq))
            return False, "Failed to obtain a SWR reading for freq {}".format(freq), None
    
    # Switch between TX and VNA
    def switch_target(self, target):
        pass
    
    def get_current_res(self):
        pass
    
    def move_to_position(self, pos):
        # pos is given as 0-100%
        # convert this into the corresponding analog value
        home = self.__model[CONFIG][CAL][HOME]
        maximum = self.__model[CONFIG][CAL][HOME]
        if home == -1 or max == -1:
            print("Failed to move as limits are not set!")
            return
        span = maximum - home
        frac = (pos/100)*span
        self.__serial_comms.move(home+frac)
    
    def move_fwd_for_ms(self, ms):
        self.__serial_comms.run_fwd(ms)
    
    def move_rev_for_ms(self, ms):
        self.__serial_comms.run_rev(ms)
    
    def nudge_fwd(self):
        self.__serial_comms.nudge_fwd()
    
    def nudge_rev(self):
        self.__serial_comms.nudge_rev()
        