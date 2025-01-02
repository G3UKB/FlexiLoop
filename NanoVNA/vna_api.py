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
import nanovna

class VNAApi:
    
    def __init__(self):
        # Get root logger
        self.logger = logging.getLogger('root')
        # Instantiate driver
        self.__nv = nanovna.NanoVNA()
        
    def open(self):
        self.__nv.open()
        
    def close(self):
        self.__nv.close()
        
    def get_vswr(self, start, stop):
        
        # Set the sweep params
        self.__nv.set_sweep(start,stop)
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
        return (f[low_idx], vswr[low_idx])
       
#======================================================================================================================
# Test code
def main():
    api = VNAApi()
    f, vswr = api.get_vswr(7e6,8e6)
    print (f, vswr)
    
# Entry point       
if __name__ == '__main__':
    main()