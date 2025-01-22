#!/usr/bin/env python
#
# nanovna.py
#
# This file is derived from the nanovna.py version at:
# github.com/ttrftech/NanoVNA/tree/master/python
#
# Low level driver for the NanoVNA device. 
#

import serial
import numpy as np
import struct
from serial.tools import list_ports
import logging

VID = 0x0483 #1155
PID = 0x5740 #22336

# Get nanovna device automatically
def getport() -> str:
    device_list = list_ports.comports()
    for device in device_list:
        if device.vid == VID and device.pid == PID:
            return True, device.device
    return False, None

REF_LEVEL = (1<<9)

class NanoVNA:
    def __init__(self):
        
        self.logger = logging.getLogger('root')
        
        self.serial = None
        self._frequencies = None
        self.points = 101
        
    @property
    def frequency(self):
        return self._frequencies

    def set_frequencies(self, start = 1e6, stop = 900e6, points = None):
        if points:
            self.points = points
        self._frequencies = np.linspace(start, stop, self.points)

    def open(self):
        if self.serial is None:
            r, self.dev =  getport()
            if r:
                try:
                    self.serial = serial.Serial(self.dev)
                except Exception as e:
                    self.logger.warn("Unable to open VNA {}".format(e))
                    return False                                   
                return True
            return False
        return True

    def close(self):
        if self.serial:
            self.serial.close()
        self.serial = None

    def send_command(self, cmd):
        self.serial.write(cmd.encode())
        self.serial.readline() # discard empty line

    def resume(self):
        self.send_command("resume\r")
    
    def pause(self):
        self.send_command("pause\r")
        
    def set_sweep(self, start, stop):
        if start is not None:
            self.send_command("sweep start %d\r" % start)
        if stop is not None:
            self.send_command("sweep stop %d\r" % stop)

    def fetch_frequencies(self):
        self.send_command("frequencies\r")
        data = self.fetch_data()
        x = []
        for line in data.split('\n'):
            if line:
                x.append(float(line))
        self._frequencies = np.array(x)
     
    def fetch_data(self):
        result = ''
        line = ''
        while True:
            c = self.serial.read().decode('utf-8')
            if c == chr(13):
                next # ignore CR
            line += c
            if c == chr(10):
                result += line
                line = ''
                next
            if line.endswith('ch>'):
                # stop on prompt
                break
        return result   
    
    def data(self, array = 0):
        self.send_command("data %d\r" % array)
        data = self.fetch_data()
        x = []
        for line in data.split('\n'):
            if line:
                d = line.strip().split(' ')
                x.append(float(d[0])+float(d[1])*1.j)
        return np.array(x)
    
    def vswr(self, x):
        vswr = (1+np.abs(x))/(1-np.abs(x))
        return vswr
    
    def set_strength(self, strength):
        if strength is not None:
            self.send_command("power %d\r" % strength)
    
    def set_gain(self, gain):
        if gain is not None:
            self.send_command("gain %d %d\r" % (gain, gain))
            
    def set_offset(self, offset):
        if offset is not None:
            self.send_command("offset %d\r" % offset)
    
    def set_filter(self, filter):
        self.filter = filter
        
    def send_scan(self, start = 1e6, stop = 900e6, points = None):
        if points:
            self.send_command("scan %d %d %d\r"%(start, stop, points))
        else:
            self.send_command("scan %d %d\r"%(start, stop))
    
    def scan(self):
        segment_length = 101
        array0 = []
        array1 = []
        if self._frequencies is None:
            self.fetch_frequencies()
        freqs = self._frequencies
        while len(freqs) > 0:
            seg_start = freqs[0]
            seg_stop = freqs[segment_length-1] if len(freqs) >= segment_length else freqs[-1]
            length = segment_length if len(freqs) >= segment_length else len(freqs)
            self.send_scan(seg_start, seg_stop, length)
            array0.extend(self.data(0))
            array1.extend(self.data(1))
            freqs = freqs[segment_length:]
        self.resume()
        return (array0, array1)
    