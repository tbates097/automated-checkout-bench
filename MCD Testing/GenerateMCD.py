"""
This module provides a robust class to interact with Aerotech Automation1 DLLs.
It uses an explicit initialize() method to ensure .NET assemblies are loaded
at the correct time, preventing initialization errors.
"""
from pythonnet import load
load("coreclr")
import os
import sys
import json

# Import System for Type.GetType
import System
from System.Collections.Generic import List
from System import String

import clr

class AerotechController:
    """
    A class to encapsulate the functionality of Aerotech's machine 
    configuration DLLs. It separates object creation from the sensitive
    .NET assembly loading and provides a clean API for core functions.

    Usage:
       
        # --- Workflow 1: JSON Specs -> Calculated MCD Object ---
        mcd_obj, _ = controller.convert_to_mcd(specs_dict, ...)
        calculated_mcd, _ = controller.calculate_parameters(mcd_obj)

        # --- Workflow 2: MCD File -> JSON File ---
        controller.convert_to_json("path/to/input.mcd", "path/to/output.json")
    """

    def __init__(self, aerotech_dll_path, config_manager_path, example_mcd_path, example_json_output_path, specs_dict, stage_type, axis):
        """
        Initializes the controller with necessary paths.
        Does NOT load any .NET assemblies.

        Args:
            aerotech_dll_path (str): The absolute path to the directory 
                                     containing the Aerotech DLLs.
            config_manager_path (str): The absolute path to the directory
                                       containing the System.Configuration.ConfigurationManager.dll.
        """
        if not os.path.exists(aerotech_dll_path):
            raise FileNotFoundError(f"Aerotech DLL path not found: {aerotech_dll_path}")
        if not os.path.exists(config_manager_path):
            raise FileNotFoundError(f"ConfigurationManager path not found: {config_manager_path}")
            
        self.aerotech_dll_path = aerotech_dll_path
        self.config_manager_path = config_manager_path
        self.specs_dict = specs_dict
        self.stage_type = stage_type
        self.axis = axis
        # Define constant paths based on the script's location
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.template_path = os.path.join(self.base_dir, "Template-iXC4e.json")
        self.working_json_path = os.path.join(self.base_dir, "WorkingTemplate-iXC4e.json")
        self.example_mcd_path = example_mcd_path
        self.example_json_output_path = example_json_output_path

        self.McdFormatConverter = None
        self.MachineControllerDefinition = None
        self.JObject = None
        self.initialized = False

    def initialize(self):
        """
        Loads all necessary .NET assemblies and types. This method
        must be called before any other methods that interact with the DLLs.
        """
        if self.initialized:
            print("Controller already initialized.")
            return

        print("Initializing Aerotech Controller...")
        os.environ["PATH"] = self.aerotech_dll_path + ";" + os.environ["PATH"]
        os.add_dll_directory(self.aerotech_dll_path)
        
        try:
            print("Loading .NET Assemblies...")
            clr.AddReference(os.path.join(self.aerotech_dll_path, "Newtonsoft.Json.dll"))
            clr.AddReference(os.path.join(self.config_manager_path, "System.Configuration.ConfigurationManager.dll"))
            clr.AddReference(os.path.join(self.aerotech_dll_path, "Aerotech.Automation1.Applications.Core.dll"))
            clr.AddReference(os.path.join(self.aerotech_dll_path, "Aerotech.Automation1.Applications.Interfaces.dll"))
            clr.AddReference(os.path.join(self.aerotech_dll_path, "Aerotech.Automation1.Applications.Shared.dll"))
            clr.AddReference(os.path.join(self.aerotech_dll_path, "Aerotech.Automation1.DotNetInternal.dll"))
            clr.AddReference(os.path.join(self.aerotech_dll_path, "Aerotech.Automation1.Applications.Wpf.dll"))
            print("Assemblies loaded successfully.")

            import Newtonsoft.Json.Linq
            self.JObject = Newtonsoft.Json.Linq.JObject

            print("Loading required types...")
            type_name1 = "Aerotech.Automation1.Applications.Wpf.McdFormatConverter, Aerotech.Automation1.Applications.Wpf"
            type_name2 = "Aerotech.Automation1.DotNetInternal.MachineControllerDefinition, Aerotech.Automation1.DotNetInternal"
            
            self.McdFormatConverter = System.Type.GetType(type_name1)
            self.MachineControllerDefinition = System.Type.GetType(type_name2)

            if self.McdFormatConverter is None or self.MachineControllerDefinition is None:
                raise TypeError("Could not load required .NET types. Check DLL versions and names.")
            
            print("Types loaded successfully.")
            self.initialized = True
            print("Controller initialized successfully.")

        except Exception as e:
            self.initialized = False
            raise RuntimeError(f"Failed to initialize controller: {e}")

    def _check_initialized(self):
        """Helper to ensure initialize() has been called."""
        if not self.initialized:
            raise RuntimeError("Controller has not been initialized. Please call controller.initialize() first.")

    def _update_json_config(self, specs_dict, template_path, output_path, stage_type=None, axis=None):
        """(Private) Updates a JSON configuration file with new specifications."""
        with open(template_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        mech_products = data.get("MechanicalProducts")
        if not mech_products:
            raise KeyError("MechanicalProducts not found in JSON.")
        
        mech_product = mech_products[0]
        mech_product.setdefault("ConfiguredOptions", {}).update(specs_dict)

        if stage_type:
            mech_product["Name"] = stage_type
            mech_product["DisplayName"] = stage_type

        interconnected_axes = data.get("InterconnectedAxes")
        if interconnected_axes:
            inter_axis = interconnected_axes[0]
            if axis:
                inter_axis["Name"] = axis
            if stage_type and "MechanicalAxis" in inter_axis:
                inter_axis["MechanicalAxis"]["DisplayName"] = stage_type

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Configuration updated in {output_path}")

    def _read_mcd_from_file(self, mcd_path):
        """(Private) Reads an MCD file from disk and returns the .NET object."""
        self._check_initialized()
        if not os.path.exists(mcd_path):
            raise FileNotFoundError(f"MCD file not found at: {mcd_path}")
            
        print(f"\nAttempting to read MCD file: {mcd_path}")
        read_from_file = self.MachineControllerDefinition.GetMethod("ReadFromFile")
        mcd = read_from_file.Invoke(None, [mcd_path])
        print("Successfully read MCD file.")
        return mcd

    def convert_to_mcd(self, specs_dict=None, stage_type=None, axis=None, workflow=None):
        """
        Creates a working JSON config from a template and converts it to an MCD object.
        Uses the constant template and working paths defined in the controller.
        """
        self._check_initialized()
        if specs_dict:
            self._update_json_config(specs_dict, self.template_path, self.working_json_path, stage_type, axis)
        
            with open(self.working_json_path, "r", encoding="utf-8") as f:
                json_str = f.read()
        else:
            full_mcd_json = os.path.join(self.base_dir, f"{stage_type}.json")
            with open(full_mcd_json, "r", encoding="utf-8") as f:
                json_str = f.read()
        jobject = self.JObject.Parse(json_str)
        warnings = List[String]()

        convert_method = self.McdFormatConverter.GetMethod("ConvertToMcd")
        mcd_obj = convert_method.Invoke(None, [jobject, warnings])
        
        if workflow == 'wf2':
            mcd_obj.WriteToFile(self.example_mcd_path)

        return mcd_obj, list(warnings)

    def convert_to_json(self, mcd_path, output_json_path):
        """
        Reads an MCD file from disk and converts it to a JSON file.
        """
        self._check_initialized()
        mcd_obj = self._read_mcd_from_file(mcd_path)
        
        warnings = List[String]()
        convert_method = self.McdFormatConverter.GetMethod("ConvertToJson")
        json_obj = convert_method.Invoke(None, [mcd_obj, warnings])

        with open(output_json_path, 'w', encoding='utf-8') as f:
            f.write(json_obj.ToString())
        print(f"JSON representation saved to {output_json_path}")
        return list(warnings)

    def calculate_parameters(self, specs_dict=None, stage_type=None, axis=None):
        """
        Creates an MCD object from specs and calculates its parameters.
        This is the primary method for the JSON -> calculated MCD workflow.
        """
        self._check_initialized()
        
        # Step 1: Convert specs to an initial MCD object.
        print("\nConverting specs to initial MCD object...")
        mcd_obj, conversion_warnings = self.convert_to_mcd(specs_dict=specs_dict, stage_type=stage_type, axis=axis)
        if conversion_warnings:
            print("Warnings during conversion:", conversion_warnings)
        print("Initial conversion complete.")

        # Step 2: Calculate parameters on the new MCD object.
        print("\nCalculating parameters...")
        warnings = List[String]()
        calculate_method = self.McdFormatConverter.GetMethod("CalculateParameters")
        calculated_mcd = calculate_method.Invoke(None, [mcd_obj, warnings])
        calculation_warnings = list(warnings)
        if calculation_warnings:
            print("Warnings during calculation:", calculation_warnings)
        print("Parameter calculation complete.")
        
        calculated_mcd.WriteToFile(self.example_mcd_path)

        # Combine warnings from both steps.
        all_warnings = conversion_warnings + calculation_warnings
        
        return calculated_mcd, all_warnings

    def save_mcd_file(self, mcd_obj):
        """
        Saves a MachineControllerDefinition object to a .mcd file.

        Args:
            mcd_obj: The .NET MCD object to save.
            output_mcd_path (str): The full path for the output .mcd file.
        """
        output_mcd_path = os.path.join(self.base_dir, f"{self.stage_type}_output.mcd")
        self._check_initialized()
        print(f"\nAttempting to save MCD object to: {output_mcd_path}")
        try:
            # The 'WriteToFile' method is likely an instance method on the mcd_obj itself.
            write_method = self.MachineControllerDefinition.GetMethod("WriteToFile")
            # The first argument to Invoke is the instance, the second is a list of method args.
            write_method.Invoke(mcd_obj, [output_mcd_path])
            print("MCD file saved successfully.")
        except Exception as e:
            raise RuntimeError(f"Failed to save MCD file: {e}")

def main(workflow, stage_type, axis):
    """
    Example usage of the AerotechController class.
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # --- Configuration ---
    AEROTECH_DLL_PATH = os.path.join(base_dir, "extern", "Automation1")
    CONFIG_MANAGER_PATH = os.path.join(base_dir, "System.Configuration.ConfigurationManager.8.0.0", "lib", "netstandard2.0")
    # For demonstrating the mcd -> json workflow
    EXAMPLE_MCD_PATH = os.path.join(base_dir, f"{stage_type}.mcd") 
    EXAMPLE_JSON_OUTPUT_PATH = os.path.join(base_dir, f"{stage_type}_from_mcd.json")
    
    #specs_dict = {
        #'Direct Linear Feedback': 'SL', 
        #'Travel': '-100', 
        #'Tabletop': '-TT1', 
        #'Motor': '-M1', 
        #'Foldback': '', 
        #'Limits': '-LI1', 
        #'Lifting Hardware': ''
    #}
    
    specs_dict = {
        'Travel': '-0100',
        'Feedback': '-E1',
        'Cable Management': '-CMS2'
    }
    # ---------------------

    try:
        # 1. Create the controller object
        controller = AerotechController(AEROTECH_DLL_PATH, CONFIG_MANAGER_PATH, EXAMPLE_MCD_PATH, EXAMPLE_JSON_OUTPUT_PATH, specs_dict, stage_type, axis)
        # 2. Explicitly initialize the controller
        controller.initialize()

        if workflow == 'wf1':
            # --- WORKFLOW 1: From JSON specs to calculated MCD object ---
            print("\n--- Starting Workflow 1: JSON -> Calculated MCD ---")
            # 3. Create and calculate parameters in a single step.
            calculated_mcd_object, warnings = controller.calculate_parameters(
                specs_dict=specs_dict, stage_type=stage_type, axis=axis
            )
            print("\nWorkflow 1 complete.")
            if warnings:
                print("Total warnings for workflow:", warnings)
            else:
                print("No warnings generated during workflow.")
            print(f'\nFinal Calculated MCD Object: {calculated_mcd_object}')
        
        if workflow == 'wf2':
            # --- WORKFLOW 2: Convert a JSON object to an MCD object
            print("\nConverting specs to initial MCD object...")
            mcd_obj, conversion_warnings = controller.convert_to_mcd(specs_dict=specs_dict, stage_type=stage_type, axis=axis, workflow=workflow)
            if conversion_warnings:
                print("Warnings during conversion:", conversion_warnings)

        if workflow == 'wf3':
            # --- WORKFLOW 3: From .mcd file to .json file ---
            # Note: This requires an actual .mcd file to exist at EXAMPLE_MCD_PATH
            print("\n--- Starting Workflow 2: MCD File -> JSON File ---")
            if os.path.exists(EXAMPLE_MCD_PATH):
                controller.convert_to_json(EXAMPLE_MCD_PATH, EXAMPLE_JSON_OUTPUT_PATH)
            else:
                print(f"\nSkipping MCD -> JSON conversion because example file not found at: {EXAMPLE_MCD_PATH}")

    except (FileNotFoundError, TypeError, RuntimeError, KeyError, Exception) as e:
        print(f"\nAn error occurred: {e}")
        if hasattr(e, 'InnerException') and e.InnerException:
            print(f"Inner Exception: {e.InnerException}")
        sys.exit()


if __name__ == "__main__":
    '''
        Workflow options:
        wf1: 
            - Before executing the program, define contents of specs_dict (stage configuration selections that appear in Machine Setup), stage_type, and axis 
              in the main() function. 
            - After clicking run, the program will pass those variables to a function that inserts those values into a JSON template and 
              writes them to a JSON object. 
            - It will then pass the JSON object to ConvertToMcd, which generates an MCD object. 
            - Finally, the MCD object will be passed to CaclulateParameters to generate a new MCD object with new parameters calculated by Machine Setup. 
              This will download the MCD to the directory.

        wf2: 
            - Takes a JSON object and converts it to an MCD object. 
            - This can either take a specs_dict dictionary to pass to the function that updates the JSON template, or will look for the JSON file in the directory. 
            - This will output a MCD object built by the values in the JSON.

        wf3: 
            - Takes an MCD and converts it to a JSON file.
    '''
    workflow = 'wf2'    ################# Enter workflow option 
    stage_type = 'PRO165LM'  ############ Example stage type
    axis = 'X'  ######################### Example axis  
    main(workflow, stage_type, axis)
