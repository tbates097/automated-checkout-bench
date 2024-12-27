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
from tkinter import ttk
import automation1 as a1
from checkout_test import hex_strut_checkout
import gc
import json
import ctypes
import threading

sys.path.append(r"K:\10. Released Software\Systems Manufacturing Support\Shared")
sys.path.append(r"C:\Users\tbates\Python\shared")
from Logger import TextLogger

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
    window_width = 1000
    
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
    
    input_frame_width = 1000
    input_frame_height = 800
    
    input_frame = tk.Frame(master=window, width=input_frame_width, height=input_frame_height)
    input_frame.grid(row=0, column=0, sticky='nsew')
    input_frame.grid_propagate(True)
    
    # Configure columns and rows
    input_frame.columnconfigure([0, 1, 2, 3, 4], weight=1, minsize=700 / 4, uniform='column')
    input_frame.rowconfigure([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12], weight=1, minsize=1)

    # Define row indices
    input_frame.h1_row = 0
    input_frame.type_row = 1
    input_frame.h2_row = 2
    input_frame.encoder_row = 3
    input_frame.speed_row = 4
    input_frame.cycles_row = 5
    input_frame.h3_row = 6
    input_frame.job_row = 7
    input_frame.op_row = 8
    input_frame.comm_row = 9
    input_frame.h4_row = 10
    input_frame.run_row = 11
    input_frame.out_row = 12

    # Create horizontal separators
    ttk.Separator(master=input_frame, orient='horizontal').grid(row=input_frame.h1_row, column=0, columnspan=5, sticky='nsew')
    ttk.Separator(master=input_frame, orient='horizontal').grid(row=input_frame.h2_row, column=0, columnspan=5, sticky='nsew')
    ttk.Separator(master=input_frame, orient='horizontal').grid(row=input_frame.h3_row, column=0, columnspan=5, sticky='nsew')
    ttk.Separator(master=input_frame, orient='horizontal').grid(row=input_frame.h4_row, column=0, columnspan=5, sticky='nsew')

