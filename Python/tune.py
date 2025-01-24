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
import math

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
    
    def __init__(self, model, serial, s_q, vna_api, cb):
        super(Tune, self).__init__()
        
        # Get root logger
        self.logger = logging.getLogger('root')
        
        # Parameters
        self.__model = model
        self.__serial_comms = serial
        self.__s_q = s_q
        self.__vna_api = vna_api
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
                if self.term: break
            if self.term: break
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
                # Not within our calibrated ranges
                if self.__model[STATE][VNA][VNA_OPEN]:
                    # We have a VNA so use that
                    if self.__vna_tune(WIDE_TUNE, None):
                        self.__cb((TUNE, (True, "", [])))
                    else:
                        # No other options
                        self.__cb((TUNE, (False, "Unable to tune to frequency {} using VNA!".format(self.__freq), [])))
                else:
                    self.__cb((TUNE, (False, "Unable to find a candidate set for frequency {}".format(self.__freq), [])))
            else:
                # We have a candidate so use that to get close
                r, pos = self.__interpolate_tune(sets, candidate)
                if not r:
                    self.__cb((TUNE, (False, "Unable to find a candidate set for frequency {}".format(self.__freq), [])))
                if self.__model[STATE][VNA][VNA_OPEN]:
                    # Try and get closer
                    if self.__vna_tune(CLOSE_TUNE, pos):
                        self.__cb((TUNE, (True, "", [])))
                    else:
                        # No other options
                        self.__cb((TUNE, (False, "Unable to get closer to frequency {} using VNA!".format(self.__freq), [])))
             
            # Give back callback
            self.__serial_comms.restore_callback()
            
        print("Tune thread  exiting...")
    
    # Move to a position that should be close to the tune point
    def __interpolate_tune(self, sets, candidate):
        aset = sets[candidate]
        # Find the two points this frequency falls between
        index = 0
        idx_low = -1
        idx_high = -1
        for ft in aset:
            if ft[1] <= self.__freq:
                # Lower than target
                idx_high = index+1 
                idx_low = index
            elif ft[1] >= self.__freq:
                break
            index+=1
        if idx_high == -1 or idx_low == -1:
            self.__cb((TUNE, (False, "Unable to find a tuning point for frequency %f" % self.__freq, [])))
            # Give back callback
            self.__serial_comms.restore_callback()
            return False, None
        
        # Calculate where between these points the frequency should be
        # Note high is the setting for higher frequency not higher feedback value
        # Same for low
        #
        # The feedback values and frequencies above and below the required frequency
        if idx_high == len(aset):
            # We are on last entry
            fb_low = aset[idx_low][0]
            target_pos = fb_low
        else:
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
            target_pos = fb_low - fb_frac
        
        # We now have a position to move to
        self.__move_to(target_pos)
        return True, target_pos
    
    # Move to best position using VNA 
    def __vna_tune(self, context, pos):
        # Get loop limits
        sec = (LIM_1, LIM_2, LIM_3)
        low_f, high_f = self.__model[CONFIG][CAL][LIMITS][sec[self.__loop-1]]
        
        if context == CLOSE_TUNE:
            # We should be almost there
            r, f, swr = self.__vna_api.get_vswr(low_f, high_f)
            return self.__get_best_vswr(low_f, high_f, pos, f, swr)
        else:
            # We could be anywhere in relation to the frequency.
            # Assume the freq distribution is approx linear.
            span = high_f - low_f
            #frac = (self.__freq - low_f)/ span
            frac = (high_f - self.__freq)/ span
            if frac < 0.0 or frac > 1.0:
                # Not within this loop
                return False
            new_pos = percent_pos_to_analog(self.__model, round(frac*100.0, 3))
            self.__move_to(new_pos)
            # See where that got us
            r, f, swr = self.__vna_api.get_vswr(low_f, high_f)
            self.__get_best_vswr(low_f, high_f, new_pos, f, swr)
            return True
    
    # Set speed
    def __speed(self, speed):
        self.__s_q.put(('speed', [speed]))
        self.__wait_for = SPEED
        self.__event.wait()
        self.__event.clear() 
        
    # Perform move       
    def __move_to(self, target_pos):
        self.__s_q.put(('move', [target_pos]))
        self.__wait_for = MOVETO
        self.__event.wait()
        self.__event.clear()
    
    # Perform move       
    def __run_ms(self, dir, ms):
        if dir == FWD:
            self.__s_q.put(('run_fwd', [ms]))
            self.__wait_for = MSFWD
        else:
            self.__s_q.put(('run_rev', [ms]))
            self.__wait_for = MSREV
        self.__event.wait()
        self.__event.clear()
        
    # Algorithm to approach best vswr for the given frequency
    def __get_best_vswr(self, low_f, high_f, pos, f, swr):
        # How far are we from the target
        # We wnat to limit the span to around the required frequency
        # modified by how far away we are
        
        # To hold modified span
        new_low_f = low_f
        new_high_f = high_f
        # Difference between actual and wanted frequency
        diff = round(f - self.__freq, 3)
        #print('1: ', low_f, high_f, f, diff)
        
        # Find minimal frequency span
        if diff > 0.0:
            # Current f if higher in freq than wanted
            # We go 1MHz above and below to incorporate wanted and diff
            new_low_f = self.__freq - 1.0
            new_high_f = self.__freq + abs(diff) + 1.0
        else:
            # Current f is lower in freq than wanted
            new_low_f = self.__freq - abs(diff) - 1.0
            new_high_f = self.__freq + 1.0
        # Make sure inside loop bounds
        if new_low_f < low_f: new_low_f = low_f
        if new_high_f > high_f: new_high_f = high_f
        # Holds latest resonant frequency
        new_f = f
        # Run for this number of ms
        run_ms = 100
        # Initial speed = slowish
        run_speed = 75
        # Set this run speed
        self.__speed(run_speed)
        # Try to get within 100KHz (not good enough)
        target_diff = 0.1
        # Can't try forever so limit to 10 tries
        attempts = 15
        result = False
        # The run_ms is reduced the closer we get to target
        modifiers = (
            (4.0, 2000),
            (3.0, 1000),
            (2.0, 750),
            (1.0, 500),
            (0.5, 250),
            (0.4, 200),
            (0.3, 150),
            (0.2, 80),
            (0.15, 60),
            (0.1, 40),
            (0.05, 20),
        )
        
        # Loop until exit condition is reached
        while True:
            # Determin which way to go
            if diff < 0.0:
                dir = REV
            else:
                dir = FWD
            # Find the modifier
            for mod in modifiers:
                if abs(diff) > mod[0]:
                    run_ms = mod[1]
                    break
            # Move to new position
            self.__run_ms(dir, run_ms)
            # See where we are
            r, new_f, swr = self.__vna_api.get_vswr(new_low_f, new_high_f, 300)
            if r:
                diff = round(new_f - self.__freq, 3)
            else:
                break
            # Check termination conditions
            if abs(diff) <= target_diff or attempts <= 0:
                result = True
                break
            else:
                attempts -= 1
                
        # Restore speed
        self.__speed(self.__model[STATE][ARDUINO][SPEED])
            
        return result
    
    def __get_best_vswr_sav(self, low_f, high_f, pos, f, swr):
        # How far are we from the target
        # We wnat to limit the span to around the required frequency
        # modified by how far away we are
        
        new_low_f = low_f
        new_high_f = high_f
        diff = round(f - self.__freq, 3)
        #print('1: ', low_f, high_f, f, diff)
        if diff > 0.0:
            # Current f if higher in freq than wanted
            # We go 1MHz above and below to incorporate wanted and diff
            new_low_f = self.__freq - 1.0
            new_high_f = self.__freq + abs(diff) + 1.0
        else:
            # Current f is lower in freq than wanted
            new_low_f = self.__freq - abs(diff) - 1.0
            new_high_f = self.__freq + 1.0
        if new_low_f < low_f: new_low_f = low_f
        if new_high_f > high_f: new_high_f = high_f
        new_f = f
        new_pos = pos
        attempts = 10
        inc_mult = 10
        # We really want to get within 10KHz
        target_diff = 0.03
        # Move increment depending on how far away we are
        inc = int(abs(diff)*inc_mult)
        #print('2: ',new_low_f, new_high_f, f, inc, diff)
        # Loop until exit condition is met
        while True:
            if diff < 0.0:
                # Lower than target
                new_pos -= inc
                self.__move_to(new_pos)
            else:
                # Higher than target
                new_pos += inc
                self.__move_to(new_pos)
            # Test again with higher resolution
            
            r, new_f, swr = self.__vna_api.get_vswr(new_low_f, new_high_f, 300)
            diff = round(new_f - self.__freq, 3)
            inc = int(abs(diff)*inc_mult)
            #print('3: ',new_low_f, new_high_f, new_f, inc, diff)
                    
            # Check termination conditions
            if inc == 0 or abs(diff) <= target_diff or attempts <= 0:
                break
            else:
                attempts -= 1
        return True
    
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
            