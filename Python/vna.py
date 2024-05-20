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
import logging

# Application imports
from defs import *
import decode

SIMULATE = True

"""
    Perform a sweep using the command line utility from vna/j.
    The sweep has a start and stop frequency and number of steps.
    The sweep results are written to a file (no option).
    The file is parsed and a condensed result set passed back to the caller.
"""

class VNA:
    
    def __init__(self, model):
        
        # Get root logger
        self.logger = logging.getLogger('root')

        self.__model = model
        
        # Simulation setup
        if SIMULATE:
            # These are just test values
            self.__low_f = 3.0          # Lowest frequency which is at max extension
            self.__high_f = 12.0        # Highest frequency which is at home position
            self.__inc_f = 10 #(self.__high_f - self.__low_f)/self.__model[CONFIG][CAL][ACTUATOR_STEPS] # Freq increment on each step
            self.__current_step = 1
            self.__swr = 1.0            # Always return 1.0
        
        # Create decoder
        self.__dec = decode.Decode(model)
        
    def fres(self, startFreq, stopFreq, incFreq, hint = HOME):
        """
        Sweep between start and end frequencies.
        Target is to determine resonant frequency.
        
        Arguments:
            startFreq   --  start freq in Hz
            stopFreq    --  stop freq in Hz
            incFreq     --  take reading every incFreq in Hz 
            optional hint -- MIN, MAX, MID (used in simulation)
        """
        
        if SIMULATE:
            if hint == VNA_HOME:
                self.__current_step = 1
                return True, [(int(self.__high_f *1000000.0), self.__swr)]
            elif hint == VNA_MAX:
                self.__current_step = 1
                return True, [(int(self.__low_f *1000000), self.__swr)]
            elif hint == VNA_RANDOM:
                i = random.randint(1,self.__model[CONFIG][CAL][ACTUATOR_STEPS])
                return True, [(int((self.__high_f - (i * self.__inc_f)) *1000000.0), self.__swr)]
            else:
                if self.__current_step > self.__model[CONFIG][CAL][ACTUATOR_STEPS]:
                    print ("Steps %d are running off end. Restarting at 1." % (self.__current_step))
                    self.__current_step = 1
                # We step from high to low frequency
                f_now = self.__high_f - (self.__current_step * self.__inc_f)
                self.__current_step += 1
                return True, [(int(f_now * 1000000.0), self.__swr)]
        
        if (stopFreq - startFreq) >= 1000:
            # Good to go
            # Calc number of steps
            steps = int((stopFreq - startFreq)/incFreq)
            if self.__sweep(startFreq, stopFreq, steps):
                return True, self.__dec.decode_fres()
            else:
                return False, []
        else:
            return False, []
    
    def fswr(self, freq):
        """
        Do spot frequency
        Target is to return SWR at the given frequency
        
        Arguments:
            freq   --  freq in Hz
        """
        print('fswr')
        if SIMULATE:
            return True, [(freq, self.__swr)]
        
        # Minimum separation is 1KHz and minimum steps is 2
        if self.__sweep(freq, freq + 1000, 2):
            return True, self.__dec.decode_fswr()
        else:
            return False, []
    
    def scan(self, startFreq, stopFreq, incFreq):
        
        """
        Sweep between start and end frequencies.
        All pairs will be returned.
        
        Arguments:
            startFreq   --  start freq in Hz
            stopFreq    --  stop freq in Hz
            incFreq     --  take reading every incFreq in Hz 
        """
        
        if (stopFreq - startFreq) >= 1000:
            # Good to go
            # Step every 10KHz
            steps = int((stopFreq - startFreq)/incFreq)
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
            params.append('-DdriverId=%d' % (self.__model[CONFIG][VNA_CONF][DRIVER_ID]))
            params.append('-DdriverPort=%s' % (self.__model[CONFIG][VNA_CONF][DRIVER_PORT]))
            params.append('-Dcalfile=%s' % (self.__model[CONFIG][VNA_CONF][CAL_FILE]))
            params.append('-Dscanmode=%s' % (SCAN_MODE))
            params.append('-Dexports=%s' % (EXPORTS))
            params.append('-DexportDirectory=%s' % (self.__model[CONFIG][VNA_CONF][EXPORT_PATH]))
            params.append('-DexportFilename=%s' % (self.__model[CONFIG][VNA_CONF][EXPORT_FILENAME]))
            params.append('-jar')
            params.append('%s' % (self.__model[CONFIG][VNA_CONF][VNA_JAR]))
            proc = subprocess.Popen(params)
            proc.wait()
            print('Scan complete')
            return True
            
        except Exception as e:
            print('Exception %s' % (str(e)))
            return False

    