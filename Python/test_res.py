#!/usr/bin/env python
#
# test_res.py
#
# User interface for testing the precsion of move and position
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
import sys
import traceback
import queue
import threading
import argparse

# PyQt5 imports
from qt_inc import *
# Qt5 imports
from PyQt5.QtWidgets import QApplication

# Application imports
from defs import *
from utils import *
import serialcomms
sys.path.append('../NanoVNA')
import vna_api


# Main window        
class TestRes(QMainWindow):
    
    def __init__(self, qt_app, start, end, points):
        super(TestRes, self).__init__()
        
        self.__qt_app = qt_app
        
        # Create the VNA instance
        self.__vna_open = False
        self.__vna_api = vna_api.VNAApi(None, False)
        if not self.__vna_api.open():
            print ('Failed to open VNA device!')
            sys.exit()
            
        # Create a SerialComms instance
        self.__s_q = queue.Queue(10)
        self.__serial_comms = serialcomms.SerialComms(None, self.__s_q, self.callback, False)
        self.__serial_comms.connect('COM3')
        self.__serial_comms.start()

        # Create the tracker
        self.__track = Track(self.__vna_api, start, end, points, self.track_cb)
        self.__track.start()
        
        # Local vars
        self.__name = ''
        self.__args = []
        self.__freq = 0.0
        self.__swr = 1.0
            
    def run(self):
        
        #=======================================================
        # Set main layout
        self.__central_widget = QWidget()
        self.setCentralWidget(self.__central_widget)
        self.__grid = QGridLayout()
        self.__central_widget.setLayout(self.__grid)
        
        # Move to feedback val
        fblabel = QLabel('Position')
        self.__grid.addWidget(fblabel, 0, 0)
        self.__fbtxt = QLineEdit()
        self.__fbtxt.setToolTip('Set feedback pos')
        self.__fbtxt.setInputMask('9000')
        self.__fbtxt.setMaximumWidth(80)
        self.__grid.addWidget(self.__fbtxt, 0, 1)
        
        self.__move = QPushButton("Move")
        self.__move.setToolTip('Move to fb val')
        self.__grid.addWidget(self.__move, 0, 2)
        self.__move.clicked.connect(self.__do_move)
        
        # Actual val
        poslabel = QLabel('Actual Pos')
        self.__grid.addWidget(poslabel, 1, 0)
        self.__posval = QLabel('?')
        self.__grid.addWidget(self.__posval, 1, 1)
        
        # reflect freq and swr
        freqlabel = QLabel('Freq')
        self.__grid.addWidget(freqlabel, 2, 0)
        self.__freqval = QLabel('?.?')
        self.__grid.addWidget(self.__freqval, 2, 1)
        
        swrlabel = QLabel('SWR')
        self.__grid.addWidget(swrlabel, 2, 2)
        self.__swrval = QLabel('?.?')
        self.__grid.addWidget(self.__swrval, 2, 3)
        
        # Show the GUI
        self.show()
        self.repaint()
        
         # Set up a minimal UI for testing
        #self.setGeometry(300,300,300,200)
        
        # Start idle processing
        QtCore.QTimer.singleShot(1000, self.__idleProcessing)
        
        # Enter event loop
        # Returns when GUI exits
        self.__qt_app.exec_()
        
        #self.__serial_comms.close()
        self.__serial_comms.terminate()
        self.__track.terminate()
    
    def __do_move(self):
        self.__s_q.put(('move', [int(self.__fbtxt.text())]))
        
    def callback(self, data):
        # Get current event data
        (name, (success, msg, args)) = data
        if not success:
            print('Failure: ', msg)
            sys.exit()
        else:
            if name == STATUS:
                self.__name = name
                self.__args = args
                
    def track_cb(self, f, swr):
        self.__freq = f
        self.__swr = swr
            
    #=======================================================
    # Idle processing called every IDLE_TICKER secs when no UI activity
    def __idleProcessing(self):
        
        if self.__name == STATUS:
            self.__posval.setText(str(self.__args[0]))
        
        self.__freqval.setText(str(round(self.__freq, 3)))
        self.__swrval.setText(str(round(self.__swr, 2)))
        
        # =======================================================
        # Reset timer
        QtCore.QTimer.singleShot(IDLE_TICKER, self.__idleProcessing)
 
# Track the VNA
class Track(threading.Thread):
    
    def __init__(self, vna_api, start, end, points, cb):
        super(Track, self).__init__()
        
        self.__vna_api = vna_api
        self.__cb = cb
        self.__term = False
        self.__start = float(start)
        self.__end = float(end)
        self.__points = int(points)
     
    # Terminate instance
    def terminate(self):
        self.__term = True
        
    def run(self):
        while not self.__term:
            r, f, vswr = self.__vna_api.get_vswr(self.__start, self.__end, self.__points)
            self.__cb(f, vswr)
            sleep(0.5)
        
        
#======================================================================================================================
# Main code
def main():
    
     # Manage command line arguments
    parser = argparse.ArgumentParser(
        prog='TEST_RES',
        description='Positioning and VNA',
        epilog='G3UKB')

    parser.add_argument('-s', '--start', action='store', required=True, help='Scan start freq in MHz')
    parser.add_argument('-e', '--end', action='store', required=True, help='Scan end freq in MHz')
    parser.add_argument('-p', '--points', action='store', required=False, default = 101, help='Number of scan points, default 101')
    args = parser.parse_args()
    start = args.start
    end = args.end
    points = args.points
    # Start application
    try:
        qt_app = QApplication(sys.argv)
        app = TestRes(qt_app, start, end, points)
        sys.exit(app.run()) 
    except Exception as e:
        print ('Exception {}, [{}]'.format(e, traceback.format_exc()))
 
# Entry point       
if __name__ == '__main__':
    main()
