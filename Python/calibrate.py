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

# Application imports
from defs import *
import model
import serialcomms
import vna

# Set False when testing
MODEL = True

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

    def __init__(self, comms, comms_q, cal_q, vna, model, callback):
        super(Calibrate, self).__init__()
        
        self.__comms = comms
        self.__comms_q = comms_q
        self.__cal_q = cal_q
        self.__vna = vna
        self.__model = model
        self.__cb = callback
        
        self.__end_points = [-1,-1]
        self.term = False
        
        self.__event = threading.Event()
        self.__wait_for = ""
        self.__args = []
    
    # Terminate instance
    def terminate(self):
        """ Thread terminating """
        self.term = True
    
    # Thread entry point
    def run(self):
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
        print("Calibrate thread exiting...")
    
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
        loop, interval = args
        cal_map = []
        
        # Retrieve the end points
        r, self.__end_points = self.retrieve_end_points()
        if not r:
            # Calibrate end points
            self.cal_end_points()
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
                r, msg, cal_map = self.create_map(loop, interval)
                if not r:
                    # We have a problem
                    return ('Calibrate', (False, "Unable to create a calibration map for loop: {}!".format(loop), cal_map))
        else:
            print ("Error in calibration map: " % msg)
            return ('Calibrate', (False, msg, cal_map))
        
        return ('Calibrate', (True, "", cal_map))
        
    def __re_calibrate_loop(args):
        loop, interval = args
        
        r, self.__end_points = retrieve_end_points()
        if not r:
            # Calibrate end points
            self.cal_end_points()
            r, self.__end_points = self.retrieve_end_points()
            if not r:
                # We have a problem
                return ('ReCalibrateLoop', (False, "Unable to retrieve or create end points!", cal_map))
        r, msg, cal_map = self.create_map(loop, interval)
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
        self.__comms_q.put(('home', []))
        # Wait response
        self.__wait_for = 'Home'
        self.__event.wait()
        self.__event.clear()
        
        self.__comms_q.put(('pos', []))
        # Wait response
        self.__wait_for = 'Pos'
        self.__event.wait()
        self.__event.clear()
        h = self.__args[0]
        
        self.__comms_q.put(('max', []))
        # Wait response
        self.__wait_for = 'Max'
        self.__event.wait()
        self.__event.clear()
        
        self.__comms_q.put(('pos', []))
        # Wait response
        self.__wait_for = 'Pos'
        self.__event.wait()
        self.__event.clear()
        m = self.__args[0]
        
        if MODEL:
            self.__model[CONFIG][CAL][HOME] = h
            self.__model[CONFIG][CAL][MAX] = m
        return h,m
    
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

    def create_map(self, loop, interval):
        
        # Get map for model
        r, m = self.retrieve_map(loop)
        if not r:
            print("Invalid loop id: %d" % loop)
            return False, "Invalid loop id: %d" % loop, []
        m.clear()
        
        # Move max and take a reading
        self.__comms_q.put(('max', []))
        # Wait response
        self.__wait_for = 'Max'
        self.__event.wait()
        self.__event.clear()
        
        r, fmax = self.__vna.fres(MIN_FREQ, MAX_FREQ, hint = MAX)
        if not r:
            print("Failed to get max frequency!")
            return False, "Failed to get max frequency!", []    
        # Move home and take a reading
        self.__comms_q.put(('home', []))
        # Wait response
        self.__wait_for = 'Home'
        self.__event.wait()
        self.__event.clear()
        
        r, fhome = self.__vna.fres(MIN_FREQ, MAX_FREQ, hint = HOME)
        if not r:
            print("Failed to get min frequency!")
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
        d = maximum - home
        step = (interval/100) * d
        next_step = home + step
        while next_step < maximum:
            # Comment out if motor not running
            self.__comms_q.put(('move', [next_step]))
            # Wait response
            self.__wait_for = 'MoveTo'
            self.__event.wait()
            self.__event.clear()
        
            r, f = self.__vna.fres(fhome, fmax, hint = FREE)
            if not r:
                print("Failed to get resonant frequency!")
                return False, "Failed to get resonant frequency!", m
            m[2].append([next_step, f])
            next_step += step
        
        # Return the map
        return True, "", m
    
    # =========================================================================
    # Callback from comms module
    # Note this is called on the comms thread
    def callback(self, data):
        
        print("Got event: ", data)
        (name, (success, msg, val)) = data
        if name == self.__wait_for:
            # Extract args and release thread
            self.__args = val
            self.__event.set()
        #else:
        #    print ("Waiting for %s, but got %s, continuing to wait!" % (self.__wait_for, name))
 
# ===============================================================
# TESTING
def comms_callback(data):
    print("Main comms cb: ", data)

def cal_callback(data):
    print("Main cal cb: ", data)
    
if __name__ == '__main__':
    
    s_q = queue.Queue(10)
    comms = serialcomms.SerialComms(None, 'COM5', s_q, comms_callback)
    comms.start()
    # This just kicks the Arduino into life
    s_q.put(('pos', []))
    sleep(10)
    
    c_q = queue.Queue(10)
    cal = Calibrate(comms, s_q, c_q, None, None, cal_callback)
    cal.start()
    c_q.put(('calibrate', [1, 10]))
    
    sleep(10)
    comms.terminate()
    comms.join()
    cal.terminate()
    cal.join()