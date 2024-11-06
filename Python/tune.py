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
import logging

# Application imports
from defs import *
from utils import *
import model
import persist
import serialcomms
import calibrate

VERB = False

#=====================================================
# Tune to a given frequency
# Again a threaded operation to keep UI alive
#===================================================== 
class Tune(threading.Thread):
    
    def __init__(self, model, serial, s_q, cb):
        super(Tune, self).__init__()
        
        # Get root logger
        self.logger = logging.getLogger('root')
        
        # Parameters
        self.__model = model
        self.__serial_comms = serial
        self.__s_q = s_q
        self.__cb = cb
        
        # Instance vars
        self.__freq = None
        self.__loop = None
        self.__event = threading.Event()
        self.__wait_for = ""
        self.__args = []
        self.one_pass = False
        self.term = False
    
    # Perform one tuning pass for given loop and frequency
    def do_one_pass(self, loop, freq):
        self.__loop = loop
        self.__freq = freq
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
                if self.term: return
            self.one_pass = False
            
            self.logger.info("Tuning -- this may take a while...")
            # Need to steal the serial comms callback
            self.__serial_comms.steal_callback(self.t_tune_cb)
            
            # Get calibration
            sets = model_for_loop(self.__model, self.__loop)
            # Stage 1: move as close to frequency as possible
            # Find suitable candidate set
            candidate = find_freq_candidate(sets, self.__freq)
            if candidate == None:
                self.__cb((TUNE, (False, "Unable to find a candidate set for frequency %f" % self.__freq, [])))
                self.__serial_comms.restore_callback()
                continue
            aset = sets[candidate]
            
            # Find the two points this frequency falls between
            index = 0
            idx_low = -1
            idx_high = -1
            for ft in aset:
                if ft[1] < self.__freq:
                    # Lower than target
                    idx_high = index+1 
                    idx_low = index
                elif ft[1] > self.__freq:
                    break
                index+=1
            if idx_high == -1 or idx_low == -1:
                self.__cb((TUNE, (False, "Unable to find a tuning point for frequency %f" % self.__freq, [])))
                # Give back callback
                self.__serial_comms.restore_callback()
                continue
            
            # Calculate where between these points the frequency should be
            # Note high is the setting for higher frequency not higher feedback value
            # Same for low
            #
            # The feedback values and frequencies above and below the required frequency
            fb_high = aset[idx_high][0]
            fb_low = aset[idx_low][0]
            frq_high = aset[idx_high][1]
            frq_low = aset[idx_low][1]
            
            # We now need to calculate the feedback value for the required frequency
            frq_span = frq_high - frq_low
            frq_inc = self.__freq - frq_low
            frq_frac = frq_inc/frq_span
            fb_span = fb_low - fb_high
            fb_frac = frq_frac * fb_span
            target_pos = fb_high + fb_frac
            
            # We now have a position to move to
            self.__s_q.put(('move', [target_pos]))
            self.__wait_for = MOVETO
            self.__event.wait()
            self.__event.clear()
            
            # Stage 2 tweak SWR
            # Its a manual tweak
            # TBD what can we do here?
            self.__cb((TUNE, (True, "", [])))
            # Give back callback
            self.__serial_comms.restore_callback()
            
        print("Tune thread  exiting...")
              
    #=======================================================
    # Stolen Callback for serial comms
    def t_tune_cb(self, data):
        if VERB: self.logger.info("Calibrate: got event: {}".format(data))
        (name, (success, msg, val)) = data
        if name == self.__wait_for:
            # Extract args and release thread
            self.__args = val
            self.__event.set() 
        elif name == STATUS:
            # Calculate position and directly event to API which has a pass-through to UI
            ppos = analog_pos_to_percent(self.__model, val[0])
            if ppos != None:
                self.__cb((name, (True, "", [str(ppos), val[0]])))
        elif name == DEBUG:
            self.logger.info("Tune: got debug: {}".format(data))
        elif name == ABORT:
            # Just release whatever was going on
            # It should then pick up the abort flag
            self.__abort = True
            self.__event.set() 
        else:
            if VERB: self.logger.info ("Waiting for {}, but got {}, continuing to wait!".format(self.__wait_for, name))
            