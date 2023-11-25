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

from defs import *
import model
import serialcomms
import vna

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
class Calibrate:

    def __init__(self, serial_comms, model):
        self.__comms = serial_comms
        self.__model = model
        
    def calibrate(self, loop, interval):
        # Retrieve the end points
        r, end_points = self.retrieve_end_points()
        if not r:
            # Calibrate end points
            self.cal_end_points()
            r, end_points = self.retrieve_end_points()
            if not r:
                # We have a problem
                return "Unable to retrieve or create end points!", False
        
        # Create a calibration map for loop
        cal_map = self.retrieve_map(loop)
        if len(cal_map) == 0:
            r,t,cal_map = self.create_map(loop, interval, end_points)
            if not r:
                # We have a problem
                return False, "Unable to create a calibration map for loop: {}!".format(loop), []
        return True, "", cal_map
    
    def re_calibrate_end_points(self):
        self.cal_end_points()
        
    def re_calibrate_loop(loop, interval):
        r, end_points = retrieve_end_points()
        if not r:
            # Calibrate end points
            self.cal_end_points()
            r, end_points = self.retrieve_end_points()
            if not r:
                # We have a problem
                return "Unable to retrieve or create end points!", False
        r,t,cal_map = self.create_map(loop, interval, end_points)
        if not r:
            # We have a problem
            return False, "Unable to create a calibration map for loop: {}!".format(loop), []
        return True, "", cal_map
        
    def retrieve_end_points(self):
        h = self.__model[CONFIG][CAL][HOME]
        m = self.__model[CONFIG][CAL][MAX]
        if h==-1 or m==-1:
            return False, [h, m]
        else:
            return True, [h, m]
        
    def cal_end_points(self):
        self.__comms.home()
        h = self.__comms.pos()
        self.__comms.max()
        m = self.__comms.pos()
        self.__model[CONFIG][CAL][HOME] = h
        self.__model[CONFIG][CAL][MAX] = m
        return h,m
    
    def retrieve_map(self, loop):
        return []

    def create_map(self, loop, interval, end_points):
        return True, "", [1,2]
        
        