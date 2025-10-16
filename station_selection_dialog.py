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
    def __init__(self, parent, num_stations, program_id, serial_number):
        self.parent = parent
        self.num_stations = num_stations
        self.program_id = program_id
        self.serial_number = serial_number
        self.result = None
        self.selected_stations = []
        
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
        
        # Initialize auto-assign mode
        self.mode_var.set("auto")
        self._on_mode_change()
    
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
        
        # Mode selection frame
        mode_frame = tk.LabelFrame(
            main_frame, 
            text="Assignment Mode", 
            **labelframe_style,
            padx=10, 
            pady=10
        )
        mode_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.mode_var = tk.StringVar()
        
        # Auto-assign radio button
        auto_radio = tk.Radiobutton(
            mode_frame,
            text="Automatically assign available stations",
            variable=self.mode_var,
            value="auto",
            command=self._on_mode_change,
            font=("Segoe UI", 10),
            **radio_style
        )
        auto_radio.pack(anchor=tk.W, pady=(0, 5))
        
        # Manual selection radio button
        manual_radio = tk.Radiobutton(
            mode_frame,
            text="Manually select stations",
            variable=self.mode_var,
            value="manual",
            command=self._on_mode_change,
            font=("Segoe UI", 10),
            **radio_style
        )
        manual_radio.pack(anchor=tk.W)
        
        # Manual selection frame
        self.manual_frame = tk.LabelFrame(
            main_frame, 
            text="Station Selection", 
            **labelframe_style,
            padx=15, 
            pady=15
        )
        self.manual_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # Create dropdown frames for each stage
        self.stage_vars = []
        self.stage_combos = []
        
        # Ensure the manual frame expands to show all content
        for i in range(self.num_stations):
            stage_frame = tk.Frame(self.manual_frame, bg=BACKGROUND, bd=0, relief="flat")
            stage_frame.pack(fill=tk.X, pady=8, padx=10)
            
            # Stage label
            stage_label = tk.Label(
                stage_frame,
                text=f"Stage {i + 1}:",
                font=("Segoe UI", 10),
                width=10,
                **supporting_label_style
            )
            stage_label.pack(side=tk.LEFT, padx=(0, 15))
            
            # Station dropdown
            stage_var = tk.StringVar()
            stage_combo = ttk.Combobox(
                stage_frame,
                textvariable=stage_var,
                state="readonly",
                width=20,
                font=("Segoe UI", 10)
            )
            stage_combo.pack(side=tk.LEFT, expand=True, fill=tk.X)
            stage_combo.bind("<<ComboboxSelected>>", 
                           lambda e, idx=i: self._on_station_selected(idx))
            
            self.stage_vars.append(stage_var)
            self.stage_combos.append(stage_combo)
        
        # Button frame
        button_frame = tk.Frame(main_frame, bg=BACKGROUND, bd=0)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
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
    
    def _on_mode_change(self):
        """Handle mode selection change"""
        mode = self.mode_var.get()
        
        if mode == "auto":
            # Disable manual selection frame and all its contents
            self.manual_frame.configure(fg=DISABLED_FG)
            for combo in self.stage_combos:
                combo.configure(state="disabled")
            # Disable stage labels too
            for widget in self.manual_frame.winfo_children():
                for child in widget.winfo_children():
                    if isinstance(child, tk.Label):
                        child.configure(fg=DISABLED_FG)
        else:
            # Enable manual selection frame and all its contents
            self.manual_frame.configure(fg=TEXT_SECONDARY)
            for combo in self.stage_combos:
                combo.configure(state="readonly")
            # Enable stage labels too
            for widget in self.manual_frame.winfo_children():
                for child in widget.winfo_children():
                    if isinstance(child, tk.Label):
                        child.configure(fg=TEXT_SECONDARY)
            
            # Update dropdown options
            self._update_station_options()
            
            # Update dialog size to accommodate all dropdowns
            self.dialog.update_idletasks()
    
    
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
    
    def _on_ok(self):
        """Handle OK button click"""
        mode = self.mode_var.get()
        
        if mode == "auto":
            # Use automatic assignment
            self.station_manager.refresh_station_status()
            allocated_stations = self.station_manager.allocate_stations(
                self.num_stations, self.program_id, self.serial_number
            )
            
            if allocated_stations is None:
                messagebox.showwarning(
                    "No Stations Available", 
                    f"Need {self.num_stations} stations, but not enough are available.\n"
                    "Please wait for other tests to complete or select stations manually."
                )
                return
            
            self.result = {"mode": "auto", "stations": allocated_stations}
        else:
            # Use manual selection
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
            
            # Check for duplicates (shouldn't happen with our dropdown logic, but just in case)
            if len(set(selected_stations)) != len(selected_stations):
                messagebox.showerror(
                    "Duplicate Selection",
                    "Each stage must be assigned to a different station"
                )
                return
            
            # Manually allocate the selected stations
            try:
                # Mark selected stations as in-use
                for station in selected_stations:
                    if not self.station_manager.is_station_available(station):
                        messagebox.showwarning(
                            "Station Unavailable",
                            f"Station {station} is no longer available. Please select different stations."
                        )
                        self._update_station_options()
                        return
                    
                    self.station_manager.set_station_in_use(
                        station, self.serial_number, self.program_id
                    )
                
                self.result = {"mode": "manual", "stations": selected_stations}
            except Exception as e:
                messagebox.showerror("Allocation Error", f"Error allocating stations: {str(e)}")
                return
        
        self.dialog.destroy()
    
    def _on_cancel(self):
        """Handle Cancel button click or window close"""
        self.result = None
        self.dialog.destroy()
    
    def show(self):
        """Show the dialog and return the result"""
        self.dialog.wait_window()
        return self.result


def show_station_selection_dialog(parent, num_stations, program_id, serial_number):
    """
    Show the station selection dialog and return the selection result.
    
    Args:
        parent: Parent window
        num_stations: Number of stations needed
        program_id: Program ID for allocation
        serial_number: Serial number for tracking
    
    Returns:
        dict: {"mode": "auto"|"manual", "stations": [list of station names]} or None if cancelled
    """
    dialog = StationSelectionDialog(parent, num_stations, program_id, serial_number)
    return dialog.show()