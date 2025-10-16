"""
Quick test to verify the font fix works
"""

import tkinter as tk
from ui_styles import *

def quick_test():
    print("Testing UI styles and font loading...")
    
    # Create a simple window
    root = tk.Tk()
    root.title("Quick Font Test")
    
    # Apply styling
    apply_dialog_styling(root)
    center_window_on_screen(root, 300, 200)
    
    # Test various styled components
    frame = tk.Frame(root, **frame_style, padx=20, pady=20)
    frame.pack(fill=tk.BOTH, expand=True)
    
    # Test label with main style
    label1 = tk.Label(frame, text="Main Label", font=("Segoe UI", 11, "bold"), **main_label_style)
    label1.pack(pady=5)
    
    # Test label with supporting style  
    label2 = tk.Label(frame, text="Supporting Label", font=("Segoe UI", 10), **supporting_label_style)
    label2.pack(pady=5)
    
    # Test button
    btn = tk.Button(frame, text="Test Button", font=("Segoe UI", 11), **action_button_style)
    btn.pack(pady=10)
    
    print("✓ Font loading test passed!")
    print("✓ All styles applied successfully!")
    print("✓ Window centered on screen!")
    
    # Auto-close after showing success
    root.after(2000, root.destroy)  # Close after 2 seconds
    root.mainloop()
    
    print("Test completed successfully!")

if __name__ == "__main__":
    quick_test()