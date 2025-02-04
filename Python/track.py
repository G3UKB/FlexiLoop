#!/usr/bin/env python 
#
# track.py
#
# Manage the tracking function 
# 
# Copyright (C) 2025 by G3UKB Bob Cowdery
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
import threading
import traceback
import logging

# Application imports
from defs import *
from utils import *

#=====================================================
# Tune to a given frequency
# Again a threaded operation to keep UI alive
#===================================================== 
class Track(threading.Thread):
    
    def __init__(self, model, vna_api, cb):
        super(Track, self).__init__()
        
        # Get root logger
        self.logger = logging.getLogger('root')
        
        # Parameters
        self.__model = model
        self.__vna_api = vna_api
        self.__cb = cb
        
        # Instance vars
        self.one_pass = False
        self.term = False
    
    # Perform one tuning pass for given loop and frequency
    def do_one_pass(self, loop, pos):
        self.__loop = loop
        self.__pos = pos
        self.one_pass = True
        
    # Terminate instance
    def terminate(self):
        self.term = True
    
    # Entry point    
    def run(self):
        # Run until terminate
        while not self.term:
            # Wait until told to execute
            while not self.one_pass:
                sleep(0.1)
                if self.term: break
            if self.term: break
            self.one_pass = False
            
            # Get current absolute position
            try:
                if self.__model[CONFIG][VNA][VNA_ENABLED] and self.__model[STATE][VNA][VNA_OPEN]:
                    # We have an active VNA so can ask it where we are
                    lc = (LIM_1, LIM_2, LIM_3)
                    start, end = self.__model[CONFIG][CAL][LIMITS][lc[self.__loop-1]]
                    if start != None and end != None:
                        r, f, swr = self.__vna_api.get_vswr(start, end, POINTS)
                    else:
                        r = False
                else:
                    # We can only get a good approximation if we are within a frequency set
                    cal_t = (CAL_L1, CAL_L2, CAL_L3)
                    cal_map = self.__model[CONFIG][CAL][cal_t[self.__loop-1]]
                    r, f, swr = self.__find_from_position(cal_map, self.__pos)
            except Exception as e:
                self.logger.info("Exception in tracking [{}]".format(e))
                r = False
                
            # Return response
            if r:
                self.__cb (((str(round(f, 4))), str(swr)))
            else:
                self.__cb (('?.?', '?.?'))
                
        print("Track thread  exiting...")
    
    # Find the frequency abd SWR from a position
    def __find_from_position(self, cal_map, pos):
        # Find the two points this pos falls between
        index = 0
        idx_low = -1
        idx_high = -1
        for pt in cal_map:
            if pt[0] <= pos:
                # Lower than target
                idx_high = index+1 
                idx_low = index
            elif pt[0] <= pos:
                break
            index+=1
        if idx_high == -1 or idx_low == -1:
            return False, None
    
        # Calculate where between these points the frequency should be
        # Note high is the setting for higher frequency not higher feedback value
        # Same for low
        #
        # The feedback values and frequencies above and below the required frequency
        fb_high = cal_map[idx_high][0]
        fb_low = cal_map[idx_low][0]
        frq_high = cal_map[idx_low][1]
        frq_low = cal_map[idx_high][1]
        swr_high = cal_map[idx_high][2]
        swr_low = cal_map[idx_low][2]
        
        # We now need to calculate the feedback value for the required frequency
        fb_span = fb_high - fb_low 
        fb_inc = fb_high - pos 
        fb_frac = fb_inc/fb_span
        frq_span = frq_high - frq_low
        frq = (frq_span * fb_frac) + frq_low
        swr = (swr_high + swr_low)/2
        
        return True, round(frq, 3), round(swr, 2)
    