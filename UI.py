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
    def run_secondary_ui():
        global secondary_ui
        secondary_ui = SecondaryUI()
        secondary_ui.run()

    thread = threading.Thread(target=run_secondary_ui, daemon=True)
    thread.start()

def UI():
    global window, station_manager
    window = tk.Tk()
    window.title("Check-out Station")
    
    # Initialize StationManager
    station_manager = StationManager(window)
    set_station_manager(station_manager)
    
    # Load stored user inputs
    stored_data = load_user_inputs()
    
    # Initialize Tkinter window
    window.resizable(True, False)  # This code helps to disable windows from resizing

    # Get screen width and height, including taskbar
    screen_width = ctypes.windll.user32.GetSystemMetrics(0)  # Full screen width
    screen_height = ctypes.windll.user32.GetSystemMetrics(1)  # Full screen height
    
    # Get the usable work area size (excluding taskbar)
    usable_width = ctypes.windll.user32.GetSystemMetrics(78)  # Width excluding taskbar
    usable_height = ctypes.windll.user32.GetSystemMetrics(79)  # Height excluding taskbar
    
    # Set desired window size
    window_height = 950
    window_width = 775
    
    # Ensure the window size does not exceed usable screen dimensions
    window_width = min(window_width, usable_width)
    window_height = min(window_height, usable_height)
    
    # Center the window on the screen
    x_cordinate = 0
    y_cordinate = 0
    
    # Set window size and position
    window.geometry(f"{window_width}x{window_height}+{x_cordinate}+{y_cordinate}")
    
    window.grid_rowconfigure(0, weight=1)
    window.grid_rowconfigure(1, weight=1)
    window.grid_columnconfigure(0, weight=1)
    window.grid_columnconfigure(1, weight=1)

    '''
    # MAIN USER INPUT FRAME
    '''
    
    input_frame_width = 700
    input_frame_height = 800
    
    input_frame = tk.Frame(master=window, width=input_frame_width, height=input_frame_height)
    input_frame.grid(row=0, column=0, sticky='nsew')
    input_frame.grid_propagate(True)
    
    # Configure columns and rows
    input_frame.columnconfigure([0, 1, 2, 3], weight=1, minsize=700 / 4, uniform='column')
    input_frame.rowconfigure([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13], weight=1, minsize=1)

    # Define row indices
    input_frame.h1_row = 0
    input_frame.ID_row = 1
    input_frame.config_button_row = 2
    input_frame.h2_row = 3
    input_frame.num_axes_row = 4
    input_frame.speed_row = 5
    input_frame.cycles_row = 6
    input_frame.h3_row = 7
    input_frame.job_row = 8
    input_frame.op_row = 9
    input_frame.comm_row = 10
    input_frame.h4_row = 11
    input_frame.run_row = 12
    input_frame.out_row = 13

    # Create horizontal separators
    ttk.Separator(master=input_frame, orient='horizontal').grid(row=input_frame.h1_row, column=0, columnspan=4, sticky='nsew')
    ttk.Separator(master=input_frame, orient='horizontal').grid(row=input_frame.h2_row, column=0, columnspan=4, sticky='nsew')
    ttk.Separator(master=input_frame, orient='horizontal').grid(row=input_frame.h3_row, column=0, columnspan=4, sticky='nsew')
    ttk.Separator(master=input_frame, orient='horizontal').grid(row=input_frame.h4_row, column=0, columnspan=4, sticky='nsew')
    
    # Load stored data or set defaults
    speed_value = stored_data.get("speed", 360)
    job_value = stored_data.get("job", '"Job Number"')
    op_value = stored_data.get("operator", '"Your Initials"')
    comm_value = stored_data.get("comments", "")
    duty_cycle_value = stored_data.get('duty_cycle', 25)
    
    '''
    # TEXT WIDGET FRAME
    '''
    
    # Create the frame without fixed width and height
    text_frame = tk.Frame(master=window)
    text_frame.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
    text_frame.grid_propagate(False)  # Allow frame to resize based on content
    
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
    
    launch_secondary_ui()
    
    def start_test_thread():
        global allocated_stations
        """Start a test thread for the required number of stations."""
        num_stations = var_num_axes.get()
        serial_number = var_job.get()
        program_id = id(threading.current_thread())
        
        try:
            # Try to allocate stations
            allocated_stations = station_manager.allocate_stations(
                num_stations, program_id, serial_number
            )
            print(f'Allocated Stations: {allocated_stations}')
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
                stations = [int(station[2:]) for station, state in station_manager.station_states.items()
                        if state["program_id"] == program_id]
                try:
                    for station in stations:
                        # Assign serial number to each station
                        text_widget = secondary_ui.station_widgets[station]["txt_logs"]
                        station_states[station]["serial_number"] = serial_number
                        # Instead of creating new TextLogger, let's use the existing one from the station
                        if station in secondary_ui.station_loggers:
                            sys.stdout = secondary_ui.station_loggers[station]
                        else:
                            # Only create new logger if one doesn't exist
                            secondary_ui.station_loggers[station] = TextLogger(text_widget, clear_existing=False)
                            sys.stdout = secondary_ui.station_loggers[station]
                    secondary_ui.update_station_status(stations, running=True, serial=serial_number)
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
                    station_manager.release_stations(allocated_stations)
                    secondary_ui.update_station_status(stations, running=False, serial="")
                    print(f"Stations {stations} are now free.")
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
            #print(f'Station Controllers-test: {station_controllers}')
            stage_test.test(reenable_run_button, initialized_controllers)  

        except Exception as e:
            print(f"Test error: {str(e)}")
            raise
        finally:
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

    # Test Type Selection
    lbl_stage = tk.Label(master=input_frame, text="Part Number", font=label_font)
    lbl_stage.grid(row=input_frame.ID_row, column=0, padx=5, pady=5)

    part_entry = tk.Entry(input_frame, textvariable=part_number, width=25)
    part_entry.grid(row=input_frame.ID_row, column=1, columnspan=2, padx=5, pady=5)
    part_entry.bind("<FocusIn>", on_entry_focus)
    part_entry.focus()

    scan_button = tk.Button(input_frame, text="Retrieve Stage Options", width=20, height=1, font=button_font, background="lightgray", command=on_scan)
    scan_button.grid(row=input_frame.config_button_row, column=1, columnspan=2, padx=5, pady=5)

    lbl_num_axes = tk.Label(master=input_frame, text="Number Of Stages", width=25, height=1, font=label_font)
    lbl_num_axes.grid(row=input_frame.num_axes_row, column=0, padx=5, pady=5)
    
    var_num_axes = tk.IntVar(value="")
    ent_num_axes = tk.Entry(master=input_frame, textvariable=var_num_axes, width=15)
    ent_num_axes.grid(row=input_frame.num_axes_row, column=1, padx=5, pady=5)
    
    lbl_abs = tk.Label(master=input_frame, text="Absolute Encoder?", width=25, height=1, font=label_font)
    lbl_abs.grid(row=input_frame.num_axes_row, column=2, padx=5, pady=5)
    
    abs_var = tk.StringVar(value="No")
    abs_ent = tk.Radiobutton(master=input_frame, text="Yes", variable=abs_var, value="Yes", command=abs_def)
    abs_ent.grid(row=input_frame.num_axes_row, column=3, padx=5, pady=5)

    lbl_speed = tk.Label(master=input_frame, text="Burn-In Speed", width=25, height=1, font=label_font)
    lbl_speed.grid(row=input_frame.speed_row, column=0, padx=5, pady=5)
    
    var_speed = tk.DoubleVar(value=speed_value)
    ent_speed = tk.Entry(master=input_frame, textvariable=var_speed, width=15)
    ent_speed.grid(row=input_frame.speed_row, column=1, padx=5, pady=5)
    
    lbl_duty_cycle = tk.Label(master=input_frame, text="Duty Cycle", width=25, height=1, font=label_font)
    lbl_duty_cycle.grid(row=input_frame.speed_row, column=2, padx=5, pady=5)
    
    var_duty_cycle = tk.DoubleVar(value=duty_cycle_value)
    ent_duty_cycle = tk.Entry(master=input_frame, textvariable=var_duty_cycle, width=15)
    ent_duty_cycle.grid(row=input_frame.speed_row, column=3, padx=5, pady=5)
    
    lbl_cycles = tk.Label(master=input_frame, text="Burn-In Time", width=25, height=1, font=label_font)
    lbl_cycles.grid(row=input_frame.cycles_row, column=0, padx=5, pady=5)
    
    time_var = tk.StringVar(value=0)
    default = tk.Radiobutton(master=input_frame, text="Default", variable=time_var, value="default", command=time_def)
    default.grid(row=input_frame.cycles_row, column=1, padx=5, pady=5)
    
    other = tk.Radiobutton(master=input_frame, text="Other (Hours)", variable=time_var, value="other", command=time_def)
    other.grid(row=input_frame.cycles_row, column=2, padx=5, pady=5)
    
    var_time = tk.IntVar(value=0)
    ent_other = tk.Entry(master=input_frame, textvariable=var_time, width=15,state=tk.DISABLED)
    ent_other.grid(row=input_frame.cycles_row, column=3, padx=5, pady=5)
    
    # Stage Serial Number Input
    lbl_job = tk.Label(master=input_frame, text="Job Number", font=label_font)
    lbl_job.grid(row=input_frame.job_row, column=0, padx=5, pady=5)
    
    var_job = tk.StringVar(value=job_value)
    ent_job = tk.Entry(master=input_frame, textvariable=var_job, width=45)
    ent_job.grid(row=input_frame.job_row, column=1, columnspan=3, padx=5, pady=5)
    
    # Operator Input
    lbl_op = tk.Label(master=input_frame, text="Operator", font=label_font)
    lbl_op.grid(row=input_frame.op_row, column=0, padx=5, pady=5)
    
    var_op = tk.StringVar(value=op_value)
    ent_op = tk.Entry(master=input_frame, textvariable=var_op, width=45)
    ent_op.grid(row=input_frame.op_row, column=1, columnspan=3, padx=5, pady=5)
    
    # Comments Input
    lbl_comments = tk.Label(master=input_frame, text="Comments", font=label_font)
    lbl_comments.grid(row=input_frame.comm_row, column=0, padx=5, pady=5)
    
    var_comm = tk.StringVar(value=comm_value)
    ent_comments = tk.Entry(master=input_frame, textvariable=var_comm, width=45)
    ent_comments.grid(row=input_frame.comm_row, column=1, columnspan=3, padx=5, pady=5)
    
    # Run and Open Plot Buttons
    btn_run = tk.Button(master=input_frame, text="Run", width=25, height=1, command=start_test_thread, bg='lightgray', font=button_font)
    btn_run.grid(row=input_frame.run_row, column=1, columnspan=2, padx=5, pady=5)
    
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

    window.mainloop()
    
if __name__ == "__main__":
    UI()