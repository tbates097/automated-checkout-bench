# -*- coding: utf-8 -*-
"""
Created on Tue Oct 15 12:20:18 2024

@author: TBates
"""
import sys
import os
import time
import logging
import datetime
from tkinter import messagebox
import tkinter as tk
import automation1 as a1
from automation1.internal.exceptions_gen import ControllerAxisFaultException, ControllerOperationException
import threading
from station_manager import StationManager

from BurnInPlotting import Burn_In_Plotting

#sys.path.append(r"K:\10. Released Software\Systems Manufacturing Support\Shared")
sys.path.append(r"C:\Users\tbates\Python\shared")
from Logger import TextLogger
from DecodeFaults import decode_faults

class burn_in():
    def __init__(self, speed, burnin_time, secondary_ui, window, test_axes, nominal_travel, fault_log, stage_info, duty_cycle, folder, stage_type, absolute, job, op, comments, specs_dict, stations, stage_log_file, release_stations_func):
        #self.stage_type = stage_type
        self.speed = speed
        self.burnin_time = burnin_time
        self.secondary_ui = secondary_ui
        self.window = window
        self.test_axes = test_axes
        self.nominal_travel = nominal_travel
        self.fault_log = fault_log
        self.stage_info = stage_info
        self.duty_cycle = duty_cycle
        self.folder = folder
        self.stage_type = stage_type
        self.absolute = absolute
        self.job = job
        self.op = op
        self.comments = comments
        self.specs_dict = specs_dict
        self.stations = stations
        self.stage_log_file = stage_log_file
        self.release_stations = release_stations_func  # Store the release function
        
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

        self.cycle_log_position = None  # Add this line
        
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

    def initialize_burnin(self, station_controllers):
        """Initialize burn-in with station controllers."""
        self.station_controllers = station_controllers
        
        self.list_commands = []
        self.list_velocity = []
        
        for axis in self.test_axes:
            self.list_commands.append(float(self.specs_dict.get('NominalTravel').split()[0]) / 2)
            self.list_velocity.append(self.speed)
        
        self.movetostart()

    def movetostart(self):
        """Move all axes to their starting positions in parallel."""
        threads = []
        def move_axis(axis):
            controller = self.station_controllers[axis]
            try:
                controller.runtime.commands.motion.moveabsolute(
                    [axis], 
                    [-1 * self.list_commands[self.test_axes.index(axis)]],
                    [self.list_velocity[self.test_axes.index(axis)]]
                )
                controller.runtime.commands.motion.waitformotiondone([axis])
            except (ControllerAxisFaultException, ControllerOperationException):
                faults_per_axis = self.check_for_faults(controller, [axis])
                if faults_per_axis:
                    controller.runtime.commands.fault_and_error.acknowledgeall(1)
                time.sleep(2)
        
        # Start all axis moves in parallel
        for axis in self.test_axes:
            thread = threading.Thread(target=move_axis, args=(axis,))
            threads.append(thread)
            thread.start()
        
        # Wait for all moves to complete
        for thread in threads:
            thread.join()
        time.sleep(2)
        
        self.increase_speed()
        
    def increase_speed(self):
        speed_increment = float(self.speed/5)      
        list_speed = [i-i for i in self.list_velocity]
        count = 1
        
        while count <= 5:
            list_speed = [i+speed_increment for i in list_speed]
            cycle_time = self.nominal_travel / list_speed[0]
            
            dwell = self.calculate_dwell_time(cycle_time, self.duty_cycle)
            
            self.forward_move(dwell, list_speed)
                
            count += 1
            if count < 5:
                list_speed = [i+speed_increment for i in list_speed]
                cycle_time = self.nominal_travel / list_speed[0]
                
                dwell = self.calculate_dwell_time(cycle_time, self.duty_cycle)
            
            self.reverse_move(dwell, list_speed)
            
            count += 1
            
        time.sleep(1)

        self.four_hour_burnin()
        
    def round_to_nearest(self, value, multiple):
        return round(value / multiple) * multiple
    
    def burn_in_data(self, cycle):
        """Collect burn-in data for all axes in parallel."""
        move_complete = threading.Event()
        
        def execute_moves():
            self.forward_move(self.dwell, self.list_velocity)
            self.reverse_move(self.dwell, self.list_velocity)
            move_complete.set()
        
        def collect_axis_data(axis):
            controller = self.station_controllers[axis]
            station_id = self.axis_to_station_map.get(axis)
            self.station_print(f'Collecting Data for cycle number: {cycle}', station_id=station_id)
            
            n = int(self.sample_rate * self.total_time)
            freq = a1.DataCollectionFrequency.Frequency1kHz
            data_config = self.data_config(n, freq, axis)
            
            # Start data collection
            controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, data_config)
            
            # Wait for moves to complete
            move_complete.wait()
            
            # Get results
            results = controller.runtime.data_collection.get_results(data_config, n)
            data_sample = self.populate(results, axis)
            
            with threading.Lock():
                if cycle not in self.axis_data:
                    self.axis_data[cycle] = {}
                self.axis_data[cycle][axis] = data_sample
        
        # Start data collection threads
        threads = []
        for axis in self.test_axes:
            thread = threading.Thread(target=collect_axis_data, args=(axis,))
            threads.append(thread)
            thread.start()
        
        # Execute moves in separate thread
        move_thread = threading.Thread(target=execute_moves)
        move_thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        move_thread.join()

    def four_hour_burnin(self):
        """Execute burn-in process with proper cycle counting for parallel operations."""
        current_date = datetime.date.today()
        current_time = datetime.datetime.now().time()
        self.stage_info.info(f'Burn in started on {current_date} at {current_time}')
        
        self.axis_data = {}
        
        # Calculate timing parameters
        self.cycle_time = self.nominal_travel / self.speed
        self.dwell = self.calculate_dwell_time(self.cycle_time, self.duty_cycle)
        self.total_time = self.cycle_time + self.dwell
        
        # Calculate total cycles and data collection intervals
        total_seconds = self.burnin_time * 3600
        self.cycles = self.round_to_nearest(total_seconds / self.total_time, 100)
        data_interval = self.round_to_nearest(1800 / self.total_time, 1)  # Data every 30 minutes
        
        cycle = 1
        data_cycle = 1
        
        try:
            while cycle <= self.cycles:
                self.current_date = datetime.date.today()
                self.current_time = datetime.datetime.now().time()
                
                # Log cycle progress
                self._log_cycle_progress(cycle)
                
                # Collect data at intervals or first cycle
                if cycle == 1 or cycle % data_interval == 0:
                    self.burn_in_data(cycle)
                    data_cycle = cycle
                else:
                    # Execute moves without data collection
                    self.forward_move(self.dwell, self.list_velocity)
                    self.reverse_move(self.dwell, self.list_velocity)
                
                cycle += 1
                
        except Exception as e:
            self.handle_burnin_error(e)
            return
        
        plot = Burn_In_Plotting(self.axis_data, self.stage_type, self.burnin_time, self.job, self.op, self.comments, self.folder, self.secondary_ui, self.specs_dict, self.stations, self.test_axes)
        plot.generate_plots()
        
        messagebox.showinfo('Burn-In Complete', f'Burn-in complete on {self.current_date} at {self.current_time}')

    def forward_move(self, dwell, speed):
        """Execute forward move for all axes."""
        # Move each axis in parallel
        threads = []
        def move_axis(axis):
            controller = self.station_controllers[axis]
            try:
                controller.runtime.commands.motion.moveabsolute(
                    [axis], 
                    [self.list_commands[self.test_axes.index(axis)]], 
                    [speed[self.test_axes.index(axis)]]
                )
            except (ControllerAxisFaultException, ControllerOperationException):
                faults_per_axis = self.check_for_faults(controller, [axis])
                if faults_per_axis:
                    controller.runtime.commands.fault_and_error.acknowledgeall(1)
        
            time.sleep(dwell)
            
            try:
                controller.runtime.commands.motion.waitformotiondone([axis])
            except (ControllerAxisFaultException, ControllerOperationException):
                faults_per_axis = self.check_for_faults(controller, [axis])
                if faults_per_axis:
                    controller.runtime.commands.fault_and_error.acknowledgeall(1)
        
        for axis in self.test_axes:
            thread = threading.Thread(target=move_axis, args=(axis,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        time.sleep(dwell)

    def reverse_move(self, dwell, speed):
        """Execute reverse move for all axes."""
        # Move each axis in parallel
        threads = []
        def move_axis(axis):
            controller = self.station_controllers[axis]
            try:
                controller.runtime.commands.motion.moveabsolute(
                    [axis], 
                    [self.list_commands[self.test_axes.index(axis)] * -1],  # Negative for reverse
                    [speed[self.test_axes.index(axis)]]
                )
            except (ControllerAxisFaultException, ControllerOperationException):
                faults_per_axis = self.check_for_faults(controller, [axis])
                if faults_per_axis:
                    controller.runtime.commands.fault_and_error.acknowledgeall(1)
        
            time.sleep(dwell)
            
            try:
                controller.runtime.commands.motion.waitformotiondone([axis])
            except (ControllerAxisFaultException, ControllerOperationException):
                faults_per_axis = self.check_for_faults(controller, [axis])
                if faults_per_axis:
                    controller.runtime.commands.fault_and_error.acknowledgeall(1)
        
        for axis in self.test_axes:
            thread = threading.Thread(target=move_axis, args=(axis,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        time.sleep(dwell)

    def data_config(self, n, freq, axis):
        #Data configurations. These are how to configure data collection parameters
        data_config = a1.DataCollectionConfiguration(n, freq)  #Freq should be 20x the max frequency required by end process
        data_config.system.add(a1.SystemDataSignal.DataCollectionSampleTime)
        data_config.axis.add(a1.AxisDataSignal.PositionFeedback, axis)
        data_config.axis.add(a1.AxisDataSignal.PositionError, axis)
        data_config.axis.add(a1.AxisDataSignal.CurrentCommand, axis)
        data_config.axis.add(a1.AxisDataSignal.CurrentFeedback, axis) 
        data_config.axis.add(a1.AxisDataSignal.AccelerationCommand, axis)
        
        return data_config
    
    def populate(self, result, axis):
        """
        Separates the primary feedback data for each axis from the results.
        
        Parameters:
            results (dict): A dictionary where keys are axes and values are the result objects 
                            containing axis data for each move.
        
        Returns:
            dict: A dictionary where keys are axis names and values are the primary feedback points.
        """
        # Initialize an empty dictionary to store data for each axis
        separated_data = {}
    
        try:
            # Retrieve the signal data for the current axis from the result object
            position_feedback = result.axis.get(a1.AxisDataSignal.PositionFeedback, axis).points
            position_error = result.axis.get(a1.AxisDataSignal.PositionError, axis).points
            current_command = result.axis.get(a1.AxisDataSignal.CurrentCommand, axis).points
            current_feedback = result.axis.get(a1.AxisDataSignal.CurrentFeedback, axis).points
            acceleration_command = result.axis.get(a1.AxisDataSignal.AccelerationCommand, axis).points
            
            # Store all the signal data in a dictionary for this axis
            separated_data = {
                "PositionFeedback": position_feedback,
                "PositionError": position_error,
                "CurrentCommand": current_command,
                "CurrentFeedback": current_feedback,
                "AccelerationCommand": acceleration_command
            }
        except Exception as e:
            # Handle any exceptions (like if data is missing for an axis)
            for axis in self.test_axes:
                station_id = self.axis_to_station_map.get(axis)
                self.station_print(f"Error retrieving data for axis {axis}: {e}", station_id=station_id)
            separated_data = None  # Use None or another placeholder for missing data
    
        return separated_data

    def calculate_dwell_time(self, total_cycle_time, duty_cycle):
        """
        Calculate the required dwell time to maintain the given duty cycle.
        
        Parameters:
        total_cycle_time (float): The total cycle time in seconds (active + idle time).
        duty_cycle (float): The desired duty cycle as a percentage (e.g., 25 for 25%).
        
        Returns:
        float: The calculated dwell time in seconds.
        """
        # Calculate active time based on duty cycle
        active_time = (duty_cycle / 100) * total_cycle_time
        # Calculate dwell time as the remaining time in the cycle
        dwell_time = total_cycle_time - active_time
        return dwell_time
    
    def check_for_faults(self, controller, axes):
        """Check for faults on specific axes."""
        faults = {}
        for axis in axes:
            status_item_configuration = a1.StatusItemConfiguration()
            status_item_configuration.axis.add(a1.AxisStatusItem.AxisFault, axis)
            results = controller.runtime.status.get_status_items(status_item_configuration)
            axis_faults = int(results.axis.get(a1.AxisStatusItem.AxisFault, axis).value)
            faults[axis] = axis_faults
        return faults
    
    def handle_faults(self, faults_per_axis):
        """Handle faults for specific axes."""
        for axis, faults in faults_per_axis.items():
            controller = self.station_controllers[axis]
            fault_init = decode_faults({axis: faults}, [axis], controller, self.fault_log)
            decoded_faults = fault_init.get_fault()
            
            if decoded_faults[axis]:
                messagebox.showerror(
                    'An Axis Fault Occurred',
                    f'Axis {axis} has the following faults: {decoded_faults[axis]}'
                )

    def _log_cycle_progress(self, cycle):
        cycle_log_message = f'Cycle Number: {cycle}/{self.cycles} at {self.current_date} {self.current_time}'
        
        if self.cycle_log_position is None:
            with open(self.stage_log_file, 'a') as log_file:
                self.cycle_log_position = log_file.tell()
                log_file.write(cycle_log_message + '\n')
        else:
            with open(self.stage_log_file, 'r+') as log_file:
                log_file.seek(self.cycle_log_position)
                log_file.write(cycle_log_message + '\n')

    def handle_burnin_error(self, error, axis):
        """Handle errors during burn-in for a specific axis."""
        station_id = self.axis_to_station_map.get(axis)
        self.station_print(f"Error on axis {axis}: {str(error)}", station_id=station_id)
        self.fault_log.error(f"Burn-in error on axis {axis}: {str(error)}")
        
        # Remove this axis from active testing
        if axis in self.test_axes:
            self.test_axes.remove(axis)
        
        # Release just this station
        station = next((s for s in self.stations if self.station_states[s]["axis_name"] == axis), None)
        if station:
            self.release_station = StationManager.release_station(station)
            self.release_station()
        # If no axes left, end the test
        if not self.test_axes:
            messagebox.showerror("Test Stopped", "All axes have encountered errors. Ending test.")
            return False
        
        return True

# =============================================================================
#     def init_logger(self):
#         # Create the root directory for logs if it doesn't exist
#         base_log_dir = r"O:\Strut Checkout"
#         os.makedirs(base_log_dir, exist_ok=True)
#         
#         # Create a subdirectory for the current job using self.job
#         job_log_dir = os.path.join(base_log_dir, self.job)
#         os.makedirs(job_log_dir, exist_ok=True)
#         
#         # Configure the first log file for fault logging
#         fault_log_file = os.path.join(job_log_dir, f'Strut Checkout Station Fault Log {self.job}.log')
#         self.fault_log = logging.getLogger('fault_log')
#         fault_handler = logging.FileHandler(fault_log_file)
#         fault_handler.setLevel(logging.INFO)
#         fault_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
#         fault_handler.setFormatter(fault_formatter)
#         self.fault_log.addHandler(fault_handler)
#         self.fault_log.setLevel(logging.INFO)
#         
#         # Configure the second log file for limit information logging
#         limit_log_file = os.path.join(job_log_dir, f'{self.job} Limit Info.log')
#         self.stage_info = logging.getLogger('limit_info')
#         limit_handler = logging.FileHandler(limit_log_file)
#         limit_handler.setLevel(logging.INFO)
#         limit_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
#         limit_handler.setFormatter(limit_formatter)
#         self.stage_info.addHandler(limit_handler)
#         self.stage_info.setLevel(logging.INFO)
# =============================================================================