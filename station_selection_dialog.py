"""
Station Selection Dialog

This module provides a popup dialog for selecting stations either automatically
or manually for the automated checkout bench system.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from station_manager_instance import get_station_manager
from ui_styles import *


class StationSelectionDialog:
    def __init__(self, parent, num_stations, program_id, serial_number, test_params):
        self.parent = parent
        self.num_stations = num_stations
        self.program_id = program_id
        self.serial_number = serial_number  # This will be unused in new workflow
        self.test_params = test_params  # Test parameters from main UI
        self.result = None
        self.selected_stations = []
        self.stage_serials = []  # Store serial numbers for each stage
        
        # Get station manager instance
        self.station_manager = get_station_manager()
        if not self.station_manager:
            raise RuntimeError("Station manager not initialized")
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Station Selection")
        
        # Set dialog properties
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Apply unified styling
        apply_dialog_styling(self.dialog)
        
        # Initialize UI
        self._setup_ui()
        
        # Let dialog size itself based on content, then center it
        self._auto_size_and_center()
        
        # Initialize station options
        self._update_station_options()
    
    def _auto_size_and_center(self):
        """Automatically size dialog based on content and center it"""
        # Update to get natural size
        self.dialog.update_idletasks()
        
        # Get the natural size the dialog wants to be
        self.dialog.geometry('')  # Clear any size constraints
        self.dialog.update_idletasks()
        
        # Get actual required size
        req_width = self.dialog.winfo_reqwidth()
        req_height = self.dialog.winfo_reqheight()
        
        # Set minimum dimensions
        final_width = max(req_width, 500)
        final_height = max(req_height, 300)
        
        # Center on screen with the calculated size
        center_window_on_screen(self.dialog, final_width, final_height)
    
    
    def _setup_ui(self):
        """Setup the dialog UI components"""
        # Main frame
        main_frame = tk.Frame(self.dialog, bg=BACKGROUND, bd=0, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = tk.Label(
            main_frame, 
            text="Station Assignment", 
            font=("Segoe UI", 14, "bold"),
            **main_label_style
        )
        title_label.pack(pady=(0, 15))
        
        # Info label
        info_text = f"Select stations for {self.num_stations} stage{'s' if self.num_stations > 1 else ''}"
        info_label = tk.Label(
            main_frame, 
            text=info_text,
            font=("Segoe UI", 10),
            **supporting_label_style
        )
        info_label.pack(pady=(0, 20))
        
        # Job Number section (added above station assignment)
        job_frame = tk.LabelFrame(
            main_frame, 
            text="Job Number", 
            **labelframe_style,
            padx=15, 
            pady=15
        )
        job_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Job number entry and button
        job_entry_frame = tk.Frame(job_frame, bg=BACKGROUND)
        job_entry_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Job number label and entry
        job_label = tk.Label(
            job_entry_frame,
            text="Job Number:",
            font=("Segoe UI", 10),
            **supporting_label_style
        )
        job_label.pack(side=tk.LEFT, padx=(0, 10))
        
        self.job_number_var = tk.StringVar()
        self.job_number_entry = tk.Entry(
            job_entry_frame,
            textvariable=self.job_number_var,
            width=20,
            font=("Segoe UI", 10)
        )
        self.job_number_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        # Get Smart String button
        get_smart_string_btn = tk.Button(
            job_entry_frame,
            text="Get Smart String",
            command=self._get_smart_string,
            font=("Segoe UI", 10),
            **action_button_style
        )
        get_smart_string_btn.pack(side=tk.LEFT)
        
        # Station selection frame (removed mode selection)
        # User must select both stations and enter serial numbers
        station_frame = tk.LabelFrame(
            main_frame, 
            text="Station & Serial Number Assignment", 
            **labelframe_style,
            padx=15, 
            pady=15
        )
        station_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        self.manual_frame = station_frame  # Keep reference for existing code
        
        # Create dropdown and serial number frames for each stage
        self.stage_vars = []
        self.stage_combos = []
        self.serial_vars = []
        self.serial_entries = []
        
        # Ensure the manual frame expands to show all content
        for i in range(self.num_stations):
            stage_frame = tk.Frame(self.manual_frame, bg=BACKGROUND, bd=0, relief="flat")
            stage_frame.pack(fill=tk.X, pady=8, padx=10)
            
            # Stage label
            stage_label = tk.Label(
                stage_frame,
                text=f"Stage {i + 1}:",
                font=("Segoe UI", 10),
                width=8,
                **supporting_label_style
            )
            stage_label.pack(side=tk.LEFT, padx=(0, 10))
            
            # Station dropdown
            stage_var = tk.StringVar()
            stage_combo = ttk.Combobox(
                stage_frame,
                textvariable=stage_var,
                state="readonly",
                width=12,
                font=("Segoe UI", 10)
            )
            stage_combo.pack(side=tk.LEFT, padx=(0, 15))
            stage_combo.bind("<<ComboboxSelected>>", 
                           lambda e, idx=i: self._on_station_selected(idx))
            
            # Serial number entry
            serial_label = tk.Label(
                stage_frame,
                text="Serial:",
                font=("Segoe UI", 10),
                **supporting_label_style
            )
            serial_label.pack(side=tk.LEFT, padx=(0, 5))
            
            serial_var = tk.StringVar()
            serial_entry = tk.Entry(
                stage_frame,
                textvariable=serial_var,
                width=15,
                font=("Segoe UI", 10)
            )
            serial_entry.pack(side=tk.LEFT)
            
            # Remove automatic smart string fetching - now done manually via job number
            
            self.stage_vars.append(stage_var)
            self.stage_combos.append(stage_combo)
            self.serial_vars.append(serial_var)
            self.serial_entries.append(serial_entry)
        
        # Smart String display section (added below manual frame)
        smart_frame = tk.LabelFrame(
            main_frame, 
            text="Configuration", 
            **labelframe_style,
            padx=15, 
            pady=15
        )
        smart_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Smart string display
        smart_label = tk.Label(
            smart_frame,
            text="Smart String:",
            font=("Segoe UI", 10),
            **supporting_label_style
        )
        smart_label.pack(anchor=tk.W, pady=(0, 5))
        
        self.smart_string_var = tk.StringVar(value="Enter job number and click 'Get Smart String'")
        self.smart_string_entry = tk.Entry(
            smart_frame,
            textvariable=self.smart_string_var,
            state="readonly",
            width=60,
            font=("Segoe UI", 10)
        )
        self.smart_string_entry.pack(fill=tk.X)
        
        # Button frame
        button_frame = tk.Frame(main_frame, bg=BACKGROUND, bd=0)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        # Refresh button (left side)
        refresh_btn = tk.Button(
            button_frame,
            text="Refresh Stations",
            command=self._refresh_stations,
            width=15,
            font=("Segoe UI", 10),
            **supporting_label_style
        )
        refresh_btn.pack(side=tk.LEFT)
        
        # Cancel button
        cancel_btn = tk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
            width=12,
            font=("Segoe UI", 10),
            **cancel_button_style
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(10, 0))
        
        # OK button
        ok_btn = tk.Button(
            button_frame,
            text="OK",
            command=self._on_ok,
            width=12,
            font=("Segoe UI", 11),
            **action_button_style
        )
        ok_btn.pack(side=tk.RIGHT)
        
        # Handle window close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
    
    
    
    def _refresh_stations(self):
        """Manually refresh station availability and update dropdowns"""
        try:
            self.station_manager.refresh_station_status()
        except Exception:
            pass
        self._update_station_options()
    
    def _update_station_options(self):
        """Update the available station options for each dropdown"""
        if not self.station_manager:
            return
        
        # For manual selection, include both "free" and "offline" stations
        # Only exclude stations that are currently "in-use"
        all_stations = self.station_manager.station_dict
        available_stations = {
            station: ip for station, ip in all_stations.items()
            if self.station_manager.station_states.get(station, {}).get("status") != "in-use"
        }
        
        available_station_names = list(available_stations.keys())
        
        # Get currently selected stations to exclude from other dropdowns
        currently_selected = []
        for var in self.stage_vars:
            if var.get() and var.get() != "":
                currently_selected.append(var.get())
        
        # Update each dropdown
        for i, combo in enumerate(self.stage_combos):
            # Get current selection
            current_selection = self.stage_vars[i].get()
            
            # Create options list (exclude already selected stations except current)
            options = [""] + [
                station for station in available_station_names 
                if station not in currently_selected or station == current_selection
            ]
            
            # Update combobox values
            combo['values'] = options
            
            # Restore selection if it's still valid
            if current_selection in options:
                self.stage_vars[i].set(current_selection)
            elif current_selection not in available_station_names:
                # Clear if the station is no longer available
                self.stage_vars[i].set("")
    
    def _on_station_selected(self, stage_index):
        """Handle when a station is selected in a dropdown"""
        # Update all other dropdowns to reflect the new selection
        self._update_station_options()
    
    def _get_smart_string(self):
        """Handle Get Smart String button click - query BigQuery using job number"""
        job_number = self.job_number_var.get().strip()
        if not job_number:
            messagebox.showwarning("Missing Job Number", "Please enter a job number")
            return
        
        if len(job_number) < 6:
            messagebox.showwarning("Invalid Job Number", "Job number must be at least 6 characters")
            return
            
        # Use the job number directly for BigQuery lookup
        self._query_smart_string(job_number)
    
    def _query_smart_string(self, job_number):
        """Query BigQuery for smart string using job number"""
        try:
            from google.cloud import bigquery
            import os
            
            client = bigquery.Client()
            
            # Read query from file (same as existing logic in UI.py)
            query_path = os.path.join(os.path.dirname(__file__), "query.txt")
            with open(query_path, 'r') as f:
                query_template = f.read()
            query = query_template.replace("@jobnum", f"'{job_number}'")
            
            query_job = client.query(query)
            results = query_job.result()
            rows = list(results)
            
            if rows:
                row = rows[0]
                part_num = getattr(row, 'PartNum', None)
                part_desc = getattr(row, 'PartDescription', None)
                
                if part_desc:  # part_desc contains the smart string
                    self.smart_string_var.set(part_desc)
                    # Store for later use
                    self.smart_string = part_desc
                    self.part_number = part_num
                else:
                    self.smart_string_var.set("No smart string found for this job number")
                    self.smart_string = None
                    self.part_number = None
            else:
                self.smart_string_var.set("No data found for this job number")
                self.smart_string = None
                self.part_number = None
                
        except Exception as e:
            self.smart_string_var.set(f"Error querying database: {str(e)}")
            self.smart_string = None
            self.part_number = None
    
    def _parse_part_number_from_smart_string(self, smart_string):
        """Parse part number from smart string (same logic as UI.py)"""
        if not smart_string:
            return None
        
        smart_string_str = str(smart_string)
        
        if smart_string_str.isdigit():
            return None
        
        try:
            parts = smart_string_str.split('-')
            if not parts or len(parts) < 2:
                return None
            
            # Remove SLE or SL suffix from PRO series
            if parts[0].startswith('PRO'):
                part_number = parts[0].rstrip('SLE').rstrip('SL')
            else:
                part_number = parts[0]
            
            return part_number
            
        except Exception as e:
            print(f"Error parsing smart string '{smart_string}': {str(e)}")
            return None
    
    def _on_ok(self):
        """Enhanced OK button - handles station selection, configuration, and test initialization"""
        
        # Step 1: Validate and collect serial numbers
        serial_numbers = []
        for i, serial_var in enumerate(self.serial_vars):
            serial = serial_var.get().strip()
            if not serial:
                messagebox.showwarning(
                    "Missing Serial Number",
                    f"Please enter a serial number for Stage {i + 1}"
                )
                return
            serial_numbers.append(serial)
        
        # Step 2: Validate station selection (always manual now)
        selected_stations = []
        for i, var in enumerate(self.stage_vars):
            station = var.get()
            if not station or station == "":
                messagebox.showwarning(
                    "Incomplete Selection",
                    f"Please select a station for Stage {i + 1}"
                )
                return
            selected_stations.append(station)
        
        # Check for duplicates
        if len(set(selected_stations)) != len(selected_stations):
            messagebox.showerror(
                "Duplicate Selection",
                "Each stage must be assigned to a different station"
            )
            return
        
        # Step 3: Allocate the selected stations
        # Skip real-time availability check - if user selected it and it was available
        # when the dialog opened, proceed with allocation. Actual connectivity will be
        # tested when initializing controllers.
        try:
            for i, station in enumerate(selected_stations):
                self.station_manager.set_station_in_use(
                    station, serial_numbers[i], self.program_id
                )
            
            allocated_stations = selected_stations
        except Exception as e:
            messagebox.showerror("Allocation Error", f"Error allocating stations: {str(e)}")
            return
        
        # Step 4: Parse part number from smart string (if available)
        if hasattr(self, 'smart_string') and self.smart_string:
            part_number = self._parse_part_number_from_smart_string(self.smart_string)
        else:
            messagebox.showerror(
                "Configuration Required",
                "Please enter a valid serial number to fetch stage configuration"
            )
            return
        
        if not part_number:
            messagebox.showerror(
                "Invalid Configuration",
                "Could not parse part number from smart string. Please verify the serial number."
            )
            return
        
        # Step 5: Launch BallscrewSizer.App configuration
        try:
            from PyQt5.QtWidgets import QApplication
            from BallscrewSizer import App
            
            app = QApplication.instance()
            if app is None:
                app = QApplication([])
            
            app_instance = App()
            config_selections, param_dict = app_instance.show_popup_config_dialog(stage=part_number)
            
            if not config_selections:
                messagebox.showinfo("Configuration Cancelled", "Stage configuration was cancelled.")
                # Clean up allocated stations
                try:
                    self.station_manager.release_stations(allocated_stations)
                except:
                    pass
                return
            
            # Step 6: Initialize checkout test with all collected data
            self._initialize_checkout_test(
                allocated_stations=allocated_stations,
                serial_numbers=serial_numbers,
                config_selections=config_selections,
                param_dict=param_dict,
                part_number=part_number
            )
            
            app_instance.deleteLater()
            del app_instance
            app.quit()
            
        except Exception as e:
            messagebox.showerror(
                "Configuration Error",
                f"Error during stage configuration: {str(e)}"
            )
            # Clean up allocated stations
            try:
                self.station_manager.release_stations(allocated_stations)
            except:
                pass
            return
        
        # Close dialog after successful initialization
        self.dialog.destroy()
    
    def _initialize_checkout_test(self, allocated_stations, serial_numbers, config_selections, param_dict, part_number):
        """Initialize and start the checkout test with collected parameters"""
        import threading
        from checkout_test import stage_checkout
        import automation1 as a1
        from tkinter import messagebox
        import sys
        import time
        
        # Get secondary_ui using the dedicated registry module
        import UI
        import secondary_ui_registry
        
        secondary_ui = secondary_ui_registry.get_secondary_ui()
        wait_count = 0
        while secondary_ui is None and wait_count < 20:  # Wait up to 2 seconds
            time.sleep(0.1)
            secondary_ui = secondary_ui_registry.get_secondary_ui()
            wait_count += 1
            if wait_count % 5 == 0:  # Print every 0.5 seconds
                print(f"DEBUG: Still waiting for secondary_ui, attempt {wait_count}, registry value: {secondary_ui}, global value: {UI.secondary_ui}")
        
        if secondary_ui is None:
            messagebox.showerror(
                "Test Error",
                "Secondary UI not initialized. Please ensure the main UI has started the secondary UI."
            )
            return
        
        def run_checkout_test():
            # Ensure worker thread has the same working directory as main thread
            import os
            main_cwd = os.getcwd()
            
            try:
                # Initialize controllers for allocated stations (matching original pattern)
                # First create station_controllers dictionary like the original
                station_controllers = {
                    self.station_manager.station_states[station]["axis_name"]: 
                    self.station_manager.station_dict[station]
                    for station in allocated_stations
                }
                
                initialized_controllers = {}
                for axis_name, ip_address in station_controllers.items():
                    try:
                        print(f"Connecting to {axis_name} at {ip_address}...")
                        controller = a1.Controller.connect(host=ip_address)
                        controller.start()
                        initialized_controllers[axis_name] = controller
                        print(f"Successfully connected to {axis_name} at {ip_address}")
                    except Exception as e:
                        # Clean up any initialized controllers
                        for ctrl in initialized_controllers.values():
                            try:
                                if ctrl and hasattr(ctrl, 'disconnect'):
                                    ctrl.disconnect()
                            except:
                                pass
                        raise RuntimeError(f"Failed to connect to {axis_name}: {str(e)}")
                
                # Validate serial_numbers before accessing index 0
                if not serial_numbers or len(serial_numbers) == 0:
                    raise ValueError("No serial numbers provided")
                
                # Create stage checkout instance with enhanced parameters
                stage_test = stage_checkout(
                    stage_type=part_number,
                    speed=self.test_params['speed'],
                    burnin_time=self.test_params['burnin_time'],
                    job=serial_numbers[0][:6],  # Use job number from first serial
                    op=self.test_params['operator'],
                    comments=self.test_params['comments'],
                    secondary_ui=secondary_ui,  # Use the secondary_ui from main thread
                    window=self.parent,
                    num_axes=self.num_stations,
                    test_axes=allocated_stations,
                    duty_cycle=self.test_params['duty_cycle'],
                    specs_dict=config_selections,
                    absolute=self.test_params['absolute'],
                    stations=[int(s[2:]) for s in allocated_stations],
                    param_dict=param_dict,
                    bus_voltage=self.test_params['bus_voltage'],
                    serial_numbers=serial_numbers,  # Pass individual serial numbers
                    full_smart_string=getattr(self, 'smart_string', None),
                    part_number=part_number  # Pass parsed part number for database JSON
                )
                
                # Update secondary UI to show running status and serial numbers
                try:
                    station_ids = [int(station[2:]) for station in allocated_stations]
                    for i, station_id in enumerate(station_ids):
                        serial_number = serial_numbers[i] if i < len(serial_numbers) else "Unknown"
                        secondary_ui.update_station_status([station_id], running=True, serial=serial_number)
                    print(f"DEBUG: Updated secondary UI status for stations {station_ids} with serials {serial_numbers}")
                except Exception as e:
                    print(f"DEBUG: Failed to update secondary UI status: {e}")
                
                try:
                    stage_test.test(lambda: None, initialized_controllers)  # reenable_run_button will be handled elsewhere
                    print(f"DEBUG: stage_test.test() completed successfully")
                except IndexError as e:
                    import traceback
                    print(f"IndexError caught during stage_test.test():")
                    print(f"  Error message: {str(e)}")
                    traceback.print_exc()
                    raise
                except Exception as e:
                    import traceback
                    print(f"Other error caught during stage_test.test():")
                    print(f"  Error type: {type(e).__name__}")
                    print(f"  Error message: {str(e)}")
                    traceback.print_exc()
                    raise
                
            except Exception as e:
                messagebox.showerror(
                    "Test Error",
                    f"Error during test initialization: {str(e)}"
                )
                # Clean up stations and UI status
                try:
                    self.station_manager.release_stations(allocated_stations)
                    # Reset UI status for failed stations
                    station_ids = [int(station[2:]) for station in allocated_stations]
                    secondary_ui.update_station_status(station_ids, running=False, serial="")
                except Exception as cleanup_error:
                    print(f"Error during cleanup: {cleanup_error}")
        
        # Start test in separate thread
        test_thread = threading.Thread(target=run_checkout_test, daemon=True)
        test_thread.start()
    
    def _on_cancel(self):
        """Handle Cancel button click or window close"""
        self.result = None
        self.dialog.destroy()
    
    def show(self):
        """Show the dialog and return the result"""
        self.dialog.wait_window()
        return self.result


def show_station_selection_dialog(parent, num_stations, program_id, test_params):
    """
    Show the enhanced station selection dialog that handles configuration and test initialization.
    
    Args:
        parent: Parent window
        num_stations: Number of stations needed
        program_id: Program ID for allocation
        test_params: Dictionary containing test parameters from main UI
    
    Returns:
        True if test was successfully initialized, None if cancelled
    """
    dialog = StationSelectionDialog(parent, num_stations, program_id, None, test_params)
    return dialog.show()
