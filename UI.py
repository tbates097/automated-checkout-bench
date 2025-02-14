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


#sys.path.append(r"K:\10. Released Software\Systems Manufacturing Support\Shared")
sys.path.append(r"C:\Users\tbates\Python\shared")
from Logger import TextLogger

# Shared station state
station_states = {
    i: {"status": "free", "thread": None, "serial_number": None, "axis_name": f"ST{i:02}"} for i in range(1, 11)
}
station_lock = threading.Lock()

secondary_ui = None
test_axes = []
specs_dict = {}
absolute = False
stations = []

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

def allocate_stations(num_stations):
    """Allocate the required number of free stations, or return None if not enough are available."""
    with station_lock:
        free_stations = [station for station, state in station_states.items() if state["status"] == "free"]
        if len(free_stations) >= num_stations:
            allocated = free_stations[:num_stations]
            for station in allocated:
                station_states[station]["status"] = "in-use"
            return allocated
        return None

def release_stations(stations):
    """Release multiple stations and mark them as free."""
    with station_lock:
        for station in stations:
            station_states[station]["status"] = "free"
            station_states[station]["thread"] = None
            station_states[station]["serial_number"] = None

def launch_secondary_ui():
    """Launch the secondary UI in a new thread."""
    def run_secondary_ui():
        global secondary_ui
        secondary_ui = SecondaryUI()
        secondary_ui.run()

    thread = threading.Thread(target=run_secondary_ui, daemon=True)
    thread.start()

