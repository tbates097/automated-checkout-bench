# -*- coding: utf-8 -*-
"""
Created on Tue Sep 24 15:15:54 2024

@author: TBates
"""

# -*- coding: utf-8 -*-
"""
Created on Tue Sep 24 13:09:21 2024

@author: TBates
"""

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


#sys.path.append(r"K:\10. Released Software\Systems Manufacturing Support\Shared")
sys.path.append(r"C:\Users\tbates\Python\shared")
from Logger import TextLogger

station_dict = {
    'ST01': '192.168.1.15',
    'ST02': '192.168.1.16',
    'ST03': '192.168.1.17'
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
test_axes = []
specs_dict = {}
absolute = False
allocated_stations = []
previously_allocated_stations = set()
part_entry = None
BI_state = 'default'  # Added global BI_state variable with default value

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
        #print(f"Attempting to allocate {num_stations} stations")  # Debug print
        # Try to acquire the lock with a timeout of 5 seconds
        if not station_lock.acquire(timeout=5):
            print("Could not acquire station lock - timeout")
            return None
            
        free_stations = [
            station for station in station_states.items() 
            if station[1]["status"] == "free"
        ]
        #print(f"Found {len(free_stations)} free stations: {free_stations}")  # Debug print
        
        if len(free_stations) >= num_stations:
            allocated = [station[0] for station in free_stations[:num_stations]]
            for station in allocated:
                station_states[station].update({
                    "status": "in-use",
                    "program_id": program_id
                })
            print(f"Successfully allocated stations: {allocated}")  # Debug print
            return allocated
        
        print(f"Not enough free stations. Need {num_stations}, found {len(free_stations)}")
        return None
    except Exception as e:
        print(f"Error in allocate_stations: {str(e)}")
        return None
    finally:
        try:
            station_lock.release()
            #print("Released station lock")
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

def launch_secondary_ui():
    """Launch the secondary UI in a new thread."""
    global part_entry
    def run_secondary_ui():
        global secondary_ui
        secondary_ui = SecondaryUI()
        secondary_ui.run()

    thread = threading.Thread(target=run_secondary_ui, daemon=True)
    thread.start()
    
    # Give the secondary UI time to launch, then refocus main window
    window.after(500, lambda: (
        window.lift(),
        window.focus_force(),
        part_entry.focus_set(),
        part_entry.select_range(0, tk.END)
    ))

def UI():
    global window, station_manager, part_entry
    window = tk.Tk()
    window.title("Aerotech Stage Check-out")
    
    # Get screen width and height, including taskbar
    screen_width = ctypes.windll.user32.GetSystemMetrics(0)  # Full screen width
    screen_height = ctypes.windll.user32.GetSystemMetrics(1)  # Full screen height
    
    # Get the usable work area size (excluding taskbar)
    usable_width = ctypes.windll.user32.GetSystemMetrics(78)  # Width excluding taskbar
    usable_height = ctypes.windll.user32.GetSystemMetrics(79)  # Height excluding taskbar
    
    # Set desired window size
    window_height = 950  # Reduced from 1100
    window_width = 900   # Keep width the same
    
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
        
        # Now set focus to part number entry
        window.after(100, lambda: (part_entry.focus_set(), part_entry.select_range(0, tk.END)))
    
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
    
    # Load stored user inputs
    stored_data = load_user_inputs()
    
    # Initialize Tkinter window
    window.resizable(True, False)  # This code helps to disable windows from resizing

    window.grid_rowconfigure(0, weight=1)
    window.grid_rowconfigure(1, weight=1)
    window.grid_columnconfigure(0, weight=1)
    window.grid_columnconfigure(1, weight=1)

    '''
    # MAIN USER INPUT FRAME
    '''
    
    input_frame_width = 850  # Keep width the same
    input_frame_height = 750  # Reduced from 900
    
    input_frame = tk.Frame(master=window, width=input_frame_width, height=input_frame_height)
    input_frame.grid(row=0, column=0, sticky='nsew', padx=20, pady=10)  # Reduced pady from 15
    input_frame.grid_propagate(True)
    
    # Configure columns and rows with more space
    input_frame.columnconfigure([0, 1, 2, 3], weight=1, minsize=850 / 4, uniform='column')
    input_frame.rowconfigure([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], weight=1, minsize=35)  # Reduced minsize from 40

    # Define row indices with better spacing and grouping
    input_frame.h1_row = 0        # Top separator
    input_frame.config_label_row = 1  # "Configuration" heading
    input_frame.ID_row = 2        # Part Number section
    input_frame.num_axes_row = 3      # Number of Stages & Absolute Encoder
    input_frame.h2_row = 4        # Separator after configuration
    
    input_frame.params_label_row = 5  # "Test Parameters" heading
    input_frame.speed_row = 6         # Burn-In Speed & Duty Cycle
    input_frame.cycles_row = 7        # Burn-In Time
    input_frame.h3_row = 8        # Separator after parameters
    
    input_frame.doc_label_row = 9    # "Documentation" heading
    input_frame.job_row = 10          # Job Number
    input_frame.op_row = 11           # Operator
    input_frame.comm_row = 12         # Comments
    input_frame.h4_row = 13       # Separator before Run button
    input_frame.run_row = 14      # Run button
    input_frame.out_row = 15      # Output area

    # Configure rows with more space
    input_frame.rowconfigure([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], weight=1, minsize=35)

    # Define Automation1 Studio-inspired color palette
    BACKGROUND = "#F0F0F0"  # Light gray background
    WHITE = "#FFFFFF"  # Pure white for input fields
    BLUE_PRIMARY = "#0078D4"  # Aerotech blue
    BLUE_HOVER = "#106EBE"  # Slightly darker blue for hover
    BLUE_ACTIVE = "#005A9E"  # Darker blue for clicking
    TEXT_PRIMARY = "#252423"  # Darker gray for primary text
    TEXT_SECONDARY = "#484644"  # Medium gray for secondary text
    BORDER = "#E1E1E1"  # Light border color
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
    
    # Create the text frame with adjusted padding
    text_frame = tk.Frame(master=window)
    text_frame.grid(row=1, column=0, sticky='nsew', padx=20, pady=10)  # Reduced pady from 15
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
    
    def start_test_thread():
        global allocated_stations
        """Start a test thread for the required number of stations."""
        num_stations = var_num_axes.get()
        serial_number = var_job.get()
        program_id = id(threading.current_thread())
        
        try:
            # Try to allocate stations
            station_manager.refresh_station_status()
            allocated_stations = station_manager.allocate_stations(
                num_stations, program_id, serial_number
            )
            print(f'Allocated Stations: {allocated_stations}')
            messagebox.showinfo("Connect Stages", f"Connect stages to the following stations: {allocated_stations}. Press OK to continue.")
            if allocated_stations is None:
                messagebox.showwarning(
                    "No Stations Available", 
                    f"Need {num_stations} stations, but not enough are available.\n"
                    "Please wait for other tests to complete."
                )
                return

            # Create station controllers dictionary
            station_controllers = {
                station_manager.station_states[station]["axis_name"]: 
                station_manager.station_dict[station]
                for station in allocated_stations
            }

            def run_test():
                # Get only newly allocated stations for this run
                new_stations = [int(station[2:]) for station, state in station_manager.station_states.items()
                                if state["program_id"] == program_id 
                                and state["status"] == "in-use"
                                and int(station[2:]) not in previously_allocated_stations]
                
                # Update our tracking of allocated stations
                previously_allocated_stations.update(new_stations)
                
                try:
                    for station in new_stations:  # Only process new stations
                        # Assign serial number to each station
                        text_widget = secondary_ui.station_widgets[station]["txt_logs"]
                        station_states[station]["serial_number"] = serial_number
                        station_states[station]["running"] = True  # Mark as running
                        
                        # Instead of creating new TextLogger, let's use the existing one from the station
                        if station in secondary_ui.station_loggers:
                            sys.stdout = secondary_ui.station_loggers[station]
                        else:
                            # Only create new logger if one doesn't exist
                            secondary_ui.station_loggers[station] = TextLogger(text_widget, clear_existing=False)
                            sys.stdout = secondary_ui.station_loggers[station]
                    
                    # Only update UI for new stations
                    secondary_ui.update_station_status(new_stations, running=True, serial=serial_number)
                    user_data = {
                                "speed": var_speed.get(),
                                "job": var_job.get(),
                                "operator": var_op.get(),
                                "comments": var_comm.get(),
                                "duty_cycle": var_duty_cycle.get()
                            }
                    save_user_inputs(user_data)
                    # Your existing test logic here
                    test(program_id, serial_number, station_controllers)
                except Exception as e:
                    messagebox.showerror(
                        "Test Error",
                        f"An error occurred during testing: {str(e)}"
                    )
                finally:
                    # Always release stations when done
                    try:
                        if allocated_stations:  # Only try to release if we have stations
                            station_manager.release_stations(allocated_stations)
                            # Remove each individual station number from previously_allocated_stations
                            for station in allocated_stations:
                                station_num = int(station[2:])  # Convert 'ST01' to 1
                                if station_num in previously_allocated_stations:
                                    previously_allocated_stations.remove(station_num)
                    except ValueError as e:
                        print(f"Station Release Error (likely already released): {str(e)}")
                    except Exception as e:
                        print(f"Unexpected error during station release: {str(e)}")
                    secondary_ui.update_station_status(new_stations, running=False, serial="")
                    available_stations = station_manager.get_available_stations()
                    print(f"Stations {new_stations} are now free.")
                    window.after(0, lambda: btn_run.config(state=tk.NORMAL))

            # Disable run button during test
            btn_run.config(state=tk.DISABLED)
            thread = threading.Thread(target=run_test, daemon=True)
            thread.start()

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
        #print("Run button re-enabled.")    
    
    def test(program_id, serial_number, station_controllers):
        """Main test function in UI.py"""
        def prompt_user(message):
            text_logger.write(message)
            txt_outStr.delete(1.0, tk.END)
            return text_logger.read_input()

        def clear_text():
            txt_outStr.delete(1.0, tk.END)
        
        sys.stdout = text_logger
        
        stage_type = str(part_number.get())
        num_axes = int(var_num_axes.get())
        speed = float(var_speed.get())
        job = str(var_job.get())
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
                    #print(f"Connecting to {axis_name} at {ip_address}...")
                    controller = a1.Controller.connect(host=ip_address)
                    #print("Controller connected, starting...")
                    controller.start()
                    initialized_controllers[axis_name] = controller
                    print(f"Successfully connected to {axis_name} at {ip_address}")
                    #print(f"{axis_name} running: {controller.is_running}")
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
            
            # Run the test
            stage_test = stage_checkout(
                stage_type, speed, BI_time, job, op, 
                comm, secondary_ui, window, num_axes, 
                test_axes, duty_cycle, specs_dict, 
                absolute, stations
            )

            # Register abort callbacks for each station
            for axis in test_axes:
                station_id = int(axis[2:])  # Convert 'ST01' to 1
                stage_test.secondary_ui.register_abort_callback(
                    station_id, 
                    lambda axis=axis: stage_test.abort_test(axis)
                )

            #print(f'Station Controllers-test: {station_controllers}')
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
        #print("Resources cleaned up and garbage collection completed.")

    global part_number
    part_number = tk.StringVar(value="Scan Part Number Barcode")

    def on_scan():
        global specs_dict
        #file_path = r'C:\Users\tbates\Python\automated-checkout-bench\Temp Files\specs.txt'
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        app_instance = App()
        try:
            stage_spec_names, stage_spec_vals, smart_string = app_instance.show_popup_config_dialog(stage=part_entry.get())
        except TypeError:
            app.quit()
            return
        if stage_spec_names and stage_spec_vals:
            # Create a dictionary by zipping the two lists
            specs_dict = dict(zip(stage_spec_names, stage_spec_vals))
        else:
            print("No stage specifications found.")

        app_instance.deleteLater()  # Close the App instance
        del app_instance      # Ensure the instance is deleted
        app.quit()            # Quit the QApplication

    def time_def():
        global BI_state
        if time_var.get() == 'default':
            ent_other["state"] = tk.DISABLED
            BI_state = 'default'
        elif time_var.get() == 'other':
            ent_other["state"] = tk.NORMAL
            BI_state = 'other'
    
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

    # Part Number section
    lbl_stage = tk.Label(master=input_frame, text="Part Number", font=label_font)
    lbl_stage.grid(row=input_frame.ID_row, column=0, padx=standard_padx, pady=standard_pady)

    part_entry = tk.Entry(input_frame, textvariable=part_number, width=25, font=("Segoe UI", 9))
    part_entry.grid(row=input_frame.ID_row, column=1, padx=standard_padx, pady=standard_pady)
    part_entry.bind("<FocusIn>", on_entry_focus)
    part_entry.focus()

    scan_button = tk.Button(input_frame, text="Configure", width=15, height=1, font=label_font, command=on_scan)
    scan_button.grid(row=input_frame.ID_row, column=2, columnspan=2, padx=standard_padx, pady=standard_pady)

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
    
    var_speed = tk.DoubleVar(value=speed_value)
    ent_speed = tk.Entry(master=input_frame, textvariable=var_speed, width=15)
    ent_speed.grid(row=input_frame.speed_row, column=1, padx=standard_padx, pady=standard_pady)
    
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
    
    # Documentation section
    lbl_job = tk.Label(master=input_frame, text="Job Number", font=label_font)
    lbl_job.grid(row=input_frame.job_row, column=0, padx=standard_padx, pady=standard_pady)
    
    var_job = tk.StringVar(value=job_value)
    ent_job = tk.Entry(master=input_frame, textvariable=var_job, width=50)
    ent_job.grid(row=input_frame.job_row, column=1, columnspan=3, padx=standard_padx, pady=standard_pady)
    
    lbl_op = tk.Label(master=input_frame, text="Operator", font=label_font)
    lbl_op.grid(row=input_frame.op_row, column=0, padx=standard_padx, pady=standard_pady)
    
    var_op = tk.StringVar(value=op_value)
    ent_op = tk.Entry(master=input_frame, textvariable=var_op, width=50)
    ent_op.grid(row=input_frame.op_row, column=1, columnspan=3, padx=standard_padx, pady=standard_pady)
    
    lbl_comments = tk.Label(master=input_frame, text="Comments", font=label_font)
    lbl_comments.grid(row=input_frame.comm_row, column=0, padx=standard_padx, pady=standard_pady)
    
    var_comm = tk.StringVar(value=comm_value)
    ent_comments = tk.Entry(master=input_frame, textvariable=var_comm, width=50)
    ent_comments.grid(row=input_frame.comm_row, column=1, columnspan=3, padx=standard_padx, pady=standard_pady)

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
                "job": var_job.get(),
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
        "relief": "solid",
        "borderwidth": 1,
        "highlightthickness": 1,
        "highlightbackground": BORDER,
        "highlightcolor": BORDER,
        "bg": WHITE,
        "fg": TEXT_SECONDARY
    }

    # Apply entry style to all entry fields
    for entry in [part_entry, ent_num_axes, ent_speed, ent_duty_cycle, ent_other, ent_job, ent_op, ent_comments]:
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
    main_input_labels = [lbl_stage, lbl_num_axes, lbl_abs, lbl_speed, lbl_duty_cycle, lbl_cycles, lbl_job, lbl_op, lbl_comments]  # Main input labels
    main_input_entries = [part_entry, ent_num_axes, ent_speed, ent_duty_cycle, ent_job, ent_op, ent_comments]  # Their corresponding entry fields
    
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
    
    scan_button.configure(
        **action_button_style,
        padx=15,
        pady=8
    )
    
    # Configure frames
    input_frame.configure(
        bg=BACKGROUND,
        highlightbackground=BORDER,
        highlightthickness=1,
        bd=0
    )
    
    text_frame.configure(
        bg=BACKGROUND,
        highlightbackground=BORDER,
        highlightthickness=1,
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