# =============================================================================
#     # Adjust column weights so the vertical separator aligns correctly
#     input_frame.columnconfigure(3, weight=1)
#     input_frame.columnconfigure(4, weight=1)
#     
#     # Add the vertical separator to the frame
#     ttk.Separator(master=window, orient='vertical').grid(row=input_frame.h1_row, column=4, rowspan=12, sticky='nsw', pady=(4, 0))
#     # Add the vertical separator to the frame
#     ttk.Separator(master=window, orient='vertical').grid(row=input_frame.h1_row, column=4, rowspan=12, sticky='nsw', pady=(7, 0))
# =============================================================================
    
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
    
    def start_test_thread():
        """
        Starts the test thread for running the test.
        """
        global test_thread
        test_thread = threading.Thread(target=run_test, daemon=True)
        test_thread.start()
        #print('Test Thread Started')
        
        # Disable the Run button during the test
        btn_run.config(state=tk.DISABLED)
    
    def run_test():
        """
        Runs the test. Handles setup, execution, and resource cleanup.
        """
        # Save user inputs before closing
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
        
        speed = float(var_speed.get())
        job = str(var_job.get())
        op = str(var_op.get())
        comm = str(var_comm.get())
        duty_cycle = int(var_duty_cycle.get())
        if BI_state == 'default':
            BI_time = 4
        else:
            BI_time = int(var_time.get())
        
        global controller, strut_test
        
        controller = a1.Controller.connect()
        controller.start()
        
        connected_axes = {}
        
        for axis_index in range(0,11):

            #try:            
            # Create status item configuration object
            status_item_configuration = a1.StatusItemConfiguration()
                        
            # Add this axis status word to object
            status_item_configuration.axis.add(a1.AxisStatusItem.AxisStatus, axis_index)
            
            # Get axis status word from controller
            result = controller.runtime.status.get_status_items(status_item_configuration)
            axis_status = int(result.axis.get(a1.AxisStatusItem.AxisStatus, axis_index).value)
            
            # Check NotVirtual bit of axis status word
            if (axis_status & 1 << 13) > 0:
                connected_axes[controller.runtime.parameters.axes[axis_index].identification.axisname.value] = axis_index
        
        # Run the test
        strut_test = hex_strut_checkout(
            hex_type, encoder, speed, BI_time, job, op, 
            comm, txt_outStr, window, connected_axes, duty_cycle
        )
        strut_test.test(controller, reenable_run_button)  
            
        cleanup_resources()
        print('Cleaning Up')
        return
    def cleanup_resources(test=None):
        """
        Cleans up resources such as threads, connections, and resets global states.
        """
        global test_thread
    
        if test_thread and test_thread.is_alive():
            try:
                test_thread.join(timeout=1)
            except RuntimeError:
                pass
        test_thread = None
        
        # Clean up rot_cal specific resources
        if test:
            del test
        
        gc.collect()
        #print("Resources cleaned up and garbage collection completed.")
        
    def test_type_def():
        global hex_type
        if hexapod.get() == "150-125":
            hex_type = 'HEX150-125HL'
        elif hexapod.get() == "150-140":
            hex_type = 'HEX150-140HL'
        elif hexapod.get() == "300":
            hex_type = 'HEX300-230HL'
        elif hexapod.get() == "500":
            hex_type = 'HEX500-350HL'
    
    def encoder_def():
        global encoder
        if enc.get() == "E1":
            encoder = 'E1'
        elif enc.get() == "E2":
            encoder = 'E2'
        elif enc.get() == "E3":
            encoder = 'E3'
    
    def time_def():
        global BI_state
        if time_var.get() == 'default':
            ent_other["state"] = tk.DISABLED
            BI_state = 'default'
        elif time_var.get() == 'other':
            ent_other["state"] = tk.NORMAL
            BI_state = 'other'
    
    # Rotary Calibration Tab UI Elements

    # Test Type Selection
    lbl_test = tk.Label(master=input_frame, text="Part Number:")
    lbl_test.grid(row=input_frame.type_row, column=0, padx=5, pady=5)
    
    hexapod = tk.StringVar(value=0)
    hex150_125 = tk.Radiobutton(master=input_frame, text="HEX150-125HL", variable=hexapod, value="150-125", command=test_type_def)
    hex150_125.grid(row=input_frame.type_row, column=1, padx=5, pady=5)
    
    hex150_140 = tk.Radiobutton(master=input_frame, text="HEX150-140HL", variable=hexapod, value="150-140", command=test_type_def)
    hex150_140.grid(row=input_frame.type_row, column=2, padx=5, pady=5)
    
    hex300 = tk.Radiobutton(master=input_frame, text="HEX300-230HL", variable=hexapod, value="300", command=test_type_def)
    hex300.grid(row=input_frame.type_row, column=3, padx=5, pady=5)
    
    hex500 = tk.Radiobutton(master=input_frame, text="HEX500-350HL", variable=hexapod, value="500", command=test_type_def)
    hex500.grid(row=input_frame.type_row, column=4, padx=5, pady=5)
    
    # Test Type Selection
    lbl_enc = tk.Label(master=input_frame, text="Select Encoder:")
    lbl_enc.grid(row=input_frame.encoder_row, column=0, padx=5, pady=5)
    
    enc = tk.StringVar(value=0)
    E1 = tk.Radiobutton(master=input_frame, text="E1", variable=enc, value="E1", command=encoder_def)
    E1.grid(row=input_frame.encoder_row, column=1, padx=5, pady=5)
    
    E2 = tk.Radiobutton(master=input_frame, text="E2", variable=enc, value="E2", command=encoder_def)
    E2.grid(row=input_frame.encoder_row, column=2, padx=5, pady=5)
    
    E3 = tk.Radiobutton(master=input_frame, text="E3", variable=enc, value="E3", command=encoder_def)
    E3.grid(row=input_frame.encoder_row, column=3, padx=5, pady=5)
    
    # Total Travel Input
    lbl_speed = tk.Label(master=input_frame, text="Burn-In Speed", width=25, height=1)
    lbl_speed.grid(row=input_frame.speed_row, column=0, padx=5, pady=5)
    
    var_speed = tk.DoubleVar(value=speed_value)
    ent_speed = tk.Entry(master=input_frame, textvariable=var_speed, width=25)
    ent_speed.grid(row=input_frame.speed_row, column=1, padx=5, pady=5)
    
    lbl_duty_cycle = tk.Label(master=input_frame, text="Duty Cycle", width=25, height=1)
    lbl_duty_cycle.grid(row=input_frame.speed_row, column=2, padx=5, pady=5)
    
    var_duty_cycle = tk.DoubleVar(value=duty_cycle_value)
    ent_duty_cycle = tk.Entry(master=input_frame, textvariable=var_duty_cycle, width=25)
    ent_duty_cycle.grid(row=input_frame.speed_row, column=3, padx=5, pady=5)
    
    lbl_cycles = tk.Label(master=input_frame, text="Burn-In Time", width=25, height=1)
    lbl_cycles.grid(row=input_frame.cycles_row, column=0, padx=5, pady=5)
    
    time_var = tk.StringVar(value=0)
    default = tk.Radiobutton(master=input_frame, text="Default", variable=time_var, value="default", command=time_def)
    default.grid(row=input_frame.cycles_row, column=1, padx=5, pady=5)
    
    other = tk.Radiobutton(master=input_frame, text="Other", variable=time_var, value="other", command=time_def)
    other.grid(row=input_frame.cycles_row, column=2, padx=5, pady=5)
    
    var_time = tk.IntVar(value=0)
    ent_other = tk.Entry(master=input_frame, textvariable=var_time, width=25,state=tk.DISABLED)
    ent_other.grid(row=input_frame.cycles_row, column=3, padx=5, pady=5)
    
    # Stage Serial Number Input
    lbl_job = tk.Label(master=input_frame, text="Job Number", width=25, height=1)
    lbl_job.grid(row=input_frame.job_row, column=0, padx=5, pady=5)
    
    var_job = tk.StringVar(value=job_value)
    ent_job = tk.Entry(master=input_frame, textvariable=var_job, width=25)
    ent_job.grid(row=input_frame.job_row, column=1, columnspan=3, padx=5, pady=5)
    
    # Operator Input
    lbl_op = tk.Label(master=input_frame, text="Operator", width=25, height=1)
    lbl_op.grid(row=input_frame.op_row, column=0, padx=5, pady=5)
    
    var_op = tk.StringVar(value=op_value)
    ent_op = tk.Entry(master=input_frame, textvariable=var_op, width=25)
    ent_op.grid(row=input_frame.op_row, column=1, columnspan=3, padx=5, pady=5)
    
    # Comments Input
    lbl_comments = tk.Label(master=input_frame, text="Comments", width=25, height=1)
    lbl_comments.grid(row=input_frame.comm_row, column=0, padx=5, pady=5)
    
    var_comm = tk.StringVar(value=comm_value)
    ent_comments = tk.Entry(master=input_frame, textvariable=var_comm, width=25)
    ent_comments.grid(row=input_frame.comm_row, column=1, columnspan=3, padx=5, pady=5)
    
    # Run and Open Plot Buttons
    btn_run = tk.Button(master=input_frame, text="Run", width=25, height=1, command=start_test_thread)
    btn_run.grid(row=input_frame.run_row, column=0, padx=5, pady=5)
    
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