def UI():
    global window
    
    # Load stored user inputs
    stored_data = load_user_inputs()
    
    # Initialize Tkinter window
    window = tk.Tk()
    window.title("Check-out Station")
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
        """Start a test thread for the required number of stations."""
        global test_axes, stations
        num_stations = var_num_axes.get()
        serial_number = var_job.get()
        stations = allocate_stations(num_stations)
        if stations is None:
            print("Not enough free stations available.")
            return

        print(f"Allocating Stations {stations} for serial number {serial_number}")
        test_axes = [str(station_states[station]["axis_name"]) for station in stations]

        def run_test():

            try:
                for station in stations:
                    # Assign serial number to each station
                    text_widget = secondary_ui.station_widgets[station]["txt_logs"]
                    station_states[station]["serial_number"] = serial_number
                    sys.stdout = TextLogger(text_widget)
                    #print(f"Running test on Station {station} with Serial Number: {serial_number}")
                secondary_ui.update_station_status(stations, running=True, serial=serial_number)
                user_data = {
                            "speed": var_speed.get(),
                            "job": var_job.get(),
                            "operator": var_op.get(),
                            "comments": var_comm.get(),
                            "duty_cycle": var_duty_cycle.get()
                        }
                save_user_inputs(user_data)
                
                try:
                    test()
                finally:
                    gc.collect()
                    window.after(0, lambda: btn_run.config(state=tk.NORMAL))

                print(f"Test completed on Stations {stations}")
            finally:
                release_stations(stations)
                secondary_ui.update_station_status(stations, running=False, serial="")
                print(f"Stations {stations} are now free.")

        thread = threading.Thread(target=run_test, daemon=True)
        for station in stations:
            station_states[station]["thread"] = thread
        thread.start()
    
    def reenable_run_button():
        """
        Re-enables the 'Run' button in the UI.
        """
        btn_run.config(state=tk.NORMAL)
        print("Run button re-enabled.")    
    
    def test():
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
        
        global controller, stage_test
        
        def controller_def():
            ver = tk.Toplevel(input_frame)
            ver.title('Connection Type')
            ver.configure(bg='white')

            custom_font = font.Font(family="Times New Roman", size=12, weight="bold", slant="italic")

            label = tk.Label(ver, text="Are you trying to connect via USB?", bg='white', font=custom_font)
            label.grid(row=0, column=0, columnspan=2, padx=10, pady=5)

            def on_yes():
                ver.result = 'yes'
                ver.destroy()

            def on_no():
                ver.result = 'No'
                ver.destroy()

            button_ok = tk.Button(ver, text="Yes", width=10, height=2, command=on_yes)
            button_ok.grid(row=4, column=0, padx=10, pady=10)

            button_cancel = tk.Button(ver, text="No", width=10, height=2, command=on_no)
            button_cancel.grid(row=4, column=1, padx=10, pady=10)

            ver.resizable(False, False)

            ver.update_idletasks()  # Ensure that the window sizes correctly

            screen_width = ver.winfo_screenwidth()
            screen_height = ver.winfo_screenheight()

            ver_width = ver.winfo_reqwidth()
            ver_height = ver.winfo_reqheight()

            x_cordinate = int((screen_width / 2) - (ver_width / 2))
            y_cordinate = int((screen_height / 2) - (ver_height / 2))

            ver.geometry("{}x{}+{}+{}".format(ver_width, ver_height, x_cordinate, y_cordinate))
            ver.focus_set()
            ver.result = None
            ver.wait_window()

            return ver.result

        try:
            controller = a1.Controller.connect()
            controller.start()
        except:
            connection_type = controller_def()
            if connection_type == 'yes':
                try:
                    controller = a1.Controller.connect_usb()
                    controller.start()
                except:
                    messagebox.showerror('Connection Error', 'Check connections and try again')
            else:
                messagebox.showerror('Update Software', 'Update Hyperwire firmware and try again')
        connected_axes = {}
        non_virtual_axes = []

        number_of_axes = controller.runtime.parameters.axes.count

        if number_of_axes <= 12:
            for axis_index in range(0,11):
                status_item_configuration = a1.StatusItemConfiguration()
                status_item_configuration.axis.add(a1.AxisStatusItem.AxisStatus, axis_index)
                
                result = controller.runtime.status.get_status_items(status_item_configuration)
                axis_status = int(result.axis.get(a1.AxisStatusItem.AxisStatus, axis_index).value)
                if (axis_status & 1 << 13) > 0:
                    connected_axes[controller.runtime.parameters.axes[axis_index].identification.axisname.value] = axis_index
            for key, value in connected_axes.items():
                non_virtual_axes.append(key)
        else:
            for axis_index in range(0,32):
                status_item_configuration = a1.StatusItemConfiguration()
                status_item_configuration.axis.add(a1.AxisStatusItem.AxisStatus, axis_index)
                result = controller.runtime.status.get_status_items(status_item_configuration)
                axis_status = int(result.axis.get(a1.AxisStatusItem.AxisStatus, axis_index).value)
                if (axis_status & 1 << 13) > 0:
                    connected_axes[controller.runtime.parameters.axes[axis_index].identification.axisname.value] = axis_index
            for key, value in connected_axes.items():
                print(f'Key: {key}')
                print(f'Value: {value}')
                non_virtual_axes.append(key)
        if len(non_virtual_axes) == 0:
            #try:
            controller = a1.Controller.connect_usb()
            number_of_axes = controller.runtime.parameters.axes.count
            if number_of_axes <= 12:
                for axis_index in range(0,11):
                    status_item_configuration = a1.StatusItemConfiguration()
                    status_item_configuration.axis.add(a1.AxisStatusItem.AxisStatus, axis_index)
                    
                    result = controller.runtime.status.get_status_items(status_item_configuration)
                    axis_status = int(result.axis.get(a1.AxisStatusItem.AxisStatus, axis_index).value)
                    if (axis_status & 1 << 13) > 0:
                        connected_axes[controller.runtime.parameters.axes[axis_index].identification.axisname.value] = axis_index
                for key, value in connected_axes.items():
                    non_virtual_axes.append(key)
            else:
                for axis_index in range(0,32):
                    status_item_configuration = a1.StatusItemConfiguration()
                    status_item_configuration.axis.add(a1.AxisStatusItem.AxisStatus, axis_index)
                    result = controller.runtime.status.get_status_items(status_item_configuration)
                    axis_status = int(result.axis.get(a1.AxisStatusItem.AxisStatus, axis_index).value)
                    if (axis_status & 1 << 13) > 0:
                        connected_axes[controller.runtime.parameters.axes[axis_index].identification.axisname.value] = axis_index
       
        # Run the test
        stage_test = stage_checkout(
            stage_type, speed, BI_time, job, op, 
            comm, secondary_ui, window, num_axes, 
            test_axes, duty_cycle, specs_dict, 
            absolute, stations
        )
        stage_test.test(controller, reenable_run_button)  
            
        #cleanup_resources()
        #print('Cleaning Up')
        return
    
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
            print(f"Specifications Dictionary: {specs_dict}")
            print(f"Smart String: {smart_string}")
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