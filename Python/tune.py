#!/usr/bin/env python
#
# tune.py
#
# Manage the tune function 
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
import queue
import threading
import traceback

# Application imports
from defs import *
from utils import *
import model
import persist
import serialcomms
import calibrate
import vna

# Make this a separate module with q etc.
class Tune(threading.Thread):
    
    def __init__(self, model, serial, s_q, cb):
        super(Tune, self).__init__()
        
        self.__model = model
        self.__serial_comms = serial
        self.__loop = None
        self.__freq = None
        self.__s_q = s_q
        self.__cb = cb
        
        self.__event = threading.Event()
        self.__wait_for = ""
        self.__args = []
        
        self.one_pass = False
        self.term = False
    
    # Allow one execution pass
    def do_one_pass(self, loop, freq):
        self.__loop = loop
        self.__freq = freq
        self.one_pass = True
        
    # Terminate instance
    def terminate(self):
        self.term = True
        
    def run(self):
        while not self.term:
            while not self.one_pass:
                sleep(0.1)
                
            print("Tuning -- this may take a while...")
            # Need to steal the serial comms callback
            self.__serial_comms.steal_callback(self.t_tune_cb)
            
            # Get calibration
            cal = model_for_loop(self.__model, self.__loop)
            print("cal ", cal)
            if self.__freq < cal[0] or self.__freq > cal[1]:
                # Not covered by this loop
                print ("Requested freq {} is outside limits for this loop [{},{}]".format(self.__loop, cal[0], cal[1]))
                self.__cb.put('Tune', (False, "Requested freq {} is outside limits for this loop [{},{}]".format(self.__loop, cal[0], cal[1]), []))
                self.__serial_comms.restore_callback()
                return
            # Stage 1: move as close to frequency as possible
            # Find the two points this frequency falls between
            index = 0
            low = 0
            high = 0
            # The list is in high to low frequency order as home is fully retracted
            for ft in cal[2]:
                if ft[1] < self.__freq:
                    # Lower than target
                    high = index-1
                    low = index
                else:
                    index += 1
            # Calculate where between these points the frequency should be
            higher = high - ft
            span = high - low
            frac = higher/span
            print("Here")
            # Offsets
            high_offset = cal[2][high][0]
            low_offset = cal[2][low][0]
            # Amount to add
            offset_span = high_offset - low_offset
            offset_frac = offset_span*frac
            target_pos = high_offset + offset_frac
            # We now have a position to move to
            rel_pos = absolute_pos_to_relative(self.__model, target_pos)
            self.__s_q.put(('move', rel_pos))
            self.__wait_for = MOVETO
            self.__event.wait()
            self.__event.clear()
            
            # Stage 2 tweak SWR
            r, swr = self.__vna.fswr(self.__freq)
            last_swr = swr
            try_for = 10
            dir = FWD
            if r:
                # Tweek if necessary
                while swr > 1.5:
                    if try_for <= 0:
                        print("Unable to reduce SWR to less than 1.5 {}".format(swr))
                        self.__cb.put (("Tune", (True, "Unable to reduce SWR to less than 1.5 {}".format(swr), [])))
                        break
                    if dir == FWD:
                        #self.__serial_comms.nudge_fwd()
                        self.__s_q.put(('nudge_fwd', []))
                        sleep(1)
                    else:
                        #self.__serial_comms.nudge_rev()
                        self.__s_q.put(('nudge_rev', []))
                        sleep(1)
                    r, swr = self.__vna.fswr(self.__freq)
                    if swr < last_swr:
                        last_swr = swr
                        try_for -= 1
                        continue
                    else:
                        dir = REV
                        last_swr = swr
                        try_for -= 1
                        continue               
                self.__cb.put ((TUNE, (True, "", swr)))
            else:
                print("Failed to obtain a SWR reading for freq {}".format(self.__freq))
                self.__cb.put ((TUNE, (False, "Failed to obtain a SWR reading for freq {}".format(self.__freq), [])))
            self.__comms.restore_callback()

    #=======================================================
    # Stolen Callback  
    def t_tune_cb(self, data):
        (name, (success, msg, val)) = data
        if name == self.__wait_for:
            # Extract args and release thread
            self.__args = val
            self.__event.set()
            