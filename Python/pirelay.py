#!/usr/bin/python

# Library for PiRelay V2
# Developed by: SB Components
# Author: Satyam
# Project: PiRelay-V2
# Python: 3.7.3


import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(False)

class Relay:
    ''' Class to handle Relay

    Arguments:
    relay = string Relay label (i.e. "RELAY1","RELAY2","RELAY3","RELAY4")
    '''
    relaypins = {"RELAY1":4, "RELAY2":17, "RELAY3":27, "RELAY4":22}


    def __init__(self, relay):
        self.pin = self.relaypins[relay]
        self.relay = relay
        GPIO.setup(self.pin,GPIO.OUT)
        GPIO.output(self.pin, GPIO.LOW)

    def on(self):
        print(self.relay + " - ON")
        GPIO.output(self.pin,GPIO.HIGH)

    def off(self):
        print(self.relay + " - OFF")
        GPIO.output(self.pin,GPIO.LOW
