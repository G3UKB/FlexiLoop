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

# Qt5 imports
from PyQt5.QtWidgets import QApplication

# Application imports
from defs import *
import model
import persist
import api
import ui

# We expect to find the config file here otherwise it will be created.
CONFIG_PATH = '../config/flexi-loop.cfg'

#=====================================================
# The main application class
#===================================================== 
class AppMain:
    
    def run(self):
        print("Flexi-Loop Controller running...")
        # Manage configuration
        self.__configured = True
        self.__model = persist.getSavedCfg(CONFIG_PATH)
        if self.__model == None:
            print ('Configuration not found, using defaults')
            self.__model = model.flexi_loop_model
            self.__configured = False
        # print(self.__model)
        
        # Extract required fields
        port = self.__model[CONFIG][SERIAL][PORT]
        
        # The one and only QApplication 
        self.__qt_app = QApplication(sys.argv)
        ui_inst = ui.UI(self.__model, self.__qt_app, port)
        ui_inst.run()
        # Return here when UI is closed
        
        # Save model
        persist.saveCfg(CONFIG_PATH, self.__model)
        
#======================================================================================================================
# Main code
def main():
    
        try:
            app = AppMain()
            sys.exit(app.run()) 
        except Exception as e:
            print ('Exception [%s][%s]' % (str(e), traceback.format_exc()))
 
# Entry point       
if __name__ == '__main__':
    main()
    