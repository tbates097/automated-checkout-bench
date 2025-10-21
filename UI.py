# -*- coding: utf-8 -*-
"""
Created on Tue Sep 24 15:15:54 2024

@author: TBates
"""

from ast import Param
import os
import sys
import tkinter as tk
from tkinter import ttk, OptionMenu, font, messagebox
import automation1 as a1
from checkout_test import stage_checkout
import gc
import json
import ctypes
import threading
import requests
import re
from BallscrewSizer import App
from secondary_UI import SecondaryUI
from PyQt5.QtWidgets import QApplication
from station_manager import StationManager
from station_manager_instance import set_station_manager
from google.cloud import bigquery
from station_selection_dialog import show_station_selection_dialog
import secondary_ui_registry

sys.path.append(r"K:\10. Released Software\Shared Python Programs\production-2.1")
#sys.path.append(r"C:\Users\tbates\Python\shared")
from Logger import TextLogger

station_dict = {
    'ST01': '192.168.1.10',
    'ST02': '192.168.1.11',
    'ST03': '192.168.1.12',
    'ST04': '192.168.1.13',
    'ST05': '192.168.1.14'
}

station_states = {
    i: {
        "status": "free",
        "thread": None,
        "serial_number": None,
        "axis_name": f"ST{i:02}",
        "program_id": None,  # Add this to track which program instance is using it
        "controllers": None  # Store controller reference here
    } for i in range(1, 11)
}
station_lock = threading.Lock()

secondary_ui = None
smartstring_travel = None
full_smart_string = None  # Store the complete smart string for MCD naming
test_axes = []
specs_dict = {}
param_dict = {}
absolute = False
allocated_stations = []
previously_allocated_stations = set()
# part_entry is now local to UI function
BI_state = 'default'  # Added global BI_state variable with default value
speed_state = 'default'  # Speed mode: 'default' or 'manual'
bus_volt = "80"

# JSON file path to store user inputs
USER_DATA_FILE = os.path.join(os.getcwd(), "user_data.json")

def save_user_inputs(data):
    """Save user inputs to a JSON file."""
    with open(USER_DATA_FILE, 'w') as f:
        json.dump(data, f)

