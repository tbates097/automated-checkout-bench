"""
Unified UI Styling Module

This module contains all the consistent styling definitions used across
the automated checkout bench application to ensure visual consistency.
"""

import tkinter as tk
import os


# Automation1 Studio-inspired color palette
BACKGROUND = "#F0F0F0"       # Light gray background
WHITE = "#FFFFFF"            # Pure white for input fields
BLUE_PRIMARY = "#0078D4"     # Aerotech blue
BLUE_HOVER = "#106EBE"       # Slightly darker blue for hover
BLUE_ACTIVE = "#005A9E"      # Darker blue for clicking
TEXT_PRIMARY = "#252423"     # Darker gray for primary text
TEXT_SECONDARY = "#484644"   # Medium gray for secondary text
BORDER = "#E1E1E1"           # Light border color
BORDER_DARK = "#CCCCCC"      # Darker border for frames
BORDER_FOCUS = "#0078D4"     # Blue border for focus
DISABLED_BG = "#F3F2F1"      # Slightly darker than background for disabled
DISABLED_FG = "#A19F9D"      # Muted text for disabled elements


def get_label_font(size=10, bold=False):
    """Get standard label font"""
    weight = "bold" if bold else "normal"
    return ("Segoe UI", size, weight)


def get_section_font():
    """Get section header font"""
    return ("Segoe UI", 9, "bold")


# Base styles
base_style = {
    "bg": BACKGROUND,
    "relief": "flat",
    "padx": 12,
    "pady": 6
}

# Label styles (without font to avoid conflicts)
main_label_style = {
    **base_style,
    "fg": TEXT_PRIMARY,
    "anchor": "w"
}

supporting_label_style = {
    **base_style,
    "fg": TEXT_SECONDARY,
    "anchor": "w"
}

section_style = {
    "bg": BACKGROUND,
    "fg": TEXT_SECONDARY,
    "font": ("Segoe UI", 9, "bold"),
    "pady": 5
}

# Entry field styles
entry_style = {
    "relief": "solid",
    "borderwidth": 1,
    "highlightthickness": 0,
    "bd": 1,
    "bg": WHITE,
    "fg": TEXT_SECONDARY
}

main_entry_style = {
    **entry_style,
    "fg": TEXT_PRIMARY,
    "insertbackground": TEXT_PRIMARY
}

supporting_entry_style = {
    **entry_style,
    "fg": TEXT_SECONDARY,
    "insertbackground": TEXT_SECONDARY
}

# Button styles (without font to avoid conflicts)
button_style = {
    "bg": WHITE,
    "fg": TEXT_PRIMARY,
    "activebackground": BLUE_PRIMARY,
    "activeforeground": WHITE,
    "relief": "solid",
    "padx": 15,
    "pady": 8,
    "cursor": "hand2",
    "bd": 1
}

action_button_style = {
    "bg": BLUE_PRIMARY,
    "fg": WHITE,
    "activebackground": BLUE_ACTIVE,
    "activeforeground": WHITE,
    "relief": "flat",
    "cursor": "hand2",
    "bd": 0
}

cancel_button_style = {
    "bg": WHITE,
    "fg": TEXT_SECONDARY,
    "activebackground": "#DC3545",
    "activeforeground": WHITE,
    "relief": "solid",
    "cursor": "hand2",
    "bd": 1
}

# Radio button style (without font to avoid conflicts)
radio_style = {
    "bg": BACKGROUND,
    "fg": TEXT_SECONDARY,
    "selectcolor": WHITE,
    "activebackground": BACKGROUND,
    "activeforeground": BLUE_PRIMARY,
    "cursor": "hand2"
}

# Frame styles
frame_style = {
    "bg": BACKGROUND,
    "bd": 0,
    "relief": "flat"
}

labelframe_style = {
    "bg": BACKGROUND,
    "fg": TEXT_SECONDARY,
    "font": ("Segoe UI", 9),
    "bd": 1,
    "relief": "groove",
    "highlightthickness": 0
}


def apply_window_icon(window):
    """Apply consistent window icon"""
    try:
        # Try to use Aerotech icon if available
        icon_path = os.path.join(os.path.dirname(__file__), "assets", "aerotech.ico")
        if os.path.exists(icon_path):
            window.iconbitmap(icon_path)
        else:
            # Fallback to default system icon
            pass
    except:
        pass


def center_window_on_screen(window, width, height):
    """Center a window on the screen"""
    # Get screen dimensions
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    
    # Calculate center position
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    
    # Set window geometry
    window.geometry(f"{width}x{height}+{x}+{y}")


def apply_dialog_styling(dialog_window):
    """Apply consistent styling to a dialog window"""
    dialog_window.configure(bg=BACKGROUND)
    apply_window_icon(dialog_window)
    
    # Make window modal and focused
    dialog_window.lift()
    dialog_window.attributes('-topmost', True)
    dialog_window.update()
    dialog_window.attributes('-topmost', False)
    dialog_window.focus_force()


def create_separator(parent, **kwargs):
    """Create a styled separator line"""
    return tk.Frame(parent, height=1, bg=BORDER, **kwargs)