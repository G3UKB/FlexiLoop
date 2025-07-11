#!/usr/bin/env python
#
# persist.py
#
# Persistance for the Flexi-loop application
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
import os
import pickle

# Application imports

"""
Utility functions to get and save configuration and state
"""
def getSavedCfg(path):
    cfg = None
    if os.path.exists(path):
        try:       
            f = open(path, 'rb')
            cfg = pickle.load(f)
        except Exception as e:
            # Error retrieving configuration file
            print('Read Configuration File exception [{}]'.format(e))
        finally:
            try:
                f.close()
            except:
                pass
    return cfg
    
def saveCfg(path, cfg):
    try:
        dir, file = os.path.split(path)
        if not os.path.exists(dir):
            os.mkdir(dir)
        f = open(path, 'wb')
        pickle.dump(cfg, f)
    except Exception as e:
        # Error saving configuration file
        print('Save Configuration File exception [{}]'.format(e))
    finally:
        try:
            f.close()
        except:
            pass
        