def load_user_inputs():
    """Load user inputs from a JSON file."""
    if os.path.exists(USER_DATA_FILE):
        with open(USER_DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def allocate_stations(num_stations, program_id):
    """Allocate the required number of free stations, or return None if not enough are available."""
    try:
        # Try to acquire the lock with a timeout of 5 seconds
        if not station_lock.acquire(timeout=5):
            print("Could not acquire station lock - timeout")
            return None
            
        free_stations = [
            station for station in station_states.items() 
            if station[1]["status"] == "free"
        ]
        
        if len(free_stations) >= num_stations:
            allocated = [station[0] for station in free_stations[:num_stations]]
            for station in allocated:
                station_states[station].update({
                    "status": "in-use",
                    "program_id": program_id
                })
            return allocated
        
        print(f"Not enough free stations. Need {num_stations}, found {len(free_stations)}")
        return None
    except Exception as e:
        print(f"Error in allocate_stations: {str(e)}")
        return None
    finally:
        try:
            station_lock.release()
        except RuntimeError:
            print("Lock was not acquired")
            pass

def release_stations(stations):
    """Release multiple stations and mark them as free."""
    with station_lock:
        program_id = id(threading.current_thread())
        for station in stations:
            if station_states[station]["program_id"] == program_id:
                # Only release if this program owns the station
                if station_states[station]["controllers"]:
                    try:
                        station_states[station]["controllers"].disconnect()
                    except:
                        pass
                station_states[station].update({
                    "status": "free",
                    "thread": None,
                    "serial_number": None,
                    "program_id": None,
                    "controllers": None
                })

def get_station_controller(station):
    """Safely get controller for a station."""
    program_id = id(threading.current_thread())
    with station_lock:
        if station_states[station]["status"] == "in-use":
            if station_states[station]["controllers"]:
                return station_states[station]["controllers"]
    return None

def launch_secondary_ui(focus_widget=None):
    """Launch the secondary UI in a new thread."""
    def run_secondary_ui():
        global secondary_ui
        secondary_ui_instance = SecondaryUI()
        
        # Set in both global variable and registry for compatibility
        secondary_ui = secondary_ui_instance
        secondary_ui_registry.set_secondary_ui(secondary_ui_instance)
        
        secondary_ui_instance.run()

    thread = threading.Thread(target=run_secondary_ui, daemon=True)
    thread.start()
    
    # Give the secondary UI time to launch, then refocus main window
    if focus_widget:
        window.after(500, lambda: (
            window.lift(),
            window.focus_force(),
            focus_widget.focus_set(),
            focus_widget.select_range(0, tk.END)
        ))
    else:
        window.after(500, lambda: (
            window.lift(),
            window.focus_force()
        ))

def UI():
    global window, station_manager
    window = tk.Tk()
    window.title("Aerotech Stage Check-out")
    
    # Get screen width and height, including taskbar
    screen_width = ctypes.windll.user32.GetSystemMetrics(0)  # Full screen width
    screen_height = ctypes.windll.user32.GetSystemMetrics(1)  # Full screen height
    
    # Get the usable work area size (excluding taskbar)
    usable_width = ctypes.windll.user32.GetSystemMetrics(78)  # Width excluding taskbar
    usable_height = ctypes.windll.user32.GetSystemMetrics(79)  # Height excluding taskbar
    
    # Set desired window size for side-by-side layout
    window_height = 800  # Reduced height since text widget moves to side
    window_width = 1400  # Increased width to accommodate side-by-side layout
    
    # Ensure the window size does not exceed usable screen dimensions
    window_width = min(window_width, usable_width)
    window_height = min(window_height, usable_height)
    
    # Get information about all screens
    def get_screen_info():
        try:
            import ctypes
            user32 = ctypes.windll.user32
            monitors = []
            
            def callback(hMonitor, hdcMonitor, lprect, dwData):
                rect = ctypes.cast(lprect, ctypes.POINTER(ctypes.c_long))
                monitor_info = {
                    'x': rect[0],
                    'y': rect[1],
                    'width': rect[2] - rect[0],
                    'height': rect[3] - rect[1]
                }
                monitors.append(monitor_info)
                return True
            
            callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, 
                                             ctypes.c_ulong, 
                                             ctypes.c_ulong,
                                             ctypes.POINTER(ctypes.c_long), 
                                             ctypes.c_ulong)
            callback_function = callback_type(callback)
            user32.EnumDisplayMonitors(None, None, callback_function, 0)
            return monitors
        except Exception as e:
            print(f"Error getting screen info: {e}")
            return None

    # Position window on rightmost screen
    screens = get_screen_info()
    if screens:
        rightmost_screen = max(screens, key=lambda m: m['x'])
        x = rightmost_screen['x'] + (rightmost_screen['width'] - window_width) // 2
        
        # Adjust y position to be higher up
        taskbar_offset = 50  # Adjust this value to move window up more or less
        y = rightmost_screen['y'] + (rightmost_screen['height'] - window_height) // 2 - taskbar_offset
        
        window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        
        # Force window to be active and focused
        window.lift()
        window.attributes('-topmost', True)
        window.update()
        window.attributes('-topmost', False)
        window.focus_force()
        
        # Now set focus to job number entry (now at the top) - will be set later after widget creation
        pass
    
    # Set window icon after positioning
    try:
        # Try to use Aerotech icon if available
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "aerotech.ico")
        if os.path.exists(icon_path):
            window.iconbitmap(icon_path)
        else:
            # If custom icon not found, use a built-in icon
            window.iconbitmap('warning')  # Other options: 'info', 'question', 'error'
    except:
        pass  # Fallback to default icon if any error occurs
    
    # Configure title bar color (Windows only)
    try:
        window.tk.call('tk', 'windowingsystem')  # Check if running on Windows
        window.tk.call('wm', 'iconphoto', window._w, tk.PhotoImage(file=os.path.join(os.path.dirname(__file__), "assets", "aerotech.jpg")))
    except:
        pass
    
    # Initialize StationManager
    station_manager = StationManager(window)
    set_station_manager(station_manager)
    station_manager.start()  # Start the background thread for station management
    
    # Load stored user inputs
    stored_data = load_user_inputs()
    
    # Initialize Tkinter window
    window.resizable(True, False)  # This code helps to disable windows from resizing

    # Configure grid for side-by-side layout
    window.grid_rowconfigure(0, weight=1)  # Single row for both frames
    window.grid_columnconfigure(0, weight=0, minsize=850)  # Left column for input frame (fixed width)
    window.grid_columnconfigure(1, weight=1)  # Right column for text frame (expandable)

    '''
    # MAIN USER INPUT FRAME
    '''
    
    input_frame_width = 830  # Slightly reduced for left side layout
    input_frame_height = 750  # Keep same height
    
    input_frame = tk.Frame(master=window, width=input_frame_width, height=input_frame_height)
    input_frame.grid(row=0, column=0, sticky='nsew', padx=(20, 10), pady=20)  # Left side padding
    input_frame.grid_propagate(True)
    
    # Configure columns and rows with more space for left side layout
    input_frame.columnconfigure([0, 1, 2, 3], weight=1, minsize=830 / 4, uniform='column')
    input_frame.rowconfigure([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14], weight=1, minsize=35)

    # Define row indices with better spacing and grouping
    input_frame.h1_row = 0        # Top separator
    input_frame.config_label_row = 1  # "Configuration" heading
    input_frame.num_axes_row = 2      # Number of Stages & Absolute Encoder
    input_frame.h2_row = 3        # Separator after configuration
    
    input_frame.params_label_row = 4  # "Test Parameters" heading
    input_frame.speed_row = 5         # Burn-In Speed & Duty Cycle
    input_frame.cycles_row = 6        # Burn-In Time
    input_frame.bus_row = 7
    input_frame.h3_row = 8        # Separator after parameters
    
    input_frame.doc_label_row = 9    # "Documentation" heading
    input_frame.op_row = 10           # Operator
    input_frame.comm_row = 11         # Comments
    input_frame.h4_row = 12       # Separator before Run button
    input_frame.run_row = 13      # Run button
    input_frame.out_row = 14      # Output area

    # Configure rows with more space
    input_frame.rowconfigure([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14], weight=1, minsize=35)

    # Define Automation1 Studio-inspired color palette
    BACKGROUND = "#F0F0F0"  # Light gray background
    WHITE = "#FFFFFF"  # Pure white for input fields
    BLUE_PRIMARY = "#0078D4"  # Aerotech blue
    BLUE_HOVER = "#106EBE"  # Slightly darker blue for hover
    BLUE_ACTIVE = "#005A9E"  # Darker blue for clicking
    TEXT_PRIMARY = "#252423"  # Darker gray for primary text
    TEXT_SECONDARY = "#484644"  # Medium gray for secondary text
    BORDER = "#E1E1E1"  # Light border color
    BORDER_DARK = "#CCCCCC"  # Darker border for frames
    BORDER_FOCUS = "#0078D4"  # Blue border for focus
    DISABLED_BG = "#F3F2F1"  # Slightly darker than background for disabled
    DISABLED_FG = "#A19F9D"  # Muted text for disabled elements

    # Create horizontal separators with light border appearance
    #sep1 = tk.Frame(master=input_frame, height=1, bg=BORDER)
    #sep1.grid(row=input_frame.h1_row, column=0, columnspan=4, sticky='ew', padx=20, pady=5)
    
    sep2 = tk.Frame(master=input_frame, height=1, bg=BORDER)
    sep2.grid(row=input_frame.h2_row, column=0, columnspan=4, sticky='ew', padx=20, pady=5)
    
    sep3 = tk.Frame(master=input_frame, height=1, bg=BORDER)
    sep3.grid(row=input_frame.h3_row, column=0, columnspan=4, sticky='ew', padx=20, pady=5)
    
    sep4 = tk.Frame(master=input_frame, height=1, bg=BORDER)
    sep4.grid(row=input_frame.h4_row, column=0, columnspan=4, sticky='ew', padx=20, pady=5)
    
    # Load stored data or set defaults
    speed_value = stored_data.get("speed", 360)
    job_value = stored_data.get("job", '"Job Number"')
    op_value = stored_data.get("operator", '"Your Initials"')
    comm_value = stored_data.get("comments", "")
    duty_cycle_value = stored_data.get('duty_cycle', 25)
    
    '''
    # TEXT WIDGET FRAME
    '''
    
    # Create the text frame on the right side
    text_frame = tk.Frame(master=window)
    text_frame.grid(row=0, column=1, sticky='nsew', padx=(10, 20), pady=20)  # Right side positioning
    text_frame.grid_propagate(False)
    
    # Configure the grid in text_frame_tab3
    text_frame.grid_rowconfigure(0, weight=1)  # Allow row 0 to expand
    text_frame.grid_columnconfigure(0, weight=1)  # Allow column 0 (Text widget) to expand
    text_frame.grid_columnconfigure(1, weight=0)  # Keep column 1 (Scrollbar) at a fixed size
    
    # Create the text widget and scrollbar
    txt_outStr = tk.Text(master=text_frame, state=tk.DISABLED, fg='white', bg='black')
    outStr_scroll = tk.Scrollbar(master=text_frame, orient=tk.VERTICAL)
    
    # Configure the scrollbar
    txt_outStr.configure(yscrollcommand=outStr_scroll.set)
    outStr_scroll.config(command=txt_outStr.yview)
    
    # Place the widgets using grid
    txt_outStr.grid(row=0, column=0, sticky='nsew')
    outStr_scroll.grid(row=0, column=1, sticky='ns')
    
    # Initialize the text logger
    text_logger = TextLogger(txt_outStr)
    
    sys.stdout = text_logger
    
    class JobQueryClient:
        def __init__(self):
            self.client = bigquery.Client()
            self.project_id = 'warehouse-363320'
        
        def get_part_info(self, job_num):
            """Query BigQuery for both PartNum and PartDescription using job number"""
            query_path = os.path.join(os.path.dirname(__file__), "query.txt")

            with open(query_path, 'r') as f:
                query_template = f.read()
            query = query_template.replace("@jobnum", f"'{job_num}'")
            
            try:
                query_job = self.client.query(query)
                results = query_job.result()
                rows = list(results)
                if not rows:
                    return None, None
                row = rows[0]

                # Return using attribute access (the correct method for BigQuery)
                part_num = getattr(row, 'PartNum', None)
                part_desc = getattr(row, 'PartDescription', None)
                
                return part_num, part_desc
                
            except Exception as e:
                print(f"Error querying BigQuery: {str(e)}")
                return None, None

    def parse_smart_string(smart_string):
        """
        Parse the smart string to extract part number and travel
        Example: PRO165LM-0310-TT1-E1-PL0 -> ("PRO165LM", "0310")
        Travel is the first all-numeric item after the part number, regardless of length or leading zeros.
        """
        if not smart_string:
            return None, None
        
        # Convert to string if it's not already (handles integers from BigQuery)
        smart_string_str = str(smart_string)
        
        # Skip if it's clearly just a number (like "25")
        if smart_string_str.isdigit():
            return None, None
        
        try:
            # Split by dashes
            parts = smart_string_str.split('-')
            if not parts or len(parts) < 2:
                return None, None
            
            # If the smart string starts with a PRO-series part, remove a trailing SLE or SL suffix
            # Example: PRO115SL-050-... -> PRO115, PRO165SLE-0310-... -> PRO165
            if parts[0].startswith('PRO'):
                part_number = re.sub(r'(SLE|SL)$', '', parts[0])
            else:
                part_number = parts[0]
            
            # Look for travel in remaining parts - first all-numeric item
            travel = None
            for part in parts[1:]:
                if part.isdigit():
                    travel = part
                    break
            
            return part_number, travel
            
        except Exception as e:
            print(f"Error parsing smart string '{smart_string}': {str(e)}")
            return None, None

    def is_smart_string(candidate):
        """Return True if candidate looks like a smart string (has dash between first two items)"""
        if not candidate:
            return False
        
        # Convert to string if it's an integer/other type
        candidate_str = str(candidate)
        
        # Skip if it's just a number (like "25")
        if candidate_str.isdigit():
            return False
        
        # Must contain at least one dash
        if '-' not in candidate_str:
            return False
            
        parts = candidate_str.split('-')
        return len(parts) >= 2 and all(parts[:2])

    def start_test_thread():
        global allocated_stations
        """Start a test thread for the required number of stations."""
        num_stations = var_num_axes.get()
        program_id = id(threading.current_thread())
        
        # Collect test parameters
        test_params = {
            'speed': 'default' if speed_mode_var.get() == 'default' else float(var_speed.get()),
            'burnin_time': 4 if BI_state == 'default' else int(var_time.get()),
            'operator': str(var_op.get()),
            'comments': str(var_comm.get()),
            'duty_cycle': int(var_duty_cycle.get()),
            'absolute': absolute,
            'bus_voltage': bus_volt
        }
        
        try:
            # Show enhanced station selection dialog that handles everything
            result = show_station_selection_dialog(
                window, num_stations, program_id, test_params
            )
            
            # If user cancelled, return
            if result is None:
                return
            
            # The enhanced dialog handles everything - test is already running
            print("Test initialization completed via enhanced station selection dialog")
            
            # Save user inputs for next time
            user_data = {
                "speed": test_params['speed'],
                "operator": test_params['operator'],
                "comments": test_params['comments'],
                "duty_cycle": test_params['duty_cycle']
            }
            save_user_inputs(user_data)
            
            # Disable run button during test
            btn_run.config(state=tk.DISABLED)

        except Exception as e:
            messagebox.showerror(
                "Allocation Error",
                f"Error allocating stations: {str(e)}"
            )
            btn_run.config(state=tk.NORMAL)

    def reenable_run_button():
        """
        Re-enables the 'Run' button in the UI.
        """
        btn_run.config(state=tk.NORMAL)
    
    def test(program_id, serial_number, station_controllers, stage_type=None, job=None):
        """Main test function in UI.py - updated for new workflow without removed UI elements"""
        def prompt_user(message):
            text_logger.write(message)
            txt_outStr.delete(1.0, tk.END)
            return text_logger.read_input()

        def clear_text():
            txt_outStr.delete(1.0, tk.END)
        
        sys.stdout = text_logger
        
        # These parameters are now passed from the station dialog rather than UI elements
        stage_type = stage_type or "Unknown"  # Will be provided by station dialog
        num_axes = int(var_num_axes.get())
        # Pass 'default' when Default mode is selected; otherwise pass manual numeric value
        if speed_mode_var.get() == 'default':
            speed = 'default'
        else:
            speed = float(var_speed.get())
        job = job or "Unknown"  # Will be provided by station dialog (first 6 chars of serial)
        op = str(var_op.get())
        comm = str(var_comm.get())
        duty_cycle = int(var_duty_cycle.get())
        if BI_state == 'default':
            BI_time = 4
        else:
            BI_time = int(var_time.get())

        try:
            # Initialize controllers
            initialized_controllers = {}
            for axis_name, ip_address in station_controllers.items():
                try:
                    print(f"Connecting to {axis_name} at {ip_address}...")
                    controller = a1.Controller.connect(host=ip_address)
                    print("Controller connected, starting...")
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

            global stage_test, allocated_stations
            test_axes = allocated_stations
            stations = [int(station[2:]) for station, state in station_manager.station_states.items()
                        if state["program_id"] == program_id]
            
            # Bus voltage will be passed separately to checkout_test.py
            # No longer adding bus voltage to specs_dict (now goes in electrical_dict)

            # Intelligent Travel comparison logic
            if smartstring_travel is not None and specs_dict and param_dict:
                try:
                    # Convert smartstring travel to integer (remove leading zeros)
                    smartstring_travel_int = int(smartstring_travel)
                    
                    # Get current travel from specs_dict
                    current_travel_raw = specs_dict.get('Travel')
                    current_nominal = param_dict.get('NominalTravel')
                    
                    # Clean and convert specs travel value (remove dashes, convert to int)
                    current_travel = None
                    if current_travel_raw is not None:
                        try:
                            # Remove leading dash if present and convert to int
                            travel_str = str(current_travel_raw).lstrip('-')
                            current_travel = int(travel_str) if travel_str.isdigit() else None
                        except (ValueError, AttributeError):
                            current_travel = None
                    
                    # Check if smartstring travel differs from database travel
                    if current_travel is not None and smartstring_travel_int != current_travel:
                        print(f"Travel mismatch detected! Updating from {current_travel} to {smartstring_travel_int}")
                        
                        # Update Travel in specs_dict
                        specs_dict['Travel'] = smartstring_travel_int
                        
                        # Calculate difference for parameter adjustments
                        if current_nominal is not None:
                            travel_difference = smartstring_travel_int - current_nominal
                            
                            # Update NominalTravel to match smartstring
                            param_dict['NominalTravel'] = float(smartstring_travel_int)
                            
                            # Adjust other travel-related parameters by the difference
                            if 'LimitToLimitTravel' in param_dict:
                                original_ltl = param_dict['LimitToLimitTravel']
                                param_dict['LimitToLimitTravel'] = original_ltl + travel_difference
                                
                            if 'HardToHard-FirstContact' in param_dict:
                                original_h2h_first = param_dict['HardToHard-FirstContact']
                                param_dict['HardToHard-FirstContact'] = original_h2h_first + travel_difference
                                
                            if 'HardToHard-Compressed' in param_dict:
                                original_h2h_comp = param_dict['HardToHard-Compressed']
                                param_dict['HardToHard-Compressed'] = original_h2h_comp + travel_difference
                                
                    elif current_travel is None and smartstring_travel_int:
                        print(f"No travel in specs_dict, using smartstring travel: {smartstring_travel_int}")
                        specs_dict['Travel'] = smartstring_travel_int
                        if 'NominalTravel' not in param_dict:
                            param_dict['NominalTravel'] = float(smartstring_travel_int)
                        
                except (ValueError, TypeError) as e:
                    print(f"Error processing travel values: {e}")
                    print(f"SmartString Travel: {smartstring_travel}, Current Travel: {current_travel}")

            # Run the test
            stage_test = stage_checkout(
                stage_type, speed, BI_time, job, op, 
                comm, secondary_ui, window, num_axes, 
                test_axes, duty_cycle, specs_dict, 
                absolute, stations, param_dict,
                full_smart_string=full_smart_string,
                bus_voltage=bus_volt
            )

            # Register abort callbacks for each station
            for axis in test_axes:
                station_id = int(axis[2:])  # Convert 'ST01' to 1
                stage_test.secondary_ui.register_abort_callback(
                    station_id, 
                    lambda axis=axis: stage_test.abort_test(axis)
                )

            stage_test.test(reenable_run_button, initialized_controllers)  

        except Exception as e:
            print(f"Test error: {str(e)}")
            raise
        finally:
            reenable_run_button()
            # Clean up controllers
            for ctrl in initialized_controllers.values():
                if ctrl and hasattr(ctrl, 'disconnect'):
                    try:
                        ctrl.disconnect()
                    except:
                        pass

    def cleanup_resources(test=None):
        """
        Cleans up resources such as threads, connections, and resets global states.
        """
        global thread
    
        if thread and thread.is_alive():
            try:
                thread.join(timeout=1)
            except RuntimeError:
                pass
        thread = None
        
        # Clean up rot_cal specific resources
        if test:
            del test
        
        gc.collect()
    
    def bus_def():
        global bus_volt
        if bus_var.get() == "40":
            bus_volt = "40"
        elif bus_var.get() == "80":
            bus_volt = "80"
        else:
            bus_volt = "160"
        
    def time_def():
        global BI_state
        if time_var.get() == 'default':
            ent_other["state"] = tk.DISABLED
            BI_state = 'default'
        elif time_var.get() == 'other':
            ent_other["state"] = tk.NORMAL
            BI_state = 'other'

    def speed_def():
        """Toggle manual speed entry enabled/disabled based on selection."""
        global speed_state
        if speed_mode_var.get() == 'default':
            ent_speed["state"] = tk.DISABLED
            speed_state = 'default'
        else:
            ent_speed["state"] = tk.NORMAL
            speed_state = 'manual'
    
    def abs_def():
        global absolute
        if abs_var.get() == "Yes":
            absolute = True
        else:
            absolute = False

    def on_entry_focus(event):
        # Select all text in the entry field
        event.widget.select_range(0, tk.END)

    # Rotary Calibration Tab UI Elements
    label_font = font.Font(family="Helvetica", size=10, weight="bold")
    button_font = font.Font(family="Arial", size=12, weight="bold") 

    # Adjust padding for all grid elements
    standard_padx = 10  # Keep the same
    standard_pady = 6   # Reduced from 8


    # Configuration section
    lbl_num_axes = tk.Label(master=input_frame, text="Number Of Stages", font=label_font)
    lbl_num_axes.grid(row=input_frame.num_axes_row, column=0, padx=standard_padx, pady=standard_pady)
    
    var_num_axes = tk.IntVar(value="")
    ent_num_axes = tk.Entry(master=input_frame, textvariable=var_num_axes, width=15)
    ent_num_axes.grid(row=input_frame.num_axes_row, column=1, padx=standard_padx, pady=standard_pady)
    
    lbl_abs = tk.Label(master=input_frame, text="Absolute Encoder?", font=label_font)
    lbl_abs.grid(row=input_frame.num_axes_row, column=2, padx=standard_padx, pady=standard_pady)
    
    abs_var = tk.StringVar(value="No")
    abs_ent = tk.Radiobutton(master=input_frame, text="Yes", variable=abs_var, value="Yes", command=abs_def)
    abs_ent.grid(row=input_frame.num_axes_row, column=3, padx=standard_padx, pady=standard_pady)

    # Test Parameters section
    lbl_speed = tk.Label(master=input_frame, text="Burn-In Speed", font=label_font)
    lbl_speed.grid(row=input_frame.speed_row, column=0, padx=standard_padx, pady=standard_pady)
    
    # Speed selection: Default vs Manual, with entry enabled when Manual is selected
    speed_mode_var = tk.StringVar(value='default')
    var_speed = tk.DoubleVar(value=speed_value)
    
    # Use a subframe to keep both radios and the entry in column 1, preserving duty cycle layout
    speed_frame = tk.Frame(master=input_frame, bg=BACKGROUND)
    speed_frame.grid(row=input_frame.speed_row, column=1, padx=standard_padx, pady=standard_pady, sticky='w')
    
    default_speed_radio = tk.Radiobutton(master=speed_frame, text="Default", variable=speed_mode_var, value='default', command=speed_def)
    manual_speed_radio = tk.Radiobutton(master=speed_frame, text="Manual", variable=speed_mode_var, value='manual', command=speed_def)
    
    # Place radios side-by-side
    default_speed_radio.grid(row=0, column=0, padx=(0, 8), pady=(0, 4), sticky='w')
    manual_speed_radio.grid(row=0, column=1, padx=(0, 0), pady=(0, 4), sticky='w')
    
    # Manual speed entry (disabled by default)
    ent_speed = tk.Entry(master=speed_frame, textvariable=var_speed, width=10, state=tk.DISABLED)
    ent_speed.grid(row=1, column=1, columnspan=2, sticky='w')

    # Ensure the row is tall enough to display radios + entry
    input_frame.rowconfigure(input_frame.speed_row, minsize=60)

    # Initialize to default mode explicitly
    try:
        speed_mode_var.set('default')
        speed_def()
    except Exception:
        pass
    
    # Style the new radios to match existing style
    try:
        default_speed_radio.configure(**radio_style)
        manual_speed_radio.configure(**radio_style)
    except Exception:
        pass
    
    lbl_duty_cycle = tk.Label(master=input_frame, text="Duty Cycle", font=label_font)
    lbl_duty_cycle.grid(row=input_frame.speed_row, column=2, padx=standard_padx, pady=standard_pady)
    
    var_duty_cycle = tk.DoubleVar(value=duty_cycle_value)
    ent_duty_cycle = tk.Entry(master=input_frame, textvariable=var_duty_cycle, width=15)
    ent_duty_cycle.grid(row=input_frame.speed_row, column=3, padx=standard_padx, pady=standard_pady)
    
    lbl_cycles = tk.Label(master=input_frame, text="Burn-In Time", font=label_font)
    lbl_cycles.grid(row=input_frame.cycles_row, column=0, padx=standard_padx, pady=standard_pady)
    
    time_var = tk.StringVar(value="default")
    default = tk.Radiobutton(master=input_frame, text="Default", variable=time_var, value="default", command=time_def)
    default.grid(row=input_frame.cycles_row, column=1, padx=standard_padx, pady=standard_pady)
    
    other = tk.Radiobutton(master=input_frame, text="Other (Hours)", variable=time_var, value="other", command=time_def)
    other.grid(row=input_frame.cycles_row, column=2, padx=standard_padx, pady=standard_pady)
    
    var_time = tk.IntVar(value=0)
    ent_other = tk.Entry(master=input_frame, textvariable=var_time, width=15, state=tk.DISABLED)
    ent_other.grid(row=input_frame.cycles_row, column=3, padx=standard_padx, pady=standard_pady)
    
    lbl_bus = tk.Label(master=input_frame, text="Bus Voltage", font=label_font)
    lbl_bus.grid(row=input_frame.bus_row, column=0, padx=standard_padx, pady=standard_pady)

    bus_var = tk.StringVar(value="80")
    bus_40 = tk.Radiobutton(master=input_frame, text="40v", variable=bus_var, value="40", command=bus_def)
    bus_40.grid(row=input_frame.bus_row, column=1, padx=standard_padx, pady=standard_pady)

    bus_80 = tk.Radiobutton(master=input_frame, text="80v", variable=bus_var, value="80", command=bus_def)
    bus_80.grid(row=input_frame.bus_row, column=2, padx=standard_padx, pady=standard_pady)

    bus_160 = tk.Radiobutton(master=input_frame, text="160v", variable=bus_var, value="160", command=bus_def)
    bus_160.grid(row=input_frame.bus_row, column=3, padx=standard_padx, pady=standard_pady)

    lbl_op = tk.Label(master=input_frame, text="Employee Number", font=label_font)
    lbl_op.grid(row=input_frame.op_row, column=0, padx=standard_padx, pady=standard_pady)
    
    var_op = tk.StringVar(value=op_value)
    ent_op = tk.Entry(master=input_frame, textvariable=var_op, width=50)
    ent_op.grid(row=input_frame.op_row, column=1, columnspan=2, padx=standard_padx, pady=standard_pady)
    
    lbl_comments = tk.Label(master=input_frame, text="Comments", font=label_font)
    lbl_comments.grid(row=input_frame.comm_row, column=0, padx=standard_padx, pady=standard_pady)
    
    var_comm = tk.StringVar(value=comm_value)
    ent_comments = tk.Entry(master=input_frame, textvariable=var_comm, width=50)
    ent_comments.grid(row=input_frame.comm_row, column=1, columnspan=2, padx=standard_padx, pady=standard_pady)

    # Run button section
    btn_run = tk.Button(master=input_frame, text="Run", width=25, height=1, command=start_test_thread, font=label_font)
    btn_run.grid(row=input_frame.run_row, column=1, columnspan=2, padx=standard_padx, pady=15)  # Increased pady for more space
    
