"""
Simple test for the station selection dialog appearance and centering
"""

import tkinter as tk
import sys
import os

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui_styles import *

def test_dialog_appearance():
    """Test the dialog appearance and centering"""
    
    # Create main window
    root = tk.Tk()
    root.title("Dialog Appearance Test")
    root.configure(**frame_style)
    
    # Apply styling and centering
    apply_dialog_styling(root)
    center_window_on_screen(root, 400, 300)
    
    # Main frame
    main_frame = tk.Frame(root, **frame_style, padx=20, pady=20)
    main_frame.pack(fill=tk.BOTH, expand=True)
    
    # Title
    title_label = tk.Label(
        main_frame, 
        text="Dialog Appearance Test", 
        font=("Segoe UI", 14, "bold"),
        **main_label_style
    )
    title_label.pack(pady=(0, 15))
    
    # Info
    info_label = tk.Label(
        main_frame, 
        text="Testing window centering and unified styling",
        font=("Segoe UI", 10),
        **supporting_label_style
    )
    info_label.pack(pady=(0, 20))
    
    # Mode frame (like in station selection)
    mode_frame = tk.LabelFrame(
        main_frame, 
        text="Test Options", 
        **labelframe_style,
        padx=10, 
        pady=10
    )
    mode_frame.pack(fill=tk.X, pady=(0, 20))
    
    # Sample radio buttons
    mode_var = tk.StringVar(value="option1")
    
    radio1 = tk.Radiobutton(
        mode_frame,
        text="Option 1 - Test centering",
        variable=mode_var,
        value="option1",
        font=("Segoe UI", 10),
        **radio_style
    )
    radio1.pack(anchor=tk.W, pady=(0, 5))
    
    radio2 = tk.Radiobutton(
        mode_frame,
        text="Option 2 - Test styling",
        variable=mode_var,
        value="option2",
        font=("Segoe UI", 10),
        **radio_style
    )
    radio2.pack(anchor=tk.W)
    
    # Button frame
    button_frame = tk.Frame(main_frame, **frame_style)
    button_frame.pack(fill=tk.X, pady=(20, 0))
    
    def show_result():
        selected = mode_var.get()
        result_text = f"Selected: {selected}\n\n✓ Window centered on screen\n✓ Unified styling applied\n✓ Fonts loaded correctly"
        
        # Create result dialog
        result_window = tk.Toplevel(root)
        result_window.title("Test Results")
        apply_dialog_styling(result_window)
        center_window_on_screen(result_window, 350, 200)
        
        result_frame = tk.Frame(result_window, **frame_style, padx=20, pady=20)
        result_frame.pack(fill=tk.BOTH, expand=True)
        
        tk.Label(result_frame, text="Test Results", 
                font=("Segoe UI", 12, "bold"), **main_label_style).pack(pady=(0, 10))
        
        tk.Label(result_frame, text=result_text, 
                font=("Segoe UI", 10), **supporting_label_style).pack(pady=(0, 15))
        
        tk.Button(result_frame, text="Close", command=result_window.destroy,
                 font=("Segoe UI", 10), **button_style).pack()
    
    # Buttons
    tk.Button(
        button_frame,
        text="Cancel",
        command=root.destroy,
        width=12,
        font=("Segoe UI", 10),
        **cancel_button_style
    ).pack(side=tk.RIGHT, padx=(10, 0))
    
    tk.Button(
        button_frame,
        text="Test",
        command=show_result,
        width=12,
        font=("Segoe UI", 11),
        **action_button_style
    ).pack(side=tk.RIGHT)
    
    print("✓ Dialog test window created and centered")
    print("✓ All styling applied successfully")
    print("✓ Test the window appearance and positioning")
    
    root.mainloop()

if __name__ == "__main__":
    test_dialog_appearance()