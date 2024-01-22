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
import tune

# Verbose flag
VERB = False

#=====================================================
# The Programming Interface class
#===================================================== 
class API:
    
    # Initialisation
    def __init__(self, model, port, callback, msgs):
        
        # Get root logger
        self.logger = logging.getLogger('root')
        
        # Params
        self.__model = model
        self.__port = port
        self.__cb = callback
        self.__msgs = msgs
        
        # Create a SerialComms instance
        self.__s_q = queue.Queue(10)
        self.__serial_comms = serialcomms.SerialComms(self.__model, self.__port, self.__s_q, self.serial_callback)
        
        # Create a VNA instance
        self.__vna = vna.VNA(model)
        
        # Create a Calibration instance
        self.__c_q = queue.Queue(10)
        self.__cal = calibrate.Calibrate(self.__serial_comms, self.__s_q, self.__c_q, self.__vna, model, self.cal_callback, msgs)
        # and start the thread
        self.__cal.start()
        
        # Create a tune inetance
        self.__tune = tune.Tune(self.__model, self.__serial_comms, self.__vna, self.__s_q, self.__cb)
        # and start the thread
        self.__tune.start()
        
        # State
        self.__serial_running = False
        self.__event = threading.Event()
        self.__wait_for = ""
        self.__args = []
        self.__absolute_pos = -1
    
    def init_comms(self):
        if self.__serial_running:
            self.__msgs('Serial comms running')
            # We were running but there has been a disconnection
            # We need to start again as a thread cannot be restarted
            self.__serial_comms = None
            self.__serial_comms = serialcomms.SerialComms(self.__model, self.__port, self.__s_q, self.serial_callback)
            if self.__serial_comms.connect():
                self.__serial_comms.start()
                self.__serial_running = True
                return True
        else:
            # Not yet running so we can connect and start the thread
            if self.__serial_comms.connect():
                self.__msgs('Serial comms running')
                self.__serial_comms.start()
                self.__serial_running = True
                return True     
        return False
            
    # Termination
    def terminate(self):
        if self.__serial_running:
            self.__serial_comms.terminate()
            self.__serial_comms.join()
        self.__cal.terminate()
        self.__cal.join()
        self.__tune.terminate()
        self.__tune.join()
    
    # Perform a calibration for the given loop    
    def calibrate(self, loop, manual, man_cb):
        self.logger.info("Calibrating loop: {}. This may take a while...".format(loop))
        self.__c_q.put(('calibrate', [loop, self.__model[CONFIG][CAL][ACTUATOR_STEPS], manual, man_cb]))
        
    # Perform a re-calibration for the given loop    
    def re_calibrate(self, loop):
        self.logger.info("Calibrating loop: {}. This may take a while...".format(loop))
        self.__c_q.put(('re_calibrate_loop', [loop, self.__model[CONFIG][CAL][ACTUATOR_STEPS]]))
        
    # Get position as a %age of full travel
    def get_pos(self):
        self.__s_q.put(('pos', []))
    
    # Move to lowest SWR for loop on given frequency
    # This is threaded separately as its long running multiple calls
    def move_to_freq(self, loop, freq):
        self.__tune.do_one_pass(loop, freq)
    
    def get_current_res(self, loop):
        # Work out where we are and do a limited frequency scan to cut down the time lag.
        if self.__absolute_pos == -1:
            self.get_pos()
            while self.__absolute_pos == -1:
                sleep(0.1)
        pos = self.__absolute_pos

        # Find the two calibration points this pos falls between
        cal = model_for_loop(self.__model, loop)
        index = 0
        idx_low = 0
        idx_high = 0
        # The list is in high to low frequency order as home is fully retracted
        while index < len(cal[2]):
            if cal[2][index][0] < pos and cal[2][index+1][0] > pos:
                # Lower than target
                idx_high = index+1 
                idx_low = index
                break
            else:
                index += 1
        # Get the corresponding frequencies
        lowf = cal[2][idx_high][1]
        highf = cal[2][idx_low][1]
        
        # Get the resonant frequency between the given frequencies
        rf, [(f,swr)] = self.__vna.fres(int(lowf*1000000), int(highf*1000000), INC_1K, VNA_RANDOM)
        # and the SWR at that frequency
        #rs, swr = self.__vna.fswr(f)
        # Return result
        if rf:
            return True, (f, swr)
        else:
            return False, ()
    
    def move_to_position(self, pos):
        # pos is given as 0-100%
        # convert this into the corresponding analog value
        home = self.__model[CONFIG][CAL][HOME]
        maximum = self.__model[CONFIG][CAL][MAX]
        if home == -1 or max == -1:
            self.logger.warning("Failed to move as limits are not set!")
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
    
    def free_fwd(self):
        self.__s_q.put(('free_fwd', []))
        
    def free_rev(self):
        self.__s_q.put(('free_rev', []))
    
    def free_stop(self):
        self.__s_q.put(('free_stop', []))
        
    def abort_activity(self):
        self.__s_q.put(('abort', []))
        
    def tx_mode(self):
        self.__s_q.put(('relay_on', []))
        
    def vna_mode(self):
        self.__s_q.put(('relay_off', []))
    
    # =========================================================================    
    # Callback
    def serial_callback(self, data):
        # Receive status and responses from the comms thread
        (name, (r, msg, args)) = data
        if name == 'Pos' or name == 'Status':
            # Calculate and return position
            home = self.__model[CONFIG][CAL][HOME]
            maximum = self.__model[CONFIG][CAL][MAX]
            if home == -1 or maximum == -1:
                if VERB: self.logger.warning("Failed to get position as limits are not set!")
                self.__cb((name, (False, "Failed to get position as limits are not set!", [])))
            else:
                # We need to save the absolute pos not the %age pos
                self.__absolute_pos = args[0]
                span = maximum - home
                offset = args[0] - home
                self.__cb((name, (True, "", [str(int((offset/span)*100))])))
        else:
            self.__cb(data)
        
    def cal_callback(self, data):
        # Receive status and responses from the calibrate thread
        # Just pass up to UI
        self.__cb(data)
    
        