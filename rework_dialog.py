# -*- coding: utf-8 -*-
"""
Rework Solution Dialog

This module provides a dialog for collecting rework solution information
when a fault has been resolved.

@author: TBates
"""

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Optional, Tuple
from ui_styles import *

class ReworkSolutionDialog:
    """Dialog for collecting rework solution information."""
    
    def __init__(self, parent, fault_info: dict):
        """
        Initialize the rework solution dialog.
        
        Args:
            parent: Parent window
            fault_info: Dictionary with fault information from rework tracker
        """
        self.parent = parent
        self.fault_info = fault_info
        self.result = None
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Rework Solution")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Apply unified styling
        apply_dialog_styling(self.dialog)
        
        # Auto-size and center the dialog
        self._auto_size_and_center()
        
        # Setup UI
        self._setup_ui()
        
        # Focus on the solution text area
        self.solution_text.focus_set()
    
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
        final_height = max(req_height, 400)
        
        # Center on screen with the calculated size
        center_window_on_screen(self.dialog, final_width, final_height)
    
    def _setup_ui(self):
        """Setup the dialog UI components."""
        # Main frame with padding
        main_frame = tk.Frame(self.dialog, **frame_style, padx=20, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = tk.Label(
            main_frame,
            text="Rework Solution Required",
            font=("Segoe UI", 14, "bold"),
            **main_label_style
        )
        title_label.pack(pady=(0, 15))
        
        # Info frame
        info_frame = tk.LabelFrame(
            main_frame, 
            text="Previous Fault Information", 
            **labelframe_style,
            padx=15, 
            pady=10
        )
        info_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Fault details
        fault_time_label = tk.Label(
            info_frame, 
            text=f"Fault Time: {self.fault_info['fault_run_timestamp']}",
            font=("Segoe UI", 10),
            **supporting_label_style
        )
        fault_time_label.pack(anchor=tk.W, pady=2)
        
        fault_type_label = tk.Label(
            info_frame, 
            text=f"Fault Type: {self.fault_info['fault_type']}",
            font=("Segoe UI", 10),
            **supporting_label_style
        )
        fault_type_label.pack(anchor=tk.W, pady=2)
        
        if self.fault_info.get('fault_description'):
            fault_desc_label = tk.Label(
                info_frame, 
                text=f"Description: {self.fault_info['fault_description']}",
                font=("Segoe UI", 10),
                **supporting_label_style
            )
            fault_desc_label.pack(anchor=tk.W, pady=2)
        
        # Solution frame
        solution_frame = tk.LabelFrame(
            main_frame, 
            text="Rework Solution", 
            **labelframe_style,
            padx=15, 
            pady=10
        )
        solution_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Instructions
        instruction_label = tk.Label(
            solution_frame,
            text="Please describe what was done to resolve the fault:",
            font=("Segoe UI", 10),
            **supporting_label_style
        )
        instruction_label.pack(anchor=tk.W, pady=(0, 8))
        
        # Solution text area with scrollbar
        text_frame = tk.Frame(solution_frame, **frame_style)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.solution_text = tk.Text(
            text_frame,
            height=8,
            width=50,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            bg=WHITE,
            fg=TEXT_PRIMARY,
            insertbackground=TEXT_PRIMARY,
            relief="solid",
            bd=1,
            highlightthickness=0
        )
        
        scrollbar = tk.Scrollbar(text_frame, orient=tk.VERTICAL, command=self.solution_text.yview)
        self.solution_text.configure(yscrollcommand=scrollbar.set)
        
        self.solution_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Employee number frame
        emp_frame = tk.Frame(main_frame, **frame_style)
        emp_frame.pack(fill=tk.X, pady=(0, 15))
        
        emp_label = tk.Label(
            emp_frame, 
            text="Employee Number:",
            font=("Segoe UI", 10),
            **supporting_label_style
        )
        emp_label.pack(side=tk.LEFT)
        
        self.emp_var = tk.StringVar()
        emp_entry = tk.Entry(
            emp_frame, 
            textvariable=self.emp_var, 
            width=15,
            font=("Segoe UI", 10),
            **main_entry_style
        )
        emp_entry.pack(side=tk.LEFT, padx=(10, 0))
        
        # Button frame
        button_frame = tk.Frame(main_frame, **frame_style)
        button_frame.pack(fill=tk.X)
        
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
        
        # Save button
        save_btn = tk.Button(
            button_frame,
            text="Save Solution",
            command=self._on_save,
            width=12,
            font=("Segoe UI", 11),
            **action_button_style
        )
        save_btn.pack(side=tk.RIGHT)
        
        # Handle window close
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_cancel)
        
        # Bind Enter key to save (when not in text area)
        self.dialog.bind("<Return>", lambda e: self._on_save() if self.dialog.focus_get() != self.solution_text else None)
    
    def _on_save(self):
        """Handle Save button click."""
        # Validate inputs
        solution = self.solution_text.get("1.0", tk.END).strip()
        emp_number = self.emp_var.get().strip()
        
        if not solution:
            messagebox.showwarning("Missing Information", "Please enter a description of the rework solution.")
            self.solution_text.focus_set()
            return
        
        if not emp_number:
            messagebox.showwarning("Missing Information", "Please enter your employee number.")
            return
        
        try:
            emp_number = int(emp_number)
        except ValueError:
            messagebox.showerror("Invalid Input", "Employee number must be a valid number.")
            return
        
        # Store the result
        self.result = {
            "solution": solution,
            "emp_number": emp_number
        }
        
        self.dialog.destroy()
    
    def _on_cancel(self):
        """Handle Cancel button click or window close."""
        self.result = None
        self.dialog.destroy()
    
    def show(self) -> Optional[dict]:
        """
        Show the dialog and return the result.
        
        Returns:
            Dictionary with 'solution' and 'emp_number' if saved, None if cancelled
        """
        self.dialog.wait_window()
        return self.result


def show_rework_solution_dialog(parent, fault_info: dict) -> Optional[Tuple[str, int]]:
    """
    Show the rework solution dialog.
    
    Args:
        parent: Parent window
        fault_info: Dictionary with fault information
        
    Returns:
        Tuple of (solution, emp_number) if saved, None if cancelled
    """
    dialog = ReworkSolutionDialog(parent, fault_info)
    result = dialog.show()
    
    if result:
        return (result["solution"], result["emp_number"])
    
    return None