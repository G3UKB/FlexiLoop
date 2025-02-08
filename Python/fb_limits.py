#!/usr/bin/env python 
#
# fb_limits.py
#
# manage setting the feedback limits in the Arduino
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
# Set limits when changed
#===================================================== 
class FBLimits(threading.Thread):
    
    def __init__(self, model, s_q, comms, msg_cb):
        super(FBLimits, self).__init__()
        # Get root logger
        self.logger = logging.getLogger('root')
        
        # Parameters
        self.__model = model
        self.__s_q = s_q
        self.__serial_comms = comms
        self.__msg_cb = msg_cb
        
        # Instance vars
        self.__event = threading.Event()
        self.one_pass = False
        self.term = False
        self.__home_limit = -1
        self.__max_limit = -1
        self.__wait_for = None
    
    # Perform one tuning pass for given loop and frequency
    def do_one_pass(self):
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
                if self.term: break
            if self.term: break
            self.one_pass = False
            
            # Check for change in limits
            try:
                # Need to steal the serial comms callback
                self.__serial_comms.steal_callback(self.limits_cb)
                homevalue = self.__model[CONFIG][CAL][HOME]
                maxvalue = self.__model[CONFIG][CAL][MAX]
                if homevalue != self.__home_limit or maxvalue != self.__max_limit:
                    # We have a change
                    self.__home_limit = homevalue
                    self.__max_limit = maxvalue
                    self.__s_q.put(('set_home', [self.__home_limit]))
                    self.__wait_for = HOMEVAL
                    self.__event.wait()
                    self.__event.clear()
                    self.__s_q.put(('set_max', [self.__max_limit]))
                    self.__wait_for = MAXVAL
                    self.__event.wait()
                    self.__event.clear() 
            except Exception as e:
                self.logger.warn("Exception in fb_limits [{}]".format(e))
                self.__msg_cb('Exception in fb_limits, please check log.', MSG_ALERT)
                break
            
            # Give back callback
            self.__serial_comms.restore_callback()
            
        print("FBLimits thread  exiting...")
    
    # Stolen callback    
    def limits_cb(self, data):
        (name, (success, msg, val)) = data
        if name == self.__wait_for:
            self.__event.set() 
        elif name == STATUS:
            # Very infrequent abd short lived so ignore
            pass
        elif name == DEBUG:
            # Very infrequent abd short lived so ignore
            pass
        elif name == ABORT:
            # Just release whatever was going on
            # It should then pick up the abort flag
            self.__event.set() 
        else:
            self.logger.info ("Waiting for {}, but got {}!".format(self.__wait_for, name))
            self.__msg_cb("Waiting for {}, but got {}!".format(self.__wait_for, name))
            self.__event.set() 
            