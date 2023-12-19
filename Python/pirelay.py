#!/usr/bin/env python
#
# pirelay.py
#
# Antenna relay functions for Flexi Loop Controller
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

SIMULATE = False

# Python imports
try:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BOARD)
    GPIO.setwarnings(False)
except:
    # Simulation mode
    SIMULATE = True
import time

# Application imports
from defs import *

# Using SB Components relay shield for RPi
class Relay:
    
    # The pre-assigned pins are
    relaypins = {"RELAY1":4, "RELAY2":17, "RELAY3":27, "RELAY4":22}
    state = TX

    def __init__(self, relay):
        self.pin = self.relaypins[relay]
        self.relay = relay
        
        if not SIMULATE:
            GPIO.setup(self.pin,GPIO.OUT)
            GPIO.output(self.pin, GPIO.LOW)

    def tx(self):
        if SIMULATE:
            if self.state != TX:
                self.state = TX
                print(self.relay + ": TX")
        else:
            GPIO.output(self.pin,GPIO.HIGH)

    def vna(self):
        if SIMULATE:
            if self.state != VNA:
                self.state = VNA
                print(self.relay + ": VNA")
        else:
            GPIO.output(self.pin,GPIO.LOW)
