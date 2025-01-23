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
import tune

# Verbose flag
VERB = False

#=====================================================
# The Programming Interface class
#===================================================== 
class API:
    
    # Initialisation
    def __init__(self, model, vna_api, cb, msgs_cb):
        
        # Get root logger
        self.logger = logging.getLogger('root')
        
        # Params
        # Current model instance
        self.__model = model
        # VNA instance
        self.__vna_api = vna_api
        # Callback for completion of function
        self.__cb = cb
        # Callback for messages
        self.__msgs = msgs_cb
        
        # Create a SerialComms instance
        self.__s_q = queue.Queue(10)
        self.__serial_comms = serialcomms.SerialComms(self.__model, self.__s_q, self.serial_callback)
        
        # Create a Calibration instance
        self.__c_q = queue.Queue(10)
        self.__cal = calibrate.Calibrate(self.__serial_comms, self.__s_q, self.__c_q, self.__vna_api, model, self.cal_callback, self.__msgs)
        # and start the thread
        self.__cal.start()
        
        # Create a tune inetance
        self.__tune = tune.Tune(self.__model, self.__serial_comms, self.__s_q, self.__vna_api, self.__cb)
        # and start the thread
        self.__tune.start()
        
        # State
        self.__serial_running = False
        self.__event = threading.Event()
        self.__wait_for = ""
        self.__args = []
        self.__absolute_pos = -1
    
    # Called to (re)connect to the Arduino via the serial link
    def init_comms(self):
        if self.__serial_running:
            # We were running but there has been a disconnection
            # We need to start again as a thread cannot be restarted
            self.__serial_running = False
            self.__serial_comms = None
            self.__serial_comms = serialcomms.SerialComms(self.__model, self.__s_q, self.serial_callback)
            if self.__serial_comms.connect():
                self.__serial_comms.start()
                self.__serial_running = True
                self.__msgs('Serial comms running')
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
        # Terminate all and wait for threads to exit
        self.logger.info("Terminating API and dependencies")
        
        if self.__model[STATE][VNA][VNA_OPEN]:
            self.__vna_api.close()
        if self.__serial_running:
            self.__serial_comms.terminate()
            self.__serial_comms.join()
        self.__cal.terminate()
        self.__cal.join()
        self.__tune.terminate()
        self.__tune.join()
    
    #=================================================================================
    # API functions
    # All function must dispatch to a queue and return immediately. If any work is
    # done in this module the UI will be locked for that period. Where responses are
    # required these are managed through callbacks to the UI.
    
    # Perform a configure for the feedback system    
    def configure(self):
        self.logger.info("Configuring potentiometer limits. This may take a while...")
        self.__c_q.put(('configure', []))
        
    # Perform a calibration for the given loop    
    def calibrate(self, loop, man_cb):
        self.logger.info("Calibrating loop: {}. This may take a while...".format(loop))
        self.__c_q.put(('calibrate', [loop, man_cb]))
    
    # Sync calibration with the loop span definitions
    def sync(self, loop, man_cb, cal_diff):
        self.logger.info("Syncing loop: {}. This may take a while...".format(loop))
        self.__c_q.put(('sync', [loop, man_cb, cal_diff]))
    
    def set_limits(self, loop, man_cb):
        self.logger.info("Setting loop limits: {}. This may take a while...".format(loop))
        self.__c_q.put(('freqlimits', [loop, man_cb]))
        
    # Move to lowest SWR for loop on given frequency
    # This is threaded separately as its long running multiple calls
    def move_to_freq(self, loop, freq):
        self.__tune.do_one_pass(loop, freq)
    
    # Move to a given extension
    def move_to_position(self, pos, using=MOVE_ABS):
        if using == MOVE_ABS:
            # pos is a feedback value
            self.__s_q.put(('move', [pos]))
        else:
            # pos is 0-100%
            # convert this into the corresponding analog value
            home = self.__model[CONFIG][CAL][HOME]
            maximum = self.__model[CONFIG][CAL][MAX]
            if home == -1 or max == -1:
                self.logger.warning("Failed to move as limits are not set!")
                return
            span = maximum - home
            frac = (int(pos)/100)*span
            self.__s_q.put(('move', [int(home+frac)]))
    
    # Simple functions
    # Change speed
    def speed_change(self, speed):
        self.__s_q.put(('speed', [speed]))
        
    # Get position as a %age of extension
    def get_pos(self):
        self.__s_q.put(('pos', []))
    
    # Forward for given ms    
    def move_fwd_for_ms(self, ms):
        self.__s_q.put(('run_fwd', [ms]))
    
    # Reverse for given ms
    def move_rev_for_ms(self, ms):
        self.__s_q.put(('run_rev', [ms]))
    
    # Nudge forward
    def nudge_fwd(self):
        self.__s_q.put(('nudge_fwd', []))
    
    # Nudge reverse
    def nudge_rev(self):
        self.__s_q.put(('nudge_rev', []))
    
    # Move forward until end of travel of stopped
    def free_fwd(self):
        self.__s_q.put(('free_fwd', []))
    
    # Move reverse until end of travel of stopped    
    def free_rev(self):
        self.__s_q.put(('free_rev', []))
    
    # Stop a forward or reverse run
    def free_stop(self):
        self.__s_q.put(('free_stop', []))
    
    # Switch relay to radio side    
    def radio_mode(self):
        self.__s_q.put(('relay_off', []))
    
    # Switch relay to analyser side    
    def analyser_mode(self):
        self.__s_q.put(('relay_on', []))
    
    # Abort is complex of which informing the serial module to abort the
    # current activity is part.
    def abort_activity(self):
        self.__s_q.put(('abort', []))
    
    # VNA
    def get_resonance(self, start, end, points=101):
        return self.__vna_api.get_vswr(start, end, points)
        
    # =========================================================================    
    # Callbacks
    # In general the serial module will callback here when a function completes
    # This is the main callback for serial functions to the UI. However in some cases
    # for complex operations (calibrate and tune) another module may steal the callback
    # for a while because it needs to handle multiple completions before handing
    # the final result back to the UI.
    
    def serial_callback(self, data):
        # Receive status and responses from the comms thread
        (name, (r, msg, args)) = data
        if name == POS or name == STATUS:
            # Calculate and return position
            # We need to save the absolute pos not the %age pos
            self.__absolute_pos = args[0]
            ppos = analog_pos_to_percent(self.__model, self.__absolute_pos)
            self.__cb((name, (True, "", [str(ppos), str(self.__absolute_pos)])))
        else:
            self.__cb(data)
    
    # When we do get a calibration callback we just hand it up to the UI.    
    def cal_callback(self, data):
        # Receive status and responses from the calibrate thread
        self.__cb(data)
    
        