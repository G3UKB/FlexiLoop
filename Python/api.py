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
# Python imports
import os,sys
from time import sleep
import queue
import threading
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
    def __init__(self, model, port, callback):
        
        self.__model = model
        self.__cb = callback
        
        # Create a SerialComms instance
        self.__s_q = queue.Queue(10)
        self.__serial_comms = serialcomms.SerialComms(model, port, self.__s_q, self.serial_callback)
        # and start the thread
        self.__serial_comms.start()
        
        # Create a VNA instance
        self.__vna = vna.VNA(MODE)
        
        # Create a Calibration instance
        self.__c_q = queue.Queue(10)
        self.__cal = calibrate.Calibrate(self.__serial_comms, self.__s_q, self.__c_q, self.__vna, model, self.cal_callback)
        # and start the thread
        self.__cal.start()
        
        self.__event = threading.Event()
        self.__wait_for = ""
        self.__args = []
    
    # Termination
    def terminate(self):
        self.__serial_comms.terminate()
        self.__serial_comms.join()
        self.__cal.terminate()
        self.__cal.join()
        
    # Perform a calibration for the given loop    
    def calibrate(self, loop):
        print("Calibrating loop: {}. This may take a while...".format(loop))
        self.__c_q.put(('calibrate', [loop, STEPS]))
        
    # Perform a re-calibration for the given loop    
    def re_calibrate(self, loop):
        print("Calibrating loop: {}. This may take a while...".format(loop))
        self.__c_q.put(('re_calibrate_loop', [loop, STEPS]))
        
    # Get position as a %age of full travel
    def get_pos(self):
        self.__s_q.put(('pos', []))
    
    # Move to lowest SWR for loop on given frequency
    # This has to be threaded as its long running
    # A transient thread is used for this rather than a permanent thread
    def move_to_freq(self, loop, freq):
        t = Thread(target=t_move_to_freq, args=[loop, freq])
        t.run()
        
    # Runs once and then exits
    def t_move_to_freq(self, loop, freq):
        # Need to steal the serial comms callback
        self.__comms.steal_callback(t_move_to_freq_cb)
        
        # Get calibration
        cal = self.__model[CONFIG][CAL][loop]
        if freq < cal[0] or freq > cal[1]:
            # Not covered by this loop
            print ("Requested freq {} is outside limits for this loop [{},{}]".format(loop, cal[0], cal[1]))
            self.__cb.put('Tune', (False, "Requested freq {} is outside limits for this loop [{},{}]".format(loop, cal[0], cal[1]), []))
            self.__comms.restore_callback()
            return
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
        self.__s_q.put(('move', [pos]))
        self.__wait_for('move')
        self.__event.wait()
        self.__event.clear()
        
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
            self.__cb.put (("Tune", (True, "", swr)))
        else:
            print("Failed to obtain a SWR reading for freq {}".format(freq))
            self.__cb.put (("Tune", (False, "Failed to obtain a SWR reading for freq {}".format(freq), [])))
        self.__comms.restore_callback()
    
    # Stolen callback for move to freq    
    def t_move_to_freq_cb(self, data):
        (name, (success, msg, val)) = data
        if name == self.__wait_for:
            # Extract args and release thread
            self.__args = val
            self.__event.set()
                       
    # Switch between TX and VNA
    def switch_target(self, target):
        pass
    
    def get_current_res(self):
        pass
    
    def move_to_position(self, pos):
        # pos is given as 0-100%
        # convert this into the corresponding analog value
        home = self.__model[CONFIG][CAL][HOME]
        maximum = self.__model[CONFIG][CAL][MAX]
        if home == -1 or max == -1:
            print("Failed to move as limits are not set!")
            return
        span = maximum - home
        frac = (int(pos)/100)*span
        self.__s_q.put(('move', [int(home+frac)]))
    
    def move_fwd_for_ms(self, ms):
        self.__s_q.put(('run_fwd', [ms]))
    
    def move_rev_for_ms(self, ms):
        self.__s_q.put(('run_rev', [ms]))
    
    def nudge_fwd(self):
        self.__s_q.put(('nudge_fwd', []))
    
    def nudge_rev(self):
        self.__s_q.put(('nudge_rev', []))
    
    # =========================================================================    
    # Callback
    def serial_callback(self, data):
        # Receive status and responses from the comms thread
        (name, (r, msg, args)) = data
        if name == 'Pos':
            # Calculate and return position
            home = self.__model[CONFIG][CAL][HOME]
            maximum = self.__model[CONFIG][CAL][MAX]
            #print('get_pos: ', home, maximum)
            if home == -1 or maximum == -1:
                if VERB: print("Failed to get position as limits are not set!")
                self.__cb((name, (False, "Failed to get position as limits are not set!", [])))
            else:
                span = maximum - home
                offset = args[0] - home
                self.__cb((name, (True, "", [str(int((offset/span)*100))])))
        else:
            self.__cb(data)
        
    def cal_callback(self, data):
        # Receive status and responses from the calibrate thread
        # Just pass up to UI
        self.__cb(data)
        
# ===============================================================
# TESTING
def api_callback(data):
    print("API cb: ", data)
    
if __name__ == '__main__':
    
    model = persist.getSavedCfg('../config/flexi-loop.cfg')
    if model == None:
        print ('Configuration not found, using defaults')
        model = model.flexi_loop_model
            
    api = API(model, 'COM5', api_callback)
    api.calibrate(1)
    sleep(15)
    api.get_pos()
    sleep(1)
    api.terminate()
    print("API test exit")
        
        