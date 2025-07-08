import zipfile
import os
import xml.etree.ElementTree as ET
import shutil
import tkinter as tk
from tkinter import filedialog, ttk

class MCDComparison():
    """
    A class to compare the parameters of two .mcd files for axis 0.
    The user is prompted to select two files, and results are shown in a
    side-by-side comparison window.
    """
    def __init__(self, window):
        """Initializes the comparison tool with a parent window."""
        self.window = window

    def extract_mcd(self, mcd_path, extract_path):
        """Extracts the contents of a .mcd file to a specified directory."""
        os.makedirs(extract_path, exist_ok=True)
        with zipfile.ZipFile(mcd_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

    def parse_parameters(self, xml_path):
        """Parses the XML parameters file, focusing only on axis 0."""
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            axis_params = {}
            axis = root.find(".//Axes/Axis[@Index='0']")
            if axis is not None:
                for param in axis.findall(".//P"):
                    name = param.get("n")
                    value = param.text
                    if name and value is not None:
                        axis_params[name] = value
            return axis_params
        except (ET.ParseError, FileNotFoundError):
            return {} # Return empty dict if file is missing or corrupt

    def select_files(self):
        """Opens two file dialogs for the user to select two .mcd files."""
        file_1 = filedialog.askopenfilename(
            title="Select the FIRST .mcd file",
            filetypes=(("MCD files", "*.mcd"), ("All files", "*.*"))
        )
        if not file_1: return None, None

        file_2 = filedialog.askopenfilename(
            title="Select the SECOND .mcd file",
            filetypes=(("MCD files", "*.mcd"), ("All files", "*.*"))
        )
        if not file_2: return None, None
            
        return file_1, file_2

    def compare_mcd_files(self):
        """Orchestrates the comparison and displays the results in a new window."""
        mcd_file1, mcd_file2 = self.select_files()
        if not mcd_file1 or not mcd_file2:
            print("File selection cancelled. Comparison aborted.")
            return
        
        extract_path1 = "extracted_mcd1"
        extract_path2 = "extracted_mcd2"

        try:
            # Extract and parse both files
            self.extract_mcd(mcd_file1, extract_path1)
            self.extract_mcd(mcd_file2, extract_path2)
            
            params1 = self.parse_parameters(os.path.join(extract_path1, "config", "Parameters"))
            params2 = self.parse_parameters(os.path.join(extract_path2, "config", "Parameters"))

            # --- Generate Full Comparison Data ---
            full_comparison_data = []
            all_param_names = sorted(set(params1.keys()) | set(params2.keys()))

            for name in all_param_names:
                if name == "AxisName": continue # Skip axis name

                val1 = params1.get(name)
                val2 = params2.get(name)
                
                if val1 is not None and val2 is not None:
                    status = "Match" if val1 == val2 else "Different"
                elif val1 is not None:
                    status = "File 1 Only"
                    val2 = "N/A"
                else:
                    status = "File 2 Only"
                    val1 = "N/A"
                
                full_comparison_data.append({
                    "name": name,
                    "value1": val1,
                    "value2": val2,
                    "status": status
                })
            
            # --- Display Results in GUI ---
            if full_comparison_data:
                dialog = ComparisonDialog(
                    self.window, 
                    full_comparison_data,
                    os.path.basename(mcd_file1),
                    os.path.basename(mcd_file2)
                )
                self.window.wait_window(dialog)
            else:
                print("No parameters found for Axis 0 in either file.")

        finally:
            # --- Cleanup ---
            shutil.rmtree(extract_path1, ignore_errors=True)
            shutil.rmtree(extract_path2, ignore_errors=True)
            print("Cleanup complete.")

class ComparisonDialog(tk.Toplevel):
    """A dialog window to display a side-by-side comparison of parameters."""
    def __init__(self, parent, data, file1_name, file2_name):
        super().__init__(parent)
        self.title("Parameter Comparison")
        self.geometry("800x600")

        # --- Create Treeview for Side-by-Side Comparison ---
        frame = ttk.Frame(self, padding="10")
        frame.pack(expand=True, fill=tk.BOTH)

        columns = ("parameter", "file1", "file2", "status")
        self.tree = ttk.Treeview(frame, columns=columns, show="headings")
        
        # Define headings
        self.tree.heading("parameter", text="Parameter Name")
        self.tree.heading("file1", text=file1_name)
        self.tree.heading("file2", text=file2_name)
        self.tree.heading("status", text="Status")

        # Configure column widths
        self.tree.column("parameter", width=200, anchor=tk.W)
        self.tree.column("file1", width=150, anchor=tk.W)
        self.tree.column("file2", width=150, anchor=tk.W)
        self.tree.column("status", width=100, anchor=tk.CENTER)

        # --- Define Tags for Coloring Rows ---
        self.tree.tag_configure('match', background='#dff0d8') # Light Green
        self.tree.tag_configure('different', background='#fcf8e3') # Light Yellow
        self.tree.tag_configure('unique', background='#f2f2f2') # Light Gray
        
        # --- Populate Treeview with Data ---
        for item in data:
            tags = ()
            if item['status'] == 'Match':
                tags = ('match',)
            elif item['status'] == 'Different':
                tags = ('different',)
            else:
                tags = ('unique',)
            
            self.tree.insert(
                "", 
                tk.END, 
                values=(item['name'], item['value1'], item['value2'], item['status']),
                tags=tags
            )
        
        # --- Add Scrollbar ---
        scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # --- Add Close Button ---
        button_frame = ttk.Frame(self, padding=(0, 0, 0, 10))
        button_frame.pack(fill=tk.X)
        close_button = ttk.Button(button_frame, text="Close", command=self.destroy)
        close_button.pack()

# --- Main execution block to run the script ---
if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # Hide the main window

    # Apply a modern theme if available
    style = ttk.Style()
    if "clam" in style.theme_names():
        style.theme_use("clam")

    comparison_tool = MCDComparison(window=root)
    comparison_tool.compare_mcd_files()

    try:
        root.destroy()
    except tk.TclError:
        # Can occur if window is already destroyed
        pass