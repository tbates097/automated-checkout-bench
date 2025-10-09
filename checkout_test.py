# -*- coding: utf-8 -*-
"""
Created on Wed Sep 25 08:27:05 2024

@author: TBates
"""

import automation1 as a1
from automation1.internal.exceptions_gen import ControllerAxisFaultException, ControllerOperationException
import os
import logging
import sys
import tkinter as tk
from tkinter import messagebox
import time
import re
import numpy as np
import datetime
from datetime import datetime
import json
import zipfile
import tempfile
import xml.etree.ElementTree as ET
from collections import deque
import threading
from station_manager import StationManager
from station_manager_instance import get_station_manager
from exceptions import TestSequenceAbort
from BurnIn import burn_in
import shutil
from GenerateMCD_v2 import AerotechController

sys.path.append(r"K:\10. Released Software\Shared Python Programs\production-2.1")
from a1_file_handler import DatFile
#from GenerateMCD import AerotechController
from Logger import TextLogger
from DecodeFaults import decode_faults
from sheets_update import Sheets, Checkout_Sheet
#from RedirectStdout import RedirectStdout

_thread_lock = threading.Lock()

class TestSequenceAbort(Exception):
    def __init__(self, message, shown_message=False):
        super().__init__(message)
        self.shown_message = shown_message

