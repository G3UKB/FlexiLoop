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

# Application imports
from defs import *
import model
import serialcomms
import vna

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

    def __init__(self, comms, comms_q, cal_q, vna, model, callback, msgs):
        super(Calibrate, self).__init__()
        
        # Get root logger
        self.logger = logging.getLogger('root')
        
        self.__comms = comms
        self.__comms_q = comms_q
        self.__cal_q = cal_q
        self.__vna = vna
        self.__model = model
        self.__cb = callback
        self.__msg_cb = msgs
                
        self.__end_points = [-1,-1]
        self.term = False
        self.__abort = False
        self.__manual = False
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
                return (CONFIGURE, (False, "Reverse pot hot ends, home > max. Configure again: {}!".format(loop), self.__end_points))
        return (CONFIGURE, (True, '', self.__end_points))
    
    def __calibrate(self, args):
        loop, steps, self.__manual, self.__man_cb, mode = args
        # If mode is CAL_STEPS then we onlt dedo the steps
        # Check we have valid end points and min/msx freq then delete step points and redo
        if mode == CAL_STEPS:
            return self.__cal_steps_only(loop, steps, self.__manual, self.__man_cb)
        
        cal_map = []
        # Retrieve the end points
        r, self.__end_points = self.retrieve_end_points()
        if not r:
            # Calibrate end points
            self.__msg_cb("Calibrating potentiometer feedback end points...")
            r, msg = self.cal_end_points()
            if not r:
                if self.__abort:
                    self.__abort = False
                    return (ABORT, (False, "Operation aborted by user!", cal_map))
                else:
                    return (CALIBRATE, (False, msg, cal_map))
            r, self.__end_points = self.retrieve_end_points()
            if not r:
                # We have a problem
                return (CALIBRATE, (False, "Unable to retrieve or create end points!", cal_map))
            # Check for correct values
            if self.__end_points[0] > self.__end_points[1]:
                # pot hot ends are reversed
                return (CALIBRATE, (False, "Reverse pot hot ends, home > max. Calibrate again: {}!".format(loop), self.__end_points))
        # Create a calibration map for loop
        r, cal_map = self.retrieve_map(loop)
        if r:
            if len(cal_map) == 0:
                r, msg, cal_map = self.create_map(loop, steps)
                if not r:
                    if self.__abort:
                        self.__abort = False
                        return (ABORT, (False, "Operation aborted by user!", []))
                    else:
                        # We have a problem
                        return (CALIBRATE, (False, "Unable to create a calibration map for loop: {}!".format(loop), cal_map))
        else:
            self.logger.warning ("Error in calibration map: " % msg)
            return (CALIBRATE, (False, msg, cal_map))
        
        self.__msg_cb("Calibration complete", MSG_STATUS)
        return ('Calibrate', (True, "", cal_map))
     
    def __cal_steps_only(self, loop, steps, manual, man_cb):
        # Retrieve the end points
        r, self.__end_points = self.retrieve_end_points()
        if not r:
            return (CALIBRATE, (False, "Unable to create new steps as end points are not configured: {}!".format(loop), cal_map))
    
        # Get current map
        r, cal_map = self.retrieve_map(loop)
        if r:
            # Check map
            # map is of form e.g.
            # [12.0, 3.0, [[500, 12.0, 1.0], [...], ...]]
            if len(cal_map) >= 2:
                # Assume we have max and min frequencies
                fhome = cal_map[0] # highest f
                fmax = cal_map[1] # lowest f
                # save min/max
                new_map = [fhome, fmax, []]
                # Configure steps
                self.__do_steps(new_map)
                self.__msg_cb("Calibration complete", MSG_STATUS)
                return ('Calibrate', (True, "", new_map))
        else:
            return (CALIBRATE, (False, "Unable to create new steps as min/max freq are not configured: {}!".format(loop), cal_map))
    
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
    
    def retrieve_map(self, loop):
        if loop == 1:
            return True, self.__model[CONFIG][CAL][CAL_L1]
        elif loop == 2:
            return True, self.__model[CONFIG][CAL][CAL_L2]
        elif loop == 3:
            return True, self.__model[CONFIG][CAL][CAL_L3]
        else:
            return False, []

    def create_map(self, loop, steps):
        
        # Get map for model
        r, m = self.retrieve_map(loop)
        if not r:
            self.logger.warning("Invalid loop id: %d" % loop)
            return False, "Invalid loop id: %d" % loop, []
        m.clear()
        
        # Move max and take a reading
        self.__msg_cb("Calibrating low frequency...")
        self.__comms_q.put(('max', []))
        # Wait response
        self.__wait_for = 'Max'
        self.__event.wait()
        if self.__abort:
            self.__event.clear()
            return False, None, None
        self.__event.clear()
        # Get res freq approx as its a full sweep takes a while
        r, [(fmax, swrmax)] = self.__get_current(MIN_FREQ, MAX_FREQ, INC_10K, VNA_MAX)
        if not r:
            self.logger.warning("Failed to get low frequency!")
            return False, "Failed to get low frequency!", []
        
        # Move home and take a reading
        self.__msg_cb("Calibrating high frequency...")
        self.__comms_q.put(('home', []))
        # Wait response
        self.__wait_for = 'Home'
        self.__event.wait()
        if self.__abort:
            self.__event.clear()
            return False, None, None
        self.__event.clear()
        # get res freq
        r, [(fhome, swrhome)] = self.__get_current(MIN_FREQ, MAX_FREQ, INC_10K, VNA_HOME)
        if not r:
            self.logger.warning("Failed to get high frequency!")
            return False, "Failed to get high frequency!", []
        
        if abs(fhome - fmax) < 2:
            # Looks like the actuator didn't move
            self.logger.warning("Actuator did not move, calibration abandoned!")
            return False, "Actuator did not move!", []
        
        # Save limits for this loop
        m = [fhome, fmax, []]
        return __do_steps(m)
        
    def __do_steps(self, m):
        # Move incrementally and take readings
        # We move from home to max by interval
        # Interval is a %age of the difference between feedback readings for home and max
        home, maximum = self.__end_points
        span = maximum - home
        inc = span/steps
        # Calc approx freq inc for each step
        fspanhz = int((fhome-fmax) * 1000000)
        fhzperstep = int(fspanhz/steps)
        # Centre next approx freq
        nextf_approx = int(fhome * 1000000)
        hzhome = int(fhome * 1000000)
        
        # Add the home position
        m[2].append([int(home), fhome, swrhome])
        
        # Add intermediate positions
        self.__msg_cb("Calibrating step frequencies...")
        next_inc = home + inc
        counter = 0
        while next_inc < maximum:
            # Comment out if motor not running
            self.__comms_q.put(('move', [next_inc]))
            # Wait response
            self.__wait_for = 'MoveTo'
            self.__event.wait()
            if self.__abort:
                self.__event.clear()
                return False, None, None
            self.__event.clear()
        
            # We don't want to do a full frequency scan for this loop on every point as it would take for ever.
            # We need to split the scan into chunks
            # The chunk should encompass each resonant frequency at the offset.
            fhigh = hzhome - (fhzperstep * counter)
            flow = hzhome - (fhzperstep * (counter+1))
            # Need a little more accuracy so every 1KHz should suffice
            r, [(f, swr)] = self.__get_current(flow, fhigh, INC_1K, VNA_MID)
            if not r:
                self.logger.inwarningfo("Failed to get resonant frequency!")
                return False, "Failed to get resonant frequency!", m
            m[2].append([int(next_inc), f, swr])
            next_inc += inc
            counter += 1
            
        # Add the max position
        m[2].append([int(maximum), fmax, swrmax])
        
        if loop == 1:
            self.__model[CONFIG][CAL][CAL_L1] = m
        elif loop == 2:
            self.__model[CONFIG][CAL][CAL_L2] = m
        elif loop == 3:
            self.__model[CONFIG][CAL][CAL_L3] = m
            
        # Return the map
        return True, "", m
    
    def __get_current(self, flow, fhigh, inc, hint):
        if self.__manual:
            # We must interact with the UI to get user input for the readings
            self.__msg_cb("Please enter frequency and swr for this calibration point [%s]" % hint, MSG_ALERT)
            # This is a manual entry so no reason why it should fail unless no entry
            while True:
                r, (f, swr) = self.__man_cb(hint)
                if r == CAL_SUCCESS:
                    # This gives a MHz freq
                    return True, [(float(f), float(swr))]
                elif r == CAL_ABORT:
                    return (False, [(None, None)])
        else:
            # This gives a Hz freq so conversion necessary
            (r, [(f, swr)]) = self.__vna.fres(flow, fhigh, inc, hint = hint)
            return (r, [(float(f)/1000000.0, swr)])
        
    # =========================================================================
    # Callback from comms module
    # Note this is called on the comms thread and stolen from api.py
    def callback(self, data):
        
        if VERB: self.logger.info("Calibrate: got event: ", data)
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
 