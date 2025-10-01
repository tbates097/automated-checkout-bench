"""
Drive Configuration GUI for GenerateMCD v2.0
===========================================
Presents a user-friendly window with dropdowns and text fields for configuring
Aerotech drive electrical options based on the drive_config.json specifications.
"""

import sys
import os
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from tkinter import font as tkfont

# Aerotech UI Guidelines Colors
AEROTECH_COLORS = {
    'blue1': '#0082BE',  # Primary Blue
    'grey1': '#4B545E',  # Primary Grey
    'grey2': '#DAE1E9',  # Light Grey
    'black': '#231F20',  # Primary Black
    'grey3': '#B5BBC3',  # Medium Grey
    'grey5': '#ECEFF3',  # Very Light Grey
    'grey6': '#F7F8F8',  # Background Grey
    'red1': '#DB2115',   # Error Red
    'orange1': '#EF8B22', # Warning Orange
    'green1': '#459A34'  # Success Green
}

sys.path.insert(0, r'C:\Users\tbates\Python\automated-checkout-bench')

class DriveConfigurationGUI:
    def __init__(self, mcd_processor, drive_type=None):
        self.mcd_processor = mcd_processor
        self.drive_type = drive_type
        self.root = None
        self.window = None  # This will be the main window (either Tk or Toplevel)
        self.config_vars = {}
        self.config_widgets = {}
        self.result = None
        
        # Set default fonts. This will be checked and potentially overridden in show()
        self.fonts = {
            'h1': ('Source Sans Pro Semibold', 20),
            'h2': ('Source Sans Pro Semibold', 18),
            't1': ('Source Sans Pro Semibold', 16),
            't2': ('Source Sans Pro', 16),
            't3': ('Source Sans Pro', 16)
        }
        
    def _clear_window(self):
        """Destroys all widgets in the current window."""
        for widget in self.window.winfo_children():
            widget.destroy()

    def _build_drive_selection_ui(self):
        """Builds the initial drive selection screen into self.window."""
        self.window.title("Select Drive Type - GenerateMCD v2.0")
        self.window.geometry("700x500")
        self.window.resizable(True, True)
        self.window.configure(bg=AEROTECH_COLORS['grey6'])

        # Center the window
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (self.window.winfo_width() // 2)
        y = (self.window.winfo_screenheight() // 2) - (self.window.winfo_height() // 2)
        self.window.geometry(f"+{x}+{y}")

        drives_info = self.mcd_processor.get_available_drives_with_info()
        drives_with_templates = [d for d in drives_info if d['template_exists']]

        title_label = tk.Label(self.window, text="Select Aerotech Drive Type", font=self.fonts['h1'], fg=AEROTECH_COLORS['grey1'], bg=AEROTECH_COLORS['grey6'])
        title_label.pack(pady=10)

        desc_label = tk.Label(self.window, text="Choose the drive type you want to configure:", font=self.fonts['t1'], fg=AEROTECH_COLORS['grey1'], bg=AEROTECH_COLORS['grey6'])
        desc_label.pack(pady=5)

        list_frame = tk.Frame(self.window, bg=AEROTECH_COLORS['grey6'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=15)

        listbox_frame = tk.Frame(list_frame, bg=AEROTECH_COLORS['grey6'])
        listbox_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        drives_listbox = tk.Listbox(listbox_frame, yscrollcommand=scrollbar.set, font=self.fonts['t2'], height=15, bg='white', fg=AEROTECH_COLORS['grey1'], selectbackground=AEROTECH_COLORS['blue1'], selectforeground='white')
        drives_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=drives_listbox.yview)

        for drive in sorted(drives_with_templates, key=lambda x: x['type']):
            multi_axis_indicator = "🔧" if drive['is_multi_axis'] else "🔹"
            display_text = f"{multi_axis_indicator} {drive['type']} - {drive['display_name']}"
            drives_listbox.insert(tk.END, display_text)

        info_text = scrolledtext.ScrolledText(list_frame, height=6, width=50, font=self.fonts['t3'], state=tk.DISABLED, bg=AEROTECH_COLORS['grey5'], fg=AEROTECH_COLORS['grey1'])
        info_text.pack(fill=tk.X, pady=(10, 0))

        def on_drive_select(event):
            selection = drives_listbox.curselection()
            if selection:
                drive_info = drives_with_templates[selection[0]]
                info_text.config(state=tk.NORMAL)
                info_text.delete(1.0, tk.END)
                info_text.insert(tk.END, f"Drive: {drive_info['display_name']}\n")
                info_text.insert(tk.END, f"Description: {drive_info['description']}\n")
                info_text.insert(tk.END, f"Type: {drive_info['controller_type']}\n")
                info_text.insert(tk.END, f"Multi-axis: {'Yes' if drive_info['is_multi_axis'] else 'No'}\n")
                info_text.insert(tk.END, f"Configuration options: {drive_info['electrical_options_count']}\n")
                info_text.insert(tk.END, f"Required options: {drive_info['required_options_count']}")
                info_text.config(state=tk.DISABLED)
        
        drives_listbox.bind('<<ListboxSelect>>', on_drive_select)

        button_frame = tk.Frame(self.window, bg=AEROTECH_COLORS['grey6'])
        button_frame.pack(fill=tk.X, padx=20, pady=10)

        def on_configure():
            selection = drives_listbox.curselection()
            if not selection:
                messagebox.showwarning("No Selection", "Please select a drive type to configure.", parent=self.window)
                return
            
            selected_drive_info = drives_with_templates[selection[0]]
            self.drive_type = selected_drive_info['type']
            self._clear_window()
            self._build_configuration_ui()
        
        tk.Button(button_frame, text="Configure Selected Drive", command=on_configure, bg=AEROTECH_COLORS['blue1'], fg='white', font=self.fonts['t2'], activebackground='#1C94D2', padx=10, pady=5).pack(side=tk.RIGHT, padx=(5, 0))
        tk.Button(button_frame, text="Cancel", command=self.cancel, bg=AEROTECH_COLORS['grey2'], fg=AEROTECH_COLORS['grey1'], font=self.fonts['t2'], activebackground='#E0E5EC', padx=10, pady=5).pack(side=tk.RIGHT)

        if drives_listbox.size() > 0:
            drives_listbox.selection_set(0)
            on_drive_select(None)
    
    def _build_configuration_ui(self):
        """Builds the main configuration screen into self.window using a grid layout."""
        menu_data = self.mcd_processor.get_drive_menu_data(self.drive_type)
        if not menu_data:
            messagebox.showerror("Configuration Error", f"No configuration data found for drive type: {self.drive_type}", parent=self.window)
            self.cancel()
            return
        
        self.window.title(f"Drive Configuration - {menu_data['drive_info']['display_name']}")
        self.window.geometry("") # Let Tkinter size the window
        self.window.configure(bg=AEROTECH_COLORS['grey6'])

        style = ttk.Style(self.window)
        style.theme_use('clam')
        style.configure('TFrame', background=AEROTECH_COLORS['grey6'])
        style.configure('TLabel', background=AEROTECH_COLORS['grey6'], foreground=AEROTECH_COLORS['grey1'])
        style.configure('TButton', font=self.fonts['t2'])
        style.configure('TCombobox', font=self.fonts['t2'])
        
        # Main container frame
        main_frame = tk.Frame(self.window, bg=AEROTECH_COLORS['grey6'], padx=25, pady=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Header
        header_label = tk.Label(main_frame, text="Add a new electrical device:", font=self.fonts['h2'], fg=AEROTECH_COLORS['grey1'], bg=AEROTECH_COLORS['grey6'])
        header_label.pack(anchor="w", pady=(0, 20))

        # Options frame with grid layout
        options_frame = tk.Frame(main_frame, bg=AEROTECH_COLORS['grey6'])
        options_frame.pack(fill=tk.BOTH, expand=True)
        options_frame.grid_columnconfigure(1, weight=1) # Makes the widget column expandable

        for i, option in enumerate(menu_data['options']):
            self.create_option_widget(options_frame, option, i)

        # Separator
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.pack(fill='x', pady=20)

        # Button frame
        button_frame = tk.Frame(main_frame, bg=AEROTECH_COLORS['grey6'])
        button_frame.pack(fill=tk.X)
        
        style.configure('Primary.TButton', background=AEROTECH_COLORS['blue1'], foreground='white', font=self.fonts['t2'])
        style.configure('Secondary.TButton', background=AEROTECH_COLORS['grey2'], foreground=AEROTECH_COLORS['grey1'], font=self.fonts['t2'])

        ttk.Button(button_frame, text="Apply Configuration", command=self.generate_mcd, style='Primary.TButton').pack(side=tk.RIGHT, padx=(10, 0), ipady=2)
        ttk.Button(button_frame, text="Cancel", command=self.cancel, style='Secondary.TButton').pack(side=tk.RIGHT, ipady=2)
        
        self.apply_defaults()
        
        self.window.update_idletasks()
        x = (self.window.winfo_screenwidth() // 2) - (self.window.winfo_width() // 2)
        y = (self.window.winfo_screenheight() // 2) - (self.window.winfo_height() // 2)
        self.window.geometry(f"+{x}+{y}")
    
    def create_option_widget(self, parent, option, row):
        """Creates a label and widget in a grid layout for a configuration option."""
        # Use T1 style for the label (Semibold)
        name_text = option['name'] + (" *" if option['required'] else "")
        label = tk.Label(parent, text=name_text, font=self.fonts['t1'], fg=AEROTECH_COLORS['grey1'], bg=AEROTECH_COLORS['grey6'])
        label.grid(row=row, column=0, sticky="w", padx=(0, 20), pady=8)
        
        var = tk.StringVar()
        widget = None

        if option['type'] == 'selection':
            # Add a placeholder for empty selections
            choices = [f"Select an option..."] + option['choices']
            widget = ttk.Combobox(parent, textvariable=var, state="readonly", values=choices, font=self.fonts['t2'])
            widget.set(choices[0]) # Set placeholder
        elif option['type'] == 'text':
            widget = ttk.Entry(parent, textvariable=var, font=self.fonts['t2'])
        
        if widget:
            widget.grid(row=row, column=1, sticky="ew", pady=8)
            self.config_vars[option['name']] = var
            self.config_widgets[option['name']] = widget
    
    def apply_defaults(self):
        """Apply default values to all configuration options"""
        menu_data = self.mcd_processor.get_drive_menu_data(self.drive_type)
        if not menu_data:
            return
        
        for option in menu_data['options']:
            if option['name'] in self.config_vars:
                default_value = option.get('default', '')
                if default_value:
                     self.config_vars[option['name']].set(default_value)
    
    def validate_config(self):
        """Validate the current configuration"""
        electrical_dict = self.get_current_config()
        validation = self.mcd_processor.validate_electrical_configuration(self.drive_type, electrical_dict)
        
        if validation['valid']:
            messagebox.showinfo("Validation Success", "✅ Configuration is valid!\n\nReady to generate MCD file.", parent=self.window)
        else:
            error_msg = "❌ Configuration validation failed:\n\n" + "\n".join(f"• {e}" for e in validation['errors'])
            if validation.get('suggestions'):
                error_msg += "\n\n💡 Suggestions:\n" + "\n".join(f"• {k}: {v}" for k, v in validation['suggestions'].items())
            messagebox.showerror("Validation Error", error_msg, parent=self.window)
    
    def get_current_config(self):
        """Get the current configuration from the GUI"""
        electrical_dict = {}
        menu_data = self.mcd_processor.get_drive_menu_data(self.drive_type)
        
        for option in menu_data['options']:
            if option['name'] in self.config_vars:
                value = self.config_vars[option['name']].get().strip()
                # Exclude placeholder text
                if value and value != "Select an option...":
                    if option['type'] == 'selection' and option.get('suffix') and not value.endswith(option['suffix']):
                        value += option['suffix']
                    electrical_dict[option['name']] = value
        return electrical_dict
    
    def generate_mcd(self):
        """Validate, get confirmation, set result, and destroy the window."""
        electrical_dict = self.get_current_config()
        validation = self.mcd_processor.validate_electrical_configuration(self.drive_type, electrical_dict)
        
        if not validation['valid']:
            self.validate_config()
            return
        
        config_summary = "Configuration Summary:\n" + "="*40 + "\n"
        config_summary += f"Drive Type: {self.drive_type}\n"
        config_summary += "Electrical Configuration:\n" + "\n".join(f"  • {k}: {v}" for k, v in electrical_dict.items())
        
        if messagebox.askyesno("Generate MCD", f"{config_summary}\n\nProceed with MCD generation?", parent=self.window):
            self.result = electrical_dict
            self.window.destroy()

    def cancel(self):
        """Set result to None and destroy the window."""
        self.result = None
        if self.window:
            self.window.destroy()
    
    def show(self):
        """
        Show the GUI. Creates a new root window if run standalone, 
        or a Toplevel window if called from an existing Tkinter app.
        """
        # Determine if we are creating a new root or using an existing one
        try:
            # This fails if there is no root, which is what we want
            is_standalone = not tk._default_root.winfo_exists()
        except (AttributeError, tk.TclError):
            is_standalone = True

        if is_standalone:
            # If no root exists (e.g., called from a script), create one.
            # This root will be our main window. DO NOT withdraw() it.
            self.root = tk.Tk()
            self.window = self.root
        else:
            # If a root already exists, create a Toplevel (child window).
            self.root = tk._default_root
            self.window = tk.Toplevel(self.root)
            self.window.transient(self.root)
            self.window.grab_set()

        # Moved font check from __init__ to here, after a root window is guaranteed to exist.
        try:
            available_fonts = list(tkfont.families(self.root))
            if 'Source Sans Pro' not in available_fonts and 'Source Sans Pro Semibold' not in available_fonts:
                self.fonts = {
                    'h1': ('Arial Bold', 20), 'h2': ('Arial Bold', 18),
                    't1': ('Arial Bold', 16), 't2': ('Arial', 16), 't3': ('Arial', 16)
                }
        except Exception as e:
            print(f"Font loading warning: {e}")

        # Bring the window to the front
        self.window.lift()
        self.window.attributes('-topmost', True)
        self.window.after(100, lambda: self.window.attributes('-topmost', False))
        self.window.focus_force()
        
        if not self.drive_type:
            self._build_drive_selection_ui()
        else:
            self._build_configuration_ui()
        
        # The mainloop/wait_window logic determines how the script waits for the GUI to close.
        if is_standalone:
            self.root.mainloop()
        else:
            self.root.wait_window(self.window)
        
        return self.result

def demo_gui():
    """
    Demo function to show the GUI in action as a standalone application.
    This will now only open the configuration window directly.
    """
    try:
        # This import will be needed for the demo to run
        from GenerateMCD_v2 import AerotechController
        
        print("🚀 Initializing GenerateMCD v2.0 for standalone GUI demo...")
        
        # The MCD processor is still needed for the GUI to get its data
        mcd_processor = AerotechController.with_file_saving(
            output_dir=os.path.join(os.getcwd(), 'GUI_Demo_Output'),
            separate_dirs=True,
            overwrite=True
        )
        mcd_processor.initialize()
        print("✅ System initialized!")
        
        # --- MODIFIED PART ---
        # Instead of creating a dummy main app, launch the GUI directly.
        # The GUI's own logic will handle creating a root window because it's standalone.
        config_gui = DriveConfigurationGUI(mcd_processor)
        electrical_config = config_gui.show()
        
        if electrical_config:
            print(f"\n✅ User configured drive '{config_gui.drive_type}' with options:")
            for key, value in electrical_config.items():
                print(f"   • {key}: {value}")
        else:
            print("\n❌ Configuration cancelled by user.")

    except ImportError:
        print("\n❌ ERROR: Could not import 'GenerateMCD_v2'.")
        print("   Please ensure 'GenerateMCD_v2.py' is in the same directory or Python path.")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    demo_gui()

