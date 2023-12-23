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
import os,sys
from time import sleep
import queue
import threading
import traceback

# Application imports
from defs import *

# Verbose flag
VERB = False
# Set False when testing
MODEL = True

#=====================================================
# Manage all serial comms to the Arduino
#===================================================== 
class SerialComms(threading.Thread):

    # =============================================================== 
    # Initialise class
    def __init__(self, model, port, q, main_callback):
        """
        Constructor
        
        Arguments:
            q           --  queue to accept commands on
            callback    --  on status or error
        
        """
        
        super(SerialComms, self).__init__()
        
        self.__model = model
        self.__q = q
        self.__cb = main_callback
        self.__originalcb = main_callback
        self.term = False
        
        try:
            self.__ser = serial.Serial(port, 9600, timeout=1)
        except:
            print("Failed to initialise Arduino port. Is the Arduino connected?")
            if MODEL: self.__model[STATE][ARDUINO][ONLINE] = False
            return
        
        if MODEL: self.__model[STATE][ARDUINO][ONLINE] = True
        self.__ser.reset_input_buffer()

    def steal_callback( self, new_callback) :
        """ Steal the dispatcher callback """
        self.__cb = new_callback
    
    def restore_callback(self) :
        """ Restore the dispatcher callback """
        self.__cb = self.__originalcb
        
    # Terminate instance
    def terminate(self):
        """ Thread terminating """
        self.term = True
    
    # Thread entry point
    def run(self):
        while not self.term:
            try:
                #print(self.__q.qsize())
                if self.__q.qsize() > 0:
                    while self.__q.qsize() > 0:
                        name, args = self.__q.get()
                        #print(name, args)
                        # By default this is synchronous so will wait for the response
                        # Response goes to main code callback, we don't care here
                        self.__dispatch(name, args)
                        self.__q.task_done()
                else:
                    sleep(0.02)
            except Exception as e:
                # Something went wrong
                print(str(e))
                #self.__cb('fatal: {0}'.format(e))
                break
        print("Comms thread exiting...")
    
    # ===============================================================
    # PRIVATE
    # Command execution
    # Switcher
    def __dispatch(self, name, args):
        disp_tab = {
            'speed': self.__speed,
            'home': self.__home,
            'max': self.__maximum,
            'pos': self.__pos,
            'move': self.__move,
            'nudge_fwd': self.__nudge_fwd,
            'nudge_rev': self.__nudge_rev,
            'run_fwd': self.__run_fwd,
            'run_rev': self.__run_rev,
            'free_fwd': self.__free_fwd,
            'free_rev': self.__free_rev,
            'free_stop': self.__free_stop,
        }
        # Execute and return response
        self.__cb(disp_tab[name](args))
        
    def __speed(self, args):
        return self.send(b"s;", 1)
            
    def __home(self, args):
        return self.send(b"h;", 30)
            
    def __maximum(self, args):
        return self.send(b"x;", 30)
            
    def __pos(self, args):
        return self.send(b"p;", 2)
            
    def __move(self, args):
        pos = args[0]
        b = bytearray(b"m,")
        b += str(pos).encode('utf-8')
        b += b'.;'
        return self.send(b, 30)
    
    def __nudge_fwd(self, args):
        return self.send(b"f;", 2)
    
    def __nudge_rev(self, args):
        return self.send(b"r;", 2)
       
    def __run_fwd(self, args):
        ms = args[0]
        b = bytearray(b"w,")
        b += str(ms).encode('utf-8')
        b += b'.;'
        return self.send(b, 10)
            
    def __run_rev(self, args):
        ms = args[0]
        b = bytearray(b"v,")
        b += str(ms).encode('utf-8')
        b += b'.;'
        return self.send(b, 10)
    
    def __free_fwd(self, args):
        return self.send(b"c;", 30)
    
    def __free_rev(self, args):
        return self.send(b"d;", 30)
    
    def __free_stop(self, args):
        return self.send(b"e;", 2)
    
    def __abort(self, args):
        return self.send(b"z;", 1)
        
    # ===============================================================
    # Send a command to the Arduino
    def send(self, cmd, timeout):
        val = 0
        msg = ""
        retries = 5
        while(1):
            if VERB: print("Sending ", cmd)
            self.__ser.write(cmd)
            self.__ser.flush()
            sleep(0.1)
            resp = self.read_resp(timeout)
            if resp[1][0] == False:
                sleep(0.2)
                if VERB: print("Command failed, retrying...")
                if retries <= 0:
                    msg = "Command failed after %d retries" % retries
                    return (resp[0], (False, msg, []))
                else:
                    retries -= 1
                continue
            else:
                break
            sleep(1)
        return resp
    
    # ===============================================================
    # Read all responses for a command.
    def read_resp(self, timeout):
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
            # Check abort
            r = self.__check_stop_abort()
            if r == ABORT:
                # We return an abort instead of the given command
                return (ABORT, (True, "User abort!", val))
            elif r == STOP:
                print("Stop actuator after forward or reverse command.")
            # Read a single character
            chr = self.__ser.read().decode('utf-8')
            if chr == '':
                # Timeout on read
                #if VERB: print("Waiting response...")
                if resp_timeout <= 0:
                    # Timeout on waiting for a response
                    if VERB: print("Response timeout!")
                    msg = "Response timeout!"
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
                    if VERB: print("Status: ", acc)
                    self.__cb(self.__encode(acc))
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
            return(self.__encode(acc))
        else:
            return (name, (success, msg, val))

    # ===============================================================
    # Encode response
    def __encode(self, data):
        # Called when we have a good response
        success = False
        name = ""
        msg = ""
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
                print("Invalid value for position (not int): %d" % param)
                success = False
        return (name, (success, msg, val))

    # ===============================================================
    # Abort?
    # This is a special command which has no response from the Arduino
    # It causes the current activity to abort i.e. actuator stops and the current command finishes
    def __check_stop_abort(self):
        #print("Check abort or stop")
        if self.__q.qsize() > 0:
            name, args = self.__q.get()
            if name == 'abort':
                self.__ser.write(b'z;')
                self.__ser.flush()
                return ABORT
            elif name == 'free_stop':
                self.__ser.write(b'e;')
                self.__ser.flush()
                return STOP 
        return NONE
    
# ===============================================================
# TESTING
def callback(data):
    print (data)

if __name__ == '__main__':
    
    q = queue.Queue(10)
    comms = SerialComms(None, 'COM5', q, callback)
    comms.start()
    q.put(('pos', []))
    #print(q.qsize())
    sleep(5)
    comms.terminate()
    comms.join()
    
        