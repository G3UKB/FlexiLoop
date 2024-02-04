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
import vna

# Make this a separate module with q etc.
class Tune(threading.Thread):
    
    def __init__(self, model, serial, vna, s_q, cb):
        super(Tune, self).__init__()
        
        # Get root logger
        self.logger = logging.getLogger('root')
        
        self.__model = model
        self.__serial_comms = serial
        self.__vna = vna
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
            cal = model_for_loop(self.__model, self.__loop)
            if self.__freq < cal[1] or self.__freq > cal[0]:
                # Not covered by this loop
                self.logger.warning ("Requested freq {} is outside limits for this loop [{},{}]".format(self.__freq, cal[1], cal[0]))
                self.__cb(('Tune', (False, "Requested freq {} is outside limits for this loop [{},{}]".format(self.__freq, cal[1], cal[0]), [])))
                self.__serial_comms.restore_callback()
                return
            # Stage 1: move as close to frequency as possible
            # Find the two points this frequency falls between
            index = 0
            idx_low = 0
            idx_high = 0
            # The list is in high to low frequency order as home is fully retracted
            for ft in cal[2]:
                if ft[1] < self.__freq:
                    # Lower than target
                    idx_high = index-1 
                    idx_low = index
                else:
                    index += 1
            
            # Calculate where between these points the frequency should be
            # Note high is the setting for higher frequency not higher feedback value
            # Same for low
            #
            # The feedback values and frequencies above and below the required frequency
            fb_high = cal[2][idx_high][0]
            fb_low = cal[2][idx_low][0]
            frq_high = cal[2][idx_high][1]
            frq_low = cal[2][idx_low][1]
            
            # We now need to calculate the feedback value for the required frequency
            frq_span = frq_high - frq_low
            frq_inc = self.__freq - frq_low
            frq_frac = frq_inc/frq_span
            fb_span = fb_low - fb_high
            fb_frac = frq_inc * fb_span
            target_pos = fb_low - fb_frac
            
            # We now have a position to move to
            self.__s_q.put(('move', [target_pos]))
            self.__wait_for = MOVETO
            self.__event.wait()
            self.__event.clear()
            
            # Stage 2 tweak SWR if we have a VNA
            if self.__model[CONFIG][VNA_CONF][VNA_PRESENT] == VNA_YES:
                r, [(f, swr)] = self.__vna.fswr(self.__freq)
                last_swr = swr
                try_for = 10
                dir = FWD
                if r:
                    # Tweek if necessary
                    while swr > 1.5:
                        if try_for <= 0:
                            self.logger.info("Unable to reduce SWR to less than 1.5 {}".format(swr))
                            self.__cb(("Tune", (True, "Unable to reduce SWR to less than 1.5 {}".format(swr), [])))
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
                    self.__cb((TUNE, (True, "", [swr])))
                else:
                    self.logger.inwarningfo("Failed to obtain a SWR reading for freq {}".format(self.__freq))
                    self.__cb((TUNE, (False, "Failed to obtain a SWR reading for freq {}".format(self.__freq), [])))
            # Give back callback
            self.__serial_comms.restore_callback()
            
        print("Tune thread  exiting...")
              
    #=======================================================
    # Stolen Callback  
    def t_tune_cb(self, data):
        (name, (success, msg, val)) = data
        if name == self.__wait_for:
            # Extract args and release thread
            self.__args = val
            self.__event.set()
            