# =============================================================================
#     btn_open = tk.Button(master=input_frame, text="Open Plot", width=25, height=1, command=open_Plot)
#     btn_open.grid(row=input_frame.run_row, column=2, padx=5, pady=5)
# =============================================================================
    
    def on_closing():
        station_manager.stop()
        global window_open
        window_open = False  # Set the flag to indicate that the window is closing
        
        try:
            user_data = {
                "speed": var_speed.get(),
                "operator": var_op.get(),
                "comments": var_comm.get(),
                "duty_cycle": var_duty_cycle.get()
            }
            
            save_user_inputs(user_data)  # Save the data to a file
        except Exception as e:
            print(f"An error occurred: {e}")  # Handle any exceptions
        try:
            # Perform any cleanup tasks here
            window.destroy()  # Close the main window
            window_open = False
        except RuntimeError:
            return
    
    # Bind the closing protocol
    window.protocol("WM_DELETE_WINDOW", on_closing)
    launch_secondary_ui()

    # Enhanced ttk styling for Automation1 look
    style = ttk.Style()
    style.configure(".", background=BACKGROUND, foreground=TEXT_PRIMARY)
    
    # Configure separator style to match border
    style.configure("TSeparator", background=BORDER)  # Add this line to style the separators
    
    # Base styles that can be extended
    base_style = {
        "bg": BACKGROUND,
        "relief": "flat",
        "padx": 12,
        "pady": 6
    }
    
    # Main input field labels (bolder, darker)
    main_label_style = {
        **base_style,
        "fg": TEXT_PRIMARY,
        "font": ("Segoe UI Semibold", 11),
        "anchor": "w"  # Left-align text
    }
    
    # Supporting field labels (regular weight, slightly lighter)
    supporting_label_style = {
        **base_style,
        "fg": TEXT_SECONDARY,
        "font": ("Segoe UI", 10),
        "anchor": "w"  # Left-align text
    }
    
    # Entry field configurations
    entry_style = {
        "relief": "flat",  # Changed from solid to flat
        "borderwidth": 0,  # Changed from 1 to 0
        "highlightthickness": 1,
        "highlightbackground": "#E1E1E1",  # Lighter gray border for unfocused entry fields
        "highlightcolor": "#0078D4",      # Blue border for focus
        "bg": WHITE,
        "fg": TEXT_SECONDARY
    }

    # Apply entry style to all entry fields
    for entry in [ent_num_axes, ent_speed, ent_duty_cycle, ent_other, ent_op, ent_comments]:
        entry.configure(**entry_style)

    # Main input fields (darker text)
    main_entry_style = {
        **entry_style,
        "fg": TEXT_PRIMARY,
        "insertbackground": TEXT_PRIMARY,
        "font": ("Segoe UI", 11)
    }
    
    # Supporting input fields (regular text)
    supporting_entry_style = {
        **entry_style,
        "fg": TEXT_SECONDARY,
        "insertbackground": TEXT_SECONDARY,
        "font": ("Segoe UI", 10)
    }

    # Standard button style
    button_style = {
        "bg": WHITE,
        "fg": TEXT_PRIMARY,
        "activebackground": BLUE_PRIMARY,
        "activeforeground": WHITE,
        "relief": "solid",
        "font": ("Segoe UI", 10),
        "padx": 15,
        "pady": 8,
        "cursor": "hand2",
        "bd": 1
    }

    # Radio button style
    radio_style = {
        "bg": BACKGROUND,
        "fg": TEXT_SECONDARY,
        "selectcolor": WHITE,
        "activebackground": BACKGROUND,
        "activeforeground": BLUE_PRIMARY,
        "font": ("Segoe UI", 10),
        "cursor": "hand2"
    }

    # Action button style (blue buttons)
    action_button_style = {
        "bg": BLUE_PRIMARY,
        "fg": WHITE,
        "activebackground": BLUE_ACTIVE,
        "activeforeground": WHITE,
        "font": ("Segoe UI", 11),
        "relief": "flat",
        "cursor": "hand2",
        "bd": 0
    }

    # Define main input fields
    main_input_labels = [lbl_num_axes, lbl_abs, lbl_speed, lbl_duty_cycle, lbl_cycles, lbl_bus, lbl_op, lbl_comments]  # Main input labels
    main_input_entries = [ent_num_axes, ent_speed, ent_duty_cycle, ent_op, ent_comments]  # Their corresponding entry fields
    
    # First apply base styles to all widgets
    for widget in input_frame.winfo_children():
        if isinstance(widget, tk.Label):
            if widget in main_input_labels:
                widget.configure(**main_label_style)
            else:
                widget.configure(**supporting_label_style)
        elif isinstance(widget, tk.Entry):
            if widget in main_input_entries:
                widget.configure(**main_entry_style)
            else:
                widget.configure(**supporting_entry_style)
        elif isinstance(widget, tk.Button):
            widget.configure(**button_style)
        elif isinstance(widget, tk.Radiobutton):
            widget.configure(**radio_style)

    # Style the text output area
    txt_outStr.configure(
        bg=WHITE,
        fg=TEXT_PRIMARY,
        insertbackground=TEXT_PRIMARY,
        font=("Consolas", 10),
        relief="solid",
        padx=10,
        pady=10,
        selectbackground=BLUE_PRIMARY,
        selectforeground=WHITE,
        bd=1,
        highlightthickness=1,
        highlightbackground=BORDER
    )
    
    # Style the scrollbar
    outStr_scroll.configure(
        bg=WHITE,
        troughcolor=BACKGROUND,
        activebackground=BLUE_PRIMARY,
        relief="flat",
        width=12,
        bd=0
    )
    
    # Configure action buttons
    btn_run.configure(
        **action_button_style,
        padx=20,
        pady=10
    )
    
    # Configure frames with consistent borders
    input_frame.configure(
        bg=BACKGROUND,
        highlightbackground=BORDER_DARK,
        highlightthickness=2,
        highlightcolor=BORDER_DARK,  # Same as highlightbackground to prevent focus change
        bd=0
    )
    
    text_frame.configure(
        bg=BACKGROUND,
        highlightbackground=BORDER_DARK,
        highlightthickness=2,
        highlightcolor=BORDER_DARK,  # Same as highlightbackground to prevent focus change
        bd=0
    )
    
    # Add section headers
    section_font = font.Font(family="Segoe UI", size=9, weight="bold")
    section_style = {
        "bg": BACKGROUND,
        "fg": TEXT_SECONDARY,
        "font": section_font,
        "pady": 5
    }

    lbl_config = tk.Label(master=input_frame, text="CONFIGURATION", **section_style)
    lbl_config.grid(row=input_frame.config_label_row, column=0, columnspan=4, sticky='w', padx=standard_padx)

    lbl_params = tk.Label(master=input_frame, text="TEST PARAMETERS", **section_style)
    lbl_params.grid(row=input_frame.params_label_row, column=0, columnspan=4, sticky='w', padx=standard_padx)

    lbl_doc = tk.Label(master=input_frame, text="DOCUMENTATION", **section_style)
    lbl_doc.grid(row=input_frame.doc_label_row, column=0, columnspan=4, sticky='w', padx=standard_padx)

    # Add all separators
    sep1 = tk.Frame(master=input_frame, height=1, bg=BORDER)
    sep1.grid(row=input_frame.h1_row, column=0, columnspan=4, sticky='ew', padx=20, pady=5)
    
    sep2 = tk.Frame(master=input_frame, height=1, bg=BORDER)
    sep2.grid(row=input_frame.h2_row, column=0, columnspan=4, sticky='ew', padx=20, pady=5)
    
    sep3 = tk.Frame(master=input_frame, height=1, bg=BORDER)
    sep3.grid(row=input_frame.h3_row, column=0, columnspan=4, sticky='ew', padx=20, pady=5)
    
    sep4 = tk.Frame(master=input_frame, height=1, bg=BORDER)
    sep4.grid(row=input_frame.h4_row, column=0, columnspan=4, sticky='ew', padx=20, pady=5)
    
    window.mainloop()
    
if __name__ == "__main__":
    UI()