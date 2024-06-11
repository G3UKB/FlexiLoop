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
from pathlib import Path
import traceback
import logging
from logging import handlers
import argparse

# Qt5 imports
from PyQt5.QtWidgets import QApplication

# Application imports
from defs import *
import model
import persist
import api
import ui

#=====================================================
# The main application class
#===================================================== 
class AppMain:
    def __init__(self, path, log ):
        self.path = path
        self.log = log
    
    def run(self):
        print("Flexi-Loop Controller running...")
        
        # Set up basic rotating file logging
        logger = logging.getLogger('root')
        logger.setLevel(logging.INFO)
        file_handler = logging.handlers.RotatingFileHandler(filename='log/flexi-loop.log', maxBytes=10000, backupCount = 3, encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(module)s - %(levelname)s - %(message)s', datefmt='%d/%m/%Y %H:%M:%S')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        # and a console handler
        stdout_handler = logging.StreamHandler(sys.stdout)
        stdout_handler.setFormatter(formatter)
        # Does user wany console logging?
        if self.log == 'Yes':
            logger.addHandler(stdout_handler)
        
        # Announce ourselves
        logger.info("***************** Start of Day *****************")
        logger.info("Flexi-Loop Controller running...")
        
        # Manage configuration
        self.__configured = True
        self.__model = persist.getSavedCfg(self.path)
        if self.__model == None:
            logger.info ('Configuration not found, using defaults')
            self.__model = model.flexi_loop_model
            self.__configured = False
        
        # The one and only QApplication 
        self.__qt_app = QApplication(sys.argv)
        # Use the stylesheet
        self.__qt_app.setStyleSheet(Path('css/flexiloop.css').read_text())
        # Create and run the UI
        ui_inst = ui.UI(self.__model, self.__qt_app)
        ui_inst.run()
        # Return here when UI is closed
        
        # Save model
        persist.saveCfg(self.path, self.__model)
        
        print("Flexi-Loop Controller exiting...")
        
#======================================================================================================================
# Main code
def main():
    
    # Manage command line arguments
    parser = argparse.ArgumentParser(
        prog='Flexi-Loop Controller',
        description='Controller for the Flexi-Loop mag loop project',
        epilog='Bob - G3UKB')
    parser.add_argument('-p', '--config-path', dest='path', default=CONFIG_PATH, help='Path to config file, default is %s' % CONFIG_PATH)
    parser.add_argument('-c', '--console-log', dest='log', choices=['Yes', 'No'], help='Yes = log to console as well as file, default is file only')
    args = parser.parse_args()
    
    # Start application
    try:
        app = AppMain(args.path, args.log)
        sys.exit(app.run()) 
    except Exception as e:
        print ('Exception [%s][%s]' % (str(e), traceback.format_exc()))
 
# Entry point       
if __name__ == '__main__':
    main()
    