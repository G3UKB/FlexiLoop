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

import serial
import time

#=====================================================
# Manage all serial comms to the Arduino
#===================================================== 
class SerialComms:

    # Initialise class
    def __init__(self, port):
        self.__ser = serial.Serial(port, 9600, timeout=1)
        self.__ser.reset_input_buffer()

    # Read all responses for a command.
    # Wait for a response.
    # Print all STATUS responses
    # Print and return RESPONSE responses
    def read_resp(self):
        acc = ""
        value = 0
        success = False
        resp_timeout = 10
        while(1):
            # Read a single character
            chr = ser.read().decode('utf-8')
            if chr == '':
                # Timeout on read
                print("Waiting response...")
                if resp_timeout <= 0:
                    # Timeout on waiting for a response
                    print("Response timeout!")
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
                print("Response: ", acc)
                if ser.in_waiting > 0:
                    # Still data in buffer, probably should not happen!
                    # Dump response and use this data
                    print("More data available - collecting... ", ser.in_waiting)
                    acc = ""
                    continue
                success = True
                break
        if success:
            # We have good response data
            # Strip data from text
            if acc.len() > 2:
                # There is some data
                p = acc[1:len(acc)-1]
                if p.isdigit():
                    val = int(p)
                else:
                    print("Invalid value for position (not int): ", p)
        return success, val
    
    # Send a command to the Arduino
    def send(self, cmd):
        val = 0
        while(1):
            print("Sending ", cmd)
            ser.write(cmd)
            ser.flush()
            time.sleep(0.1)
            r, val = read_resp()
            if r == False:
                time.sleep(0.2)
                print("Command failed, retrying...")
                continue
            else:
                break
            time.sleep(1)
        return val
    
    # Command execution                        
    def speed(self):
        send(b"s;")
            
    def home(self):
        send(b"h;")
            
    def max(self):
        send(b"x;")
            
    def pos(self):
        return send(b"p;")
            
    def move(self, pos):
        b = bytearray(b"m,")
        b += pos.encode('utf-8')
        b += b'.;'
        send(b)
    
    def nudge_fwd(self):
        send(b"f;")
    
    def nudge_rev(self):
        send(b"r;")
       
    def run_fwd(self, ms):
        b = bytearray(b"w,")
        b += ms.encode('utf-8')
        b += b'.;'
        send(b)
            
    def run_rev(self, ms):
        b = bytearray(b"v,")
        b += ms.encode('utf-8')
        b += b'.;'
        send(b)
            
        