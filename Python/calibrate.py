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

# Set False when testing
MODEL = True
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
            'calibrate': self.__calibrate,
            're_calibrate_loop': self.__re_calibrate_loop,
        }
        # Execute and return response
        # We need to steal the callback for the comms thread
        self.__comms.steal_callback(self.callback)
        self.__cb(disp_tab[name](args))
        # Restore the callback for the comms thread
        self.__comms.restore_callback()
        
    def __calibrate(self, args):
        loop, steps, self.__manual, self.__man_cb = args
        cal_map = []
        # Retrieve the end points
        r, self.__end_points = self.retrieve_end_points()
        if not r:
            # Calibrate end points
            self.__msg_cb("Calibrating potentiometer feedback end points...")
            r = self.cal_end_points()
            if not r[0]:
                if self.__abort:
                    self.__abort = False
                    return (ABORT, (False, "Operation aborted!", []))
                else:
                    return ('Calibrate', (False, "Unable to retrieve or create end points!", cal_map))
            r, self.__end_points = self.retrieve_end_points()
            if not r:
                # We have a problem
                if MODEL:
                    return ('Calibrate', (False, "Unable to retrieve or create end points!", cal_map))
                else:
                    return ('Calibrate', (True, "Test, no model", cal_map))
        
        # Create a calibration map for loop
        r, cal_map = self.retrieve_map(loop)
        if r:
            if len(cal_map) == 0:
                r, msg, cal_map = self.create_map(loop, steps)
                if not r:
                    if self.__abort:
                        self.__abort = False
                        return (ABORT, (False, "Operation aborted!", []))
                    else:
                        # We have a problem
                        return ('Calibrate', (False, "Unable to create a calibration map for loop: {}!".format(loop), cal_map))
        else:
            self.logger.warning ("Error in calibration map: " % msg)
            return ('Calibrate', (False, msg, cal_map))
        
        return ('Calibrate', (True, "", cal_map))
        
    def __re_calibrate_loop(self, args):
        loop, steps = args
        
        r, self.__end_points = retrieve_end_points()
        if not r:
            # Calibrate end points
            self.cal_end_points()
            r, self.__end_points = self.retrieve_end_points()
            if not r:
                # We have a problem
                return ('ReCalibrateLoop', (False, "Unable to retrieve or create end points!", cal_map))
        r, msg, cal_map = self.create_map(loop, steps)
        if not r:
            # We have a problem
            return ('ReCalibrateLoop', (False, "Unable to create a calibration map for loop: {}!".format(loop), cal_map))
        return ('ReCalibrateLoop', (True, "", cal_map))
        
    def retrieve_end_points(self):
        
        if MODEL:
            h = self.__model[CONFIG][CAL][HOME]
            m = self.__model[CONFIG][CAL][MAX]
        else:
            h = -1
            m = -1
            
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
                return False, None, None
            self.__event.clear()
            if act[2] != None: extents[act[2]] = self.__args[0]      
        
        if MODEL:
            self.__model[CONFIG][CAL][HOME] = extents[0]
            self.__model[CONFIG][CAL][MAX] = extents[1]
            
        return True, extents[0], extents[1]
    
    def retrieve_map(self, loop):
        if MODEL:
            if loop == 1:
                return True, self.__model[CONFIG][CAL][CAL_L1]
            elif loop == 2:
                return True, self.__model[CONFIG][CAL][CAL_L2]
            elif loop == 3:
                return True, self.__model[CONFIG][CAL][CAL_L3]
            else:
                return False, []
        else:
            return True, []

    def create_map(self, loop, steps):
        
        # Get map for model
        r, m = self.retrieve_map(loop)
        if not r:
            self.logger.warning("Invalid loop id: %d" % loop)
            return False, "Invalid loop id: %d" % loop, []
        m.clear()
        
        # Move max and take a reading
        self.__msg_cb("Calibrating maximum frequency...")
        self.__comms_q.put(('max', []))
        # Wait response
        self.__wait_for = 'Max'
        self.__event.wait()
        if self.__abort:
            self.__event.clear()
            return False, None, None
        self.__event.clear()
        # Get res freq approx as its a full sweep takes a while
        #r, [(fmax, swr)] = self.__vna.fres(MIN_FREQ, MAX_FREQ, INC_10K, hint = VNA_MAX)
        r, [(fmax, swr)] = self.__get_current(MIN_FREQ, MAX_FREQ, INC_10K, VNA_MAX)
        if not r:
            self.logger.warning("Failed to get max frequency!")
            return False, "Failed to get max frequency!", []
        
        # Move home and take a reading
        self.__msg_cb("Calibrating minimum frequency...")
        self.__comms_q.put(('home', []))
        # Wait response
        self.__wait_for = 'Home'
        self.__event.wait()
        if self.__abort:
            self.__event.clear()
            return False, None, None
        self.__event.clear()
        # get res freq
        #r, [(fhome, swr)] = self.__vna.fres(MIN_FREQ, MAX_FREQ, INC_10K, hint = VNA_HOME)
        r, [(fhome, swr)] = self.__get_current(MIN_FREQ, MAX_FREQ, INC_10K, VNA_HOME)
        if not r:
            self.logger.warning("Failed to get min frequency!")
            return False, "Failed to get min frequency!", []
        
        # Save limits for this loop
        m = [fhome, fmax, []]
        
        # Move incrementally and take readings
        # We move from home to max by interval
        # Interval is a %age of the difference between feedback readings for home and max
        home, maximum = self.__end_points
        
        # Frig here for testing with actuator power off
        #home = 200
        #maximum = 900
        span = maximum - home
        inc = span/steps
        # Calc approx freq inc for each step
        fspanhz = int((fhome-fmax) * 1000000)
        fsteps = fspanhz/steps
        nextf_approx = home
        
        # Add the home position
        m[2].append([int(home), fhome])
        
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
            fhigh = fhome - (nextf_approx * counter) + 10000
            flow = fhome - (nextf_approx * (counter+1)) - 10000
            # Need a little more accuracy so every 1KHz should suffice
            #r, [(f, swr)] = self.__vna.fres(flow, fhigh, INC_1K, hint = VNA_MID)
            r, [(f, swr)] = self.__get_current(flow, fhigh, INC_1K, VNA_MID)
            if not r:
                self.logger.inwarningfo("Failed to get resonant frequency!")
                return False, "Failed to get resonant frequency!", m
            m[2].append([int(next_inc), f])
            next_inc += inc
            counter += 1
            
        # Add the max position
        m[2].append([int(maximum), fmax])
        
        if MODEL:
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
            self.__msg_cb("Please enter frequency and swr for this calibration point", MSG_ALERT)
            f, swr = self.__man_cb(hint)
            return True, [(float(f), float(swr))]
        else:
            return self.__vna.fres(flow, fhigh, inc, hint = hint)
        
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
            # Just release whever was going on
            # It should then pick up the abort flag
            self.__abort = True
            self.__event.set() 
        else:
            if VERB: self.logger.info ("Waiting for %s, but got %s, continuing to wait!" % (self.__wait_for, name))
 