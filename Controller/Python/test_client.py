#!/usr/bin/env python
#
# test_client.py
#
# Test client for the Arduino motor controller
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
import serial

class CtrlTest:
    
    def __init__(self, port):
        self.__port = port
    
    def run_test(self):
        # Open port
        self.__ser = serial.Serial(self.__port, 9600, timeout=1)
        self.__ser.reset_input_buffer()
        
        # Heartbeat, HOME, MAX, POS, MOVE TO, POS
        cmds = ((b"y;", 0.5), (b"h;", 5), (b"x;", 5), (b"p;", 1), (b"m,300;", 5), (b"p;", 1))
        for cmd in cmds:
            self.__send(cmd[0], cmd[1])
    
    # ===============================================================
    # Send a command to the Arduino
    def __send(self, cmd, timeout):
        val = 0
        retries = 5
        while(1):
            self.__ser.write(cmd)
            self.__ser.flush()
            retries -= 1
            sleep(0.1)
            resp = self.__read_resp(timeout)
            if resp[1][0] == False:
                sleep(0.2)
                print("Command failed, retrying...")
                if retries <= 0:
                    print("Command failed after 5 retries")
                    return None
            else:
                break
            sleep(1)
        return resp
    
    # ===============================================================
    # Read all responses for a command.
    def __read_resp(self, timeout):
        # Wait for a response.
        # Send all STATUS responses
        # Return RESPONSE responses
        acc = ""
        val = 0
        success = False
        name = ""
        msg = ""
        val = []
        # timeout is secs to wait for a response
        resp_timeout = timeout*2
        while(1):
            # Read a single character
            chr = self.__ser.read().decode('utf-8')
            if chr == '':
                # Timeout on read
                if resp_timeout <= 0:
                    # Timeout on waiting for a response
                    print("Response timeout!")
                    break
                else:
                    # Continue waiting
                    resp_timeout -= 1
                    sleep(0.5)
                    continue
            acc = acc + chr
            if chr == ";":
                # Found terminator character
                if "Status" in acc:
                    # Its a status message so return this directly
                    print("Status Pos: ", self.__encode(acc)[1][1][0])
                    acc = ""
                    continue
                if "Limit" in acc:
                    print("Limit: ", self.__encode(acc)[1][1][0])
                    continue
                elif "Dbg" in acc:
                    # Its a debug message so return this directly
                    print("Debug: ", self.__encode(acc)[1][1][0])
                    acc = ""
                    continue
                # Otherwise its a response to the command
                print("Response: {}".format(self.__encode(acc)))
                if self.__ser.in_waiting > 0:
                    # Still data in buffer, probably should not happen!
                    # Dump response and use this data
                    print("More data available {} - collecting... ".format(self.__ser.in_waiting))
                    acc = ""
                    continue
                success = True
                break
        if success:
            return(self.__encode(acc))
        else:
            return (name, (success, val))

    # ===============================================================
    # Encode response
    def __encode(self, data):
        # Called when we have a good response
        success = False
        name = ""
        val = []
        
        # Strip data from text
        n = data.find(":")
        if n == -1:
            # No parameters
            success = True
            name = data[:len(data) - 1]
        else:
            # There are parameters
            success = True
            # We only expect one parameter at the moment
            name = data[:n]
            param = data[n+1:len(data)-1]
            param = param.strip()
            if param.isdigit():
                val.append(int(param))
            else:
                # Treat as a single string parameter
                val.append(param)
        return (name, (success, val))
    
#======================================================================================================================
# Test code
def main(port):
    tst = CtrlTest(port)
    tst.run_test()
    
# Entry point       
if __name__ == '__main__':
    main(sys.argv[1])