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
            if self.__model[STATE][VNA][VNA_OPEN]:
                # We have an active VNA so can ask it where we are
                lc = (LIM_1, LIM_2, LIM_3)
                start, end = self.__model[CONFIG][CAL][LIMITS][lc[self.__loop-1]]
                if start != None and end != None:
                    r, f, swr = self.__vna_api.get_vswr(start, end, 300)
                else:
                    r = False
            else:
                # We can only get a good approximation if we are within a frequency set
                r, msg, (pos, f, swr) = find_from_position(self.__model, self.__loop, self.__pos)
                
            # Return response
            if r:
                self.__cb (((str(round(f, 4))), str(swr)))
            else:
                self.__cb ('?.?', '?.?')
                
        print("Track thread  exiting...")
    
    