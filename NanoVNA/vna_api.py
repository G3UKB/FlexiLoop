#!/usr/bin/env python
#
# nano_api.py
#
# Specific API function to obtain VSWR
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
import traceback
import logging

# Application imports
sys.path.append('../python')
from defs import *
import nanovna

test = False

class VNAApi:
    
    def __init__(self, model):
        # Get root logger
        if not test: self.logger = logging.getLogger('root')
        self.__model = model
        # Instantiate driver
        self.__nv = nanovna.NanoVNA()
        
    def open(self):
        if self.__nv.open():
            if not test: self.__model[STATE][VNA][VNA_OPEN] = True
            return True
        else:
            if not test: self.__model[STATE][VNA][VNA_OPEN] = False
        return False
        
    def close(self):
        self.__nv.close()
        if not test: self.__model[STATE][VNA][VNA_OPEN] = False
        
    def get_vswr(self, start, stop):
        # start/stop in MHz
        start_int = int(start*1.0e6)
        stop_int = int(stop*1.0e6)
        # Set the sweep params
        self.__nv.set_sweep(start_int,stop_int)
        # Ask VNA to fetch the frequency set for the sweep
        self.__nv.fetch_frequencies()
        # Get the frequency set
        f = self.__nv.frequency
        # Get the VSWR set for the frequency set
        vswr = self.__nv.vswr(self.__nv.data(0))
        
        # Find lowest VSWR in the set
        low_vswr = 100.0
        low_idx = 0
        idx = 0
        for pt in vswr:
            if pt < low_vswr:
                low_vswr = pt
                low_idx = idx
            idx += 1
        
        # Return a tuple of freq and VSWR
        return (round((float(f[low_idx]))/1.0e6,3), round(vswr[low_idx], 2))
       
#======================================================================================================================
# Test code
def main(start, end):
    api = VNAApi(None)
    api.open()
    #f, vswr = api.get_vswr(6.5e6,30e6)
    f, vswr = api.get_vswr(float(start), float(end))
    print (f, vswr)
    api.close()
    
# Entry point       
if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
    