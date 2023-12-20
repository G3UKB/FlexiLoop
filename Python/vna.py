#!/usr/bin/env python3
#
# vna.py
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
import os, sys
import subprocess
import random

# Application imports
from defs import *
import decode

SIMULATE = False

"""
    Perform a sweep using the command line utility from vna/j.
    The sweep has a start and stop frequency and number of steps.
    The sweep results are written to a file (no option).
    The file is parsed and a condensed result set passed back to the caller.
"""

class VNA:
    
    def __init__(self):
        # Simulation setup
        if SIMULATE:
            # These are just test values
            self.__low_f = 3.0          # Lowest frequency which is at max extension
            self.__high_f = 12.0        # Highest frequency which is at home position
            self.__inc_f = (self.__high_f - self.__low_f)/ACT_STEPS # Freq increment on each step
            self.__current_step = 1
            self.__swr = 1.0            # Always return 1.0
        
        # Create decoder
        self.__dec = decode.Decode()
        
    def fres(self, startFreq, stopFreq, hint = HOME):
        """
        Sweep between start and end frequencies.
        Target is to determine resonant frequency.
        
        Arguments:
            startFreq   --  start freq in Hz
            stopFreq    --  stop freq in Hz
            optional hint -- MIN, MAX, MID (used in simulation)
        """
        
        if SIMULATE:
            if hint == VNA_HOME:
                self.__current_step = 1
                return True, self.__high_f
            elif hint == VNA_MAX:
                self.__current_step = 1
                return True, self.__low_f
            elif hint == VNA_RANDOM:
                i = random.randint(1,ACT_STEPS)
                return True, self.__high_f - (i * self.__inc_f)
            else:
                if self.__current_step >= ACT_STEPS:
                    print ("Steps %d are running off end. Restarting at 1." % (self.__current_step))
                    self.__current_step = 1
                else:
                    # We step from high to low frequency
                    f_now = self.__high_f - (self.__current_step * self.__inc_f)
                    self.__current_step += 1
                    return True, round(f_now, 2)
        
        if (stopFreq - startFreq) >= 1000:
            # Good to go
            # Step every 250Hz
            steps = int((stopFreq - startFreq)/250)
            if self.__sweep(startFreq, stopFreq, steps):
                return True, self.__dec.decode_fres()
            else:
                return False, None
        else:
            return False, None
    
    def fswr(self, freq):
        """
        Do spot frequency
        Target is to return SWR at the given frequency
        
        Arguments:
            freq   --  freq in Hz
        """
        if SIMULATE:
            return (freq, self.__swr)
        
        # Minimum separation is 1KHz and minimum steps is 2
        if self.__sweep(freq, freq + 1000, 2):
            return True, self.__dec.decode_fswr()
        else:
            return False, []
    
    def scan(self, startFreq, stopFreq):
        
        """
        Sweep between start and end frequencies.
        All pairs will be returned.
        
        Arguments:
            startFreq   --  start freq in Hz
            stopFreq    --  stop freq in Hz
        """
        
        if (stopFreq - startFreq) >= 1000:
            # Good to go
            # Step every 10KHz
            steps = int((stopFreq - startFreq)/10000)
            if self.__sweep(startFreq, stopFreq, steps):
                return True, self.__dec.decode_scan()
            else:
                return False, []
    
    def __sweep(self, startFreq, stopFreq, steps):
        
        """
            Perform a sweep
            
            Args:
                startFreq   --  start frequency in Hz
                stopFreq    --  stop Freq in Hz (> startFreq + 1KHz)
                steps       --  steps between start and stop (minimum 2 gives one reading at each freq)
                
        """
        
        try:
            if sys.platform == 'win32':
                exportPath = WIN_EXPORT_PATH
            elif sys.platform == 'linux':
                exportPath = LIN_EXPORT_PATH
            else:
                print('Unsupported platform %s' % (sys.platform))
                return
            params = []
            params.append('java')
            params.append('-Dfstart=%s' % (startFreq))
            params.append('-Dfstop=%s' % (stopFreq))
            params.append('-Dfsteps=%s' % (steps))
            params.append('-DdriverId=%d' % (DRIVER_ID))
            params.append('-DdriverPort=%s' % (DRIVER_PORT))
            params.append('-Dcalfile=%s' % (CAL_FILE))
            params.append('-Dscanmode=%s' % (SCAN_MODE))
            params.append('-Dexports=%s' % (EXPORTS))
            params.append('-DexportDirectory=%s' % (exportPath))
            params.append('-DexportFilename=%s' % (EXPORT_FILENAME))
            params.append('-jar')
            params.append('%s' % (JAR))
            proc = subprocess.Popen(params)
            print('Waiting for finish')
            proc.wait()
            print('Scan complete')
            return True
            
        except Exception as e:
            print('Exception %s' % (str(e)))
            return False

# Testing     
if __name__ == '__main__':
    vna = VNA()
    startf = int(sys.argv[1])
    stopf = int(sys.argv[2])
    f = int(sys.argv[3])
    vna.fres(startf, stopf)
    vna.fswr(f)
    