class stage_checkout():
    '''
    This program is intended to take a complete set of hexapod struts through an automated check-out procedure.
    '''
    def __init__(self, stage_type, speed, burnin_time, job, op, comments, secondary_ui, window, num_axes, test_axes, duty_cycle, specs_dict, absolute, stations, param_dict, **kwargs):
        """
        Initialization method for the hex_strut_checkout class.

        Parameters:
            stage_type (str): The type of hexapod being checked out
            encoder (str): The type of encoder being used (e.g. 'E1', 'E2', etc.)
            speed (int): The speed at which the struts will move during the check-out (in mm/s)
            burnin_time (int): The length of time the struts will run during the check-out (in hours)
            job (str): The serial number of the hexapod being checked out
            op (str): The operator performing the check-out
            comments (str): Any additional comments or notes the operator wishes to record
            text_widget (tkinter.Text): The text widget to which the program will write its output
            window (tkinter.Tk): The main tkinter window
            connected_axes (dict): A dictionary of the connected axes (key = axis name, value = axis index)
            duty_cycle (int): The percentage of the time the struts will be moving during the check-out
            **kwargs: Any additional keyword arguments
        """
        self.stage_type = stage_type
        self.speed = speed
        self.burnin_time = burnin_time
        self.job = job
        self.op = op
        self.comments = comments
        self.secondary_ui = secondary_ui
        self.window = window
        self.num_axes = num_axes
        self.test_axes = test_axes
        self.duty_cycle = duty_cycle
        self.specs_dict = specs_dict
        self.absolute = absolute
        self.stations = stations
        self.param_dict = param_dict
        self.full_smart_string = kwargs.get('full_smart_string', None)
        self.bus_voltage = kwargs.get('bus_voltage', '80')  # Default to 80V if not provided
        
        self.sample_rate = 1000
        
        # Define mapping between axis names and station IDs
        self.axis_to_station_map = {
            'ST01': 1,
            'ST02': 2,
            'ST03': 3,
            'ST04': 4,
            'ST05': 5,
            'ST06': 6,
            'ST07': 7,
            'ST08': 8,
            'ST09': 9,
            'ST10': 10
        }

        # Initialize station loggers without clearing existing text
        self.station_loggers = {}
        for axis in self.test_axes:
            station_id = self.axis_to_station_map.get(axis)
            if station_id:
                station_widget = self.secondary_ui.station_widgets.get(station_id)
                if station_widget:
                    # Don't clear the text widget, just create a logger for it
                    self.station_loggers[station_id] = TextLogger(station_widget["txt_logs"], clear_existing=False)
        
        self.hall_dict = {
            0: "001",
            60: "011",
            120: "010",
            180: "110",
            240: "100",
            300: "101",
            
        }
        self.window = tk.Tk()
        self.window.withdraw()
        
        # Initialize hall sensor dictionaries
        self.hall_a = {}
        self.hall_b = {}
        self.hall_c = {}
        self.hall_states = {}
        self.hall_encoder_positions = {}
        self.pri_fbk = {}
        self.ccw_fault = {}
        self.cw_fault = {}
        self.pos_error_fault = {}
        self.over_current_fault = {}
        
        # Initialize unique state tracking dictionaries
        self.unique_hall_states = {}
        
        # Create a separate logger for each station
        self.fault_log = logging.getLogger('fault_logger')
        self.st02_log = logging.getLogger('ST02_logger')
        self.st03_log = logging.getLogger('ST03_logger')
        
        # Configure each logger with its own file handler
        fault_handler = logging.FileHandler('logs with hall states.txt')
        st02_handler = logging.FileHandler('ST02_hall_states.txt')
        st03_handler = logging.FileHandler('ST03_hall_states.txt')
        
        # Set format for the logs
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fault_handler.setFormatter(formatter)
        st02_handler.setFormatter(formatter)
        st03_handler.setFormatter(formatter)
        
        # Add handlers to loggers
        self.fault_log.addHandler(fault_handler)
        self.st02_log.addHandler(st02_handler)
        self.st03_log.addHandler(st03_handler)
        
        # Set log levels
        self.fault_log.setLevel(logging.INFO)
        self.st02_log.setLevel(logging.INFO)
        self.st03_log.setLevel(logging.INFO)
        
        # Register abort callbacks for each station
        for axis in self.test_axes:
            station_id = self.axis_to_station_map[axis]
            self.secondary_ui.register_abort_callback(
                station_id, 
                lambda axis=axis: self.abort_test(axis)
            )

        # Add to your initialization
        self.aborted_stations = {}  # Track which stations have been aborted

    def abort_test(self, axis):
        """Handle abort button click for a specific axis"""
        station_id = self.axis_to_station_map[axis]
        
        # Set abort flag first
        self.aborted_stations[station_id] = True
        
        # Give threads a moment to see the abort flag
        time.sleep(0.5)
        
        # Now try to stop the axis
        try:
            controller = self.station_controllers[axis]
            controller.runtime.commands.motion.abort([axis])
            controller.runtime.commands.motion.disable([axis])
        except Exception as e:
            self.station_print(f"Error during abort: {str(e)}", station_id=station_id)
        
        # Remove from active testing
        if axis in self.test_axes:
            self.test_axes.remove(axis)
        if axis in self.station_controllers:
            del self.station_controllers[axis]
        
        # Update UI
        self.secondary_ui.update_station_status(station_id, running=False, serial="")
        
        # Immediately release this station in StationManager so it becomes available
        try:
            sm = get_station_manager()
            if sm:
                sm.release_stations(axis)  # axis is like 'ST01'
        except Exception as e:
            self.station_print(f"Station release error: {str(e)}", station_id=station_id)

        # Raise TestSequenceAbort if no axes remain
        if not self.test_axes:
            messagebox.showerror("Test Sequence Aborted", "All tests aborted by user.")
            raise TestSequenceAbort("All tests aborted by user.", shown_message=True)

    def release_axis(self, axis):
        """Disable, update UI, cleanup resources, and release a station via StationManager.
        axis is like 'ST01'"""
        try:
            station_id = self.axis_to_station_map.get(axis)
        except Exception:
            station_id = None
        # Best-effort motion stop/disable
        try:
            if axis in getattr(self, 'station_controllers', {}):
                ctrl = self.station_controllers[axis]
                try:
                    ctrl.runtime.commands.motion.abort([axis])
                except Exception:
                    pass
                try:
                    ctrl.runtime.commands.motion.disable([axis])
                except Exception:
                    pass
        except Exception:
            pass
        # UI updates
        try:
            if station_id is not None:
                self.secondary_ui.update_station_status(station_id, running=False, serial="")
                self.station_print(f"Station {station_id} has been released", station_id=station_id)
        except Exception:
            pass
        # Cleanup data structures
        try:
            if axis in getattr(self, 'test_axes', []):
                try:
                    self.test_axes.remove(axis)
                except ValueError:
                    pass
            if axis in getattr(self, 'station_controllers', {}):
                del self.station_controllers[axis]
            if hasattr(self, 'station_loggers') and station_id in getattr(self, 'station_loggers', {}):
                try:
                    del self.station_loggers[station_id]
                except Exception:
                    pass
        except Exception:
            pass
        # Actual StationManager release
        try:
            sm = get_station_manager()
            if sm:
                sm.release_stations(axis)
                sm.refresh_station_status()
        except Exception:
            pass

    def station_print(self, message, station_id=None):
        """
        Print a message to specific station(s) text_widget or all stations.
        Only prints to stations that are part of this test.
        """
        if station_id is None:
            # Only print to stations involved in this test
            for axis in self.test_axes:
                sid = self.axis_to_station_map.get(axis)
                if sid in self.station_loggers:
                    self.station_loggers[sid].write(message + "\n")
        else:
            if not isinstance(station_id, list):
                station_id = [station_id]
            
            for sid in station_id:
                if sid in self.station_loggers:
                    self.station_loggers[sid].write(message + "\n")

    def reset_stdout(self):
        """
        Reset sys.stdout to its original value.
        """
        sys.stdout = sys.__stdout__

    def get_limit_dec(self, controller, axis, limit=None):
        # Retrieve the current configuration for the axis
        electrical_limits = controller.runtime.parameters.axes[axis].protection.faultmask
        electrical_limit_value = int(electrical_limits.value)

        # Define bit positions for each limit
        CCW_SOFTWARE_LIMIT = 5
        CW_SOFTWARE_LIMIT = 4
        CCW_ELECTRICAL_LIMIT = 3
        CW_ELECTRICAL_LIMIT = 2

        # Toggle limits
        if limit == 'software on':
            electrical_limit_value |= (1 << CCW_SOFTWARE_LIMIT) | (1 << CW_SOFTWARE_LIMIT)
        elif limit == 'software off':
            electrical_limit_value &= ~((1 << CCW_SOFTWARE_LIMIT) | (1 << CW_SOFTWARE_LIMIT))
        elif limit == 'electrical on':
            electrical_limit_value |= (1 << CCW_ELECTRICAL_LIMIT) | (1 << CW_ELECTRICAL_LIMIT)
        elif limit == 'electrical off':
            electrical_limit_value &= ~((1 << CCW_ELECTRICAL_LIMIT) | (1 << CW_ELECTRICAL_LIMIT))

        return electrical_limit_value

    def get_spec_value(self, spec_key):
        """
        Get a numerical value from specs_dict, handling int, float, and string formats.
        
        Args:
            spec_key (str): The key to look up in specs_dict
            
        Returns:
            float: The numerical value
            
        Raises:
            ValueError: If the spec is not found or cannot be converted to float
        """
        spec = self.specs_dict.get(spec_key)
        if spec is None:
            raise ValueError(f"Specification '{spec_key}' not found in specs_dict")
        
        try:
            if isinstance(spec, (int, float)):
                return float(spec)
            return float(str(spec).split()[0])
        except (AttributeError, ValueError, TypeError) as e:
            raise ValueError(f"Could not convert {spec_key}={spec} to float: {e}")
    
    def get_param_value(self, spec_key):
        """
        Get a numerical value from param_dict, handling int, float, and string formats.
        
        Args:
            spec_key (str): The key to look up in param_dict
            
        Returns:
            float: The numerical value
            
        Raises:
            ValueError: If the spec is not found or cannot be converted to float
        """
        spec = self.param_dict.get(spec_key)
        if spec is None:
            raise ValueError(f"Specification '{spec_key}' not found in specs_dict")
        
        try:
            if isinstance(spec, (int, float)):
                return float(spec)
            return float(str(spec).split()[0])
        except (AttributeError, ValueError, TypeError) as e:
            raise ValueError(f"Could not convert {spec_key}={spec} to float: {e}")

    def create_tracked_thread(self, target, axis, station_id=None, args=()):
        """
        Create a thread and track it for cleanup, with error handling for aborted stations.
        """
        def wrapped_target(*args):
            try:
                # Check abort state before starting
                station_id = self.axis_to_station_map.get(axis)
                if station_id in self.aborted_stations:
                    self.station_print(f"Thread for {axis} stopping due to abort", station_id=station_id)
                    return
                
                # Run the actual function
                result = target(*args)
                
                # Check abort state after completion
                if station_id in self.aborted_stations:
                    self.station_print(f"Thread for {axis} completed but abort was triggered", station_id=station_id)
                    raise TestSequenceAbort(f"Test aborted for station {station_id}", shown_message=True)
                
                return result
                
            except Exception as e:
                station_id = thread.station_id
                if station_id in self.aborted_stations:
                    error_msg = f"Thread stopped: {str(e)}"
                    self.station_print(error_msg, station_id=station_id)
                    raise TestSequenceAbort(error_msg, shown_message=True)
                else:
                    raise

        thread = threading.Thread(target=wrapped_target, args=args)
        thread.axis = axis
        thread.station_id = station_id or self.axis_to_station_map.get(axis)
        if not hasattr(self, 'active_threads'):
            self.active_threads = []
        self.active_threads.append(thread)
        return thread

    def upload_mcd(self, controller, mcd_path):
        """Uploads an MCD file to the controller"""
        try:
            controller.upload_mcd_to_controller(
                mcd_path, 
                should_include_files=True, 
                should_include_configuration=True, 
                erase_controller=False
            )
            return True
        except Exception as e:
            print(f"❌ Error uploading MCD: {str(e)}")
            return False
        
    def test(self, reenable_run_button, station_controllers):
        """
        Main entry point for the checkout process.
        
        Args:
            station_controllers (dict): Dictionary mapping axis names to their respective controllers
        """
        self.station_controllers = station_controllers
        self.reenable_run_button = reenable_run_button
        self.reenable_run_button()

        # Resolve default burn-in speed if requested (compute as 1/4 of MaxJogSpeed)
        try:
            if isinstance(self.speed, str) and self.speed.lower() == 'default':
                if not self.test_axes:
                    raise ValueError("No test axes available to compute default speed")
                axis = self.test_axes[0]
                controller = self.station_controllers[axis]
                max_jog = controller.runtime.parameters.axes[axis].motion.maxjogspeed.value
                self.speed = float(max_jog) / 4.0
                sid = self.axis_to_station_map.get(axis)
                self.station_print(f"Using default burn-in speed = 1/4 of MaxJogSpeed for {axis}: {max_jog} -> {self.speed}", station_id=sid)
        except Exception as e:
            sid_list = [self.axis_to_station_map[a] for a in self.test_axes] if self.test_axes else None
            self.station_print(f"Failed to compute default burn-in speed: {e}", station_id=sid_list)
            raise

        # Initialize data dictionary for each axis

        station_id = [self.axis_to_station_map[axis] for axis in self.test_axes]
        self.station_print(f"Starting test for {self.job}.", station_id=station_id)
        self.data = {}
        for axis in self.test_axes:
            self.data[axis] = {
                "Testing Technician": "",
                "Date of Testing": "",
                "Halls": "",
                "Marker": "",
                "Limits": "",
                "Total Travel": "",
                "Home Marker from Limit": "",
                "Home Offset": "",
                "Absolute value at CCW EOT": "",
                "Absolute Position Offset": ""
            }
        
        self.init_logger()
        self.fault_log.info(f'Model: {self.stage_type}.  Serial Number: {self.job}.  On Station(s): {", ".join(self.test_axes)}')
        self.stage_info.info(f'Model: {self.stage_type}.  Serial Number: {self.job}.  On Station(s): {", ".join(self.test_axes)}')
        
        # Initialize motion parameters
        self.list_commands_ccw_pos = []
        self.list_commands_cw_pos = []
        self.list_commands_zero = []
        self.list_velocity = []
        self.list_low_velocity = []
        
        # Set the nominal positions and velocities for each axis
        for axis in self.test_axes:
            self.data[axis]["Testing Technician"] = self.op
            self.data[axis]["Date of Testing"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                nominal_travel = abs(self.get_spec_value('Travel'))
                self.list_commands_ccw_pos.append(nominal_travel / 2 * -1)
                self.list_commands_cw_pos.append(nominal_travel / 2)
                self.list_commands_zero.append(0)
                self.list_velocity.append(self.speed)
                self.list_low_velocity.append(0.5)
            except ValueError as e:
                station_id = self.axis_to_station_map.get(axis)
                self.station_print(f"Error: {e}", station_id=station_id)
                return

        self.zero_home_offset = 0
        self.max_current_clamp = 10
        self.low_current_clamp = 3.5

        self.nominal_travel = abs(self.get_spec_value('Travel'))
        self.mdk_path = fr'C:\Users\tbates\Documents\Automation1\{self.stage_type}.mcd'

        # Configure initial parameters for each axis
        #base_dir = os.path.dirname(os.path.abspath(__file__))
        #AEROTECH_DLL_PATH = os.path.join(base_dir, "extern", "Automation1")

        # Use full smart string for filename, fallback to stage_type if not available
        smart_string_for_filename = self.full_smart_string or self.stage_type
        
        mcd_processor = AerotechController.for_checkout_workflow(
            smart_string=smart_string_for_filename,
            output_dir=r"O:\CMP Check-out\Parameter Files\Automation1"
        )
        mcd_processor.initialize()

        for axis in self.test_axes:
            # Create electrical_dict with hardcoded iXA4 values plus user-selected bus voltage
            electrical_dict = {
                "Bus Voltage": self.bus_voltage,  # User-selected voltage from UI
                "Motor Supply Voltage": "-AC",   # Hardcoded for iXA4
                "Current Axes 1 and 2": "-20"    # Hardcoded for iXA4
            }
            # Get electrical_dict from GUI configuration
            #electrical_dict = None
            
            calculated_mcd, warnings, mcd_path = mcd_processor.calculate_parameters(
                specs_dict=self.specs_dict,      # Only mechanical configurations
                electrical_dict=electrical_dict, # Use the electrical_dict from GUI
                stage_type=self.stage_type, 
                axis=axis,
                drive_type="iXA4"                # Template selection for iXA4 drives
            )
            # Your existing Automation1 controller object
            controller = self.station_controllers[axis]  # This is the actual A1 controller
            
            # Temporarily modify MCD to set axis name
            # Use system temp directory with write permissions
            temp_dir = tempfile.mkdtemp(prefix="mcd_extract_")
            
            try:
                # Extract the original MCD
                with zipfile.ZipFile(mcd_path, 'r') as zip_ref:
                    zip_ref.extractall(temp_dir)
            
                # Modify the Parameters file
                params_path = os.path.join(temp_dir, "config", "Parameters")
                if os.path.exists(params_path):
                    tree = ET.parse(params_path)
                    root = tree.getroot()
            
                    # Find the correct Axis element (Index="0" for your use case)
                    axis_elem = root.find(".//Axes/Axis[@Index='0']")
                    if axis_elem is not None:
                        # Find all <P> children
                        p_elements = list(axis_elem.findall("P"))
                        # Find the index of AverageCurrentThreshold and CountsPerUnit
                        idx_avg = next((i for i, p in enumerate(p_elements) if p.get("n") == "AverageCurrentThreshold"), None)
                        idx_counts = next((i for i, p in enumerate(p_elements) if p.get("n") == "CountsPerUnit"), None)
            
                        if idx_avg is not None and idx_counts is not None and idx_counts > idx_avg:
                            # Create the new AxisName element
                            axis_name_element = ET.Element("P", {"id": "0", "n": "AxisName"})
                            axis_name_element.text = axis  # e.g., "ST01"
                            # Insert after AverageCurrentThreshold (before CountsPerUnit)
                            axis_elem.insert(idx_avg + 1, axis_name_element)
            
                            # Save the modified Parameters file with XML declaration
                            xml_str = '<?xml version="1.0" encoding="utf-8" standalone="yes"?>\n'
                            tree_str = ET.tostring(root, encoding='unicode')
                            if tree_str.startswith('<?xml'):
                                tree_str = tree_str[tree_str.find('?>')+2:]
                            with open(params_path, 'w', encoding='utf-8') as f:
                                f.write(xml_str + tree_str)
                        else:
                            print("Could not find both AverageCurrentThreshold and CountsPerUnit elements.")
                    else:
                        print("Axis element with Index='0' not found.")
                else:
                    print("Parameters file not found.")
            
                # Repack all files into the same new_mcd path
                with zipfile.ZipFile(mcd_path, 'w', zipfile.ZIP_DEFLATED) as new_zip:
                    for folder, dirs, files in os.walk(temp_dir):
                        for file in files:
                            file_path = os.path.join(folder, file)
                            arcname = os.path.relpath(file_path, temp_dir)
                            new_zip.write(file_path, arcname)
            
            except Exception as e:
                print(f"❌ Error modifying MCD: {str(e)}")
            finally:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
            
            self.upload_mcd(controller, mcd_path)
            
            print(f"Loading new parameters for axis {axis} from MCD: {mcd_path}")

        time.sleep(5)

        try:
            try:
                # Reset all controllers in parallel
                self.reset_controllers()
                time.sleep(5)
            except TestSequenceAbort:
                raise
            try:
                # Enable the stages
                self.enable_stages()
                time.sleep(5)
            except TestSequenceAbort:
                raise
            try:
                # Check Halls
                for axis in self.test_axes:
                    controller = self.station_controllers[axis]
                    commutation = controller.runtime.parameters.axes[axis].motor.commutationinitializationsetup.value
                if commutation == 0:
                    self.check_halls()
                    time.sleep(5)
                # Split the test to Absolute and Incremental
                if self.absolute:
                    try:
                        # Check Hardstop
                        self.absolute_hardstop()
                        time.sleep(5)
                    except TestSequenceAbort:
                        raise
                    try:
                        # Calculate Home Offset
                        self.calculate_home_offset()
                        time.sleep(5)
                    except TestSequenceAbort:
                        raise
                    try:
                        # Software Limits
                        self.software_limits()
                        time.sleep(5)
                    except TestSequenceAbort:
                        raise
                    try:
                        # Burn in
                        BI = burn_in(
                                self.speed, 
                                self.burnin_time, 
                                self.secondary_ui, 
                                self.window, 
                                self.test_axes, 
                                self.nominal_travel, 
                                self.fault_log, 
                                self.stage_info, 
                                self.duty_cycle, 
                                self.job_log_dir, 
                                self.stage_type, 
                                self.absolute, 
                                self.job, 
                                self.op, 
                                self.comments, 
                                self.specs_dict, 
                                self.stations, 
                                self.stage_log_file,
                                self.param_dict
                            )
                        BI.initialize_burnin(self.station_controllers)

                        time.sleep(5)
                        self.home_stages()
                    except TestSequenceAbort:
                        raise

                    for idx, axis in enumerate(self.test_axes, start=1):
                            # Create per-axis flat data dictionary (what Checkout_Sheet expects)
                            axis_data = {
                                "Testing Technician": self.data[axis]["Testing Technician"],
                                "Date of Testing": self.data[axis]["Date of Testing"],
                                "Halls": self.data[axis]["Halls"],
                                "Marker": self.data[axis]["Marker"],
                                "Limits": self.data[axis]["Limits"],
                                "Total Travel": self.data[axis]["Total Travel"],
                                "Home Marker from Limit": self.data[axis]["Home Marker from Limit"],
                                "Home Offset": self.data[axis]["Home Offset"],
                                "Absolute value at CCW EOT": self.data[axis]["Absolute value at CCW EOT"],
                                "Absolute Position Offset": self.data[axis]["Absolute Position Offset"]
                            }
                            job_with_suffix = f"{self.job}-{idx:02d}"
                            checkout_sheet = Checkout_Sheet(job_with_suffix, axis_data)
                            checkout_sheet.duplicate_sheet()
                            checkout_sheet.populate_sheet()

                else:
                    try:
                        # Home Stages
                        self.home_stages(initial=True)
                        time.sleep(5)
                    except TestSequenceAbort:
                        raise

                    try:
                        # Check Hardstop
                        self.check_hardstop()
                        time.sleep(5)
                    except TestSequenceAbort:
                        raise

                    try:
                        # Calculate Home Offset
                        self.calculate_home_offset()
                        time.sleep(5)
                    except TestSequenceAbort:
                        raise

                    try:
                        # Software Limits
                        self.software_limits()
                        time.sleep(5)
                    except TestSequenceAbort:
                        raise

                    try:
                        # Burn in
                        BI = burn_in(
                                self.speed, 
                                self.burnin_time, 
                                self.secondary_ui, 
                                self.window, 
                                self.test_axes, 
                                self.nominal_travel, 
                                self.fault_log, 
                                self.stage_info, 
                                self.duty_cycle, 
                                self.job_log_dir, 
                                self.stage_type, 
                                self.absolute, 
                                self.job, 
                                self.op, 
                                self.comments, 
                                self.specs_dict, 
                                self.stations, 
                                self.stage_log_file,
                                self.param_dict
                            )
                        BI.initialize_burnin(self.station_controllers)
                    except TestSequenceAbort:
                        raise
                    try:    
                        for idx, axis in enumerate(self.test_axes, start=1):
                            # Create per-axis flat data dictionary (what Checkout_Sheet expects)
                            axis_data = {
                                "Testing Technician": self.data[axis]["Testing Technician"],
                                "Date of Testing": self.data[axis]["Date of Testing"],
                                "Halls": self.data[axis]["Halls"],
                                "Marker": self.data[axis]["Marker"],
                                "Limits": self.data[axis]["Limits"],
                                "Total Travel": self.data[axis]["Total Travel"],
                                "Home Marker from Limit": self.data[axis]["Home Marker from Limit"],
                                "Home Offset": self.data[axis]["Home Offset"],
                                "Absolute value at CCW EOT": self.data[axis]["Absolute value at CCW EOT"],
                                "Absolute Position Offset": self.data[axis]["Absolute Position Offset"]
                            }
                            job_with_suffix = f"{self.job}-{idx:02d}"
                            checkout_sheet = Checkout_Sheet(job_with_suffix, axis_data)
                            checkout_sheet.duplicate_sheet()
                            checkout_sheet.populate_sheet()
                        
                    except TestSequenceAbort:
                        raise
                    try:
                        time.sleep(5)
                        self.home_stages()
                    except TestSequenceAbort:
                        raise
                # Only print completion if we get here
                if self.test_axes:  # Check if we still have axes to test
                    station_id = [self.axis_to_station_map[axis] for axis in self.test_axes]
                    self.station_print(f"Test completed for {axis}.", station_id=station_id)

            except TestSequenceAbort:
                raise

        except TestSequenceAbort as e:
            if not e.shown_message:
                messagebox.showerror("Test Sequence Aborted", str(e))
            return  # Exit the function after handling the abort

        finally:
            try:
                if not self.test_axes:
                    axes_to_cleanup = list(self.station_controllers.keys())
                    for axis in axes_to_cleanup:
                        station_id = self.axis_to_station_map[axis]
                        self.cleanup_data_structures(station_id, axis)
                else:
                    for axis in self.test_axes:
                        station_id = self.axis_to_station_map[axis]
                        self.cleanup_data_structures(station_id, axis)
            except Exception as e:
                self.fault_log.error(f"Error during cleanup: {str(e)}")
        
    def params(self, controller, axis, home_offset=None, current_clamp=None, limit=None, home_setup=None, home_speed=None):
        """
        Configure parameters for a specific axis on its controller.

        Args:
            controller: The controller object for this specific axis
            axis: The axis to configure
            home_offset (int): The home offset value for the axis
            current_clamp (float): The maximum current clamp value
            limit (str): The fault mask limits (e.g., 'software on', 'software off')
        """
        # Retrieve current configuration parameters for the axis
        configured_parameters = controller.configuration.parameters.get_configuration()
        
        if home_offset:
            if self.absolute:
                configured_parameters.axes[axis].feedback.auxiliaryabsolutefeedbackoffset.value = home_offset
            else:
                configured_parameters.axes[axis].homing.homeoffset.value = home_offset
        if home_offset == 0:
            configured_parameters.axes[axis].homing.homeoffset.value = 0
        if current_clamp:
            configured_parameters.axes[axis].protection.limitdebouncedistance.value = 1
            configured_parameters.axes[axis].protection.maxcurrentclamp.value = current_clamp

        if limit:
            electrical_limit_value = self.get_limit_dec(controller, axis, limit)
            configured_parameters.axes[axis].protection.faultmask.value = electrical_limit_value
        
        if home_setup:
            configured_parameters.axes[axis].homing.hometype.value = home_setup
            
        if home_speed:
            configured_parameters.axes[axis].homing.homespeed.value = home_speed

        # Apply the updated configuration for the axis
        controller.configuration.parameters.set_configuration(configured_parameters)
        
        # Reset individual controller
        controller.reset()

    def check_for_faults(self, controller, axes):
        """
        Retrieve the axis fault status for specified axes.

        Args:
            controller: The controller object to check
            axes: List of axes to check for faults

        Returns:
            dict: A dictionary with the axis name as the key and the axis fault status as the value.
        """
        faults = {}  # Initialize an empty dictionary to store results per axis
        
        # Loop through each specified axis
        for axis in axes:
            # Create a status item configuration to retrieve the axis fault status
            status_item_configuration = a1.StatusItemConfiguration()
            status_item_configuration.axis.add(a1.AxisStatusItem.AxisFault, axis)
            
            # Retrieve the axis fault status for the current axis
            results = controller.runtime.status.get_status_items(status_item_configuration)
            
            # Extract the axis fault status as an integer
            axis_faults = int(results.axis.get(a1.AxisStatusItem.AxisFault, axis).value)
            
            # Store the axis fault status in the faults dictionary
            faults[axis] = axis_faults
        
        return faults

    def handle_faults(self, test, faults_per_axis, reenable_run_button):
        """Handle faults for specific axes."""
        # Get the controller for the affected axis
        affected_axis = list(faults_per_axis.keys())[0]  # Get the first (and only) axis
        controller = self.station_controllers[affected_axis]
        
        fault_init = decode_faults(faults_per_axis, [affected_axis], controller, self.fault_log)
        decoded_faults = fault_init.get_fault()
        
        # Create a copy of the connected_axes list to safely remove unused axes
        updated_connected_axes = list(self.test_axes)
        
        for axis, faults in decoded_faults.items():
            station_id = self.axis_to_station_map.get(axis)
            if test == 'hardstop and limit check':
                if faults:
                    # Exclude 'CwEndOfTravelLimitFault' and 'CcwEndOfTravelLimitFault' during limit checks
                    filtered_faults = [fault for fault in faults if fault not in ['CwEndOfTravelLimitFault', 'CcwEndOfTravelLimitFault']]
                    
                    if filtered_faults:  # If there are any faults other than the excluded ones
                        for fault in filtered_faults:
                            if fault in ['CwSoftwareLimitFault', 'CcwSoftwareLimitFault']:
                                confirm = messagebox.askyesno(
                                    'An Axis Fault Occurred',
                                    f'Axis {axis} has the following faults: {filtered_faults}. Would you like to turn off software limits?'
                                )
                                if confirm:
                                    self.station_print('Turning off software limits and resuming test.', station_id=station_id)
                                    controller = self.station_controllers[axis]
                                    self.params(controller, axis, limit='software off')
                                    self.reset_controllers()
                                    self.home_stages()
                                    self.check_hardstop()
                                else:
                                    self.release_axis(axis)
                                    if axis in updated_connected_axes:
                                        updated_connected_axes.remove(axis)
                                    
                                    # Check if any axes remain
                                    if not self.test_axes:
                                        raise TestSequenceAbort("All axes have failed checks. Ending test.")
                            else:
                                confirm = messagebox.askyesno(
                                    'An Axis Fault Occurred',
                                    f'Axis {axis} has the following faults: {filtered_faults}. Would you like to remove these axes and continue?'
                                )
                                self.station_print(f'Axis {axis} has the following faults: {filtered_faults}', station_id=station_id)
                                
                                if confirm:
                                    # Remove the axis and continue
                                    self.release_axis(axis)
                                    if axis in updated_connected_axes:
                                        updated_connected_axes.remove(axis)
                                else:
                                    # Stop testing this axis and release it
                                    self.station_print(f'Axis {axis} requires attention for the following faults: {faults}.', station_id=station_id)
                                    self.release_axis(axis)
                                    if axis in updated_connected_axes:
                                        updated_connected_axes.remove(axis)
                                    
                                    # Check if any axes remain
                                    if not self.test_axes:
                                        raise TestSequenceAbort("All axes have failed checks. Ending test.")
            else:
                if faults:
                    for fault in faults:
                        if fault in ['CwSoftwareLimitFault', 'CcwSoftwareLimitFault']:
                            confirm = messagebox.askyesno(
                                'An Axis Fault Occurred',
                                f'Axis {axis} has the following fault: {fault}. Would you like to turn off software limits?'
                            )
                            if confirm:
                                self.station_print('Turning off software limits and resuming test.', station_id=station_id)
                                controller = self.station_controllers[axis]
                                self.params(controller, axis, limit='software off')
                                self.reset_controllers()
                                self.home_stages()
                                self.check_hardstop()
                            else:
                                self.release_axis(axis)
                                if axis in updated_connected_axes:
                                    updated_connected_axes.remove(axis)
                                
                                # Check if any axes remain
                                if not self.test_axes:
                                    raise TestSequenceAbort("All axes have failed checks. Ending test.")
                    
                    confirm = messagebox.askyesno(
                        'An Axis Fault Occurred',
                        f'Axis {axis} has the following faults: {faults}. Would you like to remove these axes and continue?'
                    )
                    self.station_print(f'Axis {axis} has the following faults: {faults}', station_id=station_id)
                
                    if confirm:
                        # Remove the axis and continue
                        self.release_axis(axis)
                        if axis in updated_connected_axes:
                            updated_connected_axes.remove(axis)
                    else:
                        # Stop testing this axis and release it
                        self.station_print(f'Axis {axis} requires attention for the following faults: {faults}.', station_id=station_id)
                        self.release_axis(axis)
                        if axis in updated_connected_axes:
                            updated_connected_axes.remove(axis)
                        
                        # Check if any axes remain
                        if not self.test_axes:
                            raise TestSequenceAbort("All axes have failed checks. Ending test.")
                    
        # Update the connected_axes with the updated list
        self.test_axes = updated_connected_axes
        if not self.test_axes:
            raise TestSequenceAbort("Please address faults on affected axes. Ending test.")
        
        # Update the commands for the remaining axes
        try:
            nominal_travel = abs(self.get_spec_value('Travel'))
            self.list_commands_ccw_pos = []
            self.list_commands_cw_pos = []
            self.list_commands_zero = []
            self.list_velocity = []
            self.list_low_velocity = []
            for axis in self.test_axes:
                self.list_commands_ccw_pos.append(nominal_travel / 2 * -1)
                self.list_commands_cw_pos.append(nominal_travel / 2)
                self.list_commands_zero.append(0)
                self.list_velocity.append(self.speed)
                self.list_low_velocity.append(0.5)
        except ValueError as e:
            station_id = [self.axis_to_station_map[axis] for axis in self.test_axes]
            self.station_print(f"Error updating commands: {e}", station_id=station_id)
            return
            
    def enable_stages(self):
        """Enable all stages in parallel and handle any faults."""
        station_id = [self.axis_to_station_map[axis] for axis in self.test_axes]
        self.station_print('Enabling Axes', station_id=station_id)
        
        # Create a copy of the connected_axes list to safely remove unused axes
        updated_connected_axes = list(self.test_axes)

        # Enable all axes in parallel
        threads = []
        failures = {}
        failures_lock = threading.Lock()
        
        def enable_single_axis(axis):
            try:
                # Check if this station was aborted
                station_id = self.axis_to_station_map.get(axis)
                if station_id in self.aborted_stations:
                    raise TestSequenceAbort(f"Test aborted for station {station_id}", shown_message=True)

                controller = self.station_controllers[axis]
                controller.runtime.commands.motion.enable([axis])
                time.sleep(0.5)
                
                # Check for abort again after first enable
                if station_id in self.aborted_stations:
                    raise TestSequenceAbort(f"Test aborted for station {station_id}", shown_message=True)
                    
                controller.runtime.commands.fault_and_error.acknowledgeall(1)
                controller.runtime.commands.motion.enable([axis])
                
            except TestSequenceAbort:
                # Clean up this axis and re-raise
                try:
                    controller = self.station_controllers[axis]
                    controller.runtime.commands.motion.abort([axis])
                    controller.runtime.commands.motion.disable([axis])
                    if axis in self.test_axes:
                        self.test_axes.remove(axis)
                    if axis in self.station_controllers:
                        del self.station_controllers[axis]
                except:
                    pass
                raise
                
            except (ControllerAxisFaultException, ControllerOperationException):
                # Handle the axis fault exception
                time.sleep(3)
                
                # Check for abort before handling faults
                station_id = self.axis_to_station_map.get(axis)
                if station_id in self.aborted_stations:
                    raise TestSequenceAbort(f"Test aborted for station {station_id}", shown_message=True)
                
                controller = self.station_controllers[axis]
                faults_per_axis = self.check_for_faults(controller, [axis])
                # Decode and capture details for later display/abort
                try:
                    fault_init = decode_faults(faults_per_axis, [axis], controller, self.fault_log)
                    decoded = fault_init.get_fault()
                except Exception:
                    decoded = {axis: []}
                
                with failures_lock:
                    failures[axis] = decoded.get(axis, [])
                
        try:
            # Start enable threads
            for axis in self.test_axes:
                thread = self.create_tracked_thread(target=enable_single_axis, axis=axis, args=(axis,))
                threads.append(thread)
                thread.start()
            
            # Wait for all enables to complete
            for thread in threads:
                thread.join()
                
            # If any axis failed to enable, show details and abort the sequence
            if failures:
                # Release failed axes immediately
                for ax in list(failures.keys()):
                    self.release_axis(ax)
                lines = []
                for ax, flist in failures.items():
                    desc = ", ".join(flist) if flist else "Unknown fault(s)"
                    lines.append(f"{ax}: {desc}")
                messagebox.showwarning(
                    "Axis Fault During Enable",
                    "The following axes failed to enable and were removed from testing:\n" + "\n".join(lines)
                )
                # Continue with remaining axes; if none remain, we'll abort below
                
            # Check if we still have axes to test
            if not self.test_axes:
                raise TestSequenceAbort("All axes have been aborted", shown_message=True)
                
        except TestSequenceAbort as e:
            # Clean up any remaining axes
            for axis in list(self.test_axes):
                try:
                    controller = self.station_controllers[axis]
                    controller.runtime.commands.motion.abort([axis])
                    controller.runtime.commands.motion.disable([axis])
                except:
                    pass
            raise  # Re-raise to stop the test sequence

    def rotate_to_match_start(self, observed, encoder_positions):
        """
        Rotate the observed hall states and their encoder positions to start with '100'.
        
        Parameters:
            observed (list): The list of hall states to be rotated
            encoder_positions (list): The corresponding encoder positions
            
        Returns:
            tuple: (rotated hall states, rotated encoder positions)
        """
        if '100' not in observed:
            return observed, encoder_positions
            
        # Find index of '100'
        start_idx = observed.index('100')
        
        # Rotate both lists together
        rotated_states = observed[start_idx:] + observed[:start_idx]
        rotated_positions = encoder_positions[start_idx:] + encoder_positions[:start_idx]
        
        return rotated_states, rotated_positions

    def get_motor_configuration(self, axis):
        """Get motor type and pole pitch from controller runtime parameters"""
        # Motor type mapping
        motor_type_map = {
            0: "ACBrushlessLinear",
            1: "ACBrushlessRotary", 
            2: "DCBrush",
            3: "StepperMotor"
        }
        
        try:
            controller = self.station_controllers[axis]
            
            motor_type_value = controller.runtime.parameters.axes[axis].motor.motortype.value
            pole_pitch = controller.runtime.parameters.axes[axis].motor.motorpolepitch.value
            
            # Convert numeric value to integer and get description
            motor_type_int = int(motor_type_value)
            motor_type = motor_type_map.get(motor_type_int, f"Unknown motor type ({motor_type_int})")
        
            return motor_type, pole_pitch
        except Exception as e:
            station_id = self.axis_to_station_map[axis]
            self.station_print(f"Could not read motor configuration for axis {axis}: {e}", 
                              station_id=station_id)
            return None, None

    def calculate_required_hall_travel(self, axis):
        """Calculate minimum travel required for MSET hall checking based on motor type"""
        motor_type, pole_pitch = self.get_motor_configuration(axis)
        
        if motor_type is None or pole_pitch is None:
            return float('inf')  # Force fallback if can't determine requirements
        
        electrical_degrees_tested = 300.0  # MSET sequence: 0° to 300° in 60° steps
        safety_margin_percent = 0.1  # 10% safety margin
        
        if motor_type == "ACBrushlessLinear":
            # Pole pitch = mm per pole (180° electrical)
            # Full electrical cycle = 2 × pole_pitch mm
            full_electrical_cycle = 2.0 * pole_pitch  # mm
            required_travel = (electrical_degrees_tested / 360.0) * full_electrical_cycle
            
        elif motor_type == "ACBrushlessRotary":
            controller = self.station_controllers[axis]
            units = controller.runtime.parameters.axes[axis].units.unitsname.value
            if units == 'deg':
                # Pole pitch = number of poles total
                # pole_pairs = pole_pitch / 2
                # 360° mechanical = pole_pairs electrical cycles
                # 1 electrical cycle = 360° / pole_pairs mechanical
                pole_pairs = pole_pitch / 2.0
                degrees_per_electrical_cycle = 360.0 / pole_pairs
                required_travel = (electrical_degrees_tested / 360.0) * degrees_per_electrical_cycle
            else:
                required_travel = 5
            
        else:
            station_id = self.axis_to_station_map[axis]
            self.station_print(f"Unsupported motor type '{motor_type}' for axis {axis}", 
                              station_id=station_id)
            return float('inf')  # Force fallback for unsupported motor types
        
        return required_travel * (1.0 + safety_margin_percent)

    def has_sufficient_travel_for_halls(self, axis):
        """Check if stage has enough travel for MSET hall checking"""
        try:
            required_travel = self.calculate_required_hall_travel(axis)
            available_travel = abs(self.get_spec_value('Travel'))
            
            return available_travel >= required_travel, required_travel, available_travel
        except Exception as e:
            station_id = self.axis_to_station_map[axis]
            self.station_print(f"Could not determine travel requirements for axis {axis}: {e}", 
                              station_id=station_id)
            return False, 0, 0

    def is_travel_related_fault(self, faults):
        """Determine if faults are related to insufficient travel"""
        travel_related_faults = [
            'CwSoftwareLimitFault', 
            'CcwSoftwareLimitFault',
            'CwHardwareLimitFault',
            'CcwHardwareLimitFault',
            # Add other travel-related fault codes as identified
        ]
        
        return any(fault in travel_related_faults for fault in faults)

    def check_halls_fallback(self, axis):
        """Fallback hall checking method for stages with limited travel - Enhanced debugging version"""
        try:
            controller = self.station_controllers[axis]
            station_id = self.axis_to_station_map.get(axis)
            
            # Step 1: Check parameter access
            try:
                nominal_travel = self.param_dict.get('NominalTravel')
                if nominal_travel is None:
                    return False
                nominal_travel = abs(float(nominal_travel))
            except Exception as e:
                return False
            
            # Step 2: Check and adjust home speed
            try:
                home_speed = controller.runtime.parameters.axes[axis].homing.homespeed.value
                if home_speed >= 10:    
                    controller.runtime.parameters.axes[axis].homing.homespeed.value = 5
            except Exception as e:
                return False
                
            # Step 3: Data collection setup
            try:
                test_time = nominal_travel / 1  # Speed = 1 mm/s
                n = int(self.sample_rate * test_time)
                freq = a1.DataCollectionFrequency.Frequency1kHz
            except Exception as e:
                return False
                
            # Step 4: Move to CCW limit
            try:
                controller.runtime.commands.execute(f'MoveToLimitCcw({axis})', 1)
                controller.runtime.commands.motion.waitformotiondone([axis], 1)
                time.sleep(1)
            except Exception as e:
                return False
            
            # Step 5: Restore home speed
            try:
                controller.runtime.parameters.axes[axis].homing.homespeed.value = home_speed
            except Exception as e:
                self.station_print(f"WARNING: Failed to restore home speed for axis {axis}: {str(e)}", station_id=station_id)
                # Don't return False for this - continue with test
            
            # Step 6: Configure data collection
            try:
                with _thread_lock:
                    data_config = self.data_config(n, freq, axis)
            except Exception as e:
                return False
            
            # Step 7: Start data collection and move
            try:
                controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, data_config)
                time.sleep(0.1)
                
                controller.runtime.commands.motion.moveincremental([axis], [nominal_travel], [1])
                controller.runtime.commands.motion.waitformotiondone([axis], 1)
                time.sleep(5)  # Allow settling time
                
                controller.runtime.data_collection.stop()
            except Exception as e:
                try:
                    controller.runtime.data_collection.stop()
                except:
                    pass
                return False
            
            # Step 8: Get results and populate data
            try:
                axis_results = controller.runtime.data_collection.get_results(data_config, n)
                
                self.populate(axis, axis_results)
            except Exception as e:
                return False
            
            # Step 9: Validate encoder direction
            try:
                if axis not in self.hall_encoder_positions or not self.hall_encoder_positions[axis]:
                    return False
                
                encoder_data = self.hall_encoder_positions[axis]
                start_pos = encoder_data[0] if isinstance(encoder_data, list) else list(encoder_data.values())[0]
                end_pos = encoder_data[-1] if isinstance(encoder_data, list) else list(encoder_data.values())[-1]
                encoder_direction = "positive" if end_pos > start_pos else "negative"
                
                if encoder_direction != "positive":
                    self.station_print(f"FAIL: Encoder direction incorrect on axis {axis} during fallback test. Please check encoder wiring.", station_id=station_id)
                    return False
            except Exception as e:
                return False
            
            # Step 10: Extract and validate hall states
            try:
                if axis not in self.hall_states or not self.hall_states[axis]:
                    self.station_print(f"ERROR: No hall state data collected for axis {axis}", station_id=station_id)
                    return False
                
                hall_transitions = []
                prev_state = None
                
                hall_data = self.hall_states[axis]
                
                for timestamp, state in hall_data.items():
                    if state != prev_state and state != "000" and state != "111":  # Valid states only
                        hall_transitions.append(state)
                        prev_state = state
                
                # Check that we have at least some hall state changes
                if len(hall_transitions) < 2:
                    self.station_print(f"FAIL: Insufficient hall state transitions for axis {axis} (only {len(hall_transitions)} transitions)", station_id=station_id)
                    return False
            except Exception as e:
                return False
            
            # Step 11: Validate hall state progression
            try:
                expected_order_cw = ["001", "011", "010", "110", "100", "101"]
                invalid_transitions = 0
                
                for i in range(len(hall_transitions) - 1):
                    current_state = hall_transitions[i]
                    next_state = hall_transitions[i + 1]
                    
                    if current_state in expected_order_cw and next_state in expected_order_cw:
                        current_idx = expected_order_cw.index(current_state)
                        next_idx = expected_order_cw.index(next_state)
                        
                        # Calculate forward progression (allowing wrap-around)
                        forward_steps = (next_idx - current_idx) % 6
                        
                        # Allow 1-3 steps forward, or staying in same state briefly
                        if forward_steps not in [0, 1, 2, 3]:  # 0=same, 1-3=forward progression
                            invalid_transitions += 1
                
                # Allow some noise but require majority of transitions to be valid
                error_tolerance = 0.3  # Allow 30% invalid transitions
                success = invalid_transitions <= len(hall_transitions) * error_tolerance
                
                if not success:
                    return False
                
                return True
                
            except Exception as e:
                self.station_print(f"ERROR: Hall state progression validation failed for axis {axis}: {str(e)}", station_id=station_id)
                return False
            
        except TestSequenceAbort:
            raise
        except Exception as e:
            station_id = self.axis_to_station_map.get(axis)
            error_msg = f"Unexpected error in fallback hall check for axis {axis}: {str(e)}"
            self.station_print(f"ERROR: {error_msg}", station_id=station_id)
            self.fault_log.error(error_msg)
            return False

    def collect_hall_data_fallback(self, axis):
        """Thread function for fallback hall data collection"""
        try:
            station_id = self.axis_to_station_map.get(axis)
            
            if not self.check_halls_fallback(axis):
                # Fallback failed - remove axis from testing
                self.station_print(f"Fallback hall check failed for axis {axis}", station_id=station_id)
                messagebox.showerror("Hall Check Failed", f"Both MSET and fallback methods failed for axis {axis}")
                
                self.secondary_ui.update_station_status(station_id, running=False, serial="")
                if axis in self.test_axes:
                    self.test_axes.remove(axis)
                if axis in self.station_controllers:
                    del self.station_controllers[axis]
                return
            
            # If we get here, fallback succeeded - process results and populate data
            # Build observed states and encoder values in the expected angle order
            angles = [0, 60, 120, 180, 240, 300]
            observed_states = []
            encoder_values = []
            if axis in self.hall_states:
                for ang in angles:
                    if ang in self.hall_states[axis]:
                        observed_states.append(self.hall_states[axis][ang])
                        if axis in self.hall_encoder_positions and ang in self.hall_encoder_positions[axis]:
                            encoder_values.append(self.hall_encoder_positions[axis][ang])
            
            encoder_direction = "unknown"
            if len(encoder_values) >= 2:
                encoder_direction = "positive" if encoder_values[-1] > encoder_values[0] else "negative"
            expected_states = []
            for i in range(len(observed_states)):
                expected_states.append(self.hall_dict[angles[i]])
            hall_order_valid = (encoder_direction == "positive" and observed_states == expected_states)
            unique_hall_states = []
            for s in observed_states:
                if not unique_hall_states or unique_hall_states[-1] != s:
                    unique_hall_states.append(s)
            
            self.process_hall_results(axis, station_id, observed_states, encoder_values, hall_order_valid, encoder_direction, unique_hall_states)
            
        except TestSequenceAbort:
            raise
        except Exception as e:
            station_id = self.axis_to_station_map.get(axis)
            self.station_print(f"Error during fallback hall check for axis {axis}: {str(e)}", station_id=station_id)
            messagebox.showerror("Hall Check Error", f"Error during fallback hall check for axis {axis}: {str(e)}")
            
            self.secondary_ui.update_station_status(station_id, running=False, serial="")
            if axis in self.test_axes:
                self.test_axes.remove(axis)
            if axis in self.station_controllers:
                del self.station_controllers[axis]

    def check_halls(self, retry=False):
        """Check hall sensor sequence for each axis in parallel."""
        station_id = [self.axis_to_station_map[axis] for axis in self.test_axes]
        self.station_print('Checking Halls', station_id=station_id)

        test_time = 22
        n = int(self.sample_rate * test_time)
        freq = a1.DataCollectionFrequency.Frequency1kHz
        
        # Pre-analyze travel requirements for each axis
        method_per_axis = {}

        for axis in list(self.test_axes):  # Create copy for safe iteration
            has_travel, required, available = self.has_sufficient_travel_for_halls(axis)
            station_id = self.axis_to_station_map[axis]
            
            if has_travel:
                method_per_axis[axis] = 'MSET'
                self.station_print(f"Using MSET method for axis {axis} (Available: {available:.3f}, Required: {required:.3f})", 
                                 station_id=station_id)
            else:
                method_per_axis[axis] = 'FALLBACK'
                self.station_print(f"Using fallback method for axis {axis} - insufficient travel (Available: {available:.3f}, Required: {required:.3f})", 
                                 station_id=station_id)
        
        nominal_travel = abs(self.get_spec_value('Travel'))
        centeroftravel = nominal_travel/2
        # Move to CCW limit in parallel
        threads = []
        def move_to_start(axis):
            try:
                controller = self.station_controllers[axis]
                
                # Check that home speed isn't too fast for Ccw and Cw commands
                home_speed = controller.runtime.parameters.axes[axis].homing.homespeed.value
                if home_speed >= 10:    
                    controller.runtime.parameters.axes[axis].homing.homespeed.value = 5
                    
                # Move into limit
                controller.runtime.commands.execute(f'MoveToLimitCcw({axis})', 1)
                controller.runtime.commands.motion.waitformotiondone([axis], 1)
                time.sleep(2)

                controller.runtime.commands.motion.moveincremental([axis], [centeroftravel], [5])
                controller.runtime.commands.motion.waitformotiondone([axis], 1)
                time.sleep(2)
                
                # Return to original home speed
                controller.runtime.parameters.axes[axis].homing.homespeed.value = home_speed
                
            except TestSequenceAbort:
                return
            except (ControllerAxisFaultException, ControllerOperationException):
                station_id = self.axis_to_station_map.get(axis)
                error_message = f"Axis fault occurred during initial positioning for axis {axis}."
                faults_per_axis = self.check_for_faults(controller, [axis])
                fault_init = decode_faults(faults_per_axis, [axis], controller, self.fault_log)
                decoded_faults = fault_init.get_fault()
                self.fault_log.info(f'A fault occurred on {axis} during initial positioning: {decoded_faults}')
                
                self.station_print(f"Fault during initial positioning on axis {axis}: {decoded_faults}", station_id=station_id)
                messagebox.showerror("Axis Fault", f"{error_message}\nFault: {decoded_faults}")
                
                # Release this axis/station
                self.release_axis(axis)
                return
        
        for axis in self.test_axes:
            thread = self.create_tracked_thread(target=move_to_start, axis=axis, args=(axis,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()

        # Collect hall data in parallel
        threads = []
        
        def collect_hall_data(axis):
            try:
                controller = self.station_controllers[axis]
                station_id = self.axis_to_station_map.get(axis)
                test_station_id = station_id

                angle = 0
                current_threshold = controller.runtime.parameters.axes[axis].protection.averagecurrentthreshold.value
                current = current_threshold / 2

                with _thread_lock:
                    # Configure data collection
                    data_config = self.data_config(n, freq, axis)
                    
                # Start data collection and move
                controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, data_config)
                time.sleep(0.1)
                
                try:
                    while angle < 350:
                        controller.runtime.commands.servo_loop_tuning.tuningsetmotorangle(axis, current, angle)
                        angle += 60
                        time.sleep(3)
                except (ControllerAxisFaultException, ControllerOperationException):
                    error_message = "Axis fault occurred during MSET commands."
                    faults_per_axis = self.check_for_faults(controller, [axis])
                    fault_init = decode_faults(faults_per_axis, [axis], controller, self.fault_log)
                    decoded_faults = fault_init.get_fault()
                    self.fault_log.info(f'A fault occurred on {axis}: {decoded_faults}')
                    
                    # Only attempt fallback if fault appears to be travel-related AND we haven't already tried fallback
                    if method_per_axis[axis] == 'MSET' and self.is_travel_related_fault(decoded_faults):
                        self.station_print(f"Travel-related fault detected on axis {axis}, attempting fallback method", 
                                          station_id=station_id)
                        
                        # Clear faults and try fallback
                        controller.runtime.commands.fault_and_error.acknowledgeall(1)
                        controller.runtime.commands.motion.enable([axis])
                        controller.runtime.data_collection.stop()
                        
                        if self.check_halls_fallback(axis):
                            # Fallback succeeded, continue with normal validation
                            return
                    
                    # If not travel-related, already using fallback, or fallback failed - handle as error
                    messagebox.showerror("Axis Fault", error_message)
                    controller.runtime.data_collection.stop()
                    # Release this axis/station
                    self.release_axis(axis)
                    return
                
                time.sleep(10)
                
                controller.runtime.data_collection.stop()
                controller.runtime.commands.motion.abort([axis])
                controller.runtime.commands.motion.enable([axis])
                # Get results and populate instance variables
                axis_results = controller.runtime.data_collection.get_results(data_config, n)
                
                self.populate(axis, axis_results)
                
                # Build observed states and encoder values in the expected angle order
                angles = [0, 60, 120, 180, 240, 300]
                observed_states = []
                encoder_values = []
                for ang in angles:
                    if axis in self.hall_states and ang in self.hall_states[axis]:
                        observed_states.append(self.hall_states[axis][ang])
                        if axis in self.hall_encoder_positions and ang in self.hall_encoder_positions[axis]:
                            encoder_values.append(self.hall_encoder_positions[axis][ang])
                
                # Compute encoder direction using first/last available values
                encoder_direction = "unknown"
                if len(encoder_values) >= 2:
                    encoder_direction = "positive" if encoder_values[-1] > encoder_values[0] else "negative"
                
                # Determine expected order for the angles we actually observed
                expected_states = []
                for i in range(len(observed_states)):
                    expected_states.append(self.hall_dict[angles[i]])
                hall_order_valid = (encoder_direction == "positive" and observed_states == expected_states)
                
                # Unique hall states in observation order (for logging)
                unique_hall_states = []
                for s in observed_states:
                    if not unique_hall_states or unique_hall_states[-1] != s:
                        unique_hall_states.append(s)
                
                # Centralized processing and data population
                self.process_hall_results(axis, station_id, observed_states, encoder_values, hall_order_valid, encoder_direction, unique_hall_states)
            except TestSequenceAbort:
                raise

        # Start threads for each method type
        for axis in self.test_axes:
            if method_per_axis[axis] == 'MSET':
                thread = self.create_tracked_thread(target=collect_hall_data, axis=axis, args=(axis,))
                threads.append(thread)
                thread.start()
            else:
                thread = self.create_tracked_thread(target=self.collect_hall_data_fallback, axis=axis, args=(axis,))
                threads.append(thread)
                thread.start()
        
        # Wait for all data collection to complete
        for thread in threads:
            thread.join()

    def absolute_hardstop(self):
        """Check hardstop travels for all axes and calculate absolute home offset."""
        station_id = [self.axis_to_station_map[axis] for axis in self.test_axes]
        self.station_print('Checking Hardstop Travels', station_id=station_id)
        self.abs_ccw_positions = {}
        self.abs_cw_positions = {}
        test = 'absolute hardstop check'

        def attempt_operation(axis, operation):
            """Helper function to handle and retry failed operations."""
            controller = self.station_controllers[axis]
            retries = 0
            retry_limit = 10
            while retries < retry_limit:
                try:
                    operation()
                    break
                except (ControllerAxisFaultException, ControllerOperationException):
                    retries += 1
                    faults_per_axis = self.check_for_faults(controller, [axis])
                    if faults_per_axis:
                        controller.runtime.commands.fault_and_error.acknowledgeall(1)
                        controller.runtime.commands.motion.enable([axis])
                    time.sleep(2)
                if retries == retry_limit:
                    station_id = self.axis_to_station_map.get(axis)
                    self.station_print(f'Exceeded retry limit with axis: {axis}. Exiting operation.', 
                                     station_id=station_id)
                    break

        # Set current clamp for each axis
        for axis in self.test_axes:
            controller = self.station_controllers[axis]
            controller.runtime.parameters.axes[axis][a1.AxisParameterId.MaxCurrentClamp].value = self.low_current_clamp

        # Move to CCW hardstop
        for axis in self.test_axes:
            controller = self.station_controllers[axis]
            attempt_operation(axis, lambda: controller.runtime.commands.motion.movefreerun([axis], [-0.5]))
            try:
                controller.runtime.commands.motion.waitformotiondone([axis])
            except ControllerAxisFaultException:
                faults_per_axis = self.check_for_faults(controller, [axis])
                if faults_per_axis:
                    controller.runtime.commands.fault_and_error.acknowledgeall(1)
                    controller.runtime.commands.motion.enable([axis])

            # Get CCW position
            status_config = a1.StatusItemConfiguration()
            status_config.axis.add(a1.AxisStatusItem.PositionFeedback, axis)
            results = controller.runtime.status.get_status_items(status_config)
            ccw_pos_fbk = results.axis.get(a1.AxisStatusItem.PositionFeedback, axis).value
            
            self.stage_info.info(f'Ccw Hardstop position for {axis} is {ccw_pos_fbk}')
            self.data[axis]["Absolute value at CCW EOT"] = ccw_pos_fbk
            self.abs_ccw_positions[axis] = ccw_pos_fbk

        # Move to CW hardstop
        for axis in self.test_axes:
            controller = self.station_controllers[axis]
            attempt_operation(axis, lambda: controller.runtime.commands.motion.movefreerun([axis], [0.5]))
            try:
                controller.runtime.commands.motion.waitformotiondone([axis])
            except ControllerAxisFaultException:
                faults_per_axis = self.check_for_faults(controller, [axis])
                if faults_per_axis:
                    controller.runtime.commands.fault_and_error.acknowledgeall(1)
                    controller.runtime.commands.motion.enable([axis])

            # Get CW position
            status_config = a1.StatusItemConfiguration()
            status_config.axis.add(a1.AxisStatusItem.PositionFeedback, axis)
            results = controller.runtime.status.get_status_items(status_config)
            cw_pos_fbk = results.axis.get(a1.AxisStatusItem.PositionFeedback, axis).value
            
            self.stage_info.info(f'Cw Hardstop position for {axis} is {cw_pos_fbk}')
            self.abs_cw_positions[axis] = cw_pos_fbk

        # Calculate and log travels
        for axis in self.test_axes:
            travel = abs(self.abs_ccw_positions[axis] - self.abs_cw_positions[axis])
            self.stage_info.info(f'Total travel for {axis} is {travel}')

    def calculate_home_offset(self):
        """Calculate and set home offsets for each axis."""
        station_id = [self.axis_to_station_map[axis] for axis in self.test_axes]
        self.station_print('Calculating Offset', station_id=station_id)
        self.midpoints = {}
        
        if self.absolute:
            for axis in self.test_axes:
                controller = self.station_controllers[axis]
                ccw_pos = self.abs_ccw_positions[axis]
                cw_pos = self.abs_cw_positions[axis]

                # Calculate the midpoint
                midpoint = (ccw_pos + cw_pos) / 2
                cpu = controller.runtime.parameters.axes[axis].units.countsperunit.value

                if cw_pos > ccw_pos:
                    midpoint = (midpoint * cpu) * -1
                else:
                    midpoint = midpoint * cpu
                
                self.midpoints[axis] = midpoint
                self.stage_info.info(f'The absolute feedback offset for {axis} is {midpoint}')
                self.data[axis]["Absolute Position Offset"] = midpoint

                # Configure the axis
                configured_parameters = controller.configuration.parameters.get_configuration()
                configured_parameters.axes[axis].feedback.auxiliaryabsolutefeedbackoffset.value = midpoint
                configured_parameters.axes[axis].protection.maxcurrentclamp.value = self.max_current_clamp
                controller.configuration.parameters.set_configuration(configured_parameters)
        else:
            for axis in self.test_axes:
                if axis not in self.limit_pos:
                    continue
                
                limits = self.limit_pos[axis]
                controller = self.station_controllers[axis]
                cw_pos = limits.get('Cw', 0)
                ccw_pos = limits.get('Ccw', 0)
                midpoint = (ccw_pos + cw_pos) / 2
                self.midpoints[axis] = midpoint
                self.data[axis]["Home Offset"] = round(midpoint, 4)

                configured_parameters = controller.configuration.parameters.get_configuration()
                configured_parameters.axes[axis].homing.homeoffset.value = midpoint
                controller.configuration.parameters.set_configuration(configured_parameters)
    
    def software_limits(self):
        """
        Set software limits for connected axes based on hexapod type and configure parameters.
        """
        station_id = [self.axis_to_station_map[axis] for axis in self.test_axes]
        self.station_print('Setting Software Limits', station_id=station_id)
        
        # Set software limits for each axis using its own controller
        for axis in self.test_axes:
            controller = self.station_controllers[axis]
            station_id = self.axis_to_station_map.get(axis)
            
            try:
                # Retrieve current configuration parameters
                configured_parameters = controller.configuration.parameters.get_configuration()
                configured_parameters.axes[axis].protection.softwarelimithigh.value = (abs(self.get_spec_value('Travel')) / 2) + 0.1
                configured_parameters.axes[axis].protection.softwarelimitlow.value = ((abs(self.get_spec_value('Travel')) / 2) + 0.1) * -1

                # Apply the new configuration
                controller.configuration.parameters.set_configuration(configured_parameters)
                
                self.params(controller, axis, home_offset=self.midpoints[axis], current_clamp=self.max_current_clamp, limit=['electrical on', 'software on'])
            except Exception as e:
                self.station_print(f"Error setting software limits for axis {axis}: {str(e)}", station_id=station_id)

        #self.reset_controllers()
        time.sleep(5)
        self.enable()
        self.home_stages()

    def home_stages(self, initial=False):
        """
        Home all stages in parallel based on encoder type.
        Handles homing or absolute positioning for each axis independently.
        """
        station_id = [self.axis_to_station_map[axis] for axis in self.test_axes]
        self.station_print('Homing Axes', station_id=station_id)
        test = 'homing'
        
        if initial:
            print("Changing home type")
            for axis in self.test_axes:
                controller = self.station_controllers[axis]
                stage_units = controller.runtime.parameters.axes[axis].units.unitsname.value
        
                home_speed = controller.runtime.parameters.axes[axis].homing.homespeed.value
                if home_speed >= 10:    
                    home_speed = 10
            
                if stage_units != 'deg':
                    print(f'Changing home type for {axis}')
                    self.params(controller, axis, home_setup=1, home_speed=home_speed) 
                else:
                    self.params(controller, axis, home_setup=2, home_speed=home_speed)
            print("Changing home speed")
        
            for axis in self.test_axes:
                controller = self.station_controllers[axis]
                print(f'Home type for {axis} changed to {controller.runtime.parameters.axes[axis].homing.hometype.value}')
            time.sleep(5)

        threads = []
        
        def home_single_axis(axis):
            """Handle homing/positioning for a single axis."""
            controller = self.station_controllers[axis]
            station_id = self.axis_to_station_map.get(axis)
            
            def attempt_operation(operation):
                """Attempt an operation with fault handling for this axis."""
                while True:
                    try:
                        # Check if this station was aborted
                        if station_id in self.aborted_stations:
                            raise TestSequenceAbort(f"Test aborted for station {station_id}", shown_message=True)
                        
                        operation()
                        break
                    except (ControllerAxisFaultException, ControllerOperationException):
                        time.sleep(3)
                        faults_per_axis = self.check_for_faults(controller, [axis])
                        if faults_per_axis:
                            self.handle_faults(test, {axis: faults_per_axis[axis]}, self.reenable_run_button)
                        time.sleep(2)
                    except TestSequenceAbort:
                        raise  # Re-raise TestSequenceAbort to stop the thread
            
            try:
                if not self.absolute:
                    # Enable then home for incremental axes
                    print("Enabling")
                    attempt_operation(lambda: controller.runtime.commands.motion.enable([axis]))
                    time.sleep(1)
                    print("Homing")
                    print(f'Home Type: {controller.runtime.parameters.axes[axis].homing.hometype.value}')
                    attempt_operation(lambda: controller.runtime.commands.motion.home([axis]))
                    time.sleep(1)
                    
                    # Check for faults after absolute move
                    faults_per_axis = self.check_for_faults(controller, [axis])
                    if faults_per_axis:
                        self.handle_faults(test, {axis: faults_per_axis[axis]}, self.reenable_run_button)
                        time.sleep(2)
                    # Update marker status
                    self.data[axis]["Marker"] = "Passed"
                    
                else:
                    # Move to absolute zero position
                    attempt_operation(lambda: controller.runtime.commands.motion.moveabsolute(
                        [axis], 
                        [self.list_commands_zero[self.test_axes.index(axis)]], 
                        [self.list_velocity[self.test_axes.index(axis)]]
                    ))
                    time.sleep(1)
                    
                    # Wait for motion to complete
                    attempt_operation(lambda: controller.runtime.commands.motion.waitformotiondone([axis]))
                    time.sleep(2)
                    
                    # Check for faults after absolute move
                    faults_per_axis = self.check_for_faults(controller, [axis])
                    if faults_per_axis:
                        self.handle_faults(test, {axis: faults_per_axis[axis]}, self.reenable_run_button)
            
            except TestSequenceAbort:
                # Clean up this axis and re-raise
                try:
                    controller.runtime.commands.motion.abort([axis])
                    controller.runtime.commands.motion.disable([axis])
                except:
                    pass
                raise
        
        # Start a thread for each axis
        for axis in self.test_axes:
            thread = self.create_tracked_thread(target=home_single_axis, axis=axis, args=(axis,))
            threads.append(thread)
            thread.start()
        
        try:
            # Wait for all axes to complete
            for thread in threads:
                thread.join()
                
            # Check if we still have axes to test
            if not self.test_axes:
                raise TestSequenceAbort("All axes have been aborted", shown_message=True)
                
        except TestSequenceAbort as e:
            # Clean up any remaining axes
            for axis in list(self.test_axes):
                try:
                    controller = self.station_controllers[axis]
                    controller.runtime.commands.motion.abort([axis])
                    controller.runtime.commands.motion.disable([axis])
                except:
                    pass
            raise  # Re-raise to stop the test sequence

    def check_hardstop(self):
        """Check hardstop travels for each axis in parallel."""
        self.hardstop_pos = {}
        self.limit_pos = {}
        station_id = [self.axis_to_station_map[axis] for axis in self.test_axes]
        self.station_print('Checking Limits and Hardstops', station_id=station_id)
        test = 'hardstop and limit check'

        def check_single_axis(axis, direction):
            """Handle hardstop check for a single axis."""
            controller = self.station_controllers[axis]
            station_id = self.axis_to_station_map.get(axis)
            limit = 'Cw' if direction == 'cw' else 'Ccw'
            
            try:
                # Check for abort before starting
                if station_id in self.aborted_stations:
                    raise TestSequenceAbort(f"Test aborted for station {station_id}", shown_message=True)
                
                # Check that home speed isn't too fast for Ccw and Cw commands
                home_speed = controller.runtime.parameters.axes[axis].homing.homespeed.value
                if home_speed >= 10:    
                    controller.runtime.parameters.axes[axis].homing.homespeed.value = 5
                    
                if limit == 'Cw':
                    controller.runtime.commands.execute(f'MoveToLimitCw({axis})', 1)
                else:
                    controller.runtime.commands.execute(f'MoveToLimitCcw({axis})', 1)
                time.sleep(2)
                
                controller.runtime.parameters.axes[axis].homing.homespeed.value = home_speed
                
                # Check for abort after move command
                if station_id in self.aborted_stations:
                    raise TestSequenceAbort(f"Test aborted for station {station_id}", shown_message=True)
                
                controller.runtime.commands.motion.waitformotiondone([axis])
                
            except (ControllerAxisFaultException, ControllerOperationException):
                faults_per_axis = self.check_for_faults(controller, [axis])
                if faults_per_axis:
                    self.handle_faults(test, {axis: faults_per_axis[axis]}, self.reenable_run_button)
                    time.sleep(2)
            except TestSequenceAbort:
                # Clean up and re-raise
                try:
                    controller.runtime.commands.motion.abort([axis])
                    controller.runtime.commands.motion.disable([axis])
                except:
                    pass
                raise
            
            time.sleep(3)
            
            # Check for abort before continuing
            if station_id in self.aborted_stations:
                raise TestSequenceAbort(f"Test aborted for station {station_id}", shown_message=True)
            
            # Move to limit and hardstop using this axis's controller
            self.move_into_limit(controller, test, limit, axis)
            faults_per_axis = self.check_for_faults(controller, [axis])
            if faults_per_axis:
                controller.runtime.commands.fault_and_error.acknowledgeall(1)

            time.sleep(3)

            # Check for abort before hardstop
            if station_id in self.aborted_stations:
                raise TestSequenceAbort(f"Test aborted for station {station_id}", shown_message=True)
            
            self.move_into_hardstop(controller, test, limit, axis)
            faults_per_axis = self.check_for_faults(controller, [axis])
            if faults_per_axis:
                controller.runtime.commands.fault_and_error.acknowledgeall(1)
            
            # Move out of hardstop using this axis's controller
            self.move_out_of_hardstop(controller, limit, axis)

        try:
            # Run CCW checks in parallel
            threads = []
            for axis in self.test_axes:
                thread = self.create_tracked_thread(target=check_single_axis, axis=axis, args=(axis, 'ccw'))
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
                
            # Check if we still have axes after CCW
            if not self.test_axes:
                raise TestSequenceAbort("All axes have been aborted", shown_message=True)
            
            time.sleep(5)

            # Run CW checks in parallel 
            threads = []
            for axis in self.test_axes:
                thread = self.create_tracked_thread(target=check_single_axis, axis=axis, args=(axis, 'cw'))
                threads.append(thread)
                thread.start()
            
            for thread in threads:
                thread.join()
                
            # Check if we still have axes after CW
            if not self.test_axes:
                raise TestSequenceAbort("All axes have been aborted", shown_message=True)
            
            time.sleep(5)

            # Calculate travels and update parameters
            self.calculate_limit_travel()
            time.sleep(2)
            
        except TestSequenceAbort as e:
            # Clean up any remaining axes
            for axis in list(self.test_axes):
                try:
                    controller = self.station_controllers[axis]
                    controller.runtime.commands.motion.abort([axis])
                    controller.runtime.commands.motion.disable([axis])
                except:
                    pass
            raise  # Re-raise to stop the test sequence

    def move_into_limit(self, controller, test, limit, axis):
        """Move a single axis to its limit position."""
        test_time = 2
        n = int(self.sample_rate * test_time)
        freq = a1.DataCollectionFrequency.Frequency1kHz
        
        with _thread_lock:
            # Use existing data_config method
            data_config = self.data_config(n, freq, axis)
        
        controller.runtime.commands.motion.enable([axis])
        time.sleep(1)
        
        controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, data_config)
        if limit == 'Ccw':
            controller.runtime.commands.motion.movefreerun([axis], [-1])
        else:
            controller.runtime.commands.motion.movefreerun([axis], [1])
        
        time.sleep(3)
        try:
            controller.runtime.commands.motion.waitformotiondone([axis])
        except (ControllerAxisFaultException, ControllerOperationException):
            faults_per_axis = self.check_for_faults(controller, [axis])
            if faults_per_axis:
                controller.runtime.commands.fault_and_error.acknowledgeall(1)
                time.sleep(2)
        
        faults_per_axis = self.check_for_faults(controller, [axis])
        if faults_per_axis:
            controller.runtime.commands.fault_and_error.acknowledgeall(1)
            time.sleep(2)

        time.sleep(5)

        results = controller.runtime.data_collection.get_results(data_config, n)
        
        self.populate(axis, results)

        self.log_limit_pos(axis, limit, results)
        time.sleep(2)

    def move_into_hardstop(self, controller, test, limit, axis):
        """Move a single axis into its hardstop. Ignore faults (acknowledge and proceed)."""
        try:
            hard_to_hard = self.get_param_value('HardToHard-FirstContact')
            limit_to_limit = self.get_param_value('LimitToLimitTravel')
            move_time = hard_to_hard - limit_to_limit
            test_time = ((move_time / 2) / 0.25) + 30
            n = int(self.sample_rate * test_time)
            freq = a1.DataCollectionFrequency.Frequency1kHz
            
            with _thread_lock:
                # Use existing data_config method instead of custom configuration
                data_config = self.data_config(n, freq, axis)
            
            controller.runtime.parameters.axes[axis][a1.AxisParameterId.MaxCurrentClamp].value = self.low_current_clamp
            limit_dec = self.get_limit_dec(controller, axis, limit='electrical off')
            controller.runtime.parameters.axes[axis][a1.AxisParameterId.FaultMask].value = limit_dec
            
            time.sleep(2)
            controller.runtime.commands.motion.enable([axis])
            time.sleep(1)

            controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, data_config)

            if limit == 'Ccw':
                controller.runtime.commands.motion.movefreerun([axis], [-0.25])
            else:
                controller.runtime.commands.motion.movefreerun([axis], [0.25])
            
            time.sleep(3)
            try:
                controller.runtime.commands.motion.waitformotiondone([axis])
            except (ControllerAxisFaultException, ControllerOperationException):
                faults_per_axis = self.check_for_faults(controller, [axis])
                if faults_per_axis:
                    controller.runtime.commands.fault_and_error.acknowledgeall(1)
                    time.sleep(2)

            # Acknowledge any remaining faults (we ignore faults during hardstop by design)
            faults_per_axis = self.check_for_faults(controller, [axis])
            if faults_per_axis:
                controller.runtime.commands.fault_and_error.acknowledgeall(1)
                time.sleep(2)

            time.sleep(10)
            
            controller.runtime.parameters.axes[axis][a1.AxisParameterId.MaxCurrentClamp].value = self.max_current_clamp
            limit_dec = self.get_limit_dec(controller, axis, limit='electrical on')
            controller.runtime.parameters.axes[axis][a1.AxisParameterId.FaultMask].value = limit_dec

            results = controller.runtime.data_collection.get_results(data_config, n)
            self.populate(axis, results)
            self.log_hardstop_pos(axis, limit, results)
            time.sleep(5)
        except ValueError as e:
            station_id = self.axis_to_station_map.get(axis)
            self.station_print(f"Error getting specifications: {e}", station_id=station_id)
            return

    def move_out_of_hardstop(self, controller, limit, axis):
        """
        Move a single axis out of its hardstop.

        Args:
            controller: The controller object for this axis
            limit: The direction of the limit ('Ccw' or 'Cw')
            axis: The axis to move
        """
        try:
            nominal_travel = abs(self.get_spec_value('Travel'))
            if limit == 'Ccw':
                controller.runtime.commands.motion.enable([axis])
                controller.runtime.commands.motion.moveincremental([axis], [nominal_travel / 2], [10])
                controller.runtime.commands.motion.waitformotiondone([axis])
                
                # Explicitly check for faults after moveabsolute
                faults_per_axis = self.check_for_faults(controller, [axis])
                if faults_per_axis:
                    controller.runtime.commands.fault_and_error.acknowledgeall(1)
                try:
                    controller.runtime.commands.motion.waitformotiondone([axis])
                except (ControllerAxisFaultException, ControllerOperationException):
                    faults_per_axis = self.check_for_faults(controller, [axis])
                    if faults_per_axis:
                        controller.runtime.commands.fault_and_error.acknowledgeall(1)
                        time.sleep(2)
            else:
                controller.runtime.commands.motion.enable([axis])
                controller.runtime.commands.motion.moveincremental([axis], [nominal_travel / -2], [10])
                controller.runtime.commands.motion.waitformotiondone([axis])
                
                # Explicitly check for faults after moveabsolute
                faults_per_axis = self.check_for_faults(controller, [axis])
                if faults_per_axis:
                    controller.runtime.commands.fault_and_error.acknowledgeall(1)
                try:
                    controller.runtime.commands.motion.waitformotiondone([axis])
                except (ControllerAxisFaultException, ControllerOperationException):
                    faults_per_axis = self.check_for_faults(controller, [axis])
                    if faults_per_axis:
                        controller.runtime.commands.fault_and_error.acknowledgeall(1)
                        time.sleep(2)
        except ValueError as e:
            station_id = self.axis_to_station_map.get(axis)
            self.station_print(f"Error getting nominal travel: {e}", station_id=station_id)
            return

    def enable(self, test=None):
        """
        Enables the connected axes and handles any faults that may occur.
        """
        threads = []
        
        def enable_single_axis(axis):
            controller = self.station_controllers[axis]
            station_id = self.axis_to_station_map.get(axis)
            
            retries = 0
            retry_limit = 10
            while retries < retry_limit:
                try:
                    controller.runtime.commands.motion.enable([axis])
                    break
                except (ControllerAxisFaultException, ControllerOperationException):
                    retries += 1
                    faults_per_axis = self.check_for_faults(controller, [axis])
                    if faults_per_axis:
                        self.handle_faults(test, {axis: faults_per_axis[axis]}, self.reenable_run_button)
                    time.sleep(2)
                
                if retries == retry_limit:
                    self.station_print(f'Exceeded retry limit with axis: {axis}', station_id=station_id)
        
        # Start enable threads
        for axis in self.test_axes:
            thread = self.create_tracked_thread(target=enable_single_axis, axis=axis, args=(axis,))
            threads.append(thread)
            thread.start()
        
        # Wait for all enables to complete
        for thread in threads:
            thread.join()
        
        time.sleep(1)

    def log_hardstop_pos(self, axis, limit, results):
        """Logs the current position of the given axis after it has reached its hardstop."""
        position_feedback = results.axis.get(a1.AxisDataSignal.PositionFeedback, axis).points

        # Combine signals into a dictionary for logging
        signals = {
            "Position Error Bit Toggled": self.pos_error_fault[axis],  # Now access axis-specific data
            "Over Current Bit Toggled": self.over_current_fault[axis],
            "Raw Position Feedback": position_feedback,
        }

        # Log signals to a text file
        log_file_path = os.path.join("logs", f"signal_data_log-{axis}-{limit}-Hardstop.txt")
        self.log_signals_to_file(log_file_path, signals)

        end_position = None
        # Iterate through velocity_command and track zero crossings
        for i, bit in enumerate(self.pos_error_fault[axis]):  # Access axis-specific data
            if bit == 1:
                end_position = position_feedback[i]
                break
        if end_position == None:
            for i, bit in enumerate(self.over_current_fault[axis]):  # Access axis-specific data
                if bit == 1:
                    end_position = position_feedback[i]
                    break
        if end_position == None:
            if limit == 'Ccw':
                absolute_feedback = [abs(value) for value in position_feedback]
                max_feedback = max(absolute_feedback)
                end_position = (max_feedback * -1)
            else:
                end_position = max(position_feedback)
            
        # Use a nested dictionary to store both 'Ccw' and 'Cw' positions
        if axis not in self.hardstop_pos:
            self.hardstop_pos[axis] = {}  # Create a new dictionary for each axis
        
        # Store position with the limit type as key ('Ccw' or 'Cw')
        self.hardstop_pos[axis][limit] = end_position
        station_id = self.axis_to_station_map.get(axis)
        # Log the position of the current limit
        self.log_only(f'{limit} hardstop Position for {axis}: {end_position}', station_id=station_id)
        
    def log_limit_pos(self, axis, limit, results):
        """Logs the current position of the given axis after it has reached its limit."""
        position_feedback = results.axis.get(a1.AxisDataSignal.PositionFeedback, axis).points

        if limit == 'Ccw':
            # Combine signals into a dictionary for logging
            signals = {
                "Fault Bit Toggled": self.ccw_fault[axis],  # Access axis-specific data
                "Position Feedback": position_feedback,
            }

            # Log signals to a text file
            log_file_path = os.path.join("logs", f"signal_data_log-{axis}-Ccw-Limit.txt")
            self.log_signals_to_file(log_file_path, signals)

            end_position = None
            for i, bit in enumerate(self.ccw_fault[axis]):  # Access axis-specific data
                if bit == 1:
                    end_position = position_feedback[i]
                    self.data[axis]["Home Marker from Limit"] = round(end_position, 4)
                    break
        else:
            # Combine signals into a dictionary for logging
            signals = {
                "Fault Bit Toggled": self.cw_fault[axis],  # Access axis-specific data
                "Position Feedback": position_feedback,
            }

            # Log signals to a text file
            log_file_path = os.path.join("logs", f"signal_data_log-{axis}-Cw-Limit.txt")
            self.log_signals_to_file(log_file_path, signals)

            end_position = None
            for i, bit in enumerate(self.cw_fault[axis]):  # Access axis-specific data
                if bit == 1:
                    end_position = position_feedback[i]
                    break

        # Use a nested dictionary to store both 'Ccw' and 'Cw' positions
        if axis not in self.limit_pos:
            self.limit_pos[axis] = {}  # Create a new dictionary for each axis
        
        # Store position with the limit type as key ('Ccw' or 'Cw')
        self.limit_pos[axis][limit] = end_position
        station_id = self.axis_to_station_map.get(axis)
        # Log the position of the current limit
        self.log_only(f'{limit} limit Position for {axis}: {end_position}', station_id=station_id)

    def reset_controllers(self):
        """
        Reset all controllers in parallel using threads.
        Waits for all resets to complete before returning.
        """
        threads = []
        
        def reset_single_controller(axis):
            controller = self.station_controllers[axis]
            station_id = self.axis_to_station_map.get(axis)
            try:
                controller.reset()
                self.station_print(f"Reset completed for axis {axis}", station_id=station_id)
            except Exception as e:
                self.station_print(f"Error resetting axis {axis}: {str(e)}", station_id=station_id)
        
        # Start reset threads
        for axis in self.test_axes:
            thread = self.create_tracked_thread(target=reset_single_controller, axis=axis, args=(axis,))
            threads.append(thread)
            thread.start()
        
        # Wait for all resets to complete
        for thread in threads:
            thread.join()
        
        # Standard wait time after reset
        time.sleep(10)

    def calculate_limit_travel(self):
        """
        Calculates the distance between CW and CCW limits for each axis, and
        compares it to the specified limit travel. If the distance is too small,
        it fails the test and logs an error.
        """
        try:
            # Calculate the distance between CW and CCW limits for each axis
            for axis in list(self.test_axes):  # Create a copy to safely modify during iteration
                station_id = self.axis_to_station_map.get(axis)
                if 'Ccw' in self.limit_pos[axis] and 'Cw' in self.limit_pos[axis]:
                    ccw_limit_position = self.limit_pos[axis]['Ccw']
                    cw_limit_position = self.limit_pos[axis]['Cw']
                    limit_distance = abs(cw_limit_position - ccw_limit_position)
                    limit_distance = round(limit_distance, 4)
                else:
                    self.station_print(f"Axis {axis} is missing one or more limit positions.", station_id=station_id)
                    continue  # Skip to next axis if missing positions

                if 'Ccw' in self.hardstop_pos[axis] and 'Cw' in self.hardstop_pos[axis]:
                    ccw_hardstop_position = self.hardstop_pos[axis]['Ccw']
                    cw_hardstop_position = self.hardstop_pos[axis]['Cw']
                    hardstop_distance = abs(cw_hardstop_position - ccw_hardstop_position)
                    hardstop_distance = round(hardstop_distance, 4)
                else:
                    self.station_print(f"Axis {axis} is missing one or more limit positions.", station_id=station_id)
                    continue  # Skip to next axis if missing positions

                limit_spec = self.get_param_value('LimitToLimitTravel')
                hardstop_spec = self.get_param_value('HardToHard-FirstContact')
                
                # Check limit travel
                if limit_distance < limit_spec:
                    self.station_print(f"{axis} is failing with a limit travel of {round(limit_distance, 4)} and a spec of {limit_spec}", station_id=station_id)
                    self.log_only(f'Axis {axis} is failing with a limit travel of {round(limit_distance, 4)}', station_id=station_id)
                    
                    # Ask user if they want to continue despite limit travel failure
                    response = messagebox.askyesno(
                        "Limit Travel Failure",
                        f"Station {station_id} failed limit travel check:\n\n" +
                        f"Measured: {round(limit_distance, 4)}\n" +
                        f"Required: {limit_spec}\n\n" +
                        "Would you like to continue testing this station anyway?"
                    )
                    
                    if not response:
                        self.station_print("Please address limit travel issues before continuing.", station_id=station_id)
                        
                        # Release the station and remove from testing
                        self.release_axis(axis)
                        
                        # Check if any axes remain
                        if not self.test_axes:
                            error_msg = "All axes have failed checks. Ending test."
                            messagebox.showerror("Test Sequence Aborted", error_msg)
                            raise TestSequenceAbort(error_msg, shown_message=True)

                    else:
                        self.station_print("Continuing despite limit travel failure.", station_id=station_id)
                else:
                    self.data[axis]["Limits"] = 'Passed'

                # Check hardstop travel
                if hardstop_distance < hardstop_spec:
                    self.station_print(f"{axis} is failing with a hardstop travel of {round(hardstop_distance, 4)} and a spec of {hardstop_spec}", station_id=station_id)
                    self.log_only(f'Axis {axis} is failing with a hardstop travel of {round(hardstop_distance, 4)}', station_id=station_id)
                    
                    # Ask user if they want to continue despite hardstop travel failure
                    response = messagebox.askyesno(
                        "Hardstop Travel Failure",
                        f"Station {station_id} failed hardstop travel check:\n\n" +
                        f"Measured: {round(hardstop_distance, 4)}\n" +
                        f"Required: {hardstop_spec}\n\n" +
                        "Would you like to continue testing this station anyway?"
                    )
                    
                    if not response:
                        self.station_print("Please address hardstop travel issues before continuing.", station_id=station_id)
                        
                        # Release the station and remove from testing
                        self.release_axis(axis)
                        
                        # Check if any axes remain
                        if not self.test_axes:
                            error_msg = "All axes have failed checks. Ending test."
                            messagebox.showerror("Test Sequence Aborted", error_msg)
                            raise TestSequenceAbort(error_msg, shown_message=True)
                    else:
                        self.station_print("Continuing despite hardstop travel failure.", station_id=station_id)

                # If we get here, the axis passed both checks
                self.data[axis]["Total Travel"] = limit_distance
                #self.station_print(f'Axis {axis}: CCW Limit Position = {ccw_limit_position}, CW Limit Position = {cw_limit_position}, Limit Distance = {limit_distance}', station_id=station_id)
                #self.station_print(f'Axis {axis}: CCW Hardstop Position = {ccw_hardstop_position}, CW Hardstop Position = {cw_hardstop_position}, Hardstop Distance = {hardstop_distance}', station_id=station_id)
                self.log_only(f'Axis {axis} Distance between Ccw Limit and Cw Limit: {limit_distance}', station_id=station_id)
                self.log_only(f'Axis {axis} Distance between Ccw hardstop and Cw hardstop: {hardstop_distance}', station_id=station_id)

        except TestSequenceAbort as e:
            raise  # Re-raise without showing message again

    def data_config(self, n: int, freq: a1.DataCollectionFrequency, axis: int) -> a1.DataCollectionConfiguration:
        """
        Data configurations. These are how to configure data collection parameters
        """
        # Create a data collection configuration with sample count and frequency
        data_config = a1.DataCollectionConfiguration(n, freq)

        # Add items to collect data on the entire system
        data_config.system.add(a1.SystemDataSignal.DataCollectionSampleTime)

        # Add items to collect data on the specified axis
        data_config.axis.add(a1.AxisDataSignal.DriveStatus, axis)
        data_config.axis.add(a1.AxisDataSignal.AxisFault, axis)
        data_config.axis.add(a1.AxisDataSignal.PrimaryFeedback, axis)
        data_config.axis.add(a1.AxisDataSignal.PositionFeedback, axis)
        data_config.axis.add(a1.AxisDataSignal.CurrentCommand, axis)
        data_config.axis.add(a1.AxisDataSignal.CurrentFeedback, axis)
        data_config.axis.add(a1.AxisDataSignal.VelocityCommand, axis)

        return data_config
    
    def populate(self, axis, results):
        """
        Populate the hall sensor and primary feedback data structures based on the results of a data collection run.
        """
        # Initialize dictionary entries for this axis with nested structure
        if axis not in self.hall_states:
            self.hall_states[axis] = {}
        if axis not in self.hall_encoder_positions:
            self.hall_encoder_positions[axis] = {}
        
        # Initialize other lists
        self.hall_a[axis] = []
        self.hall_b[axis] = []
        self.hall_c[axis] = []
        self.ccw_fault[axis] = []
        self.cw_fault[axis] = []
        self.pos_error_fault[axis] = []
        self.over_current_fault[axis] = []
        
        # Define check points (in seconds) and corresponding electrical angles
        check_points = [1.5, 4.5, 7.5, 10.5, 13.5, 16.5]
        electrical_angles = [0, 60, 120, 180, 240, 300]  # degrees
        
        # Get the data
        halls = results.axis.get(a1.AxisDataSignal.DriveStatus, axis).points
        pri_fbk = results.axis.get(a1.AxisDataSignal.PrimaryFeedback, axis).points
        faults = results.axis.get(a1.AxisDataSignal.AxisFault, axis).points
        self.time_array = np.array(results.system.get(a1.SystemDataSignal.DataCollectionSampleTime).points)
        self.time_array -= self.time_array[0]
        self.time_array *= .001 #msec to sec
        self.time_array = self.time_array.tolist()
        
        for i, t in enumerate(self.time_array):
            self.time_array[i] = i/self.sample_rate
            
            # Check if we're at one of our target times
            check_time = check_points[len(self.hall_states[axis].keys())] if len(self.hall_states[axis].keys()) < len(check_points) else None
            if check_time and abs(self.time_array[i] - check_time) < (1/self.sample_rate):
                hall_a = 1 if ((int(halls[i]) & a1.DriveStatus.HallAInput.value) > 0) else 0
                hall_b = 1 if ((int(halls[i]) & a1.DriveStatus.HallBInput.value) > 0) else 0
                hall_c = 1 if ((int(halls[i]) & a1.DriveStatus.HallCInput.value) > 0) else 0
                hall_state = f"{hall_a}{hall_b}{hall_c}"
                current_angle = electrical_angles[len(self.hall_states[axis].keys())]
                
                # Store values with angle as key
                self.hall_states[axis][current_angle] = hall_state
                self.hall_encoder_positions[axis][current_angle] = pri_fbk[i]
        
        # Process faults
        for x in faults:
            self.ccw_fault[axis].append(1 if ((int(x) & a1.AxisFault.CcwEndOfTravelLimitFault.value) > 0) else 0)
            self.cw_fault[axis].append(1 if ((int(x) & a1.AxisFault.CwEndOfTravelLimitFault.value) > 0) else 0)
            self.pos_error_fault[axis].append(1 if ((int(x) & a1.AxisFault.PositionErrorFault.value) > 0) else 0)
            self.over_current_fault[axis].append(1 if ((int(x) & a1.AxisFault.OverCurrentFault.value) > 0) else 0)

    def init_logger(self):
        """
        Initialize the logging system for the strut checkout station.

        Creates two log files: one for fault logging and one for limit information logging.
        Configures the loggers and handlers for both log files.
        """
        # Create the root directory for logs if it doesn't exist
        base_log_dir = r"O:\CMP Check-out"
        os.makedirs(base_log_dir, exist_ok=True)

        # Create a subdirectory for the current job using self.job
        self.job_log_dir = os.path.join(base_log_dir, self.job)
        os.makedirs(self.job_log_dir, exist_ok=True)

        # Configure the first log file for fault logging
        fault_log_file = os.path.join(base_log_dir, f'Checkout Station Fault Log.log')
        self.fault_log = logging.getLogger('fault_log')
        fault_handler = logging.FileHandler(fault_log_file)
        fault_handler.setLevel(logging.INFO)
        fault_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fault_handler.setFormatter(fault_formatter)
        self.fault_log.addHandler(fault_handler)
        self.fault_log.setLevel(logging.INFO)

        # Configure the second log file for limit information logging
        self.stage_log_file = os.path.join(base_log_dir, f'Checkout Station.log')
        self.stage_info = logging.getLogger('stage_info')
        stage_handler = logging.FileHandler(self.stage_log_file)
        stage_handler.setLevel(logging.INFO)
        stage_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        stage_handler.setFormatter(stage_formatter)
        self.stage_info.addHandler(stage_handler)
        self.stage_info.setLevel(logging.INFO)

    def log_signals_to_file(self, log_file_path, signals):
        """
        Log all collected signals to a text file.

        Args:
            log_file_path (str): Path to the log file.
            signals (dict): Dictionary of signal names and their corresponding data.
        """
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

            # Open the file in write mode
            with open(log_file_path, 'w') as log_file:
                log_file.write("Signal Data Log\n")
                log_file.write("=" * 40 + "\n\n")
                
                for signal_name, signal_data in signals.items():
                    log_file.write(f"Signal: {signal_name}\n")
                    log_file.write(f"Data Points: {len(signal_data)}\n")
                    log_file.write(f"Values: {signal_data}\n")
                    log_file.write("\n" + "-" * 40 + "\n")
        except Exception as e:
            print(f"Error logging signals: {e}")


    def process_hall_results(self, axis, station_id, hall_states, encoder_values, hall_order_valid, encoder_direction, unique_hall_states):
        """
        Process and log the results of hall sensor checks.
        
        Args:
            axis (str): The axis being tested
            station_id (int): The station ID for logging
            hall_states (list): The observed hall states in order
            encoder_values (list): The encoder values at each hall state
            hall_order_valid (bool): Whether the hall sequence is valid
            encoder_direction (str): Direction of encoder movement ('positive' or 'negative')
            unique_hall_states (list): The unique hall states observed
        """
        if hall_order_valid:
            self.station_print(f'Hall states for {axis} are in the correct order.', station_id=station_id)
            self.log_only(f'Hall states for {axis} are in the correct order.')
            self.data[axis]["Halls"] = "Passed"
        else:
            self.station_print(f'Hall states for {axis} are NOT in the correct order:', station_id=station_id)
            self.station_print(f'Expected order: {"CW" if encoder_direction == "positive" else "CCW"} sequence', station_id=station_id)
            self.station_print(f'Observed states: {unique_hall_states}', station_id=station_id)
            self.log_only(f'Hall states for {axis} are NOT in the correct order.', station_id=station_id)
            self.log_only(f'Expected order: {"CW" if encoder_direction == "positive" else "CCW"} sequence', station_id=station_id)
            self.log_only(f'Observed states: {unique_hall_states}', station_id=station_id)
            self.data[axis]["Halls"] = "Failed"

            self.station_print("Please address hall issues before continuing.", station_id=station_id)
            # Release the station and remove from testing
            #station_manager = get_station_manager()
            #station_manager.release_stations(station_id)
            self.secondary_ui.update_station_status(station_id, running=False, serial="")
            controller = self.station_controllers[axis]
            controller.runtime.commands.motion.disable([axis])

            self.test_axes.remove(axis)
            if axis in self.station_controllers:
                del self.station_controllers[axis]

        if not self.test_axes:
            raise TestSequenceAbort("Please address hall issues on affected axes. Ending test.")
        
        # Log encoder values at each hall state transition
        #self.station_print(f'Encoder values at hall transitions for {axis}:', station_id=station_id)
        self.log_only(f'Encoder values at hall transitions for {axis}:', station_id=station_id)
        for state, value in zip(hall_states, encoder_values):
            #self.station_print(f'State {state}: {value}', station_id=station_id)
            self.log_only(f'State {state}: {value}', station_id=station_id)

    def cleanup_data_structures(self, station_id, axis):
        """
        Clean up data structures and threads for a station
        """
        # Clear axis-related data structures
        if axis in self.test_axes:
            self.test_axes.remove(axis)
        
        if axis in self.station_controllers:
            del self.station_controllers[axis]

        # Clear station-related data structures
        if station_id in self.station_loggers:
            del self.station_loggers[station_id]

        # Clear any test-specific data structures
        if hasattr(self, 'hall_states'):
            self.hall_states = []
        if hasattr(self, 'pri_fbk'):
            self.pri_fbk = []
        if hasattr(self, 'hall_a'):
            self.hall_a = []
        if hasattr(self, 'hall_b'):
            self.hall_b = []
        if hasattr(self, 'hall_c'):
            self.hall_c = []
        
        # Clear any position/travel related data
        if hasattr(self, 'hardstop_pos') and axis in self.hardstop_pos:
            del self.hardstop_pos[axis]
        if hasattr(self, 'limit_pos') and axis in self.limit_pos:
            del self.limit_pos[axis]
        if hasattr(self, 'abs_ccw_positions') and axis in self.abs_ccw_positions:
            del self.abs_ccw_positions[axis]
        if hasattr(self, 'abs_cw_positions') and axis in self.abs_cw_positions:
            del self.abs_cw_positions[axis]
        
        # Enhanced thread cleanup
        if hasattr(self, 'active_threads'):
            threads_to_remove = []
            for thread in self.active_threads:
                # Check both axis and station_id
                if (thread.axis == axis or 
                    (thread.station_id is not None and thread.station_id == station_id)):
                    if thread.is_alive():
                        thread.join(timeout=1.0)
                    threads_to_remove.append(thread)
            
            for thread in threads_to_remove:
                self.active_threads.remove(thread)
        
    def setup_logging(self, serial_number):
        """Setup logging for each station."""
        # Create serial number directory if it doesn't exist
        serial_dir = os.path.join(self.job_log_dir, serial_number)
        os.makedirs(serial_dir, exist_ok=True)
        
        # Create station-specific loggers
        for axis in self.test_axes:
            station_id = self.axis_to_station_map[axis]
            station_log_file = os.path.join(serial_dir, f'ST{station_id:02d}_log.txt')
            
            # Create logger for this station
            station_logger = logging.getLogger(f'station_{station_id}')
            station_logger.setLevel(logging.INFO)
            
            # Create file handler
            fh = logging.FileHandler(station_log_file)
            fh.setLevel(logging.INFO)
            
            # Create formatter
            formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            fh.setFormatter(formatter)
            
            # Add handler to logger
            station_logger.addHandler(fh)
            
            # Store logger reference
            self.station_loggers[station_id] = station_logger

    def log_only(self, message, station_id=None):
        """Log message to station's log file without printing to UI."""
        if station_id:
            # Ensure directory exists
            serial_dir = os.path.join(self.job_log_dir)  # Remove duplicate serial number
            os.makedirs(serial_dir, exist_ok=True)
            
            if isinstance(station_id, list):
                for sid in station_id:
                    station_log_file = os.path.join(serial_dir, f'ST{sid:02d}_log.txt')
                    with open(station_log_file, 'a') as f:
                        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
                        f.write(f'{timestamp} - INFO - {message}\n')
            else:
                station_log_file = os.path.join(serial_dir, f'ST{station_id:02d}_log.txt')
                with open(station_log_file, 'a') as f:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S,%f')[:-3]
                    f.write(f'{timestamp} - INFO - {message}\n')
