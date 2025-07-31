Workflow 1 is the intended workflow of these methods within the Automated CMP Checkout program. In this folder, we are comparing the results of running Workflow 1 and creating an MCD with Machine Setup in Studio:



Workflow 1 through **GenerateMCD.py**: 

**_update_json_config()**

Reads in Template-iXC4e.json

Inserts "stage_type" and "axis" into appropriate fields with ""

Inserts key/value pairs from "specs_dict" into "ConfiguredOptions"

Saves as WorkingTemplate-iXC4e.json



**convert_to_mcd()**

Reads in WorkingTemplate-iXC4e.json

Creates a JObject

Passes JObject to **ConvertToMcd**

Returns MCD object



**calculate_parameters()**

Passes MCD object from **ConvertToMcd** to **CalculateParameters**

Returns new MCD object

Executes mcd_obj.**WriteToFile**





This one makes it all of the way through Workflow 1, however, the resulting MCD doesn't include any parameter values.





