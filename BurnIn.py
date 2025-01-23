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

from BurnInPlotting import Burn_In_Plotting

sys.path.append(r"K:\10. Released Software\Systems Manufacturing Support\Shared")
sys.path.append(r"C:\Users\tbates\Python\shared")
from Logger import TextLogger
from DecodeFaults import decode_faults

class burn_in():
    def __init__(self, speed, burnin_time, text_widget, window, connected_axes, nominal_travel, fault_log, stage_info, duty_cycle, folder, stage_type, encoder, job, op, comments, log_file_path):
        #self.stage_type = stage_type
        self.speed = speed
        self.burnin_time = burnin_time
        self.text_widget = text_widget
        self.window = window
        self.connected_axes = connected_axes
        self.nominal_travel = nominal_travel
        self.fault_log = fault_log
        self.stage_info = stage_info
        self.duty_cycle = duty_cycle
        self.folder = folder
        self.stage_type = stage_type
        self.encoder = encoder
        self.job = job
        self.op = op
        self.comments = comments
        self.log_file_path = log_file_path
        
        self.sample_rate = 1000
        
        self.text_logger = TextLogger(text_widget)
        sys.stdout = self.text_logger

        self.window = tk.Tk()
        self.window.withdraw()
    
    def initialize_burnin(self, controller: a1.Controller):
        self.controller = controller
    
        self.list_velocity = []
        self.list_commands = []
        for axis in self.connected_axes:
            self.list_commands.append(self.nominal_travel/2)
            self.list_velocity.append(self.speed)
       
        self.movetostart()
        
    def movetostart(self):
        try:
            self.controller.runtime.commands.motion.moveabsolute(self.connected_axes, [-1 * i for i in self.list_commands], self.list_velocity)
        except (ControllerAxisFaultException, ControllerOperationException):
            faults_per_axis = self.check_for_faults()
            self.handle_faults(faults_per_axis)
            time.sleep(2)
        
        try:
            self.controller.runtime.commands.motion.waitformotiondone(self.connected_axes)
        except (ControllerAxisFaultException, ControllerOperationException):
            faults_per_axis = self.check_for_faults()
            self.handle_faults(faults_per_axis)
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
        print(f'Collecting Data for cycle number: {cycle}')
        n = int(self.sample_rate * self.total_time)

        freq = a1.DataCollectionFrequency.Frequency1kHz
        
        for axis in self.connected_axes:
            data_config = self.data_config(n, freq, axis)
            
            self.collect_data(data_config)
            time.sleep(0.5)
            # Forward Move
            self.forward_move(self.dwell, self.list_velocity)
            
            self.reverse_move(self.dwell, self.list_velocity)
            
            results = self.controller.runtime.data_collection.get_results(data_config, n)
            
            self.data_sample = self.populate(results, axis)
            
            # If this is the first axis for this cycle, initialize the cycle in axis_data
            if cycle not in self.axis_data:
                self.axis_data[cycle] = {}
        
            # Store the data for the current axis within the current cycle
            self.axis_data[cycle][axis] = self.data_sample

    def four_hour_burnin(self):
        current_date = datetime.date.today()
        current_time = datetime.datetime.now().time()
        self.stage_info.info(f'Burn in started on {current_date} at {current_time}')
        # Variable to store file position of cycle counter log
        cycle_log_position = None
        
        self.axis_data = {}
        
        self.cycle_time = (self.nominal_travel / self.speed)

        self.dwell = self.calculate_dwell_time(self.cycle_time, self.duty_cycle)
        
        self.total_time = (self.cycle_time) + (self.dwell)
        
        self.cycles = (self.burnin_time*3600) / self.total_time
        self.cycles = self.round_to_nearest(self.cycles, 100)

        #self.cycles = 1
        data_interval = 1800 / self.total_time
        data_interval = self.round_to_nearest(data_interval, 1)
        #data_increment = data_interval
        
        cycle = 1
        data_cycle = 1
        
        while cycle <= self.cycles:
            self.current_date = datetime.date.today()
            self.current_time = datetime.datetime.now().time()
            
            # Log cycle counters with overwriting capability
            cycle_log_message = f'Cycle Number: {cycle}/{self.cycles} at {self.current_date} {self.current_time}'
            
            # If it's the first log, get the file position
            if cycle_log_position is None:
                # Log the message for the first time and store its file position
                with open(self.log_file_path, 'a') as log_file:
                    cycle_log_position = log_file.tell()  # Get the current position
                    log_file.write(cycle_log_message + '\n')
            else:
                # Overwrite the previous cycle log entry
                with open(self.log_file_path, 'r+') as log_file:
                    log_file.seek(cycle_log_position)  # Go back to the position
                    log_file.write(cycle_log_message + '\n')
            if data_cycle == 1 or abs(cycle - data_cycle) <= 1:
                self.burn_in_data(cycle)
                
                cycle += len(self.connected_axes) * 2
                data_cycle += data_interval
            else:
                self.forward_move(self.dwell, self.list_velocity)
                
                # Increment Counter
                cycle += 1
                
                self.reverse_move(self.dwell, self.list_velocity)
                
                # Increment Counter
                cycle += 1

        plot = Burn_In_Plotting(self.axis_data, self.stage_type, self.encoder, self.burnin_time, self.job, self.op, self.comments, self.folder,self.text_widget)
        plot.generate_plots()
        
        messagebox.showinfo('Burn-In Complete', f'Burn-in complete on {self.current_date} at {self.current_time}')    
        
    def forward_move(self, dwell, speed):
        # Forward Move
        try:
            self.controller.runtime.commands.motion.moveabsolute(self.connected_axes, self.list_commands, speed)
        except (ControllerAxisFaultException, ControllerOperationException):
            faults_per_axis = self.check_for_faults()
            self.handle_faults(faults_per_axis)
            
        time.sleep(dwell)
        
        try:
            self.controller.runtime.commands.motion.waitformotiondone(self.connected_axes, 1)
        except (ControllerAxisFaultException, ControllerOperationException):
            faults_per_axis = self.check_for_faults()
            self.handle_faults(faults_per_axis)
            
        time.sleep(dwell)
            
    def reverse_move(self, dwell, speed):       
        # Reverse Move
        try:
            self.controller.runtime.commands.motion.moveabsolute(self.connected_axes, [i*-1 for i in self.list_commands], speed)
        except (ControllerAxisFaultException, ControllerOperationException):
            faults_per_axis = self.check_for_faults()
            self.handle_faults(faults_per_axis)
            
        time.sleep(dwell)
        
        try:
            self.controller.runtime.commands.motion.waitformotiondone(self.connected_axes, 1)
        except (ControllerAxisFaultException, ControllerOperationException):
            faults_per_axis = self.check_for_faults()
            self.handle_faults(faults_per_axis)
            
        time.sleep(dwell)
            
    def collect_data(self, data_config):
        # Collect data for each axis
        #for axis, config in data_config.items():
        self.controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, data_config)

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
            print(f"Error retrieving data for axis {axis}: {e}")
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
    
    def check_for_faults(self):
        faults = {}  # Initialize an empty dictionary to store results per axis
        #decoded_faults_per_axis = {}  # Dictionary to store decoded faults for each axis
        
        for axis in self.connected_axes:
            status_item_configuration = a1.StatusItemConfiguration()
            status_item_configuration.axis.add(a1.AxisStatusItem.AxisFault, axis)
            
            # Get the results for the current axis
            results = self.controller.runtime.status.get_status_items(status_item_configuration)
            
            # Extract the axis fault status as an integer
            axis_faults = int(results.axis.get(a1.AxisStatusItem.AxisFault, axis).value)

            # Store the axis_faults in the self.faults dictionary with the axis as the key
            faults[axis] = axis_faults  # Store the result in the dictionary with the axis as the key
            
        return faults
    
    def handle_faults(self, faults_per_axis):
        fault_init = decode_faults(faults_per_axis, self.connected_axes, self.controller, self.fault_log)
        decoded_faults = fault_init.get_fault()
        
        for axis, faults in decoded_faults.items():
            if faults:
                messagebox.showerror(
                    'An Axis Fault Occurred',
                    f'Axis {axis} has the following faults: {faults}.?'
                )
                
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
