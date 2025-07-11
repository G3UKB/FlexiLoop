#!/usr/bin/env python
#
# nano_api.py
#
# Specific API function to obtain frequency and VSWR
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
import argparse

# Application imports
try:
    sys.path.append('../python')
    from defs import *
except:
    pass
import nanovna

class VNAApi:
    def __init__(self, model, msg_cb, app=True):
        # Get root logger
        self.__app = app
        self.logger = logging.getLogger('root')
        self.__model = model
        self.__msg_cb = msg_cb
            
        # Instantiate driver
        self.__nv = nanovna.NanoVNA()
        
    def open(self):
        if self.__nv.open():
            if self.__app: self.__model[STATE][VNA][VNA_OPEN] = True
            return True
        else:
            if self.__app: self.__model[STATE][VNA][VNA_OPEN] = False
        return False
        
    def close(self):
        self.__nv.close()
        if self.__app: self.__model[STATE][VNA][VNA_OPEN] = False
    
    # Get the frequency and VSWR at the resonant point    
    def get_vswr(self, start, end, points = 101):
        if self.__app:
            isopen = self.__model[STATE][VNA][VNA_OPEN]
        else:
            isopen = True
        try:
            if isopen:
                while True:
                    # Get the sets
                    f, vswr = self.__get_sets(start, end, points)
                    # Find lowest VSWR in the set
                    low_vswr = 100.0
                    low_idx = 0
                    idx = 0
                    for pt in vswr:
                        if pt < low_vswr:
                            low_vswr = pt
                            low_idx = idx
                        idx += 1
                    new_f = round((float(f[low_idx]))/1.0e6,3)
                    new_swr =  round(vswr[low_idx], 2)
                    return (True, new_f, new_swr)
            else:
                return (False, None, None)
        except Exception as e:
            self.logger.warning("VNA exception, please reset VNA [{}]".format(e))
            self.__msg_cb("VNA exception, please reset VNA [{}]".format(e), MSG_ALERT)
            return (False, None, None)
    
    # Get the VSWR as close to the given frequency as we have points
    def get_freq(self, start, end, target, points = 101):
        if self.__app:
            isopen = self.__model[STATE][VNA][VNA_OPEN]
        else:
            isopen = True
        try:
            if isopen:
                while True:
                    # Get the sets
                    freqs, vswr = self.__get_sets(start, end, points)
                    # Find the point closest to the given frequency
                    t = int(target*1.0e6)
                    f_diff = -1
                    first = True
                    idx = 0
                    for f in freqs:
                        f = int(f)
                        if first:
                            first = False
                            f_diff = f
                        else:
                            # Better or worse
                            if f_diff < 0:
                                # Step too far
                                break
                            else:
                                f_diff = t - f
                        idx += 1
                    new_f = round((float(freqs[idx-1]))/1.0e6,3)
                    new_swr =  round(vswr[idx-1], 2)
                    return (True, new_f, new_swr)
            else:
                return (False, None, None)
        except Exception as e:
            self.logger.warning("VNA exception, please reset VNA [{}]".format(e))
            self.__msg_cb("VNA exception, please reset VNA [{}]".format(e), MSG_ALERT)
            return (False, None, None)
    
    # Get the frequency and VSWR sets for the given range   
    def __get_sets(self, start, end, points):
        # start/end in MHz
        start_int = int(start*1.0e6)
        end_int = int(end*1.0e6)
        
        # Set the fequency range and number of points
        self.__nv.set_frequencies(start_int, end_int, points)
        # Get the frequency array
        f = self.__nv.frequency
        # Perform a scan() which will stitch 101 length segments together
        a0, a1 = self.__nv.scan()
        # Get the vswr array
        vswr = self.__nv.vswr(a0)

        return (f, vswr)
        
#======================================================================================================================
# Test code
def msg_cb(msg):
    print (msg)
    
def main():
     # Manage command line arguments
    parser = argparse.ArgumentParser(
        prog='VNA-API',
        description='Interface to NanoVNA',
        epilog='G3UKB')

    parser.add_argument('-s', '--start', action='store', required=True, help='Scan start freq in MHz')
    parser.add_argument('-e', '--end', action='store', required=True, help='Scan end freq in MHz')
    parser.add_argument('-t', '--target', action='store', required=True, help='Get VSWR at Target MHz freq')
    parser.add_argument('-p', '--points', action='store', required=False, default = 101, help='Number of scan points, default 101')
    args = parser.parse_args()
    start = args.start
    end = args.end
    target = args.target
    points = args.points

    # Instantiate VNAApi as stand alone
    api = VNAApi(None, msg_cb, False)
    if api.open():
        r, f, vswr = api.get_vswr(float(start), float(end), int(points))
        if r:
            print ('Resonance at Freq: {}, VSWR: {}'.format(f, vswr))
            r, f, vswr = api.get_freq(float(start), float(end), float(target), int(points))
            if r:
                print ('VSWR at Freq: {}, VSWR: {}'.format(f, vswr))
        api.close()
    else:
        print('Failed to open device!')
    
# Entry point       
if __name__ == '__main__':
    # start, end, f_at, points
    main()
    