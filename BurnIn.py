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
from station_manager_instance import get_station_manager
from exceptions import TestSequenceAbort

from BurnInPlotting import Burn_In_Plotting

sys.path.append(r"K:\10. Released Software\Shared Python Programs\production-2.1")
#sys.path.append(r"C:\Users\tbates\Python\shared")
from Logger import TextLogger
from DecodeFaults import decode_faults

class TestSequenceAbort(Exception):
    def __init__(self, message, shown_message=False):
        super().__init__(message)
        self.shown_message = shown_message

class burn_in():
    def __init__(self, speed, burnin_time, secondary_ui, window, test_axes, nominal_travel, fault_log, stage_info, duty_cycle, folder, stage_type, absolute, job, op, comments, specs_dict, stations, stage_log_file, param_dict):
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
        self.param_dict = param_dict
        
        self.sample_rate = 1000
        
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

        # Initialize station loggers without clearing existing text
        self.station_loggers = {}
        for axis in self.test_axes:
            station_id = self.axis_to_station_map.get(axis)
            if station_id:
                station_widget = self.secondary_ui.station_widgets.get(station_id)
                if station_widget:
                    # Don't clear the text widget, just create a logger for it
                    self.station_loggers[station_id] = TextLogger(station_widget["txt_logs"], clear_existing=False)

        self.window = tk.Tk()
        self.window.withdraw()

        self.cycle_log_position = None  # Add this line
        
        # Register abort callbacks for each station
        for axis in self.test_axes:
            station_id = self.axis_to_station_map[axis]
            self.secondary_ui.register_abort_callback(
                station_id, 
                lambda axis=axis: self.abort_burnin(axis)
            )
        
        self.aborted_stations = []
        self.data_lock = threading.Lock()
        
    def station_print(self, message, station_id=None, overwrite=False):
        """Print a message to specific station(s) text_widget or all stations."""
        if station_id is None:
            for axis in self.test_axes:
                sid = self.axis_to_station_map.get(axis)
                if sid in self.station_loggers:
                    if overwrite:
                        self.station_loggers[sid].write_overwrite(message + "\n")
                    else:
                        self.station_loggers[sid].write(message + "\n")
        else:
            if not isinstance(station_id, list):
                station_id = [station_id]
            
            for sid in station_id:
                if sid in self.station_loggers:
                    if overwrite:
                        self.station_loggers[sid].write_overwrite(message + "\n")
                    else:
                        self.station_loggers[sid].write(message + "\n")

    def reset_stdout(self):
        """
        Reset sys.stdout to its original value.
        """
        sys.stdout = sys.__stdout__

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
        spec = self.param_dict.get(spec_key)
        if spec is None:
            raise ValueError(f"Specification '{spec_key}' not found in specs_dict")
        
        try:
            return spec if isinstance(spec, float) else float(spec.split()[0])
        except (AttributeError, ValueError) as e:
            raise ValueError(f"Could not convert {spec_key}={spec} to float: {e}")
        
    def initialize_burnin(self, station_controllers):
        """Initialize burn-in with station controllers."""
        self.station_controllers = station_controllers
        
        self.list_commands = []
        self.list_velocity = []
        try:
            for axis in self.test_axes:
                self.list_commands.append(self.nominal_travel / 2)
                self.list_velocity.append(self.speed)
            try:
                self.movetostart()
                time.sleep(2)
            except TestSequenceAbort as e:
                raise
            try:
                self.increase_speed()
                time.sleep(2)
            except TestSequenceAbort as e:
                raise
            try:
                self.four_hour_burnin()
                time.sleep(2)
            except TestSequenceAbort as e:
                raise
            try:
                plot = Burn_In_Plotting(self.axis_data, self.stage_type, self.burnin_time, self.job, self.op, self.comments, self.folder, self.secondary_ui, self.specs_dict, self.stations, self.test_axes)
                plot.generate_plots() 

                messagebox.showinfo('Burn-In Complete', f'Burn-in complete on {self.current_date} at {self.current_time}')
            except TestSequenceAbort as e:
                raise
        except Exception as e:
            self.station_print(f"Burn-In Aborted: {str(e)}")
            messagebox.showerror("Burn-In Aborted", str(e))
        finally:
            self.perform_burnin_cleanup()

    def movetostart(self):
        """Move all axes to their starting positions in parallel."""
        threads = []
        def move_axis(axis):
            station_id = self.axis_to_station_map.get(axis)
            if station_id in self.aborted_stations:
                raise TestSequenceAbort(f"Test aborted for station {station_id}", shown_message=True)
                
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
            except TestSequenceAbort as e:
                return
        
        try:
            # Start all axis moves in parallel
            for axis in self.test_axes:
                thread = self.create_tracked_thread(target=move_axis, axis=axis, args=(axis,))
                threads.append(thread)
                thread.start()
            
            # Wait for all moves to complete
            for thread in threads:
                thread.join()
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

    def increase_speed(self):
        speed_increment = float(self.speed/5)      
        list_speed = [i-i for i in self.list_velocity]
        count = 1
        
        try:
            while count <= 5:
                # Check for aborted stations at start of each cycle
                for axis in self.test_axes:
                    station_id = self.axis_to_station_map[axis]
                    if station_id in self.aborted_stations:
                        raise TestSequenceAbort(f"Test aborted for station {station_id}", shown_message=True)
                
                try:
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
                except TestSequenceAbort as e:
                    return
        except TestSequenceAbort as e:
            raise
        time.sleep(3)
        
    def round_to_nearest(self, value, multiple):
        return round(value / multiple) * multiple
    
    def burn_in_data(self, cycle):
        """Collect burn-in data for all axes in parallel, issuing motion once per cycle."""
        move_complete = threading.Event()
        start_barrier = threading.Barrier(len(self.test_axes) + 1)
        
        def execute_moves():
            try:
                # Wait until all collectors have started data collection
                start_barrier.wait()
                # Execute the shared motion sequence once for all axes
                self.forward_move(self.dwell, self.list_velocity)
                self.reverse_move(self.dwell, self.list_velocity)
            finally:
                # Ensure the event is set even if an exception occurs, so collector threads don't hang
                move_complete.set()
        
        def collect_axis_data(axis):
            controller = self.station_controllers[axis]
            station_id = self.axis_to_station_map.get(axis)
            #self.station_print(f'Collecting Data for cycle number: {cycle}', station_id=station_id)
            
            n = int(self.sample_rate * self.total_time)
            freq = a1.DataCollectionFrequency.Frequency1kHz
            data_config = self.data_config(n, freq, axis)
            
            # Start data collection first so the entire motion is captured
            controller.runtime.data_collection.start(a1.DataCollectionMode.Snapshot, data_config)
            
            # Signal that this collector is ready and wait for motion to begin
            start_barrier.wait()
            
            # Wait for the shared motion to complete
            move_complete.wait()
            
            # Retrieve results for this axis
            results = controller.runtime.data_collection.get_results(data_config, n)
            data_sample = self.populate(results, axis)
            
            # Store data sample for this axis and cycle with a shared lock
            with self.data_lock:
                if cycle not in self.axis_data:
                    self.axis_data[cycle] = {}
                self.axis_data[cycle][axis] = data_sample
        
        # Launch data collection threads for each axis
        collector_threads = []
        for axis in self.test_axes:
            thread = self.create_tracked_thread(target=collect_axis_data, axis=axis, args=(axis,))
            collector_threads.append(thread)
            thread.start()
        
        # Start shared motion once for all axes
        move_thread = self.create_tracked_thread(target=execute_moves)
        move_thread.start()
        
        # Wait for collectors, then ensure motion thread finished
        for thread in collector_threads:
            thread.join()
        move_thread.join()

    def four_hour_burnin(self):
        """Execute burn-in process with proper cycle counting for parallel operations."""
        
        self.stage_info.info(f'Burn in started for {self.job}, On Station(s): {", ".join(self.test_axes)}')
        
        self.axis_data = {}
        
        # Calculate timing parameters
        self.cycle_time = self.nominal_travel / self.speed
        self.dwell = self.calculate_dwell_time(self.cycle_time, self.duty_cycle)
        self.total_time = self.cycle_time + self.dwell
        
        # Calculate total cycles and data collection intervals
        total_seconds = self.burnin_time * 3600
        self.cycles = self.round_to_nearest(total_seconds / self.total_time, 100)
        # Calculate data interval in cycles (30 minutes worth of cycles)
        base_interval = max(1, int(self.round_to_nearest(1800 / self.total_time, 2)))
        # Ensure data_interval is odd to match our odd-numbered cycles
        data_interval = base_interval + (1 if base_interval % 2 == 0 else 0)
        self.stage_info.info(f'Data collection interval set to every {data_interval} cycles')
        
        cycle = 1
        
        try:
            while cycle <= self.cycles:
                # Check for aborted stations at start of each cycle
                for axis in self.test_axes:
                    station_id = self.axis_to_station_map[axis]
                    if station_id in self.aborted_stations:
                        raise TestSequenceAbort(f"Test aborted for station {station_id}", shown_message=True)
                
                try:
                    self.current_date = datetime.date.today()
                    self.current_time = datetime.datetime.now().time()
                    
                    # Log cycle progress
                    self._log_cycle_progress(cycle)
                    
                    # Collect data at intervals or first cycle
                    should_collect = cycle == 1 or cycle % data_interval == 0
                    if should_collect:
                        self.stage_info.info(f"Collecting data for cycle {cycle}")
                        self.burn_in_data(cycle)
                    else:
                        # Execute moves without data collection
                        self.forward_move(self.dwell, self.list_velocity)
                        self.reverse_move(self.dwell, self.list_velocity)
                    
                    # Always increment by 2 after completing the cycle
                    cycle += 2
                except TestSequenceAbort as e:
                    return
        except TestSequenceAbort as e:
            raise

    def forward_move(self, dwell, speed):
        """Execute forward move for all axes."""
        threads = []
        def move_axis(axis):
            station_id = self.axis_to_station_map[axis]
            if station_id in self.aborted_stations:
                raise TestSequenceAbort(f"Test aborted for station {station_id}", shown_message=True)
                
            controller = self.station_controllers[axis]
            try:
                controller.runtime.commands.motion.moveabsolute(
                    [axis], 
                    [self.list_commands[self.test_axes.index(axis)]], 
                    [speed[self.test_axes.index(axis)]]
                )
                controller.runtime.commands.motion.waitformotiondone([axis])
            except (ControllerAxisFaultException, ControllerOperationException) as e:
                faults_per_axis = self.check_for_faults(controller, [axis])
                if faults_per_axis:
                    # Interactive per-axis handling; do not abort whole sequence here
                    self.handle_faults(faults_per_axis)
                return
            except TestSequenceAbort as e:
                return
            
            # Check again before continuing
            if station_id in self.aborted_stations:
                raise TestSequenceAbort(f"Test aborted for station {station_id}", shown_message=True)

        for axis in self.test_axes:
            thread = self.create_tracked_thread(target=move_axis, axis=axis, args=(axis,))
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        time.sleep(dwell)

    def reverse_move(self, dwell, speed):
        """Execute reverse move for all axes."""
        threads = []
        def move_axis(axis):
            station_id = self.axis_to_station_map[axis]
            if station_id in self.aborted_stations:
                raise TestSequenceAbort(f"Test aborted for station {station_id}", shown_message=True)
                
            controller = self.station_controllers[axis]
            try:
                controller.runtime.commands.motion.moveabsolute(
                    [axis], 
                    [self.list_commands[self.test_axes.index(axis)] * -1],  # Negative for reverse
                    [speed[self.test_axes.index(axis)]]
                )
                controller.runtime.commands.motion.waitformotiondone([axis])
            except (ControllerAxisFaultException, ControllerOperationException) as e:
                faults_per_axis = self.check_for_faults(controller, [axis])
                if faults_per_axis:
                    # Interactive per-axis handling; do not abort whole sequence here
                    self.handle_faults(faults_per_axis)
                return
            except TestSequenceAbort as e:
                return
        
            # Check again before continuing
            if station_id in self.aborted_stations:
                raise TestSequenceAbort(f"Test aborted for station {station_id}", shown_message=True)

        for axis in self.test_axes:
            thread = self.create_tracked_thread(target=move_axis, axis=axis, args=(axis,))
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
        """Handle faults per axis with interactive continue/abort. Acknowledges via DecodeFaults."""
        try:
            for axis, faults in faults_per_axis.items():
                # Axis may have already been removed
                controller = self.station_controllers.get(axis)
                if not controller:
                    continue
                
                # Decode and auto-acknowledge faults on this axis's controller
                fault_init = decode_faults({axis: faults}, [axis], controller, self.fault_log)
                decoded_faults = fault_init.get_fault()
                fault_list = decoded_faults.get(axis, [])
                if not fault_list:
                    # Nothing to act on after ack
                    continue
                
                # Prompt user: continue (keep axis) or abort axis
                confirm = messagebox.askyesno(
                    'Axis Fault Detected',
                    f'Axis {axis} has the following faults: {fault_list}.\n\nWould you like to continue testing this axis?'
                )
                if confirm:
                    # Attempt to re-enable axis and continue
                    try:
                        controller.runtime.commands.motion.enable([axis])
                    except Exception:
                        pass
                    self.stage_info.info(f"Continuing after acknowledging faults on axis {axis}: {fault_list}")
                    continue
                else:
                    # Remove only this axis from burn-in
                    self.stage_info.info(f"User chose to abort axis {axis} after faults: {fault_list}")
                    try:
                        self.handle_burnin_error("Axis fault - user chose to abort axis", axis)
                    except Exception:
                        pass
            
            # If no axes remain, stop the test sequence
            if not self.test_axes:
                raise TestSequenceAbort("All axes have been removed from burn-in.", shown_message=True)
        except TestSequenceAbort:
            raise

    def _log_cycle_progress(self, cycle):
        """Log cycle progress to file and update UI for each station."""
        cycle_log_message = f'Cycle Number: {cycle}/{self.cycles} at {self.current_date} {self.current_time}'
        
        # Log to file
        if self.cycle_log_position is None:
            with open(self.stage_log_file, 'a') as log_file:
                self.cycle_log_position = log_file.tell()
                log_file.write(cycle_log_message + '\n')
        else:
            with open(self.stage_log_file, 'r+') as log_file:
                log_file.seek(self.cycle_log_position)
                log_file.write(cycle_log_message + '\n')
        
        # Update UI for each station using station_print
        for axis in self.test_axes:
            station_id = self.axis_to_station_map[axis]
            self.station_print(cycle_log_message + '\n', station_id=station_id, overwrite=True)

    def handle_burnin_error(self, error, axis):
        """Handle errors during burn-in."""
        self.stage_info.info(f"Handling burn-in error on station {axis}")
        
        # Release just this station
        station_id = self.axis_to_station_map[axis]  # Get station directly from the map
        
        if station_id:
            #station_manager = get_station_manager()
            #station_manager.release_stations(station_id)
            #station_manager.refresh_station_status()
            self.secondary_ui.update_station_status(station_id, running=False, serial="")
            controller = self.station_controllers[axis]
            controller.runtime.commands.motion.disable([axis])
            
            # Remove this axis from testing
            if axis in self.test_axes:
                self.test_axes.remove(axis)
                self.stage_info.info(f"Removed {axis} from test_axes")
            if axis in self.station_controllers:
                del self.station_controllers[axis]
                self.stage_info.info(f"Removed {axis} from station_controllers")
        else:
            self.stage_info.error(f"Could not find station_id for axis {axis}")

    def create_tracked_thread(self, target, axis=None, station_id=None, args=()):
        """
        Create a thread and track it for cleanup.
        
        Args:
            target: The function to run in the thread
            axis: The axis associated with the thread (optional for non-motion threads)
            station_id: The station ID associated with the thread (optional)
            args: Arguments to pass to the target function
        """
        thread = threading.Thread(target=target, args=args)
        thread.axis = axis
        thread.station_id = station_id or (self.axis_to_station_map.get(axis) if axis else None)
        if not hasattr(self, 'active_threads'):
            self.active_threads = []
        self.active_threads.append(thread)
        return thread

    def cleanup_data_structures(self, station_id, axis):
        """
        Clean up data structures and threads for a station during burn-in
        """
        # Clear axis-related data structures
        if axis in self.test_axes:
            self.test_axes.remove(axis)
        
        if axis in self.station_controllers:
            del self.station_controllers[axis]

        # Clear station-related data structures
        if station_id in self.station_loggers:
            del self.station_loggers[station_id]

        # Clear burn-in specific data
        if hasattr(self, 'axis_data') and axis in self.axis_data:
            del self.axis_data[axis]
        
        # Thread cleanup
        if hasattr(self, 'active_threads'):
            threads_to_remove = []
            for thread in self.active_threads:
                if (thread.axis == axis or 
                    (thread.station_id is not None and thread.station_id == station_id)):
                    if thread.is_alive():
                        thread.join(timeout=1.0)
                    threads_to_remove.append(thread)
            
            for thread in threads_to_remove:
                self.active_threads.remove(thread)

    def perform_burnin_cleanup(self):
        """
        Perform cleanup operations after burn-in completion or abort.
        """
        current_thread = threading.current_thread()

        # Clean up each station/axis that was being tested
        for axis in list(self.test_axes):  # Create a copy of list since we'll modify it
            try:
                if axis not in self.station_controllers:
                    continue
                
                controller = self.station_controllers[axis]
                controller.runtime.data_collection.stop()
                station_id = self.axis_to_station_map.get(axis)
                
                if station_id and station_id in self.station_loggers:  # Only cleanup stations that belong to this test
                    try:
                        # Print status messages BEFORE cleanup
                        self.station_print("Cleanup complete for station", station_id=station_id)
                        self.station_print(f"Station {station_id} has been released", station_id=station_id)
                        
                        # Update UI and release station only for stations in this test
                        self.secondary_ui.update_station_status(station_id, running=False, serial="")
                        #station_manager = get_station_manager()
                        #station_manager.release_stations(station_id)
                        #station_manager.refresh_station_status()
                        
                        # Do data structure cleanup last
                        self.cleanup_data_structures(station_id, axis)
                        
                    except Exception as cleanup_error:
                        self.station_print(f"Error during cleanup: {str(cleanup_error)}", station_id=station_id)
                        self.fault_log.error(f"Cleanup error for station {station_id}: {str(cleanup_error)}")
            except Exception as e:
                self.fault_log.error(f"Error during cleanup for axis {axis}: {str(e)}")

    def abort_burnin(self, axis):
        """Abort the burn-in process for a specific axis"""
        station_id = self.axis_to_station_map[axis]
        
        if messagebox.askyesno("Confirm Abort", f"Are you sure you want to abort the burn-in for {axis}?"):
            self.aborted_stations.append(station_id)  # Add station to aborted list
        else:
            return