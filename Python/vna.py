#!/usr/bin/env python3
#
# vna.py
# 
# Copyright (C) 2017 by G3UKB Bob Cowdery
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

# Application imports
from defs import *
import decode

"""
    Perform a sweep using the command line utility from vna/j.
    The sweep has a start and stop frequency and number of steps.
    The sweep results are written to a file (no option).
    The file is parsed and a condensed result set passed back to the caller.
"""

class VNA:
    
    def __init__(self, simulate=False):
        self.__simulate = simulate
        
        # Create decoder
        self.__dec = decode.Decode()
    
    def fres(self, startFreq, stopFreq):
        """
        Sweep between start and end frequencies.
        Target is to determine resonant frequency.
        
        Arguments:
            startFreq   --  start freq in Hz
            stopFreq    --  stop freq in Hz
        """
        
        if (stopFreq - startFreq) >= 1000:
            # Good to go
            # Step every 250Hz
            steps = int((stopFreq - startFreq)/250)
            if self.__sweep(startFreq, stopFreq, steps):
                return True, self.__dec.decode_fres()
            else:
                return False, []
    
    def fswr(self, freq):
        
        """
        Do spot frequency
        Target is to return SWR at the given frequency
        
        Arguments:
            freq   --  freq in Hz
        """
        
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
            params.append('-DexportDirectory=%s' % (EXPORT_PATH))
            params.append('-DexportFilename=%s' % (EXPORT_FILENAME))
            params.append('-jar')
            params.append('%s' % (JAR))
            proc = subprocess.Popen(params)
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
    