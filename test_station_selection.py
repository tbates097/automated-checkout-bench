"""
Test script for the station selection dialog integration
"""

import tkinter as tk
from tkinter import messagebox
import sys
import os

# Add the current directory to the path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from station_manager import StationManager
    from station_manager_instance import set_station_manager
    from station_selection_dialog import show_station_selection_dialog
    from ui_styles import *
    
    def test_station_selection():
        """Test the station selection dialog"""
        
        # Create a test window
        root = tk.Tk()
        root.title("Station Selection Test")
        root.configure(**frame_style)
        
        # Apply consistent styling and centering
        apply_dialog_styling(root)
        center_window_on_screen(root, 500, 300)
        
        # Initialize station manager
        station_manager = StationManager(root)
        set_station_manager(station_manager)
        station_manager.start()
        
        def run_test():
            """Run the station selection test"""
            # Test with different numbers of stations to verify dynamic sizing
            import random
            num_stations = random.randint(1, 5)  # Random between 1-5 stations
            program_id = 12345
            serial_number = "TEST123"
            print(f"Testing with {num_stations} stations")
            
            try:
                result = show_station_selection_dialog(
                    root, num_stations, program_id, serial_number
                )
                
                if result:
                    mode = result["mode"]
                    stations = result["stations"]
                    messagebox.showinfo(
                        "Test Result",
                        f"Selection successful!\nMode: {mode}\nStations: {stations}"
                    )
                else:
                    messagebox.showinfo("Test Result", "User cancelled selection")
                    
            except Exception as e:
                messagebox.showerror("Test Error", f"Error occurred: {str(e)}")
        
        # Create test interface
        tk.Label(root, text="Station Selection Dialog Test", 
                font=("Segoe UI", 14, "bold"), **main_label_style).pack(pady=20)
        
        tk.Label(root, text="Test with different numbers of stations:", 
                font=("Segoe UI", 10), **supporting_label_style).pack(pady=10)
        
        # Button frame for multiple test options
        button_frame = tk.Frame(root, **frame_style)
        button_frame.pack(pady=10)
        
        def test_with_stages(num_stages):
            program_id = 12345
            serial_number = f"TEST{num_stages}ST"
            print(f"Testing with {num_stages} stations")
            try:
                result = show_station_selection_dialog(
                    root, num_stages, program_id, serial_number
                )
                if result:
                    mode = result["mode"]
                    stations = result["stations"]
                    messagebox.showinfo(
                        "Test Result",
                        f"Selection successful!\nStages: {num_stages}\nMode: {mode}\nStations: {stations}"
                    )
                else:
                    messagebox.showinfo("Test Result", "User cancelled selection")
            except Exception as e:
                messagebox.showerror("Test Error", f"Error occurred: {str(e)}")
        
        # Create buttons for different stage quantities
        for i in range(1, 6):
            btn = tk.Button(
                button_frame,
                text=f"{i} Stage{'s' if i > 1 else ''}",
                command=lambda n=i: test_with_stages(n),
                width=8,
                font=("Segoe UI", 11),
                **action_button_style
            )
            btn.pack(side=tk.LEFT, padx=5)
        
        # Random test button
        random_btn = tk.Button(
            root,
            text="Random Test",
            command=run_test,
            font=("Segoe UI", 10),
            **button_style
        )
        random_btn.pack(pady=20)
        
        def on_closing():
            """Clean up when closing"""
            station_manager.stop()
            root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        root.mainloop()
    
    if __name__ == "__main__":
        test_station_selection()
        
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure you're running this from the correct directory.")
except Exception as e:
    print(f"Error: {e}")