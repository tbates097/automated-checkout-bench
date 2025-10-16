"""
Quick verification script to demonstrate the station selection dialog fixes
"""

import tkinter as tk
from tkinter import messagebox
import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from station_manager import StationManager
    from station_manager_instance import set_station_manager
    from station_selection_dialog import show_station_selection_dialog
    from ui_styles import *
    
    def verify_fixes():
        """Verify the dialog fixes"""
        
        root = tk.Tk()
        root.title("Station Selection Fixes Verification")
        root.configure(**frame_style)
        
        # Apply consistent styling and centering
        apply_dialog_styling(root)
        center_window_on_screen(root, 650, 350)
        
        # Initialize station manager
        station_manager = StationManager(root)
        set_station_manager(station_manager)
        station_manager.start()
        
        # Create verification interface
        tk.Label(root, text="Station Selection Dialog Fixes Verification", 
                font=("Segoe UI", 16, "bold")).pack(pady=20)
        
        tk.Label(root, text="Testing fixes for:", font=("Segoe UI", 12)).pack(pady=10)
        tk.Label(root, text="✓ Dynamic window sizing based on stage count", font=("Segoe UI", 10)).pack()
        tk.Label(root, text="✓ Proper disable/enable of manual selection", font=("Segoe UI", 10)).pack()
        
        # Test buttons frame
        test_frame = tk.Frame(root)
        test_frame.pack(pady=30)
        
        tk.Label(test_frame, text="Test with different stage counts:", 
                font=("Segoe UI", 11, "bold")).pack(pady=(0, 10))
        
        button_frame = tk.Frame(test_frame)
        button_frame.pack()
        
        def test_stages(count):
            print(f"\\n=== Testing {count} stages ===")
            print(f"Expected window height: {250 + (count * 35)} pixels")
            
            result = show_station_selection_dialog(
                root, count, 12345, f"TEST{count}"
            )
            
            if result:
                messagebox.showinfo(
                    "Test Result",
                    f"SUCCESS!\\n\\nStages: {count}\\nMode: {result['mode']}\\n"
                    f"Stations: {result['stations']}\\n\\n"
                    f"Window should have resized to fit {count} stage{'s' if count != 1 else ''}."
                )
            else:
                print("User cancelled the dialog")
        
        # Create test buttons for 1-6 stages
        for i in range(1, 7):
            color = "#0078D4" if i <= 3 else "#28A745" if i <= 5 else "#DC3545"
            btn = tk.Button(
                button_frame,
                text=f"{i}",
                command=lambda n=i: test_stages(n),
                font=("Segoe UI", 10, "bold"),
                bg=color,
                fg="white",
                width=3,
                height=1
            )
            btn.pack(side=tk.LEFT, padx=2)
        
        # Instructions
        instructions_frame = tk.Frame(root)
        instructions_frame.pack(pady=20)
        
        tk.Label(instructions_frame, text="Instructions:", font=("Segoe UI", 11, "bold")).pack()
        tk.Label(instructions_frame, text="1. Click any number button to test that many stages", font=("Segoe UI", 10)).pack()
        tk.Label(instructions_frame, text="2. Notice the dialog window resizes automatically", font=("Segoe UI", 10)).pack()
        tk.Label(instructions_frame, text="3. Try both 'Auto' and 'Manual' modes", font=("Segoe UI", 10)).pack()
        tk.Label(instructions_frame, text="4. Verify manual dropdowns are disabled in Auto mode", font=("Segoe UI", 10)).pack()
        
        def on_closing():
            station_manager.stop()
            root.destroy()
        
        root.protocol("WM_DELETE_WINDOW", on_closing)
        root.mainloop()
    
    if __name__ == "__main__":
        verify_fixes()
        
except ImportError as e:
    print(f"Import error: {e}")
    print("Make sure all required modules are available.")
except Exception as e:
    print(f"Error: {e}")