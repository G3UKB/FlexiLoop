#!/usr/bin/env python
#
# serialcomms.py
#
# Flexi-Loop serial comms Arduino <-> RPi
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
import serial
import time

# Application imports
from defs import *

# Verbose flag
VERB = False

#=====================================================
# Manage all serial comms to the Arduino
#===================================================== 
class SerialComms:

    # Initialise class
    def __init__(self, model, port):
        
        self.__model = model
        
        try:
            self.__ser = serial.Serial(port, 9600, timeout=1)
        except:
            print("Failed to initialise Arduino port. Is the Arduino connected?")
            self.__model[STATE][ARDUINO][ONLINE] = False
            return
        
        self.__model[STATE][ARDUINO][ONLINE] = True
        self.__ser.reset_input_buffer()
        self.__first_run = True

    # Read all responses for a command.
    # Wait for a response.
    # Print all STATUS responses
    # Print and return RESPONSE responses
    def read_resp(self, timeout):
        acc = ""
        val = 0
        success = False
        # timeout is secs to wait for a response
        resp_timeout = timeout*2
        while(1):
            # Read a single character
            chr = self.__ser.read().decode('utf-8')
            if chr == '':
                # Timeout on read
                #print("Waiting response...")
                if resp_timeout <= 0 or self.__first_run:
                    # Timeout on waiting for a response
                    self.__first_run = False
                    if VERB: print("Response timeout!")
                    break
                else:
                    # Continue waiting
                    resp_timeout -= 1
                    time.sleep(0.5)
                    continue
            acc = acc + chr
            if chr == ";":
                # Found terminator character
                if "Status" in acc:
                    # Its a status message so just print and continue waiting
                    print(acc)
                    acc = ""
                    continue
                # Otherwise its a response to the command
                if VERB: print("Response: ", acc)
                if self.__ser.in_waiting > 0:
                    # Still data in buffer, probably should not happen!
                    # Dump response and use this data
                    if VERB: print("More data available - collecting... ", ser.in_waiting)
                    acc = ""
                    continue
                success = True
                break
        if success:
            # We have good response data
            # Strip data from text
            n = acc.find(":")
            if n != -1:
                # There is some data
                p = acc[n+1:len(acc)-1]
                p = p.strip()
                if p.isdigit():
                    val = int(p)
                else:
                    print("Invalid value for position (not int): ", p)
        return success, val
    
    # Send a command to the Arduino
    def send(self, cmd, timeout):
        val = 0
        while(1):
            if VERB: print("Sending ", cmd)
            self.__ser.write(cmd)
            self.__ser.flush()
            time.sleep(0.1)
            r, val = self.read_resp(timeout)
            if r == False:
                time.sleep(0.2)
                if VERB: print("Command failed, retrying...")
                continue
            else:
                break
            time.sleep(1)
        return val
    
    # Command execution                        
    def speed(self):
        self.send(b"s;", 1)
            
    def home(self):
        self.send(b"h;", 30)
            
    def max(self):
        self.send(b"x;", 30)
            
    def pos(self):
        return self.send(b"p;", 2)
            
    def move(self, pos):
        b = bytearray(b"m,")
        b += str(pos).encode('utf-8')
        b += b'.;'
        self.send(b, 30)
    
    def nudge_fwd(self):
        self.send(b"f;", 2)
    
    def nudge_rev(self):
        self.send(b"r;", 2)
       
    def run_fwd(self, ms):
        b = bytearray(b"w,")
        b += ms.encode('utf-8')
        b += b'.;'
        self.send(b, 10)
            
    def run_rev(self, ms):
        b = bytearray(b"v,")
        b += ms.encode('utf-8')
        b += b'.;'
        self.send(b, 10)
            
        