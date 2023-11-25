#!/usr/bin/env python
#
# appmain.py
#
# Entry point for Flexi-loop application
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
import sys
import traceback

# Application imports
from defs import *
import model
import persist
import serialcomms
import calibrate

#=====================================================
# The main application class
#===================================================== 
class AppMain:
    
    def run(self, path):
        # Manage configuration
        self.__configured = True
        CONFIG_PATH = path
        self.__model = persist.getSavedCfg(CONFIG_PATH)
        if self.__model == None:
            print ('Configuration not found, using defaults')
            self.__model = model.flexi_loop_model
            self.__configured = False
        #print(self.__model)
        
        # Create a SerialComms instance
        serial_comms = serialcomms.SerialComms('COM5')
        
        # Create a Calibration instance
        cal = calibrate.Calibrate(serial_comms, self.__model)
        
        # Dummy calibration.
        cal = cal.calibrate(1, 10)
        print (cal)
        # Go to location
        serial_comms.move(550)
        
        # Save model
        persist.saveCfg(CONFIG_PATH, self.__model)
        
#======================================================================================================================
# Main code
def main():
    
        try:
            if len(sys.argv) != 2:
                print("Please supply a configuration filename!")
                print("python tuner_client.py <path>/filename")
            else:
                app = AppMain()
                sys.exit(app.run(sys.argv[1])) 
        except Exception as e:
            print ('Exception [%s][%s]' % (str(e), traceback.format_exc()))
 
# Entry point       
if __name__ == '__main__':
    main()