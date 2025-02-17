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
from collections import deque
import threading
from station_manager import StationManager

from BurnIn import burn_in

#sys.path.append(r"K:\10. Released Software\Systems Manufacturing Support\Shared")
sys.path.append(r"C:\Users\tbates\Python\shared")
from Logger import TextLogger
from DecodeFaults import decode_faults
from sheets_update import Sheets
#from RedirectStdout import RedirectStdout

class stage_checkout():
    '''
    This program is intended to take a complete set of hexapod struts through an automated check-out procedure.
    '''
    def __init__(self, stage_type, speed, burnin_time, job, op, comments, secondary_ui, window, num_axes, test_axes, duty_cycle, specs_dict, absolute, stations, **kwargs):
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
        
        self.sample_rate = 1000
        
        # Initialize station loggers
        self.station_loggers = {}
        print(f'Stations: {self.stations}')
        for station_id in self.stations:
            print(f'Station ID: {station_id}')
            station_widget = self.secondary_ui.station_widgets.get(station_id)
            if station_widget:
                self.station_loggers[station_id] = TextLogger(station_widget["txt_logs"])

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
        
        self.window = tk.Tk()
        self.window.withdraw()
        
    def station_print(self, message, station_id=None):
        """
        Print a message to a specific station's text_widget or all stations.

        Parameters:
            message (str): The message to display.
            station_id (int or None): The ID of the station to print to.
                                      If None, print to all allocated stations.
        """
        #print(f'Station ID: {station_id}')
        if station_id is None:  # Print to all stations
            for sid, logger in self.station_loggers.items():
                logger.write(message + "\n")
        elif station_id in self.station_loggers:  # Print to a specific station
            self.station_loggers[station_id].write(message + "\n")
        else:
            print(f"[Warning] Invalid station_id {station_id}. Message: {message}")

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
        Get a numerical value from specs_dict, handling both float and string formats.
        
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
            return spec if isinstance(spec, float) else float(spec.split()[0])
        except (AttributeError, ValueError) as e:
            raise ValueError(f"Could not convert {spec_key}={spec} to float: {e}")
    def test(self, reenable_run_button, station_controllers):
        """
        Main entry point for the checkout process.
        
        Args:
            station_controllers (dict): Dictionary mapping axis names to their respective controllers
        """
        self.station_print(f"Starting test for {self.job}.")
        self.station_controllers = station_controllers
        print(f'Station Controllers-checkout_test: {self.station_controllers}')
        self.reenable_run_button = reenable_run_button
        # Initialize data dictionary for each axis
        self.data = {}
        for axis in self.test_axes:
            self.data[f"Axis: {axis}"] = {
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
        self.fault_log.info(f'Model: {self.stage_type}\nSerial Number: {self.job}\n')
        self.stage_info.info(f'Model: {self.stage_type}\nSerial Number: {self.job}\n')
        
        # Initialize motion parameters
        self.list_commands_ccw_pos = []
        self.list_commands_cw_pos = []
        self.list_commands_zero = []
        self.list_velocity = []
        self.list_low_velocity = []
        
        # Set the nominal positions and velocities for each axis
        for axis in self.test_axes:
            try:
                nominal_travel = self.get_spec_value('NominalTravel')
                self.list_commands_ccw_pos.append(nominal_travel / 2 * -1)
                self.list_commands_cw_pos.append(nominal_travel / 2)
                self.list_commands_zero.append(0)
                self.list_velocity.append(self.speed)
                self.list_low_velocity.append(0.5)
            except ValueError as e:
                self.station_print(f"Error: {e}")
                return

        self.zero_home_offset = 0
        self.max_current_clamp = 10
        self.low_current_clamp = 3.5
        print(f'Nominal Travel: {self.specs_dict.get("NominalTravel")}')
        self.nominal_travel = self.specs_dict.get('NominalTravel')
        print("Configuring initial parameters for each axis")
        # Configure initial parameters for each axis
        print(f'Test Axes: {self.test_axes}')
        for axis in self.test_axes:
            print(f'Axis: {axis}')
            controller = self.station_controllers[axis]  # Get the specific controller for this axis
            print(f'Controller: {controller}')
            if self.absolute:
                self.params(controller, axis, home_offset=self.zero_home_offset, current_clamp=self.max_current_clamp, limit='electrical off')
            else:
                self.params(controller, axis, home_offset=self.zero_home_offset, current_clamp=self.max_current_clamp, limit='electrical on')
        
        # Reset all controllers in parallel
        threads = []
        for axis in self.test_axes:
            def reset_controller(axis):
                controller = self.station_controllers[axis]
                controller.reset()
            thread = threading.Thread(target=reset_controller, args=(axis,))
            threads.append(thread)
            thread.start()
        
        # Wait for all resets to complete
        for thread in threads:
            thread.join()
        time.sleep(10)  # Wait for all controllers to initialize

        # Wait for the controller to finish processing the previous commands
        time.sleep(2)
        self.enable_stages()
        time.sleep(5)

    def params(self, controller, axis, home_offset=None, current_clamp=None, limit=None):
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
            
        if current_clamp:
            configured_parameters.axes[axis].protection.limitdebouncedistance.value = 1
            configured_parameters.axes[axis].protection.maxcurrentclamp.value = current_clamp

        if limit:
            electrical_limit_value = self.get_limit_dec(controller, axis, limit)
            configured_parameters.axes[axis].protection.faultmask.value = electrical_limit_value

        # Apply the updated configuration for the axis
        controller.configuration.parameters.set_configuration(configured_parameters)

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
                                    self.home_stages()
                                    self.check_hardstop()
                                else:
                                    self.release_station = StationManager.release_station(station_id)
                                    self.release_station()
                                    reenable_run_button()
                                    sys.exit()
                            else:
                                confirm = messagebox.askyesno(
                                    'An Axis Fault Occurred',
                                    f'Axis {axis} has the following faults: {filtered_faults}. Would you like to remove these axes and continue?'
                                )
                                self.station_print(f'Axis {axis} has the following faults: {filtered_faults}', station_id=station_id)
                                
                                if confirm:
                                    # Continue and remove the axis from connected_axes
                                    print('Continuing the test and removing affected axis.')
                                    if axis in updated_connected_axes:
                                        updated_connected_axes.remove(axis)
                                else:
                                    # Re-enable the "Run" button and stop further execution
                                    self.station_print(f'Axis {axis} requires attention for the following faults: {faults}.', station_id=station_id)
                                    self.release_station = StationManager.release_station(station_id)
                                    self.release_station()
                                    reenable_run_button()  # Call the callback to re-enable the button
                                    sys.exit()
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
                                self.home_stages()
                                self.check_hardstop()
                            else:
                                self.release_station = StationManager.release_station(station_id)
                                self.release_station()
                                reenable_run_button()  # Call the callback to re-enable the button
                                sys.exit()
                    
                    confirm = messagebox.askyesno(
                        'An Axis Fault Occurred',
                        f'Axis {axis} has the following faults: {faults}. Would you like to remove these axes and continue?'
                    )
                    self.station_print(f'Axis {axis} has the following faults: {faults}', station_id=station_id)
                
                    if confirm:
                        # Continue and remove the axis from connected_axes
                        print('Continuing the test and removing affected axis.')
                        if axis in updated_connected_axes:
                            updated_connected_axes.remove(axis)
                    else:
                        # Re-enable the "Run" button and stop further execution
                        self.station_print(f'Axis {axis} requires attention for the following faults: {faults}.', station_id=station_id)
                        self.release_station = StationManager.release_station(station_id)
                        self.release_station()
                        reenable_run_button()  # Call the callback to re-enable the button
                        sys.exit()
                    
        # Update the connected_axes with the updated list
        self.test_axes = updated_connected_axes
        
        # Update the commands for the remaining axes
        try:
            nominal_travel = self.get_spec_value('NominalTravel')
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
            self.station_print(f"Error updating commands: {e}")
            return
            
    def enable_stages(self):
        """Enable all stages in parallel and handle any faults."""
        self.station_print('Enabling Axes')
        
        # Enable all axes in parallel
        threads = []
        def enable_single_axis(axis):
            try:
                controller = self.station_controllers[axis]
                controller.runtime.commands.motion.enable([axis])
                time.sleep(0.5)
                controller.runtime.commands.fault_and_error.acknowledgeall(1)
                controller.runtime.commands.motion.enable([axis])
                
            except (ControllerAxisFaultException, ControllerOperationException):
                # Handle the axis fault exception
                
                time.sleep(3)
                
                faults_per_axis = self.check_for_faults()
            
                fault_init = decode_faults(faults_per_axis, self.test_axes, self.controller, self.fault_log)
                decoded_faults = fault_init.get_fault()
            
                # Create a copy of the connected_axes list to safely remove unused axes
                updated_connected_axes = list(self.test_axes)
            
                for axis, faults in decoded_faults.items():
                    station_id = self.axis_to_station_map.get(axis)
                    # Check if specific faults are present
                    if 'FeedbackInput0Fault' in faults or 'FeedbackInput1Fault' in faults:
                        # Display warning message with axis and its faults
                        confirm = messagebox.askyesno(
                            'Fault On Enable',
                            f'Axis {axis} has the following faults: {faults}. Is this an unused axis?'
                        )
            
                        if confirm:
                            # Remove axis from the connected_axes list
                            if axis in updated_connected_axes:
                                updated_connected_axes.remove(axis)
                                self.station_print(f'Axis {axis} removed from connected axes as it is unused.', station_id=station_id)
                        else:
                            # Handle case where axis is in use
                            self.station_print(f'Axis {axis} requires attention for the following faults: {faults}.', station_id=station_id)
                            self.release_station = StationManager.release_station(station_id)
                            self.release_station()
                            self.reenable_run_button()  # Call the callback to re-enable the button
                            sys.exit()
                        
                # Update the connected_axes with the updated list
                self.test_axes = updated_connected_axes
                nominal_travel = self.get_spec_value('NominalTravel')
                self.list_commands_ccw_pos = []
                self.list_commands_cw_pos = []
                self.list_velocity = []
                for axis in self.test_axes:
                    self.list_commands_ccw_pos.append(nominal_travel / 2 * -1)
                    self.list_commands_cw_pos.append(nominal_travel / 2)
                    self.list_commands_zero.append(5)
                
                try:
                    self.controller.runtime.commands.motion.enable(self.test_axes)
                    
                except (ControllerAxisFaultException, ControllerOperationException):
                    # Handle the axis fault exception
                    error_message = "Axis fault occurred during enable."
                    self.station_print(error_message, station_id=station_id)
                    messagebox.showerror("Axis Fault", error_message)
                    
                    time.sleep(3)
                    
                    faults_per_axis = self.check_for_faults()
                
                    fault_init = decode_faults(faults_per_axis, self.test_axes, self.controller, self.fault_log)
                    decoded_faults = fault_init.get_fault()
                    sys.exit()
        
        # Start enable threads
        for axis in self.test_axes:
            thread = threading.Thread(target=enable_single_axis, args=(axis,))
            threads.append(thread)
            thread.start()
        
        # Wait for all enables to complete
        for thread in threads:
            thread.join()
        
        self.check_halls()
        time.sleep(5)

    def rotate_to_match_start(self, observed, expected):
        """
        Rotate the observed list so that it starts with the same state as the expected list.

        Parameters:
            observed (list): The list to be rotated.
            expected (list): The reference list that determines the starting element.

        Returns:
            list: The rotated list starting with the same element as the expected list.
        """
        observed_deque = deque(observed)
        
        # Find the first occurrence of expected[0] in observed
        if expected[0] in observed_deque:
            # Rotate left until the first element matches expected[0]
            while observed_deque[0] != expected[0]:
                observed_deque.rotate(-1)
        
        # Convert deque back to list and return
        return list(observed_deque)

    def check_halls(self, retry=False):
        """Check hall sensor sequence for each axis in parallel."""
        self.station_print('Checking Halls')
        hall_check_step = self.get_spec_value('NominalTravel')
        hall_check_vel = 5

        test_time = hall_check_step / hall_check_vel
        n = int(self.sample_rate * test_time)
        freq = a1.DataCollectionFrequency.Frequency1kHz
        
        # Move to CCW limit in parallel
        threads = []
        def move_to_limit(axis):
            controller = self.station_controllers[axis]
            controller.runtime.commands.execute(f'MoveToLimitCcw({axis})', 1)
            controller.runtime.commands.motion.waitformotiondone([axis], 1)
            time.sleep(2)
        
        for axis in self.test_axes:
            thread = threading.Thread(target=move_to_limit, args=(axis,))
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
                
                # Configure data collection
                data_config = self.data_config(n, freq, axis)
                
                # Start data collection and move
                controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, data_config)
                time.sleep(0.1)
                
                try:
                    controller.runtime.commands.motion.enable([axis])
                    controller.runtime.commands.motion.moveincremental([axis], [hall_check_step], [hall_check_vel])
                    controller.runtime.commands.motion.waitformotiondone([axis], 1)
                except (ControllerAxisFaultException, ControllerOperationException):
                    error_message = "Axis fault occurred during enable."
                    faults_per_axis = self.check_for_faults(controller, [axis])
                    fault_init = decode_faults(faults_per_axis, [axis], controller, self.fault_log)
                    decoded_faults = fault_init.get_fault()
                    self.fault_log.info(f'A fault occurred on {axis}: {decoded_faults}')
                    messagebox.showerror("Axis Fault", error_message)
                    return
                
                time.sleep(test_time)
                time.sleep(1)
                
                # Get results and populate instance variables
                axis_results = controller.runtime.data_collection.get_results(data_config, n)
                self.populate(axis, axis_results)
                
                # Process hall states for this axis
                hall_status = []
                encoder_values = []
                
                # Use instance variables populated by self.populate
                for c, a, b, encoder in zip(self.hall_c, self.hall_a, 
                                          self.hall_b, self.pri_fbk):
                    hall_state = f"{c}{a}{b}"
                    hall_status.append(hall_state)
                    encoder_values.append(encoder)
                
                # Process unique states
                unique_hall_states = []
                unique_encoder_values = []
                seen_states = set()
                
                for state, encoder in zip(hall_status, encoder_values):
                    if state not in seen_states:
                        unique_hall_states.append(state)
                        unique_encoder_values.append(encoder)
                        seen_states.add(state)
                
                # Validate hall sequence
                expected_order_cw = ["100", "101", "001", "011", "010", "110"]
                expected_order_ccw = expected_order_cw[::-1]
                
                encoder_direction = "positive" if sum(y > x for x, y in zip(unique_encoder_values, unique_encoder_values[1:])) > len(unique_encoder_values) // 2 else "negative"
                
                if encoder_direction == "positive":
                    rotated_hall_states = self.rotate_to_match_start(unique_hall_states, expected_order_cw)
                    hall_order_valid = rotated_hall_states == expected_order_cw
                else:
                    rotated_hall_states = self.rotate_to_match_start(unique_hall_states, expected_order_ccw)
                    hall_order_valid = rotated_hall_states == expected_order_ccw
                
                # Process results
                if len(rotated_hall_states) < 6:
                    self.station_print(f'Not all hall states seen on axis {axis}', station_id=station_id)
                    self.stage_info.info(f"A fault occurred on {axis}. Not all hall states seen.")
                else:
                    self.process_hall_results(axis, station_id, rotated_hall_states, unique_encoder_values, 
                                            hall_order_valid, encoder_direction, unique_hall_states)
                    
            except Exception as e:
                self.station_print(f"Error collecting hall data for {axis}: {str(e)}", station_id=station_id)
        
        # Start data collection threads
        for axis in self.test_axes:
            thread = threading.Thread(target=collect_hall_data, args=(axis,))
            threads.append(thread)
            thread.start()
        
        # Wait for all data collection to complete
        for thread in threads:
            thread.join()

    def absolute_hardstop(self):
        """Check hardstop travels for all axes and calculate absolute home offset."""
        self.station_print('Checking Hardstop Travels')
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
            self.data[f"Axis: {axis}"]["Absolute value at CCW EOT"] = ccw_pos_fbk
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

        self.calculate_home_offset()

    def calculate_home_offset(self):
        """Calculate and set home offsets for each axis."""
        self.station_print('Calculating Offset')
        self.midpoints = {}
        
        if self.absolute:
            for axis in self.abs_ccw_positions:
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
                self.data[f"Axis: {axis}"]["Absolute Position Offset"] = midpoint

                # Configure the axis
                configured_parameters = controller.configuration.parameters.get_configuration()
                configured_parameters.axes[axis].feedback.auxiliaryabsolutefeedbackoffset.value = midpoint
                configured_parameters.axes[axis].protection.maxcurrentclamp.value = self.max_current_clamp
                controller.configuration.parameters.set_configuration(configured_parameters)
                controller.reset()
        else:
            for axis, limits in self.limit_pos.items():
                controller = self.station_controllers[axis]
                cw_pos = limits.get('Cw', 0)
                ccw_pos = limits.get('Ccw', 0)
                midpoint = (ccw_pos + cw_pos) / 2
                self.midpoints[axis] = midpoint
                self.data[f"Axis: {axis}"]["Home Offset"] = midpoint

                configured_parameters = controller.configuration.parameters.get_configuration()
                configured_parameters.axes[axis].homing.homeoffset.value = midpoint
                controller.configuration.parameters.set_configuration(configured_parameters)
                controller.reset()

        time.sleep(10)

        # Enable all axes
        for axis in self.test_axes:
            controller = self.station_controllers[axis]
            controller.runtime.commands.motion.enable([axis])

        time.sleep(2)
        self.software_limits()
    
    def software_limits(self):
        """
        Set software limits for connected axes based on hexapod type and configure parameters.
        
        This function sets the software limits for each axis in the connected_axes list.
        The limits are determined by the hexapod type and parameters stored in param_dict.
        After setting the limits, the function resets the controller to apply changes
        and re-enables the axes. It also initializes a burn-in process.
        """
        self.station_print('Setting Software Limits')
        
        for axis in self.test_axes:
            # Retrieve current configuration parameters
            configured_parameters = self.controller.configuration.parameters.get_configuration()
            configured_parameters.axes[axis].protection.softwarelimithigh.value = (((float(self.specs_dict.get('NominalTravel').split()[0]) / 2) + 0.1))
            configured_parameters.axes[axis].protection.softwarelimitlow.value = ((((float(self.specs_dict.get('NominalTravel').split()[0]) / 2) + 0.1) * -1))

            # Apply the new configuration
            self.controller.configuration.parameters.set_configuration(configured_parameters)
        
        # Set additional parameters and reset the controller
        for axis in self.test_axes:
            self.params(axis, home_offset=self.midpoints[axis], current_clamp=self.max_current_clamp, limit=['electrical on', 'software on'])
        self.controller.reset()
        time.sleep(10)
        
        # Enable the connected axes
        self.controller.runtime.commands.motion.enable(self.test_axes)
        
        if self.absolute:
        # Initialize burn-in process
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
                self.stage_log_file
            )
            
            # Pass the station controllers to burn-in
            BI.initialize_burnin(self.station_controllers)

            populate_sheet = Sheets(self.job, self.data)
            populate_sheet.populate_sheet()
        else:
            # Home the struts
            self.home_stages()
            
    def home_stages(self):
        """
        Home all stages in parallel based on encoder type.
        Handles homing or absolute positioning for each axis independently.
        """
        self.station_print('Homing Axes')
        test = 'homing'
        
        threads = []
        
        def home_single_axis(axis):
            """Handle homing/positioning for a single axis."""
            controller = self.station_controllers[axis]
            station_id = self.axis_to_station_map.get(axis)
            
            def attempt_operation(operation):
                """Attempt an operation with fault handling for this axis."""
                while True:
                    try:
                        operation()
                        break
                    except (ControllerAxisFaultException, ControllerOperationException):
                        time.sleep(3)
                        faults_per_axis = self.check_for_faults(controller, [axis])
                        if faults_per_axis:
                            self.handle_faults(test, {axis: faults_per_axis[axis]}, self.reenable_run_button)
                        time.sleep(2)
            
            if not self.absolute:
                # Enable then home for incremental axes
                attempt_operation(lambda: controller.runtime.commands.motion.enable([axis]))
                time.sleep(1)
                
                attempt_operation(lambda: controller.runtime.commands.motion.home([axis]))
                time.sleep(1)
                
                # Update marker status
                self.data[f"Axis: {axis}"]["Marker"] = "Passed"
                
            else:
                # Move to absolute zero position
                attempt_operation(lambda: controller.runtime.commands.motion.moveabsolute(
                    [axis], 
                    [self.list_commands_zero[self.test_axes.index(axis)]], 
                    [self.list_velocity[self.test_axes.index(axis)]]
                ))
                time.sleep(1)
                
                # Wait for motion to complete
                controller.runtime.commands.motion.waitformotiondone([axis])
                time.sleep(2)
                
                # Check for faults after absolute move
                faults_per_axis = self.check_for_faults(controller, [axis])
                if faults_per_axis:
                    self.handle_faults(test, {axis: faults_per_axis[axis]}, self.reenable_run_button)
        
        # Start a thread for each axis
        for axis in self.test_axes:
            thread = threading.Thread(target=home_single_axis, args=(axis,))
            threads.append(thread)
            thread.start()
        
        # Wait for all axes to complete
        for thread in threads:
            thread.join()

    def check_hardstop(self):
        """Check hardstop travels for each axis in parallel."""
        self.hardstop_pos = {}
        self.limit_pos = {}
        self.station_print('Checking Limits and Hardstops')
        test = 'hardstop and limit check'

        def check_single_axis(axis, direction):
            """Handle hardstop check for a single axis."""
            controller = self.station_controllers[axis]
            station_id = self.axis_to_station_map.get(axis)
            limit = 'Cw' if direction == 'cw' else 'Ccw'
            
            # Move to limit and hardstop using this axis's controller
            self.move_into_limit(controller, test, limit, axis)
            time.sleep(2)
            self.move_into_hardstop(controller, test, limit, axis)
            
            # Check and clear faults using this axis's controller
            faults_per_axis = self.check_for_faults(controller, [axis])
            if faults_per_axis:
                controller.runtime.commands.fault_and_error.acknowledgeall(1)
            
            # Move out of hardstop using this axis's controller
            self.move_out_of_hardstop(controller, limit, axis)

        # Run CCW checks in parallel
        threads = []
        for axis in self.test_axes:
            thread = threading.Thread(target=check_single_axis, args=(axis, 'ccw'))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        time.sleep(5)

        # Run CW checks in parallel 
        threads = []
        for axis in self.test_axes:
            thread = threading.Thread(target=check_single_axis, args=(axis, 'cw'))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        time.sleep(5)

        # Calculate travels and update parameters
        self.calculate_limit_travel()
        time.sleep(2)
        self.calculate_home_offset()
        time.sleep(2)
        self.marker_to_limit()
        time.sleep(2)

        print(f'Data To Sheet: {self.data}')
        
        # Initialize burn-in with the station controllers
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
            self.stage_log_file
        )
        
        # Pass the station controllers to burn-in
        BI.initialize_burnin(self.station_controllers)

        populate_sheet = Sheets(self.job, self.data)
        populate_sheet.populate_sheet()

        time.sleep(5)
        self.home_stages()
        self.station_print("All tests completed.")

    def move_into_limit(self, controller, test, limit, axis):
        """Move a single axis to its limit position."""
        test_time = 2
        n = int(self.sample_rate * test_time)
        freq = a1.DataCollectionFrequency.Frequency1kHz
        
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
        
        results = controller.runtime.data_collection.get_results(data_config, n)
        self.populate(axis, results)
        if test != 'marker to limit':
            self.log_limit_pos(axis, limit, results)
        time.sleep(2)

    def move_into_hardstop(self, controller, test, limit, axis):
        """Move a single axis into its hardstop."""
        try:
            hard_to_hard = self.get_spec_value('HardToHard-FirstContact')
            limit_to_limit = self.get_spec_value('LimitToLimitTravel')
            move_time = hard_to_hard - limit_to_limit
            test_time = ((move_time / 2) / 0.25) + 30
            n = int(self.sample_rate * test_time)
            freq = a1.DataCollectionFrequency.Frequency1kHz
            
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
            time.sleep(10)
            
            results = controller.runtime.data_collection.get_results(data_config, n)
            self.populate(axis, results)
            self.log_hardstop_pos(axis, limit, results)
            time.sleep(2)
        except ValueError as e:
            self.station_print(f"Error getting specifications: {e}")
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
            nominal_travel = self.get_spec_value('NominalTravel')
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
            self.station_print(f"Error getting nominal travel: {e}")
            return

    def log_hardstop_pos(self, axis, limit, results):
        """
        Logs the current position of the given axis after it has reached its hardstop in the specified direction.

        Parameters:
            axis (int): The axis number to log the hardstop position for.
            limit (str): The direction of the limit ('Ccw' or 'Cw').
            results (a1.DataCollectionResults): The results of the data collection run.
        """
        position_feedback = results.axis.get(a1.AxisDataSignal.PositionFeedback, axis).points

        # Combine signals into a dictionary for logging
        signals = {
            "Position Error Bit Toggled": self.pos_error_fault,
            "Over Current Bit Toggled": self.over_current_fault,
            "Raw Position Feedback": position_feedback,
        }

        # Log signals to a text file
        log_file_path = os.path.join("logs", f"signal_data_log-{axis}-{limit}-Hardstop.txt")
        self.log_signals_to_file(log_file_path, signals)

        end_position = None  # Initialize variable to store the position feedback

        # Iterate through velocity_command and track zero crossings
        for i, bit in enumerate(self.pos_error_fault):
            if bit == 1:
                end_position = position_feedback[i]
                break  # Stop searching after finding the second zero crossing
        if end_position == None:
            # Iterate through velocity_command and track zero crossings
            for i, bit in enumerate(self.over_current_fault):
                if bit == 1:
                    end_position = position_feedback[i]
                    break  # Stop searching after finding the second zero crossing
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
        
        # Log the position of the current limit
        self.stage_info.info(f'{limit} hardstop Position for {axis}: {end_position}')
        
    def log_limit_pos(self, axis, limit, results):
        """
        Logs the current position of the given axis after it has reached its limit in the specified direction.

        Parameters:
            axis (int): The axis number to log the limit position for.
            limit (str): The direction of the limit ('Ccw' or 'Cw').
            results (a1.DataCollectionResults): The results of the data collection run.
        """
        position_feedback = results.axis.get(a1.AxisDataSignal.PositionFeedback, axis).points

        if limit == 'Ccw':
            # Combine signals into a dictionary for logging
            signals = {
                "Fault Bit Toggled": self.ccw_fault,
                "Position Feedback": position_feedback,
            }

            # Log signals to a text file
            log_file_path = os.path.join("logs", f"signal_data_log-{axis}-Ccw-Limit.txt")
            self.log_signals_to_file(log_file_path, signals)

            end_position = None  # Initialize variable to store the position feedback

            # Iterate through velocity_command and track zero crossings
            for i, bit in enumerate(self.ccw_fault):
                if bit == 1:  # Check if velocity_command is zero
                    end_position = position_feedback[i]
                    break  # Stop searching after finding the second zero crossing
        else:
            # Combine signals into a dictionary for logging
            signals = {
                "Fault Bit Toggled": self.cw_fault,
                "Position Feedback": position_feedback,
            }

            # Log signals to a text file
            log_file_path = os.path.join("logs", f"signal_data_log-{axis}-Cw-Limit.txt")
            self.log_signals_to_file(log_file_path, signals)

            end_position = None  # Initialize variable to store the position feedback

            # Iterate through velocity_command and track zero crossings
            for i, bit in enumerate(self.cw_fault):
                if bit == 1:  # Check if velocity_command is zero
                    end_position = position_feedback[i]
                    break  # Stop searching after finding the second zero crossing

        # Use a nested dictionary to store both 'Ccw' and 'Cw' positions
        if axis not in self.limit_pos:
            self.limit_pos[axis] = {}  # Create a new dictionary for each axis
        
        # Store position with the limit type as key ('Ccw' or 'Cw')
        self.limit_pos[axis][limit] = end_position
        
        # Log the position of the current limit
        self.stage_info.info(f'{limit} limit Position for {axis}: {end_position}')
            
    def calculate_limit_travel(self):
        """
        Calculates the distance between CW and CCW limits for each axis, and
        compares it to the specified limit travel. If the distance is too small,
        it fails the test and logs an error.
        """
        limit_fail_list  = []
        hardstop_fail_list = []
        # Calculate the distance between CW and CCW limits for each axis
        for axis in self.test_axes:
            station_id = self.axis_to_station_map.get(axis)
            if 'Ccw' in self.limit_pos[axis] and 'Cw' in self.limit_pos[axis]:
                ccw_limit_position = self.limit_pos[axis]['Ccw']
                cw_limit_position = self.limit_pos[axis]['Cw']
                limit_distance = abs(cw_limit_position - ccw_limit_position)
                limit_distance = round(limit_distance, 4)
            else:
                self.station_print(f"Axis {axis} is missing one or more limit positions.", station_id=station_id)
            if 'Ccw' in self.hardstop_pos[axis] and 'Cw' in self.hardstop_pos[axis]:
                ccw_hardstop_position = self.hardstop_pos[axis]['Ccw']
                cw_hardstop_position = self.hardstop_pos[axis]['Cw']
                hardstop_distance = abs(cw_hardstop_position - ccw_hardstop_position)
                hardstop_distance = round(hardstop_distance, 4)
            else:
                self.station_print(f"Axis {axis} is missing one or more limit positions.", station_id=station_id)

            limit_spec = float(self.specs_dict.get('LimitToLimitTravel').split()[0])
            hardstop_spec = float(self.specs_dict.get('HardToHard-FirstContact').split()[0])
            
            if limit_distance < limit_spec:
                #limit_failing = (limit_spec - limit_distance)
                self.station_print(f'Axis {axis} is failing with a limit travel of {round(limit_distance, 4)}', station_id=station_id)
                self.stage_info.info(f'Axis {axis} is failing with a limit travel of {round(limit_distance, 4)}')
                limit_fail_list.append(axis)
            else:
                self.data[f"Axis: {axis}"]["Total Travel"] = limit_distance
            if hardstop_distance < hardstop_spec:
                #hardstop_failing = (hardstop_spec - hardstop_distance)
                self.station_print(f'Axis {axis} is failing with a hardstop travel of {round(hardstop_distance, 4)}', station_id=station_id)
                self.stage_info.info(f'Axis {axis} is failing with a limit travel of {round(hardstop_distance, 4)}')
                hardstop_fail_list.append(axis)
            #else:
                #self.data[f"Axis: {axis}"]["Total Travel"] = limit_distance

            self.station_print(f'Axis {axis}: CCW Limit Position = {ccw_limit_position}, CW Limit Position = {cw_limit_position}, Limit Distance = {limit_distance}', station_id=station_id)
            self.station_print(f'Axis {axis}: CCW Hardstop Position = {ccw_hardstop_position}, CW Hardstop Position = {cw_hardstop_position}, Hardstop Distance = {hardstop_distance}', station_id=station_id)
            self.stage_info.info(f'Axis {axis} Distance between Ccw Limit and Cw Limit: {limit_distance}')
            self.stage_info.info(f'Axis {axis} Distance between Ccw hardstop and Cw hardstop: {hardstop_distance}')
            
                
        if len(limit_fail_list) > 0:
            limit_fail = "One or more axes do not meet the minimum limit-to-hardstop distance. Please adjust before moving on."
            self.station_print(limit_fail, station_id=station_id)
            messagebox.showerror("Fail", limit_fail)
            self.release_station = StationManager.release_station(station_id)
            self.release_station()
            self.reenable_run_button()  # Call the callback to re-enable the button
            sys.exit()           

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

        Parameters:
            axis (int): The axis number for which to retrieve data.
            results (a1.DataCollectionResults): The results of the data collection run.
        """
        # Initialize empty lists for the hall sensors and primary feedback
        self.hall_a = []
        self.hall_b = []
        self.hall_c = []
        self.pri_fbk = []
        self.ccw_fault = []
        self.cw_fault = []
        self.pos_error_fault = []
        self.over_current_fault = []

        # Retrieve the drive status points for the specified axis
        halls = results.axis.get(a1.AxisDataSignal.DriveStatus, axis).points
        faults = results.axis.get(a1.AxisDataSignal.AxisFault, axis).points
        # Retrieve the primary feedback points for the specified axis
        self.pri_fbk = results.axis.get(a1.AxisDataSignal.PrimaryFeedback, axis).points

        # Iterate over the drive status points and extract the hall sensor values
        for x in halls:
            self.hall_a.append(1 if ((int(x) & a1.DriveStatus.HallAInput.value) > 0) else 0)
            self.hall_b.append(1 if ((int(x) & a1.DriveStatus.HallBInput.value) > 0) else 0)
            self.hall_c.append(1 if ((int(x) & a1.DriveStatus.HallCInput.value) > 0) else 0)
        for x in faults:
            self.ccw_fault.append(1 if ((int(x) & a1.AxisFault.CcwEndOfTravelLimitFault.value) > 0) else 0)
            self.cw_fault.append(1 if ((int(x) & a1.AxisFault.CwEndOfTravelLimitFault.value) > 0) else 0)
            self.pos_error_fault.append(1 if ((int(x) & a1.AxisFault.PositionErrorFault.value) > 0) else 0)
            self.over_current_fault.append(1 if ((int(x) & a1.AxisFault.OverCurrentFault.value) > 0) else 0)

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
        fault_log_file = os.path.join(self.job_log_dir, f'Strut Checkout Station Fault Log {self.job}.log')
        self.fault_log = logging.getLogger('fault_log')
        fault_handler = logging.FileHandler(fault_log_file)
        fault_handler.setLevel(logging.INFO)
        fault_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        fault_handler.setFormatter(fault_formatter)
        self.fault_log.addHandler(fault_handler)
        self.fault_log.setLevel(logging.INFO)

        # Configure the second log file for limit information logging
        self.stage_log_file = os.path.join(self.job_log_dir, f'{self.job} Stage Info.log')
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
            self.stage_info.info(f'Hall states for {axis} are in the correct order.')
            self.data[f"Axis: {axis}"]["Halls"] = "Passed"
        else:
            self.station_print(f'Hall states for {axis} are NOT in the correct order:', station_id=station_id)
            self.station_print(f'Expected order: {"CW" if encoder_direction == "positive" else "CCW"} sequence', station_id=station_id)
            self.station_print(f'Observed states: {unique_hall_states}', station_id=station_id)
            self.stage_info.info(f'Hall states for {axis} are NOT in the correct order.')
            self.stage_info.info(f'Expected order: {"CW" if encoder_direction == "positive" else "CCW"} sequence')
            self.stage_info.info(f'Observed states: {unique_hall_states}')
            self.data[f"Axis: {axis}"]["Halls"] = "Failed"

        # Log encoder values at each hall state transition
        self.station_print(f'Encoder values at hall transitions for {axis}:', station_id=station_id)
        self.stage_info.info(f'Encoder values at hall transitions for {axis}:')
        for state, value in zip(hall_states, encoder_values):
            self.station_print(f'State {state}: {value}', station_id=station_id)
            self.stage_info.info(f'State {state}: {value}')