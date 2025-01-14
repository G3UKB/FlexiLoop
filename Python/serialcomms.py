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
import logging

# Application imports
from defs import *

# Verbose flag
VERB = True

# Pause at end of processing SLEEP_TIMER secs
SLEEP_TIMER = 0.1

#=====================================================
# Manage all serial comms to the Arduino
#===================================================== 
class SerialComms(threading.Thread):

    # =============================================================== 
    # Initialise class
    def __init__(self, model, q, main_callback):
        super(SerialComms, self).__init__()
        
        # Get root logger
        self.logger = logging.getLogger('root')

        # Parameters
        self.__model = model
        self.__q = q
        self.__cb = main_callback
        
        # Instance vars
        self.__originalcb = main_callback
        self.term = False
        self.__port = None
        self.__ser = None
        self.__ticks = (HEARTBEAT_TIMER/1000)/SLEEP_TIMER
        self.__heartbeat = self.__ticks

    # Attempt connect to Arduino
    def connect(self):
        self.__port = self.__model[CONFIG][ARDUINO][PORT]
        try:
            self.__ser = serial.Serial(self.__port, 9600, timeout=1)
        except Exception as e:
            self.__model[STATE][ARDUINO][ONLINE] = False
            return False
        
        self.__model[STATE][ARDUINO][ONLINE] = True
        self.__ser.reset_input_buffer()
        return True
    
    # Caller changes callback     
    def steal_callback( self, new_callback) :
        """ Steal the dispatcher callback """
        self.__cb = new_callback
    
    # Caller restors callback
    def restore_callback(self) :
        """ Restore the dispatcher callback """
        self.__cb = self.__originalcb
        
    # Terminate instance
    def terminate(self):
        """ Thread terminating """
        self.term = True
    
    # Thread entry point
    def run(self):
        global VERB
        self.logger.info("Running...")
        while not self.term:
            # Heartbeat
            self.__heartbeat -= 1
            if self.__heartbeat <= 0:
                self.__heartbeat = self.__ticks
                # Time to check
                heartbeat = True
                try:
                    verb = VERB
                    VERB = False
                    name, (success, msg, val) = self.send(b"y;", 1)
                    VERB = verb
                    if not success:
                        heartbeat = False
                except:
                    heartbeat = False
                if not heartbeat:
                    # This will get picked up and a reconnect attempted
                    self.__model[STATE][ARDUINO][ONLINE] = False
                    self.__ser.close()
                    self.logger.warn("Exiting serial comms as no heartbeat detected. It will be restarted but any current activity will fail.")
                    break
            
            # Process messages
            try:
                if self.__q.qsize() > 0:
                    if VERB: self.logger.info("Q sz: {}, ".format(self.__q.qsize()))
                    while self.__q.qsize() > 0:
                        name, args = self.__q.get()
                        if VERB: self.logger.info("Name: {}, Args: {}".format(name, args))
                        # Execute command, responses are by callback
                        self.__dispatch(name, args)
                        # Here after command/response sequence
                        self.__q.task_done()
                else:
                    sleep(SLEEP_TIMER)
            except Exception as e:
                # Something went wrong
                self.logger.warn('Exception processing serial command! Serial comms will restart but any current activity will fail. {}, [{}]'.format(e, traceback.print_exc()))
                break
                
        self.logger.info("Comms thread exiting...")
    
    # ===============================================================
    # PRIVATE
    # Command execution
    # Dispatch to handler
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
            'relay_on' : self.__relay_on,
            'relay_off' : self.__relay_off,
            'abort' : self.__abort,
        }
        # Execute and return response
        self.__cb(disp_tab[name](args))
    
    # Execute Arduino function and wait response    
    def __speed(self, args):
        speed = args[0]
        b = bytearray(b"s,")
        b += str(speed).encode('utf-8')
        b += b'.;'
        return self.send(b, 2)
            
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
    
    def __relay_on(self, args):
        return self.send(b"a;", 2)
    
    def __relay_off(self, args):
        return self.send(b"b;", 2)
    
    def __abort(self, args):
        # There is no response to an abort it just forces a return
        # from any move in progress or absorbs it if no activity
        self.__ser.write(b"z;")
        self.__ser.flush()
        return (ABORT, (True, "User abort!", []))
        
    # ===============================================================
    # Send a command to the Arduino
    def send(self, cmd, timeout):
        val = 0
        msg = ""
        retries = 5
        while(1):
            if VERB: self.logger.info("Sending {}".format(cmd))
            self.__ser.write(cmd)
            self.__ser.flush()
            retries -= 1
            sleep(0.1)
            resp = self.read_resp(timeout)
            if resp[1][0] == False:
                sleep(0.2)
                if VERB: self.logger.info("Command failed, retrying...")
                if retries <= 0:
                    msg = "Command failed after 5 retries" 
                    return (resp[0], (False, msg, []))
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
                self.logger.info("Stop motor after forward or reverse command.")
            # Read a single character
            chr = self.__ser.read().decode('utf-8')
            if chr == '':
                # Timeout on read
                if resp_timeout <= 0:
                    # Timeout on waiting for a response
                    if VERB: self.logger.info("Response timeout!")
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
                    #if VERB: self.logger.info("Status: {0}".format(acc))
                    self.__cb(self.__encode(acc))
                    acc = ""
                    continue
                if "Limit" in acc:
                    self.__cb(self.__encode(acc))
                    continue
                elif "Dbg" in acc:
                    # Its a debug message so return this directly
                    #if VERB: self.logger.info("Dbg: {0}".format(acc))
                    self.__cb(self.__encode(acc))
                    acc = ""
                    continue
                # Otherwise its a response to the command
                if VERB: self.logger.info("Response: {}".format(acc))
                if self.__ser.in_waiting > 0:
                    # Still data in buffer, probably should not happen!
                    # Dump response and use this data
                    if VERB: self.logger.info("More data available {} - collecting... ".format(self.__ser.in_waiting))
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
                # Treat as a single string parameter
                val.append(param)
        return (name, (success, msg, val))

    # ===============================================================
    # Abort is available for long running commands that maybe have multiple actions.
    # Stop is used to stop the actuator when using manual free running forward or reverse.
    # An abort has no response but simply closes all current and pending activities.
    # A stop will cause the forward or reverse commands to complete with their normal response.
    def __check_stop_abort(self):
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
    
    
        