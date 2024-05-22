#!/usr/bin/env python
#
# calibrate.py
#
# Flexi-Loop calibration sequence
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
import copy

# Application imports
from defs import *
import model
import serialcomms

VERB = False

# This is a relatively slow process.
# 1.    Establish the travel end points as feedback analogue values from the Arduino.
#       The analogue limits are 0-1023 but the 10 turn pot will have travel at each end
#       so actual values could be e.g. 200 - 800.These end points stay the same so this
#       is a one off calibration until a recalibration is requested.
# 2.    We need to know which loop is connected. This will be a UI function as is calling
#       (re)calibration.
# 3.    We set calibration point at the (user selectable) interval as a percentage of
#       the full travel. So if we select 10% there will be 11 calibration points. The
#       more points the slower calibration will be but the quicker the (re)tuning as we
#       get closer to the requested frequency.
# 4.    At each calibration point we get a resonance reading and SWR from the VNA.
# 5.    The tables of readings are stored and retrieved. If there is no retrieved table
#       for the current loop the user will be asked to perform calibration.

#=====================================================
# The main application class
#===================================================== 
class Calibrate(threading.Thread):

    def __init__(self, comms, comms_q, cal_q, model, callback, msgs):
        super(Calibrate, self).__init__()
        
        # Get root logger
        self.logger = logging.getLogger('root')
        
        self.__comms = comms
        self.__comms_q = comms_q
        self.__cal_q = cal_q
        self.__model = model
        self.__cb = callback
        self.__msg_cb = msgs
                
        self.__end_points = [-1,-1]
        self.term = False
        self.__abort = False
        self.__man_cb = None
        
        self.__event = threading.Event()
        self.__wait_for = ""
        self.__args = []
    
    # Terminate instance
    def terminate(self):
        """ Thread terminating """
        self.term = True

    # Thread entry point
    def run(self):
        self.logger.info("Running...")
        while not self.term:
            try:
                if self.__cal_q.qsize() > 0:
                    while self.__cal_q.qsize() > 0:
                        name, args = self.__cal_q.get()
                        # By default this is synchronous so will wait for the response
                        # Response goes to main code callback, we don't care here
                        self.__dispatch(name, args)
                        self.__cal_q.task_done()
                else:
                    sleep(0.02)
            except Exception as e:
                # Something went wrong
                print(str(e))
                #self.__cb('fatal: {0}'.format(e))
                break
        self.logger.info("Calibrate thread exiting...")
    
    # ===============================================================
    # PRIVATE
    # Command execution
    # Switcher
    def __dispatch(self, name, args):
        disp_tab = {
            'configure': self.__configure,
            'calibrate': self.__calibrate,
        }
        # Execute and return response
        # We need to steal the callback for the comms thread
        self.__comms.steal_callback(self.callback)
        self.__cb(disp_tab[name](args))
        # Restore the callback for the comms thread
        self.__comms.restore_callback()
    
    def __configure(self, args):
        # Retrieve the end points
        r, self.__end_points = self.retrieve_end_points()
        if not r:
            # Calibrate end points
            self.__msg_cb("Configuring potentiometer feedback end points...")
            r, msg = self.cal_end_points()
            if not r:
                if self.__abort:
                    self.__abort = False
                    return (ABORT, (False, "Operation aborted by user!", [self.__end_points]))
                else:
                    return (CONFIGURE, (False, msg, []))
            r, self.__end_points = self.retrieve_end_points()
            if not r:
                # We have a problem
                return (CONFIGURE, (False, "Unable to retrieve or create end points!", self.__end_points))
            # Check for correct values
            if self.__end_points[0] > self.__end_points[1]:
                # pot hot ends are reversed
                return (CONFIGURE, (False, "Reverse pot hot ends, home > max. Configure again: {}!".format(self.__end_points), self.__end_points))
        return (CONFIGURE, (True, '', self.__end_points))
    
    def __calibrate(self, args):
        # Get args
        loop, self.__man_cb = args
        cal_map = []
        # Retrieve the end points
        r, self.__end_points = self.retrieve_end_points()
        if not r:
            # We have a problem
            return (CALIBRATE, (False, "Unable to retrieve end points!", cal_map))
        # Create a calibration map for loop
        # Get descriptor and map for the loop
        r, sets, cal_map = self.retrieve_context(loop)
        if r:
            if len(cal_map) == 0:
                r, msg, cal_map = self.create_map(loop, sets, cal_map)
                if not r:
                    if self.__abort:
                        self.__abort = False
                        return (ABORT, (False, "Operation aborted by user!", []))
                    else:
                        # We have a problem
                        return (CALIBRATE, (False, "Unable to create a calibration map for loop: {}!".format(loop), cal_map))
        else:
            self.logger.warning ("Error in retrieving calibration map!: {}".format(cal_map))
            return (CALIBRATE, (False, "Error in retrieving calibration map!", cal_map))
        
        self.__msg_cb("Calibration complete", MSG_STATUS)
        self.save_context(self, loop, cal_map)
        return ('Calibrate', (True, "", cal_map))
     
    def retrieve_end_points(self):
        
        h = self.__model[CONFIG][CAL][HOME]
        m = self.__model[CONFIG][CAL][MAX]
            
        if h==-1 or m==-1:
            return False, [h, m]
        else:
            return True, [h, m]
        
    def cal_end_points(self):
        
        extents = [0, 0]    # home, max
        # Note we do max first as that positions us at home for next phase
        seq = (('max', 'Max', None), ('pos', 'Pos', 1), ('home', 'Home', None), ('pos', 'Pos', 0))
        
        for act in seq:
            self.__comms_q.put((act[0], []))
            # Wait response
            self.__wait_for = act[1]
            self.__event.wait()
            if self.__abort:
                self.__event.clear()
                return False, "Aborted by user!"
            self.__event.clear()
            if act[2] != None: extents[act[2]] = self.__args[0]      
        
        home = extents[0]
        maximum = extents[1]
        if abs(home - maximum) < 2:
            return False, "Actuator did not move!"
        
        self.__model[CONFIG][CAL][HOME] = extents[0]
        self.__model[CONFIG][CAL][MAX] = extents[1]
            
        return True, ""
    
    def retrieve_context(self, loop):
        if loop == 1:
            return True, self.__model[CONFIG][CAL][SETS][CAL_S1], copy.deepcopy(self.__model[CONFIG][CAL][CAL_L1])
        elif loop == 2:
            return True, self.__model[CONFIG][CAL][SETS][CAL_S2], copy.deepcopy(self.__model[CONFIG][CAL][CAL_L2])
        elif loop == 3:
            return True, self.__model[CONFIG][CAL][SETS][CAL_S2], copy.deepcopy(self.__model[CONFIG][CAL][CAL_L3])
        else:
            return False, []

    def save_context(self, loop, cal_map):
        if loop == 1:
            self.__model[CONFIG][CAL][CAL_L1] = cal_map
        elif loop == 2:
            self.__model[CONFIG][CAL][CAL_L2] = cal_map
        elif loop == 3:
            self.__model[CONFIG][CAL][CAL_L3] = cal_map
        
    def create_map(self, loop, sets, cal_map):
        
        # Just in case
        cal_map.clear()
        
        # Sets are {name: [low_freq, high_freq, steps], name:[...], ...}
        # Each set is treated as a calibration but combined in cal_map
        # For each set we must ask the user to move to the low and then high freq
        # such that we can get the feedback values and then we can work out the steps
        # and do those in sequence asking the user to enter freq and SWR at each step.
        
        # Current low/high pos
        current = None
        
        # Iterate the sets dictionary
        for key, values in sets.items():
            # Calibrating set n of sets
            self.__msg_cb("Calibrating set %s..." % key)
            # Ask the user to move to the low frequency
            r, [(f_low, swr_low, pos_low)] = self.__get_current(values[0], HINT_MOVETO, 'Move to %f' % float(values[0]))
            if not r:
                self.logger.warning("Failed to move to low frequency for set %s!" % key)
                return False, "Failed to move to low frequency for set %s [%f]!" % (key, float(values[0]))
            # Ask the user to move to the high frequency
            r, [(f_high, swr_high, pos_high)] = self.__get_current(float(values[1]), HINT_MOVETO, 'Move to %f' % float(values[1]))
            if not r:
                self.logger.warning("Failed to move to High frequency for set %s [%f]!" % (key, float(values[1])))
                return False, "Failed to move to high frequency for set %s [%f]!" % (key, float(values[1])), []
            # Stash these values
            current = [values[2], [f_low, swr_low, pos_low], [f_high, swr_high, pos_high]]
            
            # Now do the intermediate steps and build the cal-map
            r, msg, cal_map = self.__do_steps(self, loop, cal_map, current)
            if not r:
                return False, "Failed to generate calibration map for %s [%f]!" % (key, float(values[1])), []
        return True, '', cal_map       
        
    def __do_steps(self, loop, cal_map, current):
        # Move incrementally and take readings
        # We move from high to low for the given number of steps
        # Interval is a %age of the difference between feedback readings for low and high
        
        [steps, [f_low, swr_low, pos_low], [f_high, swr_high, pos_high]] = current
        
        span = pos_high - pos_low
        feedback_inc = span/steps
        
        # Add the high position
        cal_map.append([pos_low, f_low, swr_low])
        
        # Add intermediate positions
        self.__msg_cb("Calibrating step frequencies...")
        next_inc = pos_high + feedback_inc
        counter = 0
        while next_inc < pos_low:
            # Comment out if motor not running
            self.__comms_q.put(('move', [next_inc]))
            # Wait response
            self.__wait_for = 'MoveTo'
            self.__event.wait()
            if self.__abort:
                self.__event.clear()
                return False, None, None
            self.__event.clear()

            r, [(f, swr, pos)] = self.__get_current(values[0], HINT_STEP, 'Enter frequency and SWR at this step.')
            if not r:
                self.logger.warning("Failed to get values at current step!")
                return False, "Failed to get resonant frequency!", cal_map
            cal_map.append([pos, f, swr])
            next_inc += inc
            counter += 1
            
        # Add the low position
        cal_map.append([pos_low, f_low, swr_low])
            
        # Return the map
        return True, "", cal_map
    
    def __get_current(self, f, hint, msg):
        # We must interact with the UI to get user input for the readings
        if hint == HINT_MOVETO:
            self.__msg_cb("Please move to given freq {} [{}]".format(str(f), msg), MSG_ALERT)
        elif hint == HINT_STEP:
            self.__msg_cb("Please enter frequency and swr for this step [{}]".format(msg), MSG_ALERT)
        # This is a manual entry so no reason why it should fail unless no entry
        while True:
            r, (f, swr, pos) = self.__man_cb(hint)
            if r == CAL_SUCCESS:
                # This gives a MHz freq
                return True, [(float(f), float(swr), pos)]
            elif r == CAL_ABORT:
                return (False, [(None, None, None)])
        
    # =========================================================================
    # Callback from comms module
    # Note this is called on the comms thread and stolen from api.py
    def callback(self, data):
        
        if VERB: self.logger.info("Calibrate: got event: %s" % str(data))
        (name, (success, msg, val)) = data
        if name == self.__wait_for:
            # Extract args and release thread
            self.__args = val
            self.__event.set() 
        elif name == STATUS:
            # Calculate position and directly event to API which has a pass-through to UI
            home = self.__model[CONFIG][CAL][HOME]
            maximum = self.__model[CONFIG][CAL][MAX]
            if home > 0 and maximum > 0:
                span = maximum - home
                offset = val[0] - home
                self.__cb((name, (True, "", [str(int((offset/span)*100))])))
        elif name == ABORT:
            # Just release whatever was going on
            # It should then pick up the abort flag
            self.__abort = True
            self.__event.set() 
        else:
            if VERB: self.logger.info ("Waiting for %s, but got %s, continuing to wait!" % (self.__wait_for, name))
 