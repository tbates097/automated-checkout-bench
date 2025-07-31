For this one, I couldn't make it through Workflow 1 because of the error (error.txt in **ConvertToMcd** using Template JSON). Instead, I just saved the MCD objects created by **ConvertToMCD**.



In GenerateMCD.py, changing the workflow variable to 'wf2' accomplishes this.



**convert_to_mcd()** has the option to pass specs_dict as None if you want to create an MCD from a fully configured JSON file, otherwise, it will take the path that inserts the variables into Template-iXC4e.json and uses it.



You will notice that the resulting JSON from running the outputted MCD objects through **ConvertToJson** results in an empty MechanicalProducts list.

