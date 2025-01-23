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

from BurnIn import burn_in

sys.path.append(r"K:\10. Released Software\Systems Manufacturing Support\Shared")
sys.path.append(r"C:\Users\tbates\Python\shared")
from Logger import TextLogger
from DecodeFaults import decode_faults
from sheets_update import Sheets
from RedirectStdout import RedirectStdout

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
        
        self.station_loggers = {}
        for station_id in self.stations:
            station_widget = self.secondary_ui.station_widgets.get(station_id)
            if station_widget:
                self.station_loggers[station_id] = TextLogger(station_widget["txt_logs"])

        # Define a mapping between axis names and station IDs
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
            # Add more mappings as needed
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
    def get_limit_dec(self, axis, limit=None):
            # Retrieve the current configuration for the axis
            electrical_limits = self.controller.runtime.parameters.axes[axis].protection.faultmask
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
    def test(self, controller: a1.Controller, reenable_run_button):
        """
        This method is the main entry point for the hexapod check-out process.

        Parameters:
            controller (a1.Controller): The Aerotech controller object
            reenable_run_button (Callable): A callable to re-enable the "Run" button in the GUI
        """
        self.station_print(f"Starting test for {self.job}.")

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

        self.controller = controller
        self.reenable_run_button = reenable_run_button
        self.init_logger()
        self.fault_log.info(f'Model: {self.stage_type}\nSerial Number: {self.job}\n')
        self.stage_info.info(f'Model: {self.stage_type}\nSerial Number: {self.job}\n')
        
        # Initialize the lists of commands for each axis
        self.list_commands_ccw_pos = []
        self.list_commands_cw_pos = []
        self.list_commands_zero = []
        self.list_velocity = []
        self.list_low_velocity = []
        
        # Set the nominal positions and velocities for each axis
        for axis in self.test_axes:
            self.list_commands_ccw_pos.append((float(self.specs_dict.get('NominalTravel').split()[0]) / 2) * -1)
            self.list_commands_cw_pos.append(float(self.specs_dict.get('NominalTravel').split()[0]) / 2)
            self.list_commands_zero.append(0)
            self.list_velocity.append(self.speed)
            self.list_low_velocity.append(0.5)
        # Set up the motion target mode to Absolute
        #self.controller.runtime.commands.motion_setup.setuptasktargetmode(a1.TargetMode.Absolute)

        #time.sleep(60)
        self.zero_home_offset = 0
        self.max_current_clamp = 10
        self.low_current_clamp = 3.5
        self.nominal_travel = self.specs_dict.get('NominalTravel').split()[0]

        # Set the home offset and fault mask based on the encoder type
        if self.absolute:
            nominal_home_offset = 0
            self.params(home_offset=self.zero_home_offset, current_clamp=self.max_current_clamp, limit='electrical off')
        else:
            self.params(home_offset=self.zero_home_offset, current_clamp=self.max_current_clamp, limit='electrical on')
        
        # Wait for the controller to finish processing the previous commands
        time.sleep(2)
        self.enable_stages()
        time.sleep(5)

    def params(self, home_offset=None, current_clamp=None, limit=None):
        """
        Configure parameters for each connected axis on the controller.

        Args:
            home_offset (int or dict): The home offset value(s) for the axes.
            current_clamp (float): The maximum current clamp value.
            limit (str): The fault mask limits (e.g., 'software on', 'software off').
        """
        def toggle_limits(limit, axis):
            # Retrieve the current configuration for the axis
            electrical_limits = self.controller.runtime.parameters.axes[axis].protection.faultmask
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
        
        for axis in self.test_axes:
            # Retrieve current configuration parameters for the axis
            configured_parameters = self.controller.configuration.parameters.get_configuration()
            if home_offset:
                if self.absolute:
                    if isinstance(home_offset, int):
                        configured_parameters.axes[axis].feedback.auxiliaryabsolutefeedbackoffset.value = home_offset
                    else:
                        configured_parameters.axes[axis].feedback.auxiliaryabsolutefeedbackoffset.value = home_offset[axis]
                else:
                    configured_parameters.axes[axis].homing.homeoffset.value = home_offset
            if current_clamp:
                configured_parameters.axes[axis].protection.limitdebouncedistance.value = 1
                configured_parameters.axes[axis].protection.maxcurrentclamp.value = current_clamp

            if limit:
                electrical_limit_value = toggle_limits(limit, axis)
                configured_parameters.axes[axis].protection.faultmask.value = electrical_limit_value

            # Apply the updated configuration for each axis
            self.controller.configuration.parameters.set_configuration(configured_parameters)

        # Reset the controller to apply changes
        self.controller.reset()
        time.sleep(10)  # Wait for the controller to initialize
        
    def check_for_faults(self):
        """
        This method retrieves the axis fault status for each connected axis and stores the results in a dictionary.

        Returns:
            dict: A dictionary with the axis name as the key and the axis fault status as the value.
        """
        faults = {}  # Initialize an empty dictionary to store results per axis
        
        # Loop through each connected axis
        for axis in self.test_axes:
            # Create a status item configuration to retrieve the axis fault status
            status_item_configuration = a1.StatusItemConfiguration()
            status_item_configuration.axis.add(a1.AxisStatusItem.AxisFault, axis)
            
            # Retrieve the axis fault status for the current axis
            results = self.controller.runtime.status.get_status_items(status_item_configuration)
            
            # Extract the axis fault status as an integer
            axis_faults = int(results.axis.get(a1.AxisStatusItem.AxisFault, axis).value)
            
            # Store the axis fault status in the self.faults dictionary with the axis as the key
            faults[axis] = axis_faults  # Store the result in the dictionary with the axis as the key
            
        return faults
    
    def handle_faults(self, test, faults_per_axis, reenable_run_button):
        """
        This method is called when an axis fault is detected. It handles the fault by asking the user if they want to continue or stop the test.

        Parameters:
            test (str): The name of the test that is being run.
            faults_per_axis (dict): A dictionary of the axis faults, where the key is the axis name and the value is the fault.
            reenable_run_button (Callable): A callable to re-enable the "Run" button in the GUI
        """
        fault_init = decode_faults(faults_per_axis, self.test_axes, self.controller, self.fault_log)
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
                                    # Continue and remove the axis from connected_axes
                                    self.station_print('Turning off software limits and resuming test.', station_id=station_id)
                                    self.params(limit='software off')
                                    self.home_stages()
                                    self.check_hardstop()
                                else:
                                    reenable_run_button()  # Call the callback to re-enable the button
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
                                # Continue and remove the axis from connected_axes
                                self.station_print('Turning off software limits and resuming test.', station_id=station_id)
                                self.params(limit='software off')
                                self.home_stages()
                                self.check_hardstop()
                            else:
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
                        reenable_run_button()  # Call the callback to re-enable the button
                        sys.exit()
                    
        # Update the connected_axes with the updated list
        self.test_axes = updated_connected_axes
        
        # Update the commands for the remaining axes
        self.list_commands_ccw_pos = []
        self.list_commands_cw_pos = []
        self.list_commands_zero = []
        self.list_velocity = []
        self.list_low_velocity = []
        for axis in self.test_axes:
            self.list_commands_ccw_pos.append((float(self.specs_dict.get('NominalTravel').split()[0]) / 2) * -1)
            self.list_commands_cw_pos.append(float(self.specs_dict.get('NominalTravel').split()[0]) / 2)
            self.list_commands_zero.append(0)
            self.list_velocity.append(self.speed)
            self.list_low_velocity.append(0.5)
            
           
    def enable_stages(self):
        """
        Enable the struts and handle any axis faults that may occur during enable.

        This method will enable the struts and handle any axis faults that may occur
        during enable. If an axis fault occurs, it will be handled by removing the
        axis from the connected_axes list and continue with the remaining axes.

        If the hexapod type is HEX150-125HL or HEX150-140HL, the home_stages method
        will be called to home the struts before checking the hardstops.
        """
        self.station_print('Enabling Axes')
        try:
            self.controller.runtime.commands.motion.enable(self.test_axes)
            time.sleep(0.5)
            self.controller.runtime.commands.fault_and_error.acknowledgeall(1)
            self.controller.runtime.commands.motion.enable(self.test_axes)
            
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
                        self.reenable_run_button()  # Call the callback to re-enable the button
                        sys.exit()
                    
            # Update the connected_axes with the updated list
            self.test_axes = updated_connected_axes
            
            self.list_commands_ccw_pos = []
            self.list_commands_cw_pos = []
            self.list_velocity = []
            for axis in self.test_axes:
                self.list_commands_ccw_pos.append((self.specs_dict.get('NominalTravel').split()[0] / 2) * -1)
                self.list_commands_cw_pos.append(self.specs_dict.get('NominalTravel').split()[0] / 2)
                self.list_velocity.append(5)
            
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
        """
        Check the hall sensor sequence for each axis, comparing it to the expected sequence based on the encoder direction.
        """
        self.station_print('Checking Halls')
        hall_check_step = 50
        hall_check_vel = 5
    
        test_time = hall_check_step / hall_check_vel
        n = int(self.sample_rate * test_time)
        freq = a1.DataCollectionFrequency.Frequency1kHz
    
        for axis in self.test_axes:
            self.controller.runtime.commands.execute(f'MoveToLimitCcw({axis})', 1)
            time.sleep(2)
            self.controller.runtime.commands.motion.waitformotiondone([axis], 1)
            station_id = self.axis_to_station_map.get(axis)
            hall_status = []
            encoder_values = []
            
            data_config = self.data_config(n, freq, axis)
    
            # Collect data and move
            self.controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, data_config)
            time.sleep(0.1)
            try:
                self.controller.runtime.commands.motion.enable(axis)
                self.controller.runtime.commands.motion.moveincremental([axis], [hall_check_step], [hall_check_vel])
            except (ControllerAxisFaultException, ControllerOperationException):
                # Handle the axis fault exception
                error_message = "Axis fault occurred during enable. Check fault log"
                faults_per_axis = self.check_for_faults()
            
                fault_init = decode_faults(faults_per_axis, self.test_axes, self.controller, self.fault_log)
                decoded_faults = fault_init.get_fault()
                
                self.fault_log.info(f'A fault occured on {axis}: {decoded_faults}')
                messagebox.showerror("Axis Fault", error_message)
        
                sys.exit()
                
            time.sleep(test_time)

            self.controller.runtime.commands.motion.waitformotiondone([axis], 1)
            
            time.sleep(1)
            results = self.controller.runtime.data_collection.get_results(data_config, n)
            
            self.populate(axis, results)
    
            # Zip the three hall lists together and group them as (c, a, b)
            for c, a, b, encoder in zip(self.hall_c, self.hall_a, self.hall_b, self.pri_fbk):
                hall_state = f"{c}{a}{b}"
                hall_status.append(hall_state)  # Append the hall state as a string
                encoder_values.append(encoder)  # Append the corresponding encoder value
    
            # Use a set to track and filter unique hall states in the order they first appear
            unique_hall_states = []
            unique_encoder_values = []
            seen_states = set()
    
            for state, encoder in zip(hall_status, encoder_values):
                if state not in seen_states:
                    unique_hall_states.append(state)
                    unique_encoder_values.append(encoder)  # Keep track of encoder values for each unique hall state
                    seen_states.add(state)
    
            # Define expected hall state transitions for both directions
            expected_order_cw = ["100", "101", "001", "011", "010", "110"]  # Clockwise order
            expected_order_ccw = expected_order_cw[::-1]  # Counter-clockwise order (reverse)
    
            # Determine encoder direction: check if encoder counts are mostly increasing or decreasing
            encoder_direction = "positive" if sum(y > x for x, y in zip(unique_encoder_values, unique_encoder_values[1:])) > len(unique_encoder_values) // 2 else "negative"
    
            # Rotate observed hall states to match expected start
            if encoder_direction == "positive":
                rotated_hall_states = self.rotate_to_match_start(unique_hall_states, expected_order_cw)
                hall_order_valid = rotated_hall_states == expected_order_cw
            else:
                rotated_hall_states = self.rotate_to_match_start(unique_hall_states, expected_order_ccw)
                hall_order_valid = rotated_hall_states == expected_order_ccw
           
            if len(rotated_hall_states) < 6:
                self.station_print(f'Not all hall states seen on axis {axis}', station_id=station_id)
                self.stage_info.info(f"A fault occured on {axis}. Not all hall states seen.")
            else:    
                self.stage_info.info(f"Hall Cycle for {axis}: {rotated_hall_states}")
                self.stage_info.info(f"Encoder Points for {axis}: {unique_encoder_values}")
                # Output results
                if hall_order_valid:
                    self.station_print(f'Hall sequence passed for axis {axis}', station_id=station_id)
                    self.stage_info.info(f"Axis {axis}: Hall states match the expected order for {encoder_direction} encoder movement.")
                    self.data[f"Axis: {axis}"]["Halls"] = "Passed"
                else:
                    self.stage_info.info(f"Axis {axis}: Hall states do NOT match the expected order for {encoder_direction} encoder movement. Observed: {unique_hall_states}")
                    self.station_print(f'Halls sequence for {axis} does not match encoder direction. Physically check motor direction (Cw) against hall sequence to verify. Potential issues include halls, encoder, or limits (linear motor).', station_id=station_id)
                    confirm = messagebox.askyesno(
                        'Halls',
                        f'Hall states do NOT match the expected order. Does this stage have halls?'
                    )
        
                    if confirm:
                        self.station_print(f'Please address potential motor issue', station_id=station_id)
                        self.reenable_run_button()  # Call the callback to re-enable the button
                        sys.exit()
                    else:
                        pass
                        
                # Check if the encoder direction and hall states are consistent
                if encoder_direction == "positive" and hall_order_valid:
                    self.stage_info.info(f"Axis {axis} is moving in the expected clockwise direction.")
                elif encoder_direction == "negative" and hall_order_valid:
                    self.stage_info.info(f"Axis {axis} is moving in the expected counter-clockwise direction.")
                else:
                    self.station_print(f"Axis {axis} has an unexpected hall state sequence or encoder direction.", station_id=station_id)
                    
                try:
                    self.controller.runtime.commands.motion.moveincremental([axis], [-(hall_check_step/2)], [5])
                except (ControllerAxisFaultException, ControllerOperationException):
                    # Handle the axis fault exception
                    error_message = "Axis fault occurred during enable."
                    faults_per_axis = self.check_for_faults()
                
                    fault_init = decode_faults(faults_per_axis, self.test_axes, self.controller, self.fault_log)
                    decoded_faults = fault_init.get_fault()
                    
                    self.fault_log.info(f'A fault occured on {axis}: {decoded_faults}')
                    messagebox.showerror("Axis Fault", error_message)
                    
                    sys.exit()
                    
                time.sleep(3)
                
                self.controller.runtime.commands.motion.waitformotiondone([axis], 1)
        
                time.sleep(3)
        
        if self.absolute:
            self.absolute_hardstop()
            time.sleep(1)
        else:
            self.home_stages()
            time.sleep(5)
            self.check_hardstop()
            time.sleep(5)
    
    def absolute_hardstop(self):
        """
        This function checks the hardstop travels for all connected axes and then
        calculates the absolute home offset for each axis.
        """
        self.station_print('Checking Hardstop Travels')
        self.abs_ccw_positions = {}
        self.abs_cw_positions = {}
        test = 'absolute hardstop check'
        def attempt_operation(operation):
            """
            Helper function to handle and retry failed operations due to axis faults.
            """
            retries = 0
            retry_limit = 10  # Set a retry limit to prevent infinite loops
            while retries < retry_limit:
                try:
                    operation()  # Attempt the operation
                    break  # Exit the loop if successful
                except (ControllerAxisFaultException, ControllerOperationException):
                    retries += 1
                    faults_per_axis = self.check_for_faults()
                    if faults_per_axis:
                        self.controller.runtime.commands.fault_and_error.acknowledgeall(1)
                        self.controller.runtime.commands.motion.enable(self.test_axes)
                    time.sleep(2)
                if retries == retry_limit:
                    self.station_print(f'Exceeded retry limit with axes: {self.test_axes}. Exiting operation.', station_id=station_id)
                    break
                    
        for axis in self.test_axes:            
            self.controller.runtime.parameters.axes[axis][a1.AxisParameterId.MaxCurrentClamp].value = self.low_current_clamp
        
        attempt_operation(lambda: self.controller.runtime.commands.motion.movefreerun(self.test_axes, [-i for i in self.list_low_velocity]))
        time.sleep(3)
        try:
            self.controller.runtime.commands.motion.waitformotiondone(self.test_axes)
        except ControllerAxisFaultException:
            # Explicitly check for faults after moveabsolute
            faults_per_axis = self.check_for_faults()  # Check for faults
            if faults_per_axis:
                self.controller.runtime.commands.fault_and_error.acknowledgeall(1)
                
        for axis in self.test_axes:
            station_id = self.axis_to_station_map.get(axis)
            attempt_operation(lambda: self.controller.runtime.commands.motion.movefreerun([axis], [-0.5]))
            try:
                self.controller.runtime.commands.motion.waitformotiondone(axis)
            except ControllerAxisFaultException:
                # Explicitly check for faults after moveabsolute
                faults_per_axis = self.check_for_faults()  # Check for faults
                if faults_per_axis:
                    self.controller.runtime.commands.fault_and_error.acknowledgeall(1)
                    self.controller.runtime.commands.motion.enable(axis)
                        
            # Validate limit to hardstop distance.
            status_item_configuration = a1.StatusItemConfiguration()
            status_item_configuration.axis.add(a1.AxisStatusItem.PositionFeedback, axis)
            self.results = self.controller.runtime.status.get_status_items(status_item_configuration)
            ccw_pos_fbk = self.results.axis.get(a1.AxisStatusItem.PositionFeedback, axis).value
            
            self.stage_info.info(f'Ccw Hardstop position for {axis} is {ccw_pos_fbk}')

            self.data[f"Axis: {axis}"]["Absolute value at CCW EOT"] = ccw_pos_fbk
            
            self.abs_ccw_positions[axis] = ccw_pos_fbk
        
        attempt_operation(lambda: self.controller.runtime.commands.motion.movefreerun(self.test_axes, self.list_low_velocity))
        time.sleep(3)
        try:
            self.controller.runtime.commands.motion.waitformotiondone(self.test_axes)
        except ControllerAxisFaultException:
            # Explicitly check for faults after moveabsolute
            faults_per_axis = self.check_for_faults()  # Check for faults
            if faults_per_axis:
                self.controller.runtime.commands.fault_and_error.acknowledgeall(1)
                
        for axis in self.test_axes:
            station_id = self.axis_to_station_map.get(axis)
            attempt_operation(lambda: self.controller.runtime.commands.motion.movefreerun([axis], [0.5]))
            try:
                self.controller.runtime.commands.motion.waitformotiondone(axis)
            except ControllerAxisFaultException:
                # Explicitly check for faults after moveabsolute
                faults_per_axis = self.check_for_faults()  # Check for faults
                if faults_per_axis:
                    self.controller.runtime.commands.fault_and_error.acknowledgeall(1)
                    self.controller.runtime.commands.motion.enable(axis)
                
            # Validate limit to hardstop distance.
            status_item_configuration = a1.StatusItemConfiguration()
            status_item_configuration.axis.add(a1.AxisStatusItem.PositionFeedback, axis)
            self.results = self.controller.runtime.status.get_status_items(status_item_configuration)
            cw_pos_fbk = self.results.axis.get(a1.AxisStatusItem.PositionFeedback, axis).value
            
            self.stage_info.info(f'Cw Hardstop position for {axis} is {cw_pos_fbk}')
            
            self.abs_cw_positions[axis] = cw_pos_fbk
        for axis in self.test_axes:
                travel = (abs(self.abs_ccw_positions[axis]) - abs(self.abs_cw_positions[axis]))
                self.stage_info.info(f'Total travel for {axis} is {travel}')
        self.calculate_home_offset()
        
    def calculate_home_offset(self):
        """
        Calculate the absolute feedback offset for each axis by averaging the CW and CCW hardstop positions.
        Set the absolute feedback offset for each axis using the calculated midpoints.
        """
        self.station_print('Calculating Absolute Offset')
        # Initialize a new dictionary to store midpoints
        self.midpoints = {}
        
        if self.absolute:
            # Iterate over each axis in the positions dictionaries
            for axis in self.abs_ccw_positions:
                ccw_pos = self.abs_ccw_positions[axis]
                cw_pos = self.abs_cw_positions[axis]

                # Calculate the midpoint
                midpoint = (ccw_pos + cw_pos) / 2

                cpu = self.controller.runtime.parameters.axes[axis].units.countsperunit.value

                if cw_pos > ccw_pos:
                    midpoint = (midpoint * cpu) * -1
                else:
                    midpoint = midpoint * cpu

                self.stage_info.info(f'The absolute feedback offset for {axis} is {midpoint}')

            # Optional: Print or log the midpoints to verify
            #print("Midpoints for each axis:", self.midpoints)

            #for axis in self.test_axes:
                configured_parameters = self.controller.configuration.parameters.get_configuration()
                # Following 4 lines along with reset command physically change the values in the active MCD
                configured_parameters.axes[axis].feedback.auxiliaryabsolutefeedbackoffset.value = self.midpoints[axis]
                configured_parameters.axes[axis].protection.maxcurrentclamp.value = self.max_current_clamp
                self.controller.configuration.parameters.set_configuration(configured_parameters)
                
                self.data[f"Axis: {axis}"]["Absolute Position Offset"] = self.midpoints[axis]
        else:
            for axis, limits in self.limit_pos.items():
                for limit_type, strut_limit_pos in limits.items():
                    if limit_type == 'cw':
                        cw_pos = strut_limit_pos
                    elif limit_type == 'ccw':
                        ccw_pos = strut_limit_pos

                # Calculate the midpoint
                midpoint = (ccw_pos + cw_pos) / 2

                configured_parameters = self.controller.configuration.parameters.get_configuration()
                # Following 4 lines along with reset command physically change the values in the active MCD
                configured_parameters.axes[axis].homing.homeoffset.value = self.midpoints[axis]
                self.controller.configuration.parameters.set_configuration(configured_parameters)

                self.data[f"Axis: {axis}"]["Home Offset"] = self.midpoints[axis]
                
        self.controller.reset()
        time.sleep(10)

        self.controller.runtime.commands.motion.enable(self.test_axes)

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
            configured_parameters.axes[axis].protection.softwarelimithigh.value = (((self.specs_dict.get('NominalTravel')) / 2) + 0.1)
            configured_parameters.axes[axis].protection.softwarelimitlow.value = ((((self.specs_dict.get('NominalTravel')) / 2) + 0.1) * -1)
            
            # Apply the new configuration
            self.controller.configuration.parameters.set_configuration(configured_parameters)
        
        # Set additional parameters and reset the controller
        for axis in self.test_axes:
            self.params(self.midpoints[axis], self.max_current_clamp, limit=['electrical on', 'software on'])
        self.controller.reset()
        time.sleep(10)
        
        # Enable the connected axes
        self.controller.runtime.commands.motion.enable(self.test_axes)
        
        # Initialize burn-in process
        BI = burn_in(self.speed, self.burnin_time, self.text_widget, self.window, self.test_axes, self.nominal_travel, self.fault_log, self.stage_info, self.duty_cycle, self.job_log_dir, self.stage_type, self.absolute, self.job, self.op, self.comments, self.limit_log_file)
        BI.initialize_burnin(self.controller)
        
        populate_sheet = Sheets(self.job, self.data)
        populate_sheet.populate_sheet()

        # Home the struts
        self.home_stages()
            
    def home_stages(self):
        """
        Home the struts based on the encoder type. 

        This method attempts to enable or home the connected axes, handling
        any faults that may occur during the process.
        """
        self.station_print('Homing Axes')
        test = 'homing'
        
        def attempt_operation(operation):
            """
            Attempt an operation and handle faults if they occur.

            The operation is retried after faults are handled.
            """
            while True:
                try:
                    operation()  # Attempt the operation (either enable or home)
                    break  # Exit the loop if successful
                except (ControllerAxisFaultException, ControllerOperationException):
                    time.sleep(3)
                    # Check for faults if an exception occurs
                    faults_per_axis = self.check_for_faults()
                    # Handle faults and attempt the operation again
                    self.handle_faults(test, faults_per_axis, self.reenable_run_button)
                    time.sleep(2)
        
        if not self.absolute:
            # Attempt to enable the connected axes
            attempt_operation(lambda: self.controller.runtime.commands.motion.enable(self.test_axes.copy()))
            time.sleep(1)  # Time delay between operations
        
            # Attempt to home the connected axes
            attempt_operation(lambda: self.controller.runtime.commands.motion.home(self.test_axes.copy()))
            time.sleep(1)

            # If no faults, update the "Marker" field for each axis
            for axis in self.test_axes:
                self.data[f"Axis: {axis}"]["Marker"] = "Passed"
        else:
            # Attempt to move the connected axes to zero position
            attempt_operation(lambda: self.controller.runtime.commands.motion.moveabsolute(self.test_axes, self.list_commands_zero, self.list_velocity))
            time.sleep(1)
            
            # Wait for motion to complete
            self.controller.runtime.commands.motion.waitformotiondone(self.test_axes)
            time.sleep(2)
        
            # Check for faults explicitly after moveabsolute
            faults_per_axis = self.check_for_faults()
            if faults_per_axis:
                # Handle any faults before proceeding
                self.handle_faults(test, faults_per_axis, self.reenable_run_button)
        
    def check_hardstop(self):
        """
        Function to check the hardstop travels for each axis.

        This function moves the stage to the Ccw hardstop and records the position.
        It then moves the stage into the Cw hardstop and records the position
        again. The difference between the two positions is the hardstop travel.

        Returns
        -------
        None.
        """
        self.hardstop_pos = {}
        self.limit_pos = {}
        self.station_print('Checking Limits and Hardstops')
        test = 'hardstop and limit check'
        
        def attempt_operation(operation):
            """
            Attempt an operation and handle faults if they occur.

            The operation is retried after faults are handled.
            """
            retries = 0
            retry_limit = 10  # Set a retry limit to prevent infinite loops
            while retries < retry_limit:
                try:
                    operation()  # Attempt the operation
                    break  # Exit the loop if successful
                except (ControllerAxisFaultException, ControllerOperationException):
                    retries += 1
                    faults_per_axis = self.check_for_faults()
                    self.handle_faults(test, faults_per_axis, self.reenable_run_button)
                    time.sleep(2)
                if retries == retry_limit:
                    self.station_print(f'Exceeded retry limit with axes: {self.test_axes}. Exiting operation.')
                    break
    
        test_time = abs(self.list_commands_ccw_pos[1]) / self.list_velocity[1]
        
        def cw_check():
            limit = 'Cw'
            self.enable(test)
            time.sleep(2)
            self.move_to_pos(test, test_time, limit)
            time.sleep(2)
            
            # Explicitly check for faults after moveabsolute
            faults_per_axis = self.check_for_faults()  # Check for faults
            if faults_per_axis:
                self.handle_faults(test, faults_per_axis, self.reenable_run_button)  # Handle any faults before moving forward
            
            self.move_into_limit(test, limit)
            time.sleep(2)
            self.move_into_hardstop(test, limit)
            
            faults_per_axis = self.check_for_faults()  # Check for faults
            if faults_per_axis:
                self.controller.runtime.commands.fault_and_error.acknowledgeall(1)
                time.sleep(2)
            
            self.move_out_of_hardstop(limit)
            
        def ccw_check():
            limit = 'Ccw'
            self.enable(test)
            time.sleep(2)
            self.move_to_pos(test, test_time, limit)
            time.sleep(2)
            
            # Explicitly check for faults after moveabsolute
            faults_per_axis = self.check_for_faults()  # Check for faults
            if faults_per_axis:
                self.handle_faults(test, faults_per_axis, self.reenable_run_button)  # Handle any faults before moving forward
            
            self.move_into_limit(test, limit)
            time.sleep(2)
            self.move_into_hardstop(test, limit)
                
            faults_per_axis = self.check_for_faults()  # Check for faults
            if faults_per_axis:
                self.controller.runtime.commands.fault_and_error.acknowledgeall(1)
                time.sleep(2)
            
            self.move_out_of_hardstop(limit)
           
        # Perform CCW and CW checks
        ccw_check()
        time.sleep(5)
        cw_check()
        time.sleep(5)
        
        for axis in self.test_axes:
            self.data[f"Axis: {axis}"]["Limits"] = "Passed"

        # Reapply parameters and home the struts
        self.params(current_clamp=self.max_current_clamp, limit='electrical on')
    
        # Enable connected axes before homing
        attempt_operation(lambda: self.controller.runtime.commands.motion.enable(self.test_axes.copy()))
        
        # Calculate the limit travel and home the struts
        self.calculate_limit_travel()

        self.marker_to_limit()
        
        BI = burn_in(self.speed, self.burnin_time, self.text_widget, self.window, self.test_axes, self.nominal_travel, self.fault_log, self.stage_info, self.duty_cycle, self.job_log_dir, self.stage_type, self.absolute, self.job, self.op, self.comments, self.limit_log_file)
        BI.initialize_burnin(self.controller)
        
        populate_sheet = Sheets(self.job, self.data)
        populate_sheet.populate_sheet()

        time.sleep(5)
        
        self.home_stages()

        self.station_print("All tests completed.")
    def marker_to_limit(self):
        """
        Move the connected axes to the marker position and log the position.

        This function moves the connected axes to the marker position and logs the position.
        It handles any faults that may occur during the operation and retries if necessary.
        """
        self.station_print('Checking Marker to Limit Distance')
        test = 'marker to limit'
        limit = 'Ccw'
        
        # Change home offset to zero for marker to limit check
        self.params(home_offset=self.zero_home_offset, current_clamp=self.max_current_clamp, limit='electrical on')

        self.home_stages()

        self.move_into_limit(test, limit)

        for axis in self.test_axes:
            # Configuration to retrieve items from the A1 controller
            status_item_configuration = a1.StatusItemConfiguration()
            status_item_configuration.axis.add(a1.AxisStatusItem.PositionFeedback, axis)
            # Retrieve position feedback from the controller
            results = self.controller.runtime.status.get_status_items(status_item_configuration)
            
            # Retrieve position feedback and round to 4 decimal places
            strut_limit_pos = round(results.axis.get(a1.AxisDataSignal.PositionFeedback, axis).value, 4)

            self.data[f"Axis: {axis}"]["Home Marker From Limit"] = strut_limit_pos

        # Reapply parameters and home the struts
        for axis in self.test_axes:
            self.params(home_offset=self.midpoints[axis], current_clamp=self.max_current_clamp, limit='electrical on')

    def enable(self, test):
        """
        Enables the connected axes and handles any faults that may occur.

        Parameters:
            test (str): The name of the test being performed.
        """
        def attempt_operation(operation):
            """
            Helper function to handle and retry failed operations due to axis faults.
            """
            retries = 0
            retry_limit = 10  # Set a retry limit to prevent infinite loops
            while retries < retry_limit:
                try:
                    operation()  # Attempt the operation
                    break  # Exit the loop if successful
                except (ControllerAxisFaultException, ControllerOperationException):
                    retries += 1
                    faults_per_axis = self.check_for_faults()
                    self.handle_faults(test, faults_per_axis, self.reenable_run_button)
                    time.sleep(2)
                if retries == retry_limit:
                    self.station_print(f'Exceeded retry limit with axes: {self.test_axes}. Exiting operation.')
                    break
        # Enable connected axes
        attempt_operation(lambda: self.controller.runtime.commands.motion.enable(self.test_axes))
        time.sleep(1)
        
    def move_to_pos(self, test, test_time, limit):
        """
        Move the connected axes to a specified position based on the given limit.

        Parameters:
            test (str): The name of the test being performed.
            test_time (float): The time to wait after initiating the move.
            limit (str): The direction of the limit ('Ccw' or 'Cw').

        This function attempts to move the connected axes to either the
        counter-clockwise (Ccw) or clockwise (Cw) end of nominal travel.
        It handles any faults that occur during the operation and retries if necessary.
        """
        def attempt_operation(operation):
            """
            Helper function to handle and retry failed operations due to axis faults.
            """
            retries = 0
            retry_limit = 10  # Set a retry limit to prevent infinite loops
            while retries < retry_limit:
                try:
                    operation()  # Attempt the operation
                    break  # Exit the loop if successful
                except (ControllerAxisFaultException, ControllerOperationException):
                    retries += 1
                    faults_per_axis = self.check_for_faults()
                    self.handle_faults(test, faults_per_axis, self.reenable_run_button)
                    time.sleep(2)
                if retries == retry_limit:
                    self.station_print(f'Exceeded retry limit with axes: {self.test_axes}. Exiting operation.')
                    break

        if limit == 'Ccw':
            # Move to CCW end of nominal travel for connected axes
            attempt_operation(lambda: self.controller.runtime.commands.motion.moveabsolute(
                self.test_axes, self.list_commands_ccw_pos, self.list_velocity))
            time.sleep(test_time)
            try:
                self.controller.runtime.commands.motion.waitformotiondone(self.test_axes)
            except ControllerAxisFaultException:
                # Explicitly check for faults after moveabsolute
                faults_per_axis = self.check_for_faults()  # Check for faults
                if faults_per_axis:
                    self.handle_faults(test, faults_per_axis, self.reenable_run_button)  # Handle any faults before moving forward
        else:
            # Move to CW end of nominal travel for connected axes
            attempt_operation(lambda: self.controller.runtime.commands.motion.moveabsolute(
                self.test_axes, self.list_commands_cw_pos, self.list_velocity))
            time.sleep(test_time)
            try:
                self.controller.runtime.commands.motion.waitformotiondone(self.test_axes)
            except ControllerAxisFaultException:
                # Explicitly check for faults after moveabsolute
                faults_per_axis = self.check_for_faults()  # Check for faults
                if faults_per_axis:
                    self.handle_faults(test, faults_per_axis, self.reenable_run_button)  # Handle any faults before moving forward

        time.sleep(1)  # Ensure all operations have completed before proceeding
        
    def move_into_limit(self, test, limit):
        """
        Move the connected axes to a specified limit (CCW or CW) and log the position.

        Parameters:
            test (str): The name of the test being performed.
            limit (str): The direction of the limit ('Ccw' or 'Cw').
        """
        def attempt_operation(operation):
            """
            Helper function to handle and retry failed operations due to axis faults.
            """
            retries = 0
            retry_limit = 10  # Set a retry limit to prevent infinite loops
            while retries < retry_limit:
                try:
                    operation()  # Attempt the operation
                    break  # Exit the loop if successful
                except (ControllerAxisFaultException, ControllerOperationException):
                    retries += 1
                    faults_per_axis = self.check_for_faults()
                    self.handle_faults(test, faults_per_axis, self.reenable_run_button)
                    time.sleep(2)
                if retries == retry_limit:
                    self.station_print(f'Exceeded retry limit with axes: {self.test_axes}. Exiting operation.')
                    break
                
        # For each axis, move to CCW limit and log position
        for axis in self.test_axes:
            attempt_operation(lambda: self.controller.runtime.commands.motion.enable(axis))
            time.sleep(1)
            if limit == 'Ccw':
                attempt_operation(lambda: self.controller.runtime.commands.execute(f'MoveToLimitCcw({axis})', 1))
                time.sleep(3)
                try:
                    self.controller.runtime.commands.motion.waitformotiondone(axis)
                except (ControllerAxisFaultException, ControllerOperationException):
                    # Explicitly check for faults after moveabsolute
                    faults_per_axis = self.check_for_faults()  # Check for faults
                    if faults_per_axis:
                        self.handle_faults(test, faults_per_axis, self.reenable_run_button)  # Handle any faults before moving forward
            else:
                attempt_operation(lambda: self.controller.runtime.commands.execute(f'MoveToLimitCw({axis})', 1))
                time.sleep(3)
                try:
                    self.controller.runtime.commands.motion.waitformotiondone(axis)
                except (ControllerAxisFaultException, ControllerOperationException):
                    # Explicitly check for faults after moveabsolute
                    faults_per_axis = self.check_for_faults()  # Check for faults
                    if faults_per_axis:
                        self.handle_faults(test, faults_per_axis, self.reenable_run_button)  # Handle any faults before moving forward
            
            if test != 'marker to limit':
                # Ensure only active axes are logged
                if axis in self.test_axes:
                    self.log_limit_pos(axis, limit)
            time.sleep(2)

        time.sleep(1)
    
    def move_into_hardstop(self, test, limit):
        """
        Move the connected axes into their hardstops to detect electrical limits. Then turn off the limits, lower the current clamp, 
        and move into the hardstop. Finally, move out of the hardstop and log the position.

        Parameters:
            test (str): The name of the test being performed.
            limit (str): The direction of the limit ('Ccw' or 'Cw').
        """
        def attempt_operation(operation):
            """
            Attempt an operation and handle faults if they occur.

            The operation is retried after faults are handled.
            """
            retries = 0
            retry_limit = 10  # Set a retry limit to prevent infinite loops
            while retries < retry_limit:
                try:
                    operation()  # Attempt the operation
                    break  # Exit the loop if successful
                except (ControllerAxisFaultException, ControllerOperationException):
                    retries += 1
                    faults_per_axis = self.check_for_faults()
                    self.handle_faults(test, faults_per_axis, self.reenable_run_button)
                    time.sleep(2)
                if retries == retry_limit:
                    self.station_print(f'Exceeded retry limit with axes: {self.test_axes}. Exiting operation.')
                    break
        test_time = 1.75
        n = int(self.sample_rate * test_time)
        freq = a1.DataCollectionFrequency.Frequency1kHz
        
        for axis in self.test_axes:
            data_config = self.data_config(n, freq, axis)
            # Set the maximum current clamp to the low value
            self.controller.runtime.parameters.axes[axis][a1.AxisParameterId.MaxCurrentClamp].value = self.low_current_clamp
            # Set the fault mask to disable electrical limits
            limit_dec = self.get_limit_dec(axis, limit='electrical off')
            self.controller.runtime.parameters.axes[axis][a1.AxisParameterId.FaultMask].value = limit_dec
            
            time.sleep(2)
            attempt_operation(lambda: self.controller.runtime.commands.motion.enable(axis))
            time.sleep(1)
            
            if limit == 'Ccw':
                self.controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, data_config)
                attempt_operation(lambda: self.controller.runtime.commands.motion.movefreerun([axis], [-0.25]))
                
                time.sleep(3)
                
                try:
                    self.controller.runtime.commands.motion.waitformotiondone(axis)
                except (ControllerAxisFaultException, ControllerOperationException):
                    # Explicitly check for faults after moveabsolute
                    faults_per_axis = self.check_for_faults()  # Check for faults
                    if faults_per_axis:
                        self.controller.runtime.commands.fault_and_error.acknowledgeall(1)
                        time.sleep(2)   
                # Ensure only active axes are logged
                results = self.controller.runtime.data_collection.get_results(data_config, n)
                if axis in self.test_axes:
                    self.log_hardstop_pos(axis, limit, results)
            else:
                self.controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, data_config)
                attempt_operation(lambda: self.controller.runtime.commands.motion.movefreerun([axis], [0.25]))
                time.sleep(3)
                
                try:
                    self.controller.runtime.commands.motion.waitformotiondone(axis)
                except (ControllerAxisFaultException, ControllerOperationException):
                    # Explicitly check for faults after moveabsolute
                    faults_per_axis = self.check_for_faults()  # Check for faults
                    if faults_per_axis:
                        self.controller.runtime.commands.fault_and_error.acknowledgeall(1)
                        time.sleep(2)   
                results = self.controller.runtime.data_collection.get_results(data_config, n)
                # Ensure only active axes are logged
                if axis in self.test_axes:
                    self.log_hardstop_pos(axis, limit, results)
                
            time.sleep(2)
        time.sleep(1)   
    
    def move_out_of_hardstop(self, limit):
        """
        Move the connected axes out of their hardstops in the specified direction.

        Parameters:
            limit (str): The direction of the limit ('Ccw' or 'Cw').
        """
        if limit == 'Ccw':
            # Move out of the hardstop in the Ccw direction
            for axis in self.test_axes:
                self.controller.runtime.commands.motion.enable([axis])
                self.controller.runtime.commands.motion.moveincremental([axis], [((float(self.specs_dict.get('NominalTravel').split()[0])) / 2)], [1])
                self.controller.runtime.commands.motion.waitformotiondone([axis])
                
                # Explicitly check for faults after moveabsolute
                faults_per_axis = self.check_for_faults()  # Check for faults
                if faults_per_axis:
                    self.controller.runtime.commands.fault_and_error.acknowledgeall(1)
                try:
                    self.controller.runtime.commands.motion.waitformotiondone(axis)
                except (ControllerAxisFaultException, ControllerOperationException):
                    # Explicitly check for faults after moveabsolute
                    faults_per_axis = self.check_for_faults()  # Check for faults
                    if faults_per_axis:
                        self.controller.runtime.commands.fault_and_error.acknowledgeall(1)  # Handle any faults before moving forward
                        
                time.sleep(2)
        else:
            # Move out of the hardstop in the Cw direction
            for axis in self.test_axes:
                self.controller.runtime.commands.motion.enable([axis])
                self.controller.runtime.commands.motion.moveincremental([axis], [(((float(self.specs_dict.get('NominalTravel').split()[0])) / 2) * -1)], [1])
                self.controller.runtime.commands.motion.waitformotiondone([axis])
                
                # Explicitly check for faults after moveabsolute
                faults_per_axis = self.check_for_faults()  # Check for faults
                if faults_per_axis:
                    self.controller.runtime.commands.fault_and_error.acknowledgeall(1)
                try:
                    self.controller.runtime.commands.motion.waitformotiondone(axis)
                except (ControllerAxisFaultException, ControllerOperationException):
                    # Explicitly check for faults after moveabsolute
                    faults_per_axis = self.check_for_faults()  # Check for faults
                    if faults_per_axis:
                        self.controller.runtime.commands.fault_and_error.acknowledgeall(1)  # Handle any faults before moving forward
                        
                time.sleep(2)
                    
        for axis in self.test_axes:
            # Set the maximum current clamp to the low value
            self.controller.runtime.parameters.axes[axis][a1.AxisParameterId.MaxCurrentClamp].value = self.max_current_clamp
            # Set the fault mask to disable electrical limits
            limit_dec = self.get_limit_dec(axis, limit='electrical on')
            self.controller.runtime.parameters.axes[axis][a1.AxisParameterId.FaultMask].value = limit_dec
            
            
    def log_hardstop_pos(self, axis, limit, results):
        """
        Logs the current position of the given axis after it has reached its hardstop in the specified direction.

        Parameters:
            axis (int): The axis number to log the hardstop position for.
            limit (str): The direction of the limit ('Ccw' or 'Cw').
            results (a1.DataCollectionResults): The results of the data collection run.
        """
        axis = str(axis)
        
        position_feedback = results.axis.get(a1.AxisDataSignal.PositionFeedback, axis).points
        current_feedback = results.axis.get(a1.AxisDataSignal.CurrentFeedback, axis).points
        print(current_feedback)
        # Ensure all values in current_feedback are positive
        current_feedback = [abs(value) for value in current_feedback]

        position_at_clamp = None  # Initialize variable to store the position feedback

        for i, value in enumerate(current_feedback):
            if value >= self.low_current_clamp:
                # Record the corresponding position_feedback value
                position_at_clamp = position_feedback[i]
                break

        # Retrieve the primary feedback points for the specified axis
        #self.pri_fbk = results.axis.get(a1.AxisDataSignal.PrimaryFeedback, axis).points
        # Configuration to retrieve items from the A1 controller
        #status_item_configuration = a1.StatusItemConfiguration()
        #status_item_configuration.axis.add(a1.AxisDataSignal.PositionFeedback, axis)
        
        # Retrieve position feedback from the controller
        #results = self.controller.runtime.status.get_status_items(status_item_configuration)
        
        # Retrieve position feedback and round to 4 decimal places
        #stage_hardstop_pos = round(results.axis.get(a1.AxisDataSignal.PositionFeedback, axis).value, 4)
        
        # Use a nested dictionary to store both 'Ccw' and 'Cw' positions
        if axis not in self.hardstop_pos:
            self.hardstop_pos[axis] = {}  # Create a new dictionary for each axis
        
        # Store position with the limit type as key ('Ccw' or 'Cw')
        self.hardstop_pos[axis][limit] = position_at_clamp
        
        # Log the position of the current limit
        self.stage_info.info(f'{limit} hardstop Position for {axis}: {position_at_clamp}')
        
    def log_limit_pos(self, axis, limit):
        """
        Logs the current position of the given axis after it has reached its limit in the specified direction.

        Parameters:
            axis (int): The axis number to log the limit position for.
            limit (str): The direction of the limit ('Ccw' or 'Cw').
        """
        # Configuration to retrieve items from the A1 controller
        status_item_configuration = a1.StatusItemConfiguration()
        status_item_configuration.axis.add(a1.AxisStatusItem.PositionFeedback, axis)
        # Retrieve position feedback from the controller
        results = self.controller.runtime.status.get_status_items(status_item_configuration)

        # Retrieve position feedback and round to 4 decimal places
        stage_limit_pos = round(results.axis.get(a1.AxisDataSignal.PositionFeedback, axis).value, 4)
        
        # Use a nested dictionary to store both 'Ccw' and 'Cw' positions
        if axis not in self.limit_pos:
            self.limit_pos[axis] = {}  # Create a new dictionary for each axis
        
        # Store position with the limit type as key ('Ccw' or 'Cw')
        self.limit_pos[axis][limit] = stage_limit_pos
        
        # Log the position of the current limit
        self.stage_info.info(f'{limit} limit Position for {axis}: {stage_limit_pos}')
            
    def calculate_limit_travel(self):
        """
        Calculates the distance between CW and CCW limits for each axis, and
        compares it to the specified limit travel. If the distance is too small,
        it fails the test and logs an error.
        """
        limit_fail_list  = []
        hardstop_fail_list = []
        print(f'Limit Position: {self.limit_pos}')
        print(f'Hardstop Position: {self.hardstop_pos}')
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
                hardstop_distance = round(limit_distance, 4)
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
            if hardstop_distance < limit_spec:
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
        data_config.axis.add(a1.AxisDataSignal.PrimaryFeedback, axis)
        data_config.axis.add(a1.AxisDataSignal.PositionFeedback, axis)
        data_config.axis.add(a1.AxisDataSignal.CurrentCommand, axis)
        data_config.axis.add(a1.AxisDataSignal.CurrentFeedback, axis)

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

        # Retrieve the drive status points for the specified axis
        halls = results.axis.get(a1.AxisDataSignal.DriveStatus, axis).points

        # Retrieve the primary feedback points for the specified axis
        self.pri_fbk = results.axis.get(a1.AxisDataSignal.PrimaryFeedback, axis).points

        # Iterate over the drive status points and extract the hall sensor values
        for x in halls:
            self.hall_a.append(1 if ((int(x) & a1.DriveStatus.HallAInput.value) > 0) else 0)
            self.hall_b.append(1 if ((int(x) & a1.DriveStatus.HallBInput.value) > 0) else 0)
            self.hall_c.append(1 if ((int(x) & a1.DriveStatus.HallCInput.value) > 0) else 0)
    def init_logger(self):
        """
        Initialize the logging system for the strut checkout station.

        Creates two log files: one for fault logging and one for limit information logging.
        Configures the loggers and handlers for both log files.
        """
        # Create the root directory for logs if it doesn't exist
        base_log_dir = r"O:\Strut Checkout"
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
        stage_log_file = os.path.join(self.job_log_dir, f'{self.job} Stage Info.log')
        self.stage_info = logging.getLogger('stage_info')
        stage_handler = logging.FileHandler(stage_log_file)
        stage_handler.setLevel(logging.INFO)
        stage_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        stage_handler.setFormatter(stage_formatter)
        self.stage_info.addHandler(stage_handler)
        self.stage_info.setLevel(logging.INFO)