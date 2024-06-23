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
from utils import *
import persist

VERB = True

# This is a relatively slow process.
# 1.    Establish the travel end points as feedback analogue values from the Arduino.
#       The analogue limits are 0-1023 but the 10 turn pot will have travel at each end
#       so actual values could be e.g. 200 - 800.These end points stay the same so this
#       is a one off calibration until a recalibration is requested.
# 2.    We need to know which loop is connected. This will be a UI function as is calling
#       calibration.
# 3.    Calibration is done according to the configuration where multiple spans can be
#       set for each loop. The actuator is positioned manually for the config limits on
#       each span and then automatically during configuration. However the frequency and
#       swr has to be entered manually.

#=====================================================
# The main calibration class
# Calibration is threaded as the UI must remain available throughout.
#===================================================== 
class Calibrate(threading.Thread):

    def __init__(self, comms, comms_q, cal_q, model, callback, msgs):
        super(Calibrate, self).__init__()
        
        # Get root logger
        self.logger = logging.getLogger('root')
        
        # Parameters
        # Serial interface and queue
        self.__comms = comms
        self.__comms_q = comms_q
        # Incoming queue
        self.__cal_q = cal_q
        # Model instance
        self.__model = model
        # Callbacks to UI for completion and messages
        self.__cb = callback
        self.__msg_cb = msgs
         
        # Instance variables       
        self.__end_points = [-1,-1]
        self.term = False
        self.__abort = False
        self.__man_cb = None
        self.__event = threading.Event()
        self.__wait_for = ""
        self.__args = []
    
    # Terminate
    def terminate(self):
        self.term = True

    # Thread entry point
    def run(self):
        self.logger.info("Running...")
        while not self.term:
            try:
                if self.__cal_q.qsize() > 0:
                    while self.__cal_q.qsize() > 0:
                        name, args = self.__cal_q.get()
                        # Execute the command
                        self.__dispatch(name, args)
                        # Returns when the command and response completes
                        self.__cal_q.task_done()
                else:
                    sleep(0.02)
            except Exception as e:
                # Something went wrong
                self.__msg_cb('Exception in calibrate: [%s]' % str(e))
                self.__cb((CONFIGURE, (False, 'Exception in calibrate: [%s]' % str(e), [])))
                self.logger.fatal('Exception in calibrate: [{}]'.format(e))
                break
        self.logger.info("Calibrate thread exiting...")
    
    # ===============================================================
    # PRIVATE
    # Command execution
    # Dispatch command
    def __dispatch(self, name, args):
        disp_tab = {
            'configure': self.__configure,
            'calibrate': self.__calibrate,
            'sync': self.__sync,
        }
        # Execute and return response
        # We need to steal the callback for the comms thread
        self.__comms.steal_callback(self.callback)
        self.__cb(disp_tab[name](args))
        # Restore the callback for the comms thread
        self.__comms.restore_callback()
    
    # Configure the feedback end points
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
        self.__msg_cb("Configuring fedback endpoints complete.")
        # Save model
        persist.saveCfg(CONFIG_PATH, self.__model)
        return (CONFIGURE, (True, '', self.__end_points))
    
    # Do calibration sequence for given loop
    def __calibrate(self, args):
        # Get args
        loop, self.__man_cb = args
        cal_map = {}
        # Retrieve the end points
        r, self.__end_points = self.retrieve_end_points()
        if not r:
            # We have a problem
            return (CALIBRATE, (False, "Unable to retrieve end points!", cal_map))
        # Create a calibration map for loop
        # Get descriptor and map for the loop
        r, sets, cal_map = self.retrieve_context(loop)
        if len(sets) == 0:
            return (CALIBRATE, (False, "Calibration sets are empty for loop: {}!".format(loop), cal_map))
        if r:
            if len(cal_map) == 0:
                try:
                    r, msg, cal_map = self.create_map(loop, sets, cal_map)
                except Exception as e:
                    print('Calibrate exception {}, [{}]'.format(e, traceback.print_exc()))
                    exit()
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
        self.save_context(loop, cal_map)
        # Save model
        persist.saveCfg(CONFIG_PATH, self.__model)
        return ('Calibrate', (True, "", cal_map))
    
    # Do calibration sequence for given loop according to the calibration differences
    # [added, removed, changed]
    def __sync(self, args):
        # Get args
        loop, self.__man_cb, cal_diff = args
        
        cal_map = []
        # Retrieve the end points
        r, self.__end_points = self.retrieve_end_points()
        if not r:
            # We have a problem
            return (CALIBRATE, (False, "Unable to retrieve end points for sync!", cal_map))
        # Create a calibration map for loop
        # Get descriptor and map for the loop
        r, sets, cal_map = self.retrieve_context(loop)
        if len(sets) == 0:
            return (CALIBRATE, (False, "Calibration sets are empty for loop: {}!".format(loop), cal_map))
        if r:
            try:
                r, msg, cal_map = self.create_synced_map(loop, sets, cal_map, cal_diff)
            except Exception as e:
                print('Calibrate exception {}, [{}]'.format(e, traceback.print_exc()))
                exit()
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
        self.save_context(loop, cal_map)
        return ('Calibrate', (True, "", cal_map))
    
    # Retrieve feedback end points from model
    def retrieve_end_points(self):
        
        h = self.__model[CONFIG][CAL][HOME]
        m = self.__model[CONFIG][CAL][MAX]
            
        if h==-1 or m==-1:
            return False, [h, m]
        else:
            return True, [h, m]
    
    # Set the feedback end points    
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
    
    # Retrieve the calibration definition and execution maps from the model 
    def retrieve_context(self, loop):
        if loop == 1:
            return True, self.__model[CONFIG][CAL][SETS][CAL_S1], copy.deepcopy(self.__model[CONFIG][CAL][CAL_L1])
        elif loop == 2:
            return True, self.__model[CONFIG][CAL][SETS][CAL_S2], copy.deepcopy(self.__model[CONFIG][CAL][CAL_L2])
        elif loop == 3:
            return True, self.__model[CONFIG][CAL][SETS][CAL_S2], copy.deepcopy(self.__model[CONFIG][CAL][CAL_L3])
        else:
            return False, (), {}

    # Save the configured/updated calibration for the loop
    def save_context(self, loop, cal_map):
        if loop == 1:
            self.__model[CONFIG][CAL][CAL_L1] = cal_map
        elif loop == 2:
            self.__model[CONFIG][CAL][CAL_L2] = cal_map
        elif loop == 3:
            self.__model[CONFIG][CAL][CAL_L3] = cal_map
    
    # Perform calibration and create the calibration map    
    def create_map(self, loop, sets, cal_map):
        
        # Just in case
        cal_map.clear()
        
        # Sets are {name: [low_freq, low_pos, high_freq, high_pos, steps], name:[...], ...}
        # Each set is treated as a calibration but combined in cal_map
        # For each set we step between low and high positions.
        
        # Current low/high pos
        current = None
        
        # Iterate the sets dictionary
        for key, values in sets.items():
            # Calibrating set n of sets
            self.__msg_cb("Calibrating set %s..." % key)
            
            # Run steps and build the cal-map
            r, msg, cal_map = self.__do_steps(loop, cal_map, key, values)
            if not r:
                return False, "Failed to generate calibration map for %s [%f]!" % (key, float(values[1])), []
        return True, '', cal_map
    
    # As above but for the map changes only
    def create_synced_map(self, loop, sets, cal_map, cal_diff):
        
        # See what we have to deal with
        added, removed, changed = cal_diff
        
        # Delete sets that have been removed
        for name in removed:
            del cal_map[name]
            
        # Sets that have been added or modified need to be re-calibrated
        # Remove sets that have changed
        for name in changed:
            del cal_map[name]
            
        # Merge the sets we need to add
        merged = added + changed
        
        # Sets are {name: [low_freq, low_pos, high_freq, high_pos, steps], name:[...], ...}
        # Each set is treated as a calibration but combined in cal_map
        # For each set we step between low and high positions.
        
        # Current low/high pos
        current = None
        
        # Iterate the sets dictionary
        for key, values in sets.items():
            # Only add merged items
            if key in merged:
                # Calibrating set n of sets
                self.__msg_cb("Calibrating set %s..." % key)
                
                # Run steps and build the cal-map
                r, msg, cal_map = self.__do_steps(loop, cal_map, key, values)
                if not r:
                    return False, "Failed to generate calibration map for %s [%f]!" % (key, float(values[1])), []
        return True, '', cal_map
    
    # Step through the given calibration set and save the points to the map    
    def __do_steps(self, loop, cal_map, name, cal_set):
        # Holds current data
        temp_map = []
        
        # Move incrementally and take readings
        # We move from high to low for the given number of steps
        # Interval is a %age of the difference between feedback readings for low and high
        [low_freq, low_pos, high_freq, high_pos, steps] = cal_set
        low_pos_abs = percent_pos_to_analog(self.__model, low_pos)
        high_pos_abs = percent_pos_to_analog(self.__model, high_pos)
        span = low_pos_abs - high_pos_abs
        fb_inc = float(span)/float(steps)
        
        # Do high pos
        if not self.__move_wait(low_pos_abs):
            self.logger.warning("Failed to move to low frequency position!")
            return False, "Failed to move to low frequency position!", cal_map
        self.__msg_cb("Please enter frequency and SWR for low limit [%s]" % str(round(low_freq, 2)), MSG_ALERT)
        r, (f, swr, pos) = self.__get_current()
        if not r:
            self.logger.warning("Failed to get params for low frequency position!")
            return False, "Failed to get params for low frequency position!", cal_map
        self.__msg_cb("Target: %d, Actual %d" % (low_pos_abs, pos))
        # Add the low position
        temp_map.append([pos, f, swr])
        
        # Do intermediate steps
        self.__msg_cb("Calibrating intermediate frequencies...")
        next_inc = round(float(low_pos_abs) - fb_inc, 0)
        counter = 0
        while next_inc > high_pos_abs:
            if not self.__move_wait(int(next_inc)):
                self.logger.warning("Failed to move to intermediate position!")
                return False, "Failed to move to intermediate position!", cal_map
            self.__msg_cb("Please enter frequency and SWR for step %d" % (counter+1), MSG_ALERT)
            r, (f, swr, pos) = self.__get_current()
            if not r:
                self.logger.warning("Failed to get params for step position!")
                return False, "Failed to get params for step position!", cal_map
            self.__msg_cb("Step: %d, Target: %d, Actual %d" % (counter, next_inc, pos)) 
            temp_map.append([pos, f, swr])
            next_inc -= fb_inc
            counter += 1
        
        # Do high pos
        if not self.__move_wait(high_pos_abs):
            self.logger.warning("Failed to move to high frequency position!")
            return False, "Failed to move to high frequency position!", cal_map
        self.__msg_cb("Please enter frequency and SWR for high frequency limit [%s]" % str(round(low_freq, 2)), MSG_ALERT)
        r, (f, swr, pos) = self.__get_current()
        if not r:
            self.logger.warning("Failed to get params for high frequency position!")
            return False, "Failed to get params for high frequency position!", cal_map
        self.__msg_cb("Target: %d, Actual %d" % (high_pos_abs, pos))
        # Add the high position
        temp_map.append([pos, f, swr])
        
        # Assign this set to the set name
        cal_map[name] = temp_map
        
        # Return the map
        return True, "", cal_map
    
    # Move to a position and wait for the response
    def __move_wait(self, move_to):
        self.__comms_q.put(('move', [move_to]))
        # Wait response
        self.__wait_for = 'MoveTo'
        if VERB: self.logger.info("Waiting for: MoveTo")
        self.__event.wait()
        if VERB: self.logger.info("Out of wait")
        if self.__abort:
            self.__event.clear()
            return False
        self.__event.clear()
        return True
    
    # Get the manual input for this step (frequency/swr)
    def __get_current(self):
        r, [vals] = self.__get_vals()
        if not r:
            self.logger.warning("Failed to get values at current step!")
            return False, (None, None, None)
        return True, vals
        
    def __get_vals(self):
        # We must interact with the UI to get user input for the readings
        while True:
            r, (f, swr, pos) = self.__man_cb()
            if r == CAL_SUCCESS:
                # This gives a MHz freq
                return True, [(float(f), float(swr), percent_pos_to_analog(self.__model, float(pos)))]
            elif r == CAL_ABORT:
                return False, [(None, None, None)]
        
    # =========================================================================
    # Callback from comms module
    # Note this is called on the comms thread and stolen from api.py
    def callback(self, data):
        
        (name, (success, msg, val)) = data
        if name == self.__wait_for:
            if VERB: self.logger.info("Calibrate: got event: {}".format(data))
            # Extract args and release thread
            self.__args = val
            self.__event.set() 
        elif name == STATUS:
            # Calculate position and directly event to API which has a pass-through to UI
            ppos = analog_pos_to_percent(self.__model, val[0])
            if ppos != None:
                self.__cb((name, (True, "", [str(ppos)])))
        elif name == ABORT:
            # Just release whatever was going on
            # It should then pick up the abort flag
            self.__abort = True
            self.__event.set() 
        else:
            if VERB: self.logger.info ("Waiting for {}, but got {}, continuing to wait!".format(self.__wait_for, name))
 