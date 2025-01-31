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
from time import sleep

# Application imports
from defs import *
import model
import serialcomms
from utils import *
import persist

VERB = True

# This is a relatively slow process.
# 1.    Establish the travel end points as feedback analogue values from the Arduino.
#       The analogue limits are 0-1023 but depends on the pot sweep.These end points stay 
#       the same so this is a one off calibration until a recalibration is requested.
# 2.    Calibration is done for the entire loop with number of steps in the config.

#=====================================================
# The main calibration class
# Calibration is threaded as the UI must remain available throughout.
#===================================================== 
class Calibrate(threading.Thread):

    def __init__(self, comms, comms_q, cal_q, vna_api, model, callback, msgs):
        super(Calibrate, self).__init__()
        
        # Get root logger
        self.logger = logging.getLogger('root')
        
        # Parameters
        # Serial interface and queue
        self.__comms = comms
        self.__comms_q = comms_q
        # Incoming queue
        self.__cal_q = cal_q
        # VNA instance
        self.__vna_api = vna_api
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
        self.__pos = 0
    
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
                self.logger.fatal('Exception in calibrate: {}, [{}]'.format(e, traceback.print_exc()))
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
            'freqlimits': self.__limits,
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
        r, self.__end_points = self.__retrieve_end_points()
        sleep(0.1)
        if not r:
            # Calibrate end points
            self.__msg_cb("Configuring potentiometer feedback end points...")
            r, msg = self.__cal_end_points()
            if not r:
                if self.__abort:
                    self.__abort = False
                    return (ABORT, (False, "Operation aborted!", [self.__end_points]))
                else:
                    return (CONFIGURE, (False, msg, []))
            r, self.__end_points = self.__retrieve_end_points()
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
        acc = []
        
        # Retrieve the end points
        r, [home, maximum] = self.__retrieve_end_points()
        sleep(0.1)
        if not r:
            # We have a problem
            return (CALIBRATE, (False, "Unable to retrieve end points!", cal_map))
        
        # Get loop limits
        sec = (LIM_1, LIM_2, LIM_3)
        low_f_vna, high_f_vna = self.__model[CONFIG][CAL][LIMITS][sec[loop-1]]
        
        # Create a calibration map for loop
        # Get number of steps for loop
        steps_for_loop = (STEPS_1, STEPS_2, STEPS_3)
        steps = self.__model[CONFIG][CAL][STEPS][steps_for_loop[loop - 1]]
        
        # We have end points and steps so work out the increment.
        fb_points =  maximum - home
        fb_inc = int(fb_points/steps)
        # Start at the home position
        new_pos = home
        # Move to each increment from home to max and get the resonant freq vswr
        for step in range(steps):
            if self.__abort:
                self.__abort = False
                return (ABORT, (False, "Configuration operation aborted!"))
            if not self.__move_wait(new_pos):
                self.logger.warning("Failed to move to feedback position!")
                return False, "Failed to move to position!", cal_map
            
            r, (f, swr, pos) = self.__manage_vals(low_f_vna, high_f_vna, "Please enter frequency and SWR for step {}, offset {}".format(n, fb_inc), MSG_ALERT)
            self.__msg_cb("Step {}, pos: actual {}, wanted {}, f {}, swr {}".format(step, pos, new_pos, f, swr))
            #print('Low: pos, pos_fb, f, swr:', low_pos_abs, pos, f, swr)
            if not r:
                self.logger.warning("Failed to get params for position!")
                return False, "Failed to get params for position!", cal_map
            
            # Add the position
            acc.append([new_pos, f, swr])
            new_pos = new_pos + fb_inc
        
        l = ('Loop-1', 'Loop_2', 'Loop-3') 
        cal_map[l[loop-1]] = acc   
        self.__msg_cb("Calibration complete", MSG_STATUS)
        self.__save_context(loop, cal_map)
        # Save model
        persist.saveCfg(CONFIG_PATH, self.__model)
        return ('Calibrate', (True, "", cal_map))
    
    # Set the frequency limits
    def __limits(self, args):
        loop, cb = args
        # If we have a VNA then set the frequency limits
        if self.__model[STATE][VNA][VNA_OPEN]:
            try:
                self.__set_limits(loop, 'move', self.__model[CONFIG][CAL][HOME], MOVETO, HOME)
                self.__set_limits(loop, 'move', self.__model[CONFIG][CAL][MAX], MOVETO, MAX)
            except Exception as e:
                self.logger.fatal('Exception in Calibrate {}, [{}]'.format(e, traceback.print_exc()))
                return (FREQLIMITS, (False, 'Exception in Calibrate {}'.format(e), []))
            self.__msg_cb("Set limits complete", MSG_STATUS)
            return (FREQLIMITS, (True, "", []))
        
    def __set_limits(self, loop, cmd, args, resp, where):
        self.__comms_q.put((cmd, [args]))
        # Wait response
        self.__wait_for = resp
        self.__event.wait()
        if self.__abort:
            self.__event.clear()
            return (FREQLIMITS, (False, "Operation aborted!", [])), 
        self.__event.clear()
        # Get the freq at this extent
        # We don't know what this loop covers so wide scan
        # We only need to be approximate as its just scan limits
        r, f, swr = self.__vna_api.get_vswr(1.8, 30.0, POINTS)
        sec = (LIM_1, LIM_2, LIM_3)
        # Give it a little breathing space each side on max and min
        if where == HOME:
            self.__model[CONFIG][CAL][LIMITS][sec[loop-1]][1] = round(f) + 2.0
        elif where == MAX:
            self.__model[CONFIG][CAL][LIMITS][sec[loop-1]][0] = round(f) - 2.0
                    
    # Retrieve feedback end points from model
    def __retrieve_end_points(self):
        
        h = self.__model[CONFIG][CAL][HOME]
        m = self.__model[CONFIG][CAL][MAX]
            
        if h==-1 or m==-1:
            return False, [h, m]
        else:
            return True, [h, m]
    
    # Set the feedback end points    
    def __cal_end_points(self):
        
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
                return False, "Operation aborted!"
            self.__event.clear()
            if act[2] != None: extents[act[2]] = self.__args[0]
        
        home = extents[0]
        maximum = extents[1]
        if abs(home - maximum) < 2:
            return False, "Actuator did not move!"
        
        self.__model[CONFIG][CAL][HOME] = extents[0]
        self.__model[CONFIG][CAL][MAX] = extents[1]
        
        return True, ""

    # =========================================================================
    # Utility methods
    
    # Save the configured/updated calibration for the loop
    def __save_context(self, loop, cal_map):
        if loop == 1:
            self.__model[CONFIG][CAL][CAL_L1] = cal_map
        elif loop == 2:
            self.__model[CONFIG][CAL][CAL_L2] = cal_map
        elif loop == 3:
            self.__model[CONFIG][CAL][CAL_L3] = cal_map
    
    # Move to a position and wait for the response
    def __move_wait(self, move_to):
        self.__comms_q.put(('move', [move_to]))
        # Wait response
        self.__wait_for = MOVETO
        if VERB: self.logger.info("Waiting for: MoveTo")
        self.__event.wait()
        if VERB: self.logger.info("Out of wait")
        if self.__abort:
            self.__event.clear()
            return False, "Operation aborted!"
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
                return True, [(float(f), float(swr), float(pos))]
            elif r == CAL_ABORT:
                return False, [(None, None, None)]
    
    # Get values at this point from user or VNA
    def __manage_vals(self, start, stop, msg, msg_type):
        if self.__model[STATE][VNA][VNA_OPEN]:
            # Get current from VNA
            sleep(0.5)
            r, f, swr = self.__vna_api.get_vswr(start, stop, POINTS)
            if r:
                return True, (f, swr, self.__pos)
            else:
                return False, (None, None, None)
        else:
            # Get current from user
            self.__msg_cb(msg, msg_type)
            r, (f, swr, pos) = self.__get_current()
            
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
            self.__pos = val[0]
            ppos = analog_pos_to_percent(self.__model, val[0])
            if ppos != None:
                self.__cb((name, (True, "", [str(ppos), val[0]])))
        elif name == DEBUG:
            if VERB: self.logger.info("Calibrate: got debug: {}".format(data))
        elif name == ABORT:
            # Just release whatever was going on
            # It should then pick up the abort flag
            self.__abort = True
            self.__event.set() 
        else:
            # Wrong response means something has in the sequence has messed up
            if VERB: self.logger.info ("Waiting for {}, but got {}. Aborting current operation!".format(self.__wait_for, name))
            self.__abort = True
            self.__event.set() 
 