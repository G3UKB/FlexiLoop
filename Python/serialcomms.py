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

ser = serial.Serial('COM5', 9600, timeout=1)
ser.reset_input_buffer()

def read_resp():
        acc = ""
        success = False
        resp_timeout = 5
        while(1):
                chr = ser.read().decode('utf-8')
                if chr == '':
                        print("Waiting response...")
                        if resp_timeout <= 0:
                                print("Response timeout - retrying...")
                                break
                        else:
                                resp_timeout -= 1
                                time.sleep(0.5)
                                continue
                acc = acc + chr
                if chr == ";":
                        print("Response: ", acc)
                        if ser.in_waiting > 0:
                                print("Mode data available - collecting... ", ser.in_waiting)
                                acc = ""
                                continue
                        success = True
                        break
        return success, acc

def send(cmd):
        while(1):
                print("Sending ", cmd)
                ser.write(cmd)
                ser.flush()
                time.sleep(0.1)
                r, acc = read_resp()
                if r == False:
                        time.sleep(0.2)
                        continue
                else:
                        break
                time.sleep(1)
                        
def speed():
        send(b"s;")
        
def home():
        send(b"h;")
        
def max():
        send(b"x;")
        
def pos():
        send(b"p;")
        
def move(pos):
        b = bytearray(b"m,")
        b += pos.encode('utf-8')
        b += b'.;'
        send(b)

def nudge_fwd():
        send(b"f;")

def nudge_rev():
        send(b"r;")
   
def run_fwd(ms):
        b = bytearray(b"w,")
        b += ms.encode('utf-8')
        b += b'.;'
        send(b)
        
def run_rev(ms):
        b = bytearray(b"v,")
        b += ms.encode('utf-8')
        b += b'.;'
        send(b)
        
def main():
        # Command sequence
        #move("86")
        #pos()
        #nudge_rev()
        #run_fwd("500")
        #p = pos()
        move("100")
        
        print("Press any key to exit...")
        input()
        
if __name__ == '__main__':
        main()
        