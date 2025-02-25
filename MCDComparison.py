import zipfile
import os
import xml.etree.ElementTree as ET
import json
import shutil
import tkinter as tk
from tkinter import filedialog

class MCDComparison():
    def __init__(self, part_number, controller):
        self.part_number = part_number
        self.controller = controller

    def extract_mcd(self,mcd_path, extract_path):
        """Extracts the contents of an .MCD file to a specified directory."""
        os.makedirs(extract_path, exist_ok=True)
        with zipfile.ZipFile(mcd_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)

    def parse_parameters(self, xml_path):
        """Parses the XML parameters file for axis 0 only."""
        tree = ET.parse(xml_path)
        root = tree.getroot()
        axis_params = {}

        # Find axis 0 specifically
        axis = root.find(".//Axes/Axis[@Index='0']")
        if axis is not None:
            # Get all parameters for axis 0
            params = axis.findall(".//P")
            for param in params:
                name = param.get("n")
                value = param.text
                if name and value is not None:
                    axis_params[name] = value

        return axis_params
    
    def download_mcd(self):
        self.mdk_path = fr'C:\Users\tbates\Python\automated-checkout-bench\Old MCD\old.mcd'
        self.controller.download_mcd_to_file(self.mdk_path, should_include_files=True, should_include_configuration=True)
    
    def select_files(self):
        """Opens a file dialog to select two .MCD files."""
        root = tk.Tk()
        root.withdraw()  # Hide the root window
        self.download_mcd()
        path_1 = 'Old MCD'
        path_2 = 'New MCD'
        # Get the only file in path_1
        files_in_path1 = os.listdir(path_1)
        if len(files_in_path1) == 1:
            file_1 = os.path.join(path_1, files_in_path1[0])
        else:
            #print(f"Expected 1 file in {path_1}, found {len(files_in_path1)}")
            return None, None
        file_2 = os.path.join(path_2, f'{self.part_number}.mcd')
        file_paths = [file_1, file_2]

        if len(file_paths) != 2:
            print("Not enough files found.")
            return None, None
        
        return file_paths

    def compare_mcd_files(self):
        """Compares two .MCD files' parameters for axis 0 only."""
        mcd_file1, mcd_file2 = self.select_files()
        if not mcd_file1 or not mcd_file2:
            return
        
        extract_path1 = "extracted_mcd1"
        extract_path2 = "extracted_mcd2"
        output_json = "parameters_comparison.json"

        # Extract and parse files
        self.extract_mcd(mcd_file1, extract_path1)
        self.extract_mcd(mcd_file2, extract_path2)
        
        params1 = self.parse_parameters(os.path.join(extract_path1, "config", "Parameters"))
        params2 = self.parse_parameters(os.path.join(extract_path2, "config", "Parameters"))

        # Find differences and missing parameters
        missing_params = {}
        
        # Check params in file2 but not in file1
        for param, value in params2.items():
            if param != "AxisName":
                if param not in params1:
                    missing_params[param] = {"value": value, "source": "file2"}
        
        # Check params in file1 but not in file2
        for param, value in params1.items():
            if param != "AxisName":
                if param not in params2:
                    missing_params[param] = {"value": value, "source": "file1"}

        comparison_results = {}
        
        # Show dialog for missing parameters
        if missing_params:
            root = tk.Tk()
            root.withdraw()
            dialog = ParameterDialog(root, missing_params, "Current Config", "New Config")
            root.wait_window(dialog)
            
            if dialog.result:
                comparison_results.update(dialog.result)

        # Add different parameters
        for param, value2 in params2.items():
            if param in params1 and param != "AxisName":
                if params1[param] != value2:
                    comparison_results[param] = value2

        # Save results
        if comparison_results:
            with open(output_json, "w", encoding="utf-8") as json_file:
                json.dump({"0": comparison_results}, json_file, indent=4)

        # Cleanup
        shutil.rmtree(extract_path1, ignore_errors=True)
        shutil.rmtree(extract_path2, ignore_errors=True)
        self._cleanup_old_mcd()

    def _cleanup_old_mcd(self):
        # Clean up Old MCD directory
        old_mcd_dir = 'Old MCD'
        try:
            for file in os.listdir(old_mcd_dir):
                file_path = os.path.join(old_mcd_dir, file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f'Error deleting {file_path}: {e}')
        except Exception as e:
            print(f"Error accessing {old_mcd_dir}: {e}")

class ParameterDialog(tk.Toplevel):
    def __init__(self, parent, missing_params, file1_name, file2_name):
        super().__init__(parent)
        self.title("Missing Parameters")
        self.modified_params = {}
        
        # Create main frame
        main_frame = tk.Frame(self)
        main_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)
        
        # Add header
        header = tk.Label(main_frame, text="Parameters present in one file but missing in the other:", font=('Arial', 10, 'bold'))
        header.pack(pady=(0, 10))
        
        # Create scrollable frame
        canvas = tk.Canvas(main_frame)
        scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Add parameter entries
        for param, details in missing_params.items():
            frame = tk.Frame(scrollable_frame)
            frame.pack(fill=tk.X, pady=2)
            
            source = file1_name if details["source"] == "file1" else file2_name
            label_text = f"{param} (from {source})"
            tk.Label(frame, text=label_text).pack(side=tk.LEFT)
            
            entry = tk.Entry(frame)
            entry.insert(0, details["value"])
            entry.pack(side=tk.RIGHT)
            
            self.modified_params[param] = entry
        
        # Pack scrollable components
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Add buttons
        button_frame = tk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        tk.Button(button_frame, text="Apply", command=self.apply).pack(side=tk.RIGHT, padx=5)
        tk.Button(button_frame, text="Cancel", command=self.cancel).pack(side=tk.RIGHT)
        
        self.result = None
        
    def apply(self):
        self.result = {param: entry.get() for param, entry in self.modified_params.items()}
        self.destroy()
        
    def cancel(self):
        self.result = None
        self.destroy()

