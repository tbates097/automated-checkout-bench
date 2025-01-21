from PyQt5 import QtWidgets, QtSql, QtGui
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import QCompleter
from mainwindow import Ui_MainWindow
#from popup_accel_decel import Ui_Dialog as popup_accel_decel
#from popup_constant_velocity import Ui_Dialog as popup_constant_velocity
#from popup_decel_to_zero import Ui_Dialog as popup_decel_to_zero
#from popup_dwell import Ui_Dialog as popup_dwell
#from popup_point_to_point import Ui_Dialog as popup_point_to_point
#from popup_brake import Ui_Dialog as popup_brake
from popup_config_window import Ui_Dialog as popup_config
#from popup_inertia_calc import Ui_Dialog as popup_inertia_calc
#from popup_payload_calc import Ui_Dialog as popup_payload_calc
from popup_spec_display import Ui_Dialog as popup_spec_display
# from shutil import copyfile  # moved local to "save" "saveAs" and "open" functions
import sys
import os
import time
import re
#from setuptools import pkg_resources
#.py2_warn
#from setuptools import pkg_resources.markers
# import winreg
# from win32comext.shell import shell, shellcon
import sqlite3 as lite
# import re  # moved local to "refresh_plots" "edit_profile" and "calc_results" functions
import datetime
import numpy as np
# import time  # moved local to "save" and "saveAs" functions
# from matplotlib.figure import Figure  # moved loacal to "MplCanvas" class
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as Canvas
# from matplotlib import rc  # moved local to "refresh_plot"
# import scipy.integrate as sint  # moved local to "refresh_plot"
# import pandas as pd  # moved local to "calc_results" function
# from reportlab.lib.pagesizes import letter  # moved local to "print" function
# from reportlab.pdfgen import canvas  # moved local to "print" function
# from reportlab.pdfbase import pdfmetrics, ttfonts  # moved local to "print" function


# Version 1.08
# global definitions---------------------------------------

if not getattr(sys, 'frozen', False):
    dir_path = r"C:\Users\tbates\Python\automated-checkout-bench"
    if not os.path.exists(dir_path + r"\Temp Files"):
        os.makedirs(dir_path + r"\Temp Files")
    temp_files = [f for f in os.listdir(dir_path + r"\Temp Files\\")]  # remove all previously created temp files
    for f in temp_files:
        try:
            os.remove(os.path.join(dir_path, "Temp Files", f))
        except PermissionError as error:
            print("file currently in use")
else:
    dir_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    pf_path = os.path.dirname(dir_path)
    temp_files = [f for f in os.listdir(pf_path + r"\Temp Files\\")]  # remove all previously created temp files
    for f in temp_files:
        try:
            os.remove(os.path.join(pf_path, "Temp Files", f))
        except PermissionError as error:
            print("file currently in use")


def resource_path(relative_path):  # this function opens files that are packaged with the .exe
    return os.path.join(dir_path, relative_path)

# toggle the two lines below depending on if the code is to be executed from IDE or compiled .exe.
if not getattr(sys, 'frozen', False):
    db_filepath = r"C:\Users\tbates\Python\automated-checkout-bench\ballscrew_sizer.db"  # use this when running in python
else:
    db_filepath = resource_path('ballscrew_sizer.db')  # change to this before deploying as .exe

if not getattr(sys, 'frozen', False):
    config_filepath = r"C:\Users\tbates\Python\automated-checkout-bench\master.db"  # use this when running in python
else:
    config_filepath = resource_path('master.db')  # change to this before deploying as .exe

'''        if not getattr(sys, 'frozen', False):
            plot_path = dir_path + r"\Temp Files\\" + "print_plot" + date_string + ".png"  # saves in temp file dir
        else:
            plot_path = pf_path + r"\Temp Files\\" + "print_plot" + date_string + ".png"  # saves in temp file dir'''

# create temp file
date_string = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-4]
if not getattr(sys, 'frozen', False):
    temp_filepath = dir_path + r"\Temp Files\\" + date_string + ".amszr"
else:
    temp_filepath = pf_path + r"\Temp Files\\" + date_string + ".amszr"
filepath = None  # initialize global variable for saved filepath

# initialize calculated arrays (these large arrays are saved as globals to speed up calculations)
a = [0]
v = [0]
t = [0]
b = [0]


# create necessary tables in temp file
con = lite.connect(temp_filepath)
with con:
    cur = con.cursor()
    cur.execute(
        "CREATE TABLE IF NOT EXISTS [Profile](id INTEGER PRIMARY KEY, Operation INTEGER, Type TEXT, Parameters TEXT,"
        " Brake TEXT)")
    cur.execute("CREATE TABLE IF NOT EXISTS [Save] (id INTEGER PRIMARY KEY, SaveState TEXT, Time DATETIME)")
    cur.execute("CREATE TABLE IF NOT EXISTS [Inputs] (id INTEGER PRIMARY KEY, Stage TEXT, Motor TEXT, Drive TEXT,"
                " BusVoltage TEXT, Payload TEXT, Orientation TEXT, Temperature TEXT, Vacuum TEXT, Voltage TEXT)")

# -----------------------------------------------------------------


class Database:
    """Creates connection to temp file database."""
    def __init__(self, parent=None):
        self.data = QtSql.QSqlDatabase.addDatabase("QSQLITE", "file")
        self.data.setDatabaseName(temp_filepath)
        self.data.open()


class Model(QtSql.QSqlQueryModel):
    """Establishes initial QSqlQueryModel with a SELECT * query."""
    def __init__(self, parent=None):
        super(Model, self).__init__(parent)
        self.db = QtSql.QSqlDatabase.database(connectionName="file")
        self.setQuery("SELECT Operation, Type, Parameters FROM Profile ORDER BY Operation ASC", db=self.db)


class DatabaseSizer:
    """Creates connection to sizer info database."""
    def __init__(self, parent=None):
        self.data = QtSql.QSqlDatabase.addDatabase("QSQLITE", "db")
        self.data.setDatabaseName(db_filepath)
        self.data.open()

class ConfigSizer:
    
    def __init__(self, parent=None):
        self.data = QtSql.QSqlDatabase.addDatabase("QSQLITE", "db")
        self.data.setDatabaseName(config_filepath)
        self.data.open()

class PopupConfig(QtWidgets.QDialog, popup_config):
    """Instantiates and performs all configuration logic via Master db and logical adjustments"""
    def __init__(self, parent=None,stage=None):

        QtWidgets.QDialog.__init__(self)
        self.stage = stage 
        #print(self.stage)
        self.spec_names = []
        self.spec_vals = []
        self.spec_dtype = []
        self.spec_units=[]
        self.mtr_spec_dtype=[]
        self.mtr_spec_names=[]
        self.mtr_spec_vals=[]
        self.mtr_spec_units=[]
        self.motor =""
        self.motorType=""
        self.stageType=""
        self.configured = False
        #if not ("-" in self.stage) or (not "XY-" in self.stage ):
        text_file = open(resource_path("Products.txt"), "r")
        names = text_file.readlines()
        #print(names)
        new_names =[]
        for name in names:
            new_names.append(name.strip())
        text_file.close()
        text_file = open(resource_path("Motors.txt"),"r")
        motor_names = text_file.readlines()
        corrected_motor_names=[]
        for name in motor_names:
            corrected_motor_names.append(name.strip())
            
        #print(corrected_motor_names)
        #print(self.stage in corrected_motor_names)
        checkMotor = self.stage.split("-")
        if (not self.stage in new_names and not (self.stage in corrected_motor_names)):
            self.configured = True
        
        
        # if "XY" in self.stage:
            # if "XY-" in self.stage:
               # self.configured = True 
        # if "-" in self.stage and "XY" not in self.stage :
            # self.configured = True
        if not self.configured: 
            #print("need to configure")
            self.setupUi(self)
        else:
            self.configured = True
            #self.l1=QtWidgets.QLabel("Let's Close this Window")
            self.resize(200,40)
            
            
            self.configured_txt_box = QtWidgets.QLabel(self)
            
            self.configured_txt_box.setText("Press Ok to Configure")
            self.buttonBox = QtWidgets.QDialogButtonBox(self)
            #self.buttonBox.setAlignment(Lower)
            self.buttonBox.setStandardButtons(QtWidgets.QDialogButtonBox.Cancel|QtWidgets.QDialogButtonBox.Ok)
            self.buttonBox.accepted.connect(self.accept)
            self.buttonBox.rejected.connect(self.reject)
            self.layout = QtWidgets.QGridLayout()
            self.layout.addWidget(self.configured_txt_box,0,0)
            self.layout.addWidget(self.buttonBox,1,0)
            self.setLayout(self.layout)
            #self.l1.setAlignment(QtGui.AlignCenter)
            #self.setCentralWidget(self.l1)
            self.exit=QtWidgets.QAction("Exit Application",shortcut=QtGui.QKeySequence("Ctrl+q"),triggered=lambda:self.exit_app)
            self.addAction(self.exit)
    
    
    def exit_app(self):
        #Used to close config window when stage is already preconfigured (opening from previous)
        print("Shortcut pressed") #verification of shortcut press
        self.close()

    
    def getElements(self):
        ##Function used to return value elements in debugging
        values = []
        for i in range(self.config_options.rowCount()):
            values.append(self.config_options.record(i).value("Value Description"))
        return values
   

    def setDBTable(self,table_input,tblname):
        ##Establishes new connection based off of input for stage and which sheet we want to query on
        self.config_options = QtSql.QSqlTableModel(db = self.config_sizer.data)
        self.config_options.setTable(tblname + table_input)
        self.config_options.select()
    
    
    def printTable(self,firstVal,secondVal):
        ##Print table used for debugging to see what the query results in 
        for i in range(self.config_options.rowCount()):
            first = self.config_options.record(i).value(firstVal)
            second = self.config_options.record(i).value(secondVal)
            if isinstance(first,int) or isinstance(first,float):
                print(firstVal +": " + str(first) + "\n" + secondVal +": "+ second + "\n")
            elif isinstance(second,int) or isinstance(second,float):
                print(firstVal +": " + first + "\n" + secondVal +": "+ str(second) + "\n")
            else:
                print(firstVal +": " + first + "\n" + secondVal +": "+ second + "\n")
    
    
    def getParams(self):
        ##Retrieves all parameters when configurating from scratch
        self.configs = []
        for config_box in self.config_boxes:
            if config_box.placeholderText() == config_box.currentText():
                self.configs.append("~")
            else:
                #print(config_box.currentText())
                if config_box.currentText().rstrip() == "Lower" or config_box.currentText().rstrip() == "Upper" or config_box.currentText().rstrip() == "Azimuth" or config_box.currentText().rstrip() == "Elevation":
                    #print("Here")
                    self.configs.append("~")
                    if config_box.currentText() =="Lower" or config_box.currentText() == "Azimuth":
                        self.axis = 1  #keep as int to match the DB
                    elif config_box.currentText() == "Upper" or config_box.currentText() == "Elevation":
                        self.axis = 2  #keep as int to match the DB
                else:
                    self.config_options.setFilter("\"Value Description\" LIKE '" + config_box.currentText().rstrip()+"'")
                    self.config_options.select()
                    if self.config_options.record(0).value("Value") == '':
                        self.configs.append("NULL")
                    else:
                        self.configs.append(self.config_options.record(0).value("Value"))
                        
        #print(self.configs)

  
    def getParamsPreConfig(self,configs):
        ##Retrieves parameters when the stage has been sent as preconfigured (opening from previous file)
        self.configs =[]
        self.config_txts = []
        i=0
        #print(configs)
        for config in configs:
            #print(config)
            self.config_options.setFilter("Value LIKE '" + config +"'")
            self.config_options.select()
            if self.config_options.record(0).value("Value") == '':
                self.configs.append("NULL")
            else:
                self.configs.append(self.config_options.record(0).value("Value"))
                self.config_txts.append(self.config_options.record(0).value("Input Name"))
        #print(self.configs)
    
    def addRuleIDs(self):
        for i in range(self.config_options.rowCount()): #added-1
            rule = self.config_options.record(i).value("Rule Id")
            #print(rule)
            if not rule in self.ruleIDS:
                self.ruleIDS.append(rule)
    
        
    def checkEqual(self):
      #self.config_options.setFilter("Operator LIKE Equal")
      filter = "Operator LIKE 'Equal' AND ("
      #print(self.configs)
      i=0
      
      # if self.configs is None:
          # print("return")
          # return
      for config in self.configs:
          if config is not None:
              #print(type(config))
              #print(config)
              if not str(config).startswith("~"):
                  if self.configured is False:
                      if config == 'NULL':
                          filter = filter + "(Value IS NULL AND \"Input Name\" LIKE '" + self.config_txts[i].text() + "') OR "
                      else:
                          filter = filter + "(Value LIKE '" + str(config) + "' AND \"Input Name\" LIKE '" + self.config_txts[i].text() + "') OR "
                  elif self.configured is True:
                      if config == 'NULL':
                          filter = filter + "(Value IS NULL AND \"Input Name\" LIKE '" + self.config_txts[i] + "') OR "
                      else:
                          filter = filter + "(Value LIKE '" + str(config) + "' AND \"Input Name\" LIKE '" + self.config_txts[i] + "') OR "
          i=i+1
      filter = filter[:len(filter)-3]
      filter = filter + ")"
      #print(filter)
      self.config_options.setFilter(filter)
      self.config_options.select()
      self.addRuleIDs()
    def checkNotEqual(self):
        filter = "Operator LIKE 'Not Equal' AND ("
        i=0
        for config in self.configs:
            if not config is None:
                if not str(config).startswith("~"):
                    if self.configured is False:
                        if config == 'NULL':
                            filter = filter + "(Value IS NOT NULL AND \"Input Name\" LIKE '" + self.config_txts[i].text() + "') OR "
                        else:
                            filter = filter + "((Value NOT LIKE '" + str(config) + "' OR Value IS NULL) AND \"Input Name\" LIKE '" + self.config_txts[i].text() + "') OR "
                    elif self.configured is True:
                        if config == 'NULL':
                            filter = filter + "(Value IS NOT NULL AND \"Input Name\" LIKE '" + self.config_txts[i] + "') OR "
                        else:
                            filter = filter + "((Value NOT LIKE '" + str(config) + "' OR Value IS NULL) AND \"Input Name\" LIKE '" + self.config_txts[i] + "') OR "
            i=i+1
        filter = filter[:len(filter)-3]
        
        filter = filter + ")"
        self.config_options.setFilter(filter)
        self.config_options.select()
        #print(filter)
        #configs = self.getParams()
        # for config in configs:
            # if not config.startswith("~"):
        self.addRuleIDs()
    def checkIn(self):
        filter = "Operator LIKE 'In' AND ("
        i=0
        for config in self.configs:
            if not config is None:
                if not str(config).startswith("~"):
                    if self.configured is False:
                        filter = filter +"(Value LIKE '%" + str(config) + "%' AND \"Input Name\" LIKE '" + self.config_txts[i].text() + "') OR "
                    elif self.configured is True:
                        filter = filter +"(Value LIKE '%" + str(config) + "%' AND \"Input Name\" LIKE '" + self.config_txts[i] + "') OR "
            i =i+1
        filter = filter[:len(filter)-3]
        filter = filter + ")"
        #print(filter)
        self.config_options.setFilter(filter)
        self.config_options.select()
        self.addRuleIDs()
    def getTarget(self,input_name):
        for i in range(len(self.config_boxes)):
            #input_name = self.config_options.record(0).value("Target")
            if  input_name == self.config_txts[i].text():
                return i
        return -1
    def remove(self, config_to_remove,tblname):
       # print("Remove")
        #print(config_to_remove)
        #print(self.config_options.record(0).value("Target")) 
        count =0
        for config_box in self.config_boxes:
            input_name = self.config_options.record(0).value("Target")
            if  input_name == self.config_txts[count].text() and self.configured is False:
                if config_to_remove == '':
                    #print("Is null")
                    config_box.removeItem(config_box.findText('None'))
                else:
                    #print(config_to_remove)
                    self.setDBTable(self.inputs_app,tblname)
                    self.config_options.setFilter("\"Input Name\" LIKE '" + input_name + "' AND Value LIKE '" + config_to_remove + "'")
                    self.config_options.select()
                    config_box.removeItem(config_box.findText(self.config_options.record(0).value("Value Description")))
            count = count+1
    def removeExcept(self, configs_to_remove,tblname):
        #print("Remove except")
        #configs_to_remove = self.config_options.record(0).value("Value")
        remove_except = configs_to_remove.split("~")
        count =0
        for config_box in self.config_boxes:
            input_name = self.config_options.record(0).value("Target")
            if  input_name == self.config_txts[count].text() and self.configured is True:
                    self.setDBTable(self.inputs_app,tblname)
                    filter = "\"Input Name\" LIKE '" + input_name + "' AND Value  != '" 
                    for item in remove_except:
                        filter = filter + item + "' AND Value != '"
                    filter = filter[:len(filter)-14]
                    #print(filter)
                    self.config_options.setFilter(filter)  
                    self.config_options.select()
                    #self.printTable("Value","Value Description")
                    for i in range(self.config_options.rowCount()):
                        config_box.removeItem(config_box.findText(self.config_options.record(i).value("Value Description")))
            count = count+1
    def disable(self,config_to_remove,tblname):
        #print("disable")
        loc = self.getTarget(config_to_remove)
        #print(loc)
        self.config_boxes[loc].setVisible(False)
    def setSpec(self,action_id,tblname,flag,rule):
        #loc = self.getTarget()
        self.setDBTable(self.actions_app,tblname)
        #print(str(action_id))
        self.config_options.setFilter("\"Action Id\" LIKE '" + str(action_id) + "' AND \"Rule Id\" LIKE '" + str(rule) + "' AND Axis LIKE '" + str(self.axis) + "'")
        self.config_options.select()
        #self.printTable("Action Id", "Target")
        if flag == "stage":
            for i in range(len(self.spec_names)):
                if self.spec_names[i] == self.config_options.record(0).value("Target"):
                    if (self.spec_dtype[i] == "decimal" or self.spec_dtype[i] == "int") and not self.config_options.record(0).value("Value") == "" :
                        self.spec_vals[i] = float(self.config_options.record(0).value("Value"))
                    else:
                        self.spec_vals[i] = self.config_options.record(0).value("Value")
        else:
            #print("motor spec equal")
            #self.printTable("Action Id", "Value")
            for i in range(len(self.mtr_spec_names)):
                if self.mtr_spec_names[i] == self.config_options.record(0).value("Target"):
                    if self.mtr_spec_dtype[i] == "decimal" or self.mtr_spec_dtype[i] == "int":
                        #print("\nBefore add: " +self.mtr_spec_names[i] + ": " +str(self.mtr_spec_vals[i]))
                        #print("\nNew Value: " + self.config_options.record(0).value("Value"))
                        self.mtr_spec_vals[i] = float(self.config_options.record(0).value("Value"))
                        #print("\nAfter add: "+str(self.mtr_spec_vals[i]))
                    else:
                        self.mtr_spec_vals[i] = self.config_options.record(0).value("Value")
    
    def specAdd(self,action_id,tblname,flag,rule):
        self.setDBTable(self.actions_app,tblname)
        self.config_options.setFilter("\"Action Id\" LIKE '" + str(action_id) +"'AND Axis like '"+ str(self.axis)+ "' AND \"Rule Id\" LIKE '" + str(rule) + "'")
        self.config_options.select()
        if flag == "stage":
            for i in range(len(self.spec_names)):
                if self.spec_names[i] == self.config_options.record(0).value("Target"):
                    if self.spec_dtype[i] == "decimal" or self.spec_dtype[i] == "int":
                        #print("\nBefore add: "+str(self.spec_vals[i]))
                        self.spec_vals[i] = self.spec_vals[i] + float(self.config_options.record(0).value("Value"))
                        #print("\nAfter add: "+str(self.spec_vals[i]))
                    else:
                        #print(self.config_options.record(0).value("DataType"))
                        #print(str(self.spec_vals[i]) + ": Value to add: " + str(self.config_options.record(0).value("Value")) + "\n")
                        self.spec_vals[i] = self.spec_vals[i] + self.config_options.record(0).value("Value")
        else:
            for i in range(len(self.mtr_spec_names)):
                #print("motor spec add")
                if self.mtr_spec_names[i] == self.config_options.record(0).value("Target"):
                    if self.mtr_spec_dtype[i] == "decimal" or self.mtr_spec_dtype[i] == "int":
                        #print("\nBefore add: "+str(self.mtr_spec_vals[i]))
                        self.mtr_spec_vals[i] = self.mtr_spec_vals[i] + float(self.config_options.record(0).value("Value"))
                        #print("\nAfter add: "+str(self.mtr_spec_vals[i]))
                    else:
                        #print(self.config_options.record(0).value("DataType"))
                        #print(str(self.spec_vals[i]) + ": Value to add: " + str(self.config_options.record(0).value("Value")) + "\n")
                        self.mtr_spec_vals[i] = self.mtr_spec_vals[i] + self.config_options.record(0).value("Value")
        #loc = self.getTarget()
    def checkActions(self,tblname,rules,flag):
        #print(self.ruleIDS)
        #print(rules)
        rulesToRemove=[]
        self.test = 1
        #if self.configs==None:
            #self.configs=[]
        #print(self.axis)
        self.setDBTable(self.conditions_app,tblname)
        for rule in rules:
            #print(rule)
            #rule = rules[i]
            self.config_options.setFilter("\"Rule Id\" = " + str(rule))
            self.config_options.select()
            #print(str(rule) + "rows " + str(self.config_options.rowCount()))
            #self.printTable("Rule Id", "Value")
            if self.config_options.rowCount()!=1 and self.config_options.rowCount() >0:
                cont=True
                for j in range(self.config_options.rowCount()-1):  #must have -1 for correct motor configuration for ADRT
                    #print(str(rule))
                    #print(self.config_options.record(j).value("Value"))
                    #print(self.configs)
                    try:
                        if self.config_options.record(j).value("Value") not in self.configs and rule in rules:
                            #print("removing " + str(rule))
                            rulesToRemove.append(rule)   
                    except AttributeError as error:
                        return 
                        #print("No configs defined")
                #print(self.configs)
        for rule in rulesToRemove:
            if rule in rules:
                rules.remove(rule)  
        #print(rules)
        for i in range(len(rules)):
    
            #print(i)
            self.setDBTable(self.actions_app,tblname)
            rule = rules[i]
            self.config_options.setFilter("\"Rule Id\" = " + str(rule) + " AND (Axis LIKE '" + str(self.axis) + "' OR Axis is NULL OR Axis Like 'All')")
            self.config_options.select()
            #print(str(rule))
            #self.printTable("Action Id", "Target")
            #print(self.config_options.rowCount())
            #print(str(self.config_options.record(0).value("Action Id")))
            for j in range(self.config_options.rowCount()):
                self.setDBTable(self.actions_app,tblname)
                self.config_options.setFilter("\"Rule Id\" = " + str(rule) + " AND (Axis LIKE '" + str(self.axis) + "' OR Axis is NULL OR Axis Like 'All')")
                self.config_options.select()
                #print(self.config_options.record(j).value("Action Id"))
                #print(str(j))
                action_id = self.config_options.record(j).value("Action Id") 
                #print(str(action_id))
                action = self.config_options.record(j).value("Operator")
                if action == "Remove" and self.configured is False:
                    self.remove(self.config_options.record(j).value("Value"),tblname)
                elif action == "Remove All Values" and self.configured is False:
                    self.removeExcept(self.config_options.record(j).value("Value"),tblname)
                elif action == "Disable" and self.configured is False:
                    self.disable(self.config_options.record(j).value("Target"),tblname)
                elif action == "Spec Equals":
                    #print("spec equals")
                    self.setSpec(self.config_options.record(j).value("Action Id"),tblname,flag,rule)
                elif action == "Spec Add":
                    #print("spec equals")
                    self.specAdd(self.config_options.record(j).value("Action Id"),tblname,flag,rule)
                #print("check actions")
                #print(self.mtr_spec_vals)
        #return self.motorType
    def store_specs(self):
        if not getattr(sys, 'frozen', False):
            spec_path = dir_path + r"\Temp Files\\" + "specs.txt"  # saves in temp file dir
        else:
            spec_path = pf_path + r"\Temp Files\\" + "specs.txt"  # saves in temp file dir
        if len(self.spec_names)!=0:
            #print(self.spec_names)
            specs_file = open(spec_path, "w",encoding="utf-8")
            i=0
            for i in range(len(self.spec_names)):
                specs_file.write(str(self.spec_names[i])+":" + str(self.spec_vals[i])+" "+str(self.spec_units[i])+"\n")
            specs_file.close()
            
    def getMotor(self):
        self.mtr_rules = []
        self.store_specs()
        #print("in getMotor")
        for i in range(len(self.spec_names)):
            #print(self.spec_names[i])
            #print(self.spec_vals[i])
            if self.spec_names[i] == "Motor" and not self.spec_vals[i] == "":
                #print("found motor")
                self.motor = self.spec_vals[i]
                #print(self.motor)
                motor = self.spec_vals[i].split('(')
                tblname = motor[0].rstrip()
                if not len(motor)==1: 
                    config = motor[1]
                    config = config[:-1]
                else:
                    config =""
                #print(config)
                self.setDBTable(self.specs_app,tblname)
                self.config_options.select()
                for i in range(self.config_options.rowCount()):
                    if not self.config_options.record(i).value("SpecName") in self.mtr_spec_names:
                        self.mtr_spec_dtype.append(self.config_options.record(i).value("DataType"))
                        self.mtr_spec_names.append(self.config_options.record(i).value("SpecName"))
                        if self.mtr_spec_dtype[i] == "decimal" or self.mtr_spec_dtype[i] == "int":
                            if self.config_options.record(i).value("Value") == '':
                                self.mtr_spec_vals.append(float())
                            else:
                                self.mtr_spec_vals.append(float(self.config_options.record(i).value("Value")))
                        else:
                            self.mtr_spec_vals.append(self.config_options.record(i).value("Value"))
                    # if self.mtr_spec_names[i] == "URL":
                        # self.getMotorType(self.mtr_spec_vals[i])
                
                self.setDBTable(self.conditions_app,tblname)
                self.conditions_app = "_Conditions"
                self.setDBTable(self.conditions_app,tblname)
                self.checkEqual()
                self.checkNotEqual()
                self.checkIn()      
                self.config_options.select()
                if not config == "":
                    cfgs = config.split(',')
                    for cfg in cfgs:
                        val = cfg.split(':')
                        self.config_options.setFilter("\"Input Name\" LIKE '" + val[0].strip() + "' AND Value LIKE " + val[1].strip())
                        self.config_options.select()
                        self.mtr_rules.append(self.config_options.record(0).value("Rule Id"))
                    #print(self.mtr_rules)
                    self.conditions_app = "_Conditions"
                    self.setDBTable(self.conditions_app,tblname)
                    self.checkEqual()
                    self.checkNotEqual()
                    self.checkIn()      
                    self.checkActions(tblname,self.mtr_rules,"motor")
        
        return self.motor,self.mtr_spec_names,self.mtr_spec_vals,self.mtr_spec_dtype
     
    def checkRules(self, count,tblname):
        self.setDBTable(self.inputs_app,tblname)
        #print(type(count))
        if type(count) is list:
            self.getParamsPreConfig(count)
        else:
            self.getParams()
        #print(self.configs)
        self.setDBTable(self.specs_app,tblname)
        #self.config_options.setFilter()
        #print(tblname)
        self.config_options.select()
        #self.config_options.setFilter()
        self.config_options.select()
        #self.printTable("SpecName","Value")
        
        for i in range(self.config_options.rowCount()):
            if self.config_options.record(i).value("SpecName") not in self.spec_names:
                self.spec_dtype.append(self.config_options.record(i).value("DataType"))
                self.spec_names.append(self.config_options.record(i).value("SpecName"))
                self.spec_units.append(self.config_options.record(i).value("Units"))
                if self.spec_dtype[i] == "decimal" or self.spec_dtype[i] == "int":
                    #print(self.config_options.record(i).value("Value"))
                    if self.config_options.record(i).value("Value") == ''or self.config_options.record(i).value("Value")=="NA":
                        self.spec_vals.append(float())
                    else:
                        self.spec_vals.append(float(self.config_options.record(i).value("Value")))
                else:
                    self.spec_vals.append(self.config_options.record(i).value("Value"))      
                
        self.conditions_app = "_Conditions"
        self.setDBTable(self.conditions_app,tblname)
        self.checkEqual()
        self.checkNotEqual()
        self.checkIn()      
        self.checkActions(tblname,self.ruleIDS,"stage")
        self.ruleIDS = []
        self.getMotor()
        self.config_options.select()
        #return self.ruleIDS
    def makeConnections(self,count):    
        self.config_boxes[count].currentTextChanged.connect(lambda: self.checkRules(count,self.stage))
        

    def return_values(parent = None,stage = None):
        #stage = self.stage
        #print("return_values")
        stage = stage.rstrip()
        dialog = PopupConfig(parent,stage)
        #print(dialog.configured)
        if dialog.configured is True:
            #print("configured")
            dialog.setVisible(False)
        axes = []
        dialog.stage = stage
        dialog.config_sizer = ConfigSizer()
        dialog.inputs_app = "_Inputs"
        dialog.actions_app = "_Actions"
        dialog.specs_app = "_TemplateSpecs"
        dialog.conditions_app = "_Conditions"
        dialog.ruleIDS = []
        dialog.axis = "All"
        if dialog.configured == False:
            #print("not configured")
            dialog.setDBTable(dialog.inputs_app,dialog.stage)
            # dialog.config_options.select() printTable
            #print(dialog.stage)
            dialog.config_inputs = []
            dialog.config_boxes = [dialog.Config1,dialog.Config2,dialog.Config3,dialog.Config4,dialog.Config5,dialog.Config6,dialog.Config7]
            dialog.config_txts = [dialog.txt_config_1,dialog.txt_config_2,dialog.txt_config_3,dialog.txt_config_4,dialog.txt_config_5,dialog.txt_config_6,dialog.txt_config_7]
            
            for i in range(dialog.config_options.rowCount()):
                dialog.input_name = dialog.config_options.record(i).value("Input Name")
                dialog.value = dialog.config_options.record(i).value("Value")
                if not dialog.input_name in dialog.config_inputs:
                    dialog.config_inputs.append(dialog.input_name)
                 
            if dialog.config_options.rowCount() ==0:
                dialog.setDBTable(dialog.specs_app, dialog.stage)
                dialog.config_options.select()
                # print("no configurations")
                for i in range(dialog.config_options.rowCount()):
                    if dialog.config_options.record(i).value("SpecName") not in dialog.spec_names:
                        dialog.spec_dtype.append(dialog.config_options.record(i).value("DataType"))
                        dialog.spec_names.append(dialog.config_options.record(i).value("SpecName"))
                        if dialog.spec_dtype[i] == "decimal" or dialog.spec_dtype[i] == "int":
                            # print(dialog.config_options.record(i).value("Value"))
                            if dialog.config_options.record(i).value("Value") == '':
                                dialog.spec_vals.append(float())
                            else:
                                dialog.spec_vals.append(float(dialog.config_options.record(i).value("Value")))
                        else:
                            dialog.spec_vals.append(dialog.config_options.record(i).value("Value"))
                    

            count =-1
            dialog.setDBTable(dialog.specs_app, dialog.stage)
            dialog.config_options.setFilter("SpecName LIKE 'NumAxes'")
            dialog.config_options.select()
            #print("num axes " +str(dialog.config_options.record(0).value("Value")))
            if str(dialog.config_options.record(0).value("Value")) == "2.0":
                #print("where I should be")
                dialog.setDBTable(dialog.actions_app,dialog.stage)
                dialog.config_options.setFilter("Target LIKE 'AxisDesc'")
                axes = [dialog.config_options.record(0).value("Value"), dialog.config_options.record(1).value("Value")]
            dialog.setDBTable(dialog.inputs_app, dialog.stage)
            dialog.config_options.select()
            #print(axes)
            for parameter in dialog.config_inputs:
                dialog.config_options.setFilter("\"Input Name\" LIKE '" + parameter + "'")  
                dialog.config_options.select()
                count = count+1 
                dialog.config_boxes[count].setPlaceholderText("Select " + parameter)
                dialog.config_txts[count].setText(parameter)
                dialog.config_boxes[count].addItems(dialog.getElements())
                if count == len(dialog.config_inputs)-1:
                    if len(axes):
                        count = count+1
                        dialog.config_boxes[count].setPlaceholderText("Select Axis")
                        dialog.config_txts[count].setText("Axis")
                        #print(str(axes[0]) + "Axes[1]: " + str(axes[1]))
                        if axes[0] is None: #and not axes[1] == "Lower":
                            #print("first is true")
                            if axes[1] =="Lower":
                                axes[0] = "Upper"
                            else:
                                axes[0] = "Lower"
                        if axes[1] is None: #and not axes[0] == "Upper":
                            #print("second is true")
                            if axes[0] =="Upper":
                                axes[1] = "Lower"
                            else:
                                axes[1] = "Upper"
                        dialog.config_boxes[count].addItems([axes[0],axes[1]])
                        
                        dialog.axis =1
                dialog.makeConnections(count)
                
            
            while count != 6:
                count = count +1
                dialog.config_boxes[count].setVisible(False)
                dialog.config_txts[count].setVisible(False)
        else:
            #print("configured")
            temp = dialog.stage 
            if dialog.stage.endswith("-Lower"):
                #print("true")
                dialog.axis = 1
                temp = dialog.stage.replace("-Lower","")
                #temp = dialog.stage[0:len(dialog.stage)-6]
                #dialog.stage = temp
            if dialog.stage.endswith("-Upper"):
                dialog.axis = 2
                temp = dialog.stage.replace("-Upper","")
                #dialog.stage = temp
            #print(dialog.stage[0:len(dialog.stage)-6])
            #print(temp)
            configs = temp.split("-")
            testAgainst = ["MPS50SL","ECO115SL","ECO165SL","ECO225SL"]
            planarCheck = ["PlanarDL","PlanarDLA","ATS3600","MPS50SV","MPS75SV","ANT95V","ANT130V","CCS130DR"]
            #for config in configs[1:]:
             #   config = "-" + config
            configs[1:] = ["-" + config for config in configs[1:]]
            #print(configs)
            if configs[0].endswith("SL") or configs[0].endswith("SLE") and configs[0] not in testAgainst:
                if configs[0].endswith("SL"):
                    configs[0] = configs[0][:-2]
                    configs.insert(1,"SL")
                elif configs[0].endswith("SLE"):
                    configs[0]= configs[0][:-3]
                    configs.insert(1,"SLE-E1")
            if configs[0] in planarCheck:
                dialog.checkRules(configs[2:],configs[0]+configs[1])
            else:
                #print(str(configs[1:]))
                #print(str(configs[0]))
                dialog.checkRules(configs[1:], configs[0])
          
            dialog.setVisible(False)
       
        #print(dialog.spec_names)
        dialog.motor,dialog.mtr_spec_names,dialog.mtr_spec_vals,dialog.mtr_spec_dtype = dialog.getMotor()
        # for name in dialog.mtr_spec_names:
            # print(name)
        # for val in dialog.mtr_spec_vals:
            # print(val)
        #print(dialog.mtr_spec_names)
        #print("stage = "+ stage)

        result = dialog.exec_()
        dialog.setDBTable(dialog.inputs_app,stage)
        dialog.config_options.select()
        #dialog.printTable("Value Description","Value")
        smart_string = []
        #motor_smart_string = []
        if dialog.configured is False:
            for config in dialog.config_boxes:
                #dialog.config_options.setFilter()
                dialog.config_options.select()
                #dialog.printTable("Value Description", "Value")
                #print("Value Desc: " +str(dialog.config_options.record(0).value("Value Description")))
                #print("row count " +str(dialog.config_options.rowCount()))
                #print(config.currentText())
                if config.currentText() != "":
                    #print("\"Value Description\" LIKE '" + config.currentText().rstrip() + "'")
                    #dialog.printTable("Input Name", "Value")
                    dialog.config_options.setFilter("\"Value Description\" LIKE '" + config.currentText().rstrip() + "'")
                    dialog.config_options.select()
                    #print(dialog.config_options.rowCount())
                    if dialog.config_options.rowCount()!=0:
                        #print(str(dialog.config_options.record(0).value("Value")))
                        smart_string.append(str(dialog.config_options.record(0).value("Value")))
                        dialog.smart_string = smart_string

        #print(smart_string)
        motor_smart_string=""
        stage_config = stage
        for item in smart_string:
            stage_config = stage_config + item
        if dialog.axis == 1 and not stage_config.endswith("-Lower"):
            stage_config = stage_config + "-Lower"
        if dialog.axis == 2 and not stage_config.endswith("-Upper"):
            stage_config = stage_config + "-Upper"
        #print(stage_config)
        configs =[]
        # print(dialog.motor)
        if dialog.motor != "":
            motorConfig= dialog.motor.split(" ",1)
            #print(motorConfig)
            if len(motorConfig) > 1:
                configs = re.findall(r'"(.*?)"', motorConfig[1])
                motor_smart_string = motorConfig[0]
                #print("if")
                #print(configs)
                dialog.setDBTable(dialog.inputs_app,motorConfig[0])
                dialog.config_options.select()
                if motorConfig[0].endswith("_Specs"):
                    motorConfig[0]= motorConfig[0][:-6]
                    #print(motorConfig[0])
                    motor_smart_string=motorConfig[0]
                elif dialog.config_options.rowCount()==0:
                    temp=dialog.motor.split("(",1)   
                    motor_smart_string=temp[0]
                for param in configs:
                    motor_smart_string = motor_smart_string + param
                if configs ==[]:
                    motor_smart_string = motor_smart_string + "-" + motorConfig[1]

                
            else:
                motor_smart_string = motorConfig[0]
            #param_split = motorConfig[1].split(":")
            #for param in param_split:
                
                
                #print(config)
            
        #temp = re.findall('\(([^)]+)', motor_smart_string[1])
        #print(temp)
        #print(dialog.spec_names)
        #print(dialog.spec_vals)
        return motor_smart_string, "", dialog.mtr_spec_names, dialog.mtr_spec_vals, dialog.stage, "", \
            dialog.spec_names, dialog.spec_vals,stage_config
    
class PopupSpecDisplay(QtWidgets.QDialog, popup_spec_display):
    """Opens Spec Display window form"""
    def __init__(self, parent=None):
        QtWidgets.QDialog.__init__(self)
        #self.inertia= str(round(inertia,4))
        self.setupUi(self)        
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)
        '''        else:
            plot_path = pf_path + r"\Temp Files\\" + "print_plot" + date_string + ".png"  # saves in temp file dir'''

    def return_values(parent=None,config=None):
        dialog=PopupSpecDisplay(parent)
        if not getattr(sys, 'frozen', False):
            if config=="stage":
                spec_path = dir_path + r"\Temp Files\\" + "specs.txt"
                read_file=open(spec_path, "r",encoding="utf-8")
            else:
                spec_path = dir_path + r"\Temp Files\\" + "motor_specs.txt" 
                read_file=open(spec_path, "r",encoding="utf-8")
                 # saves in temp file dir
        else:
            if config=="stage":
                spec_path = pf_path + r"\Temp Files\\" + "specs.txt"
                read_file=open(spec_path, "r",encoding="utf-8")
            else:
                spec_path = pf_path + r"\Temp Files\\" + "motor_specs.txt" 
                read_file=open(spec_path, "r",encoding="utf-8")
                 # saves in temp file dir

        # Write the smart string as the first line
        with open(spec_path, "r", encoding="utf-8") as read_file:
            file_content = read_file.readlines()
        
        with open(spec_path, "w", encoding="utf-8") as write_file:
            # Write the smart string followed by the original file content
            write_file.write(dialog.smart_string + "\n")
            write_file.writelines(file_content)
        
        specs=[dialog.Spec_01,dialog.Spec_02,dialog.Spec_03,dialog.Spec_04,dialog.Spec_05,dialog.Spec_06,dialog.Spec_07,dialog.Spec_08,dialog.Spec_09,dialog.Spec_10,\
        dialog.Spec_11,dialog.Spec_12,dialog.Spec_13,dialog.Spec_14,dialog.Spec_15,dialog.Spec_16,dialog.Spec_17,dialog.Spec_18,dialog.Spec_19,dialog.Spec_20,dialog.Spec_21,dialog.Spec_22,\
        dialog.Spec_23,dialog.Spec_24,dialog.Spec_25,dialog.Spec_26,dialog.Spec_27,dialog.Spec_28,dialog.Spec_29,dialog.Spec_30,dialog.Spec_31,dialog.Spec_32,dialog.Spec_33,dialog.Spec_34]
        vals=[dialog.Value_01,dialog.Value_02,dialog.Value_03,dialog.Value_04,dialog.Value_05,dialog.Value_06,dialog.Value_07,dialog.Value_08,dialog.Value_09,dialog.Value_10,\
        dialog.Value_11,dialog.Value_12,dialog.Value_13,dialog.Value_14,dialog.Value_15,dialog.Value_16,dialog.Value_17,dialog.Value_18,dialog.Value_19,dialog.Value_20,dialog.Value_21,dialog.Value_22,\
        dialog.Value_23,dialog.Value_24,dialog.Value_25,dialog.Value_26,dialog.Value_27,dialog.Value_28,dialog.Value_29,dialog.Value_30,dialog.Value_31,dialog.Value_32,dialog.Value_33,dialog.Value_34]
        units=[dialog.Unit_01,dialog.Unit_02,dialog.Unit_03,dialog.Unit_04,dialog.Unit_05,dialog.Unit_06,dialog.Unit_07,dialog.Unit_08,dialog.Unit_09,dialog.Unit_10,\
        dialog.Unit_11,dialog.Unit_12,dialog.Unit_13,dialog.Unit_14,dialog.Unit_15,dialog.Unit_16,dialog.Unit_17,dialog.Unit_18,dialog.Unit_19,dialog.Unit_20,dialog.Unit_21,dialog.Unit_22,\
        dialog.Unit_23,dialog.Unit_24,dialog.Unit_25,dialog.Unit_26,dialog.Unit_27,dialog.Unit_28,dialog.Unit_29,dialog.Unit_30,dialog.Unit_31,dialog.Unit_32,dialog.Unit_33,dialog.Unit_34]
        i=0
        while True:
            line = read_file.readline()
            if not line:
                break
            line=line.split("**")
            
            specs[i].setText(line[0])
            #if line[1]:
            vals[i].setText(line[1])
            
            #elif line[2]:
            units[i].setText(line[2])
            i=i+1
        while i<34:
            specs[i].setVisible(False)
            vals[i].setVisible(False)
            units[i].setVisible(False)
            i=i+1
        result=dialog.exec_()
        return result

        
 # def accept(self):
        # self.return_values(self,inertia=self.inertia,completed=True)
    # def reject(self):
        # self.return_values(self,inertia="",completed=True)

class MplCanvas(Canvas):
    def __init__(self):
        """Creates Canvas object for matplotlib plots to reside in."""
        from matplotlib.figure import Figure  # local import to reduce startup time
        screen_size = QtWidgets.QDesktopWidget.availableGeometry(QtWidgets.QApplication.desktop())
        w_scale = float(screen_size.width()) / 1920  # normalize by the 1920x1080 screen the form was designed on.
        h_scale = float(screen_size.height()) / 1080
        # if not w_scale == 1:
        #     w_scale = .75*w_scale
        # if not h_scale >= .9:
        #     h_scale = .75*h_scale
        self.fig = Figure(figsize=(6.75*w_scale, 3.75*h_scale))  # empirically chosen scale factors (same below)
        self.ax = self.fig.add_subplot(311)
        self.ax.set_xticklabels(labels=self.ax.get_xticklabels(), visible=False)
        self.ax.set_xticks([])
        self.ax.spines['right'].set_visible(False)
        self.ax.spines['top'].set_visible(False)
        # self.ax.spines['left'].set_color((.8, .8, .8))
        self.ax.spines['bottom'].set_visible(False)
        self.ax2 = self.fig.add_subplot(312)
        self.ax2.set_xticklabels(labels=self.ax.get_xticklabels(), visible=False)
        self.ax2.set_xticks([])
        self.ax2.spines['right'].set_visible(False)
        self.ax2.spines['top'].set_visible(False)
        # self.ax2.spines['left'].set_color((.8, .8, .8))
        self.ax2.spines['bottom'].set_visible(False)
        self.ax3 = self.fig.add_subplot(313)
        self.ax3.spines['right'].set_visible(False)
        self.ax3.spines['top'].set_visible(False)
        # self.ax3.spines['left'].set_color((.8, .8, .8))
        self.fig.subplots_adjust(hspace=0.25 / (h_scale * 1.25), left=0.13 * (1920 / screen_size.width()), right=.975, top=.975)
        self.fig.align_ylabels(axs=[self.ax, self.ax2, self.ax3])
        Canvas.__init__(self, self.fig)
        Canvas.setSizePolicy(self, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        Canvas.updateGeometry(self)


class MplWidget(QtWidgets.QWidget):
    """Creates matplotlib widget."""
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)
        self.canvas = MplCanvas()
        self.vbl = QtWidgets.QVBoxLayout()
        self.vbl.addWidget(self.canvas)
        self.setLayout(self.vbl)

class App(QtWidgets.QMainWindow):
    """Main Window"""
    def __init__(self):
    
        """Initialize all UI elements, mostly linking buttons to functions and tables to sources."""
        super(App, self).__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self.configured = False
        # comment the 3 lines below if running out of IDE
        icon = QtGui.QIcon()
        icon.addPixmap(QtGui.QPixmap(resource_path("amszr.png")), QtGui.QIcon.Normal, QtGui.QIcon.Off)
        self.setWindowIcon(icon)

       
        self.ui.actionNew.triggered.connect(self.new)
        self.ui.actionOpen.triggered.connect(self.open)
        self.ui.actionSave.triggered.connect(self.save)
        self.ui.actionSave_As.triggered.connect(self.saveAs)
        self.ui.actionPrint.triggered.connect(self.print)
        self.ui.actionExit.triggered.connect(self.close)
        self.ui.actionInertia_Calculator.triggered.connect(self.show_inertia_calc)
       # self.ui.actionPayload_Calculator.triggered.connect(self.show_payload_calc)
        self.ui.actionSpecs_Display.triggered.connect(lambda: self.show_spec_display(config="stage"))
        self.ui.actionDisplay_Motor_Specs.triggered.connect(lambda: self.show_spec_display(config="motor"))
        
        self.ui.btn_current_limitation_browser.setVisible(False)
        self.ui.btn_current_limitation_browser.clicked.connect(self.show_current_limitation_browser)

        self.ui.btn_add_dwell.clicked.connect(self.show_dwell_dialog)
        self.ui.btn_add_decel_to_zero.clicked.connect(self.show_decel_to_zero_dialog)
        self.ui.btn_add_accel.clicked.connect(self.show_accel_decel_dialog)
        self.ui.btn_add_constant_velocity.clicked.connect(self.show_constant_velocity_dialog)
        self.ui.btn_add_point_to_point.clicked.connect(self.show_point_to_point_dialog)
        self.ui.btn_add_config_window.clicked.connect(lambda: self.show_popup_config_dialog(config="stage"))
        self.ui.btn_add_motor_config_window.clicked.connect(lambda: self.show_popup_config_dialog(config ="motor"))

        self.ui.btn_motion_up.clicked.connect(lambda: self.move_profile(direction="up"))
        self.ui.btn_motion_down.clicked.connect(lambda: self.move_profile(direction="down"))
        self.ui.btn_motion_delete.clicked.connect(self.delete_profile)
        self.ui.btn_motion_edit.clicked.connect(self.edit_profile)
        self.ui.btn_motion_brake.clicked.connect(self.brake_profile)
        
        text_file = open(resource_path("Products.txt"), "r")
        names = text_file.readlines()
        completer = QCompleter(names)
        completer.setCaseSensitivity(0)
        self.ui.stage_config_input.setCompleter(completer)
        stage = self.ui.stage_config_input.text()
        text_file.close()
        
        text_file = open(resource_path("Motors.txt"), "r")
        motor_names = text_file.readlines()
        MotorCompleter = QCompleter(motor_names)
        MotorCompleter.setCaseSensitivity(0)
        self.ui.motor_name.setCompleter(MotorCompleter)
        motor = self.ui.motor_name.text()

        self.plotWidget = MplWidget(self.ui.widget_plot)
        screen_size = QtWidgets.QDesktopWidget.screenGeometry(QtWidgets.QApplication.desktop())

        # scale factors below chosen empirically to optimize for both 1920x1080 and 1024x768 resolutions
        if screen_size.width() >= 1900 and screen_size.height() >= 1000:
            self.plotWidget.setMinimumWidth(int(float(screen_size.width()) * .45))
            self.plotWidget.setMinimumHeight(int(float(screen_size.height()) * .45))
            self.ui.widget_plot.setMinimumWidth(int(float(screen_size.width()) * .45))
            self.ui.widget_plot.setMinimumHeight(int(float(screen_size.height()) * .45))
        else:
            self.plotWidget.setMinimumWidth(int(float(screen_size.width()) * .4))
            self.plotWidget.setMinimumHeight(int(float(screen_size.height()) * .4))
            self.ui.widget_plot.setMinimumWidth(int(float(screen_size.width()) * .4))
            self.ui.widget_plot.setMinimumHeight(int(float(screen_size.height()) * .4))
        MplWidget.updateGeometry(self.ui.widget_plot)
        self.refresh_plot()

        self.db = Database()
        self.model = Model(self)
        self.ui.list_motion.setModel(self.model)
        self.ui.list_motion.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.ui.list_motion.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.ui.list_motion.setColumnWidth(0, 60)
        self.ui.list_motion.setColumnWidth(1, 100)
        self.ui.list_motion.setColumnWidth(2, int(680*(screen_size.width()/1920)))
        self.ui.list_motion.selectRow(0)  # select first row by default to help avoid errors.

        self.db_sizer = DatabaseSizer()
        self.stage_type = self.ui.txt_stage_type.text()
        # self.model_stages = QtSql.QSqlTableModel(self, db=self.db_sizer.data)
        # self.model_stages.setTable("Stages")
        # self.model_stages.setFilter("Name NOT LIKE 'Units' ORDER BY Name ASC")
        # self.model_stages.select()
        # self.ui.cmb_stage_select.setModel(self.model_stages)
        # self.ui.cmb_stage_select.setModelColumn(0)
        
        

        # self.model_motors = QtSql.QSqlTableModel(self, db=self.db_sizer.data)
        # self.model_motors.setTable("Motors")
        # self.model_motors.setFilter("Name NOT LIKE 'Units' ORDER BY Name ASC")
        # self.model_motors.select()
        #self.ui.cmb_motor_select.setModel(self.model_motors)
        #self.ui.cmb_motor_select.setCurrentText(self.show_popup_config_dialog.motor)

        self.model_drives = QtSql.QSqlTableModel(self, db=self.db_sizer.data)
        self.model_drives.setTable("Drives")
        self.model_drives.select()
        self.ui.cmb_drive_select.setModel(self.model_drives)
        self.ui.cmb_drive_select.setModelColumn(1)

        self.model_bus_voltage = QtSql.QSqlTableModel(self, db=self.db_sizer.data)
        self.model_bus_voltage.setTable("BusVoltages")

        #self.ui.stage_config_input.editingFinished.connect(self.on_stage_change)
        #self.ui.motor_name.editingFinished.connect(lambda: self.on_motor_change(motor=self.ui.motor_name.text()))
        self.ui.cmb_drive_select.currentTextChanged.connect(self.on_drive_change)
        self.ui.cmb_select_bus_voltage.currentTextChanged.connect(self.on_bus_change)
        self.ui.cmb_vacuum.currentTextChanged.connect(self.calc_results)
        self.ui.cmb_input_voltage.currentTextChanged.connect(self.calc_results)
        self.ui.cmb_aircooling.currentTextChanged.connect(self.calc_results)

        self.ui.txt_payload.editingFinished.connect(self.calc_results)
        self.ui.txt_ambient_temperature.editingFinished.connect(self.calc_results)
        self.ui.txt_orientation.editingFinished.connect(self.calc_results)
        
       # count =0
        #print(self.ui.stage_config_input.text())
        #self.on_stage_change()
        #self.on_motor_change(self.ui.motor_name.text())
        self.on_drive_change(self.ui.cmb_drive_select.currentText())
        self.ui.stage_config_input.setFocus()
        self.set_units()
        #self.bus_voltage_visible()

        sys._excepthook = sys.excepthook

        def exception_hook(exctype, value, traceback):
            print(exctype, value, traceback)
            sys._excepthook(exctype, value, traceback)
            sys.exit(1)

        sys.excepthook = exception_hook
        
        # if below detects if app was launched from save file (sys.argv is length 1 if launched from .exe) and opens it.
        if len(sys.argv) >= 2:
            # msg = QtWidgets.QMessageBox()
            # disp = ' '.join(sys.argv[1:])
            # self.open(path=sys.argv[1])
            self.open(path=' '.join(sys.argv[1:]))
    
    def readProducts(self):
        #print("reading products")
        text_file = open(resource_path("Linear Motor.txt"), "r")
        self.linear_motors = text_file.read().splitlines()
        text_file.close()
        text_file = open(resource_path("Linear Stage_Direct-Drive.txt"), "r")
        self.dd_linear_stages = text_file.read().splitlines()
        text_file.close()
        text_file = open(resource_path("Linear Stage_Screw-Drive.txt"), "r")
        self.sd_linear_stages = text_file.read().splitlines()
        text_file.close()
        text_file = open(resource_path("Rotary Motor.txt"), "r")
        self.rotary_motors = text_file.read().splitlines()
        text_file.close()
        text_file = open(resource_path("Rotary Stage_Direct-Drive.txt"), "r")
        self.dd_rotary_stages = text_file.read().splitlines()
        text_file.close()
        text_file = open(resource_path("Rotary Stage_Gear-Drive.txt"), "r")
        self.gd_rotary_stages = text_file.read().splitlines()
        text_file.close()
    
    def getStageType(self,stage):
        #print(self.stage)
        stageType = ""
      
        stage = stage.rstrip()
        # temp = stage
        # while temp not in (self.dd_linear_stages or self.dd_rotary_stages or self.sd_linear_stages or self.gd_rotary_stages):
            # temp = temp[:-1]
        #print("stage = " + stage)
        #print(self.dd_linear_stages)
        if stage in self.dd_linear_stages:
            stageType = "dd_linear"
        elif stage in self.sd_linear_stages:
            stageType = "sd_linear"
        elif stage in self.dd_rotary_stages:
            stageType = "dd_rotary"
        elif stage in self.gd_rotary_stages:
            stageType = "gd_rotary"
        #print("stage type = " + stageType)
        return stageType
    
    def getMotorType(self,motor):
    
        #print("self.motor in get motor type: " + self.motor)
        #print("motor in get motor type: " + motor)
        # motor =motor.split("-")
        # motor = motor[0].rstrip()
        motorType = ""
        if motor in self.rotary_motors:
            motorType = "Rotary"
        elif motor in self.linear_motors:
            motorType = "Linear"
        #print(motorType)
        return motorType
    
    
    def calc_results_sd_linear(self):
        import re  # moved local to reduce startup time
        import pandas as pd  # moved local to reduce startup time
        #v_nonzero = np.array(v)
        v_nonzero = np.round(v, 4) #Kevin added to fix order of operation bug
        v_nonzero[v_nonzero != 0] = 1
        '''if round(v_nonzero[-1]-0.0001, 1) != 0:
            v_nonzero[v_nonzero != 0] = 1
        else:
            v_nonzero[v_nonzero != 0] = 0'''
        if not self.ui.txt_payload.text():
            payload = 0
        else:
            payload = float(self.ui.txt_payload.text())
        #screw_lead = float(self.ui.txt_screw_lead.text())  # m
        #screw_diameter = float(self.ui.txt_screw_diameter.text())  # m
        #screw_length = float(self.ui.txt_screw_length.text())  # m
        if not self.ui.txt_orientation.text():
            incline_angle = 0
        else:
            incline_angle = np.radians(float(self.ui.txt_orientation.text()))  # rad
        moving_mass = float(self.ui.stage_param_txt_1.text())
        screw_lead = float(self.ui.stage_param_txt_5.text())
        bearing_friction = float(self.ui.stage_param_txt_2.text())  # N
        foldback_friction = float(self.ui.stage_param_txt_6.text())
        screw_friction = float(self.ui.stage_param_txt_3.text())*v_nonzero  # N*m
        motor_inertia = float(self.ui.motor_param_txt_1.text())  # kg*m^2
        torque_constant = float(self.ui.motor_param_txt_2.text())  # N*m/Apk
        resistance = float(self.ui.motor_param_txt_5.text())  # Ohm
        inductance = float(self.ui.motor_param_txt_6.text())  # H
        bemf = float(self.ui.motor_param_txt_4.text())  # Vpk/krpm
        number_of_poles = int(self.ui.motor_param_txt_8.text())
        if not self.ui.txt_ambient_temperature.text():
            ambient_temperature = 20
        else:
            ambient_temperature = float(self.ui.txt_ambient_temperature.text())  # C
        thermal_resistance = float(self.ui.motor_param_txt_7.text())  # C/W
        if self.ui.cmb_vacuum.currentText() == "Yes":
            thermal_resistance = thermal_resistance*8

        con = lite.connect(db_filepath)
        with con:
            cur = con.cursor()
            motor = self.ui.motor_name.text().split("-")
            # if "Winding Designation" in motor[1]:
                # print(motor[1])
            ####Will need to generate motor db for rated speed, and power output
                # motor = motor[0] + motor[1][:2] 
            #print(motor)
            cur.execute("SELECT * FROM Motors WHERE Name='%s'" % motor[0].rstrip())
            motor_record = cur.fetchone()
            if motor_record==None:
                motor_string=motor[0]+"-" + motor[1]
                cur.execute("SELECT * FROM Motors WHERE Name='%s'" % motor_string.rstrip())
                motor_record=cur.fetchone()
            if not motor_record==None:
                self.rated_speed = motor_record[33]
                self.brake_holding_torque = motor_record[36]
                if self.rated_speed:
                    self.rated_speed = float(self.rated_speed)
                self.rated_power_output = motor_record[34]
                if self.rated_power_output:
                    self.rated_power_output = float(self.rated_power_output)
                self.gear_ratio = motor_record[35]
                if self.gear_ratio:
                    self.gear_ratio = int(self.gear_ratio)
                else:
                    self.gear_ratio = 1
                if self.brake_holding_torque:
                    self.brake_holding_torque = float(self.brake_holding_torque)
            else:
                self.gear_ratio=1

        load_inertia = (moving_mass+payload)*(screw_lead/(2*np.pi))**2  # kg*m^2
        screw_inertia = float(self.ui.stage_param_txt_4.text())#(7700*np.pi*screw_diameter**4*screw_length)/32  # kg*m^2
        reflected_inertia = (load_inertia+screw_inertia)/(0.9*self.gear_ratio)+motor_inertia  # kg*m^2
        load_torque = ((np.sin(incline_angle) * (moving_mass + payload) * 9.81 * screw_lead) /
                       (2 * np.pi))*np.ones_like(v)  # N*m
        bearing_friction_torque = (bearing_friction + .0015 * np.cos(incline_angle) * (moving_mass + payload) * 9.81) \
            * (screw_lead / (2 * np.pi))*v_nonzero
        total_static_reflected_torque = (load_torque+bearing_friction_torque+screw_friction)/(0.9*self.gear_ratio)  # N*m
        torque = total_static_reflected_torque + (reflected_inertia*2*np.pi*np.array(a))/(screw_lead*1000) + foldback_friction  # N*m
       
        # this bit shifts the torque required closer to zero by the holding torque for all portions of the torque
        # array during which the brake is on.
        if 1 in b:
            torque_sign = np.sign(torque)
            torque = abs(torque)-np.array(b)*self.brake_holding_torque
            torque[torque < 0] = 0
            torque = torque*torque_sign
        '''        
        print("---------------------------------------------------------")
        print("load_inertia =" +str(load_inertia))
        print("screw_inertia =" +str(screw_inertia))
        print("reflected_inertia =" + str(reflected_inertia))
        print("load_torque =" + str(load_torque))
        print("bearing friction_torque =" +str(bearing_friction_torque))
        print("total_static_reflected_torque =" +str(total_static_reflected_torque))
        print("torque =" + str(torque)) 
        print("Brake Holding torque =" + str(self.brake_holding_torque))
        print("v nonzero =" + str(v_nonzero))
        '''
        self.peak_torque = np.max(abs(torque))  # N*m
        self.rms_torque = np.sqrt((1/t[-1])*np.trapz(torque**2, t, .0001))  # N*m
        self.peak_motor_speed = np.max(abs(np.array(v))/1000)/screw_lead*360/self.gear_ratio  # deg/sec
        self.sto_decel = self.peak_motor_speed/.450*(np.pi/180)  # rad/sec^2 - hard coded 450 msec decel for STO
        self.sto_torque = np.max(total_static_reflected_torque) + reflected_inertia*self.sto_decel  # N*m
        self.sto_current = self.sto_torque/torque_constant  # A
        self.peak_current = self.peak_torque/torque_constant  # A
        self.rms_current = self.rms_torque/torque_constant  # A
        #self.peak_power_output = self.peak_current**2*resistance  # W
        #-------------------------Kevin added---------------
        try:
            con = lite.connect(db_filepath)
            with con:
                cur = con.cursor()
                cur.execute("SELECT * FROM Drives WHERE Name='%s'" % self.ui.cmb_drive_select.currentText())
                drive_record = cur.fetchone()
                bus_voltage = None
                if drive_record[2] == "PWM":
                    #self.rated_power_output = self.peak_torque * self.peak_motor_speed/1000
                    self.peak_power_output1 = torque_constant  * self.rms_current * self.peak_motor_speed/1000  #calculate power output
                    #print(str(resistance))
                    #print("speed is" + str(self.peak_motor_speed/1000))
                    #print("force constant is " + str(ForceConst))
                    self.rated_power_loss = 3/2 * self.rms_current**2 * resistance
                    self.peak_power_output = self.peak_power_output1 + self.rated_power_loss #Formula based on HWMAN-2141 input power, no need to divide efficiency because we're interested in how much power the motor draws
                    
                else: #calculate linear amplifier case
                    if drive_record[5]:
                        input_voltage_text = self.ui.cmb_input_voltage.currentText()
                        input_voltage_text_clean = re.sub('[^\d]', '', input_voltage_text)
                        if "+/-" in input_voltage_text:
                            input_voltage = int(input_voltage_text_clean)*2
                        else:
                            input_voltage = int(input_voltage_text_clean)
                        bus_voltage = float(drive_record[5])*input_voltage
                    elif drive_record[6]:
                        bus_voltage_text = drive_record[6]
                        bus_voltage = self.convert_bus_voltage_text(bus_voltage_text)
                    elif drive_record[7]:
                        special_text = drive_record[7]
                        if not self.ui.cmb_select_bus_voltage.currentText() == "--Select--"\
                                and not self.ui.cmb_select_bus_voltage.currentText() == "1"\
                                and self.ui.cmb_select_bus_voltage.currentText():
                            cur.execute("SELECT %s FROM BusVoltages WHERE %s='%s'" %
                                        ((str(special_text) + "Bus"), str(special_text),
                                         self.ui.cmb_select_bus_voltage.currentText()))
                            bus_voltage_text = cur.fetchone()[0]
                            bus_voltage = self.convert_bus_voltage_text(bus_voltage_text)
                    self.peak_power_output = self.rms_current * int(bus_voltage)
        
        #--------------------------------------------------
            self.rms_power_output = 3/2 * self.rms_current**2 * resistance # W Kevin added *3/2 for three phase motors
            self.bus_voltage_required = ((bemf*self.peak_motor_speed/6000)+self.peak_current
                                    * np.sqrt(resistance**2
                                              + (2*np.pi*(self.peak_motor_speed/360)*(number_of_poles/2)*inductance)**2))/0.866
            self.final_coil_temperature = thermal_resistance*self.rms_power_output + ambient_temperature  # C

            n = int(4/.00001)
            torque_squared = np.power(torque, 2)
            df = pd.DataFrame(torque_squared, pd.to_timedelta(t, unit='second'))  # time indexes torque_squared
            df = df.resample('100U').bfill()  # upsamples df to 100 microsecond - uses bfill to replace NaNs
            if t[-1]/.00001 > n:
                rm = df.rolling('4s').mean()
                self.rolling_torque = np.sqrt(rm.values)
            else:
                self.rolling_torque = self.rms_torque

            self.max_rolling_rms_current = np.nanmax(self.rolling_torque)/torque_constant  # A
            round_v = np.round(v, 2)
            round_v[round_v != 0] = 1
            # this line retrieves each point in round_v that transitions from 1 to 0 or 0 to 1
            v_transitions = np.argwhere(np.diff(round_v)).squeeze() / 100000
            if type(v_transitions) == np.float64:  # if only 1 transition, type is float - this fixes that
                if round_v[-1] == 1:
                    v_transitions = np.array([v_transitions, (len(t)-1) / 100000])
                else:
                    v_transitions = np.array([0, v_transitions])
            if not len(v_transitions) % 2 == 0:  # if odd # transitions, adds final t as last transition
                v_transitions = np.append(v_transitions, (len(t)-1) / 100000)
            v_transitions = v_transitions.reshape(-1, 2)
            vel_time = 0
            for start, stop in v_transitions:
                vel_time += (t[int(stop*100000)]-t[int(start*100000)])
            
            self.duty_cycle = round((vel_time/t[-1]*100), 1)

            self.ui.txt_peak_torque_required.setText(str(round(self.peak_torque, 2)) + " N*m")
            self.ui.txt_rms_torque.setText(str(round(self.rms_torque, 2)) + " N*m")
            self.ui.txt_peak_motor_speed.setText(str(round(self.peak_motor_speed, 0)) + " deg/sec")
            self.ui.txt_peak_power_output.setText(str(round(self.peak_power_output, 2)) + " W")
            self.ui.txt_rms_power_output.setText(str(round(self.rms_power_output, 2)) + " W")
            self.ui.txt_bus_voltage_required.setText(str(round(self.bus_voltage_required, 2)) + " V")
            self.ui.txt_peak_current_required.setText(str(round(self.peak_current, 2)) + " A")
            self.ui.txt_rms_current_required.setText(str(round(self.rms_current, 2)) + " A")
            self.ui.txt_final_coil_temperature.setText(str(round(self.final_coil_temperature, 2)) + " C")
            self.ui.txt_rolling_rms_current.setText(str(round(self.max_rolling_rms_current, 2)) + " A")
            self.ui.txt_duty_cycle.setText(str(self.duty_cycle) + "%")
            self.ui.txt_sto_current.setText(str(round(self.sto_current, 2)) + " A")
            
        except:
            msg = QtWidgets.QMessageBox()
            msg.setText("Check drive configuration.")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setWindowTitle("Error")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
            return    
  

    def calc_results_dd_linear(self):
        import re  # moved local to reduce startup time
        import pandas as pd  # moved local to reduce startup time
        v_nonzero = np.array(v)
        v_nonzero[v_nonzero != 0] = 1
        if not self.ui.txt_payload.text():
            payload = 0
        else:
            payload = float(self.ui.txt_payload.text())
        #screw_lead = float(self.ui.txt_screw_lead.text())  # m
        #screw_diameter = float(self.ui.txt_screw_diameter.text())  # m
        #screw_length = float(self.ui.txt_screw_length.text())  # m
        if not self.ui.txt_orientation.text():
            incline_angle = 0
        else:
            incline_angle = np.radians(float(self.ui.txt_orientation.text()))  # rad
        moving_mass = float(self.ui.stage_param_txt_1.text())
        #screw_lead = float(self.ui.stage_param_txt_5.text())
        bearing_friction = float(self.ui.stage_param_txt_2.text())  # N
        #screw_friction = float(self.ui.stage_param_txt_3.text())*v_nonzero  # N*m
        WedgeRatio = float(self.ui.stage_param_txt_3.text())
        
        MotorDerate = float(self.ui.stage_param_txt_4.text())
        NumMotors = float(self.ui.stage_param_txt_5.text())
        #print(self.ui.motor_param_txt_1.text())
        ForceConst = float(self.ui.motor_param_txt_1.text())  # kg*m^2
        MotorConst = float(self.ui.motor_param_txt_2.text())  # N*m/Apk
        bemf = float(self.ui.motor_param_txt_3.text())
        # = float(self.ui.motor_param_txt_8.text())  # Ohm
        CoilMass = float(self.ui.motor_param_txt_6.text())  # H
        resistance = float(self.ui.motor_param_txt_4.text())  # Ohm  Kevin changed to *, before was /NumMotors
        max_temp = float(self.ui.motor_param_txt_8.text())
        
       # number_of_poles = int(self.ui.motor_param_txt_8.text())
        if not self.ui.txt_ambient_temperature.text():
            ambient_temperature = 20
        else:
            ambient_temperature = float(self.ui.txt_ambient_temperature.text())  # C
        thermal_resistance = float(self.ui.motor_param_txt_5.text())  # C/W
        if self.ui.cmb_vacuum.currentText() == "Yes":
            thermal_resistance = thermal_resistance*4

        # con = lite.connect(db_filepath)
        # with con:
            # cur = con.cursor()
            # motor = self.ui.motor_name.text().split("(")
            # if "Winding Designation" in motor[1]:
               # print(motor[1])
            # Will need to generate motor db for rated speed, and power output
                # motor = motor[0] + motor[1][:2] 
           # print(motor)
            # cur.execute("SELECT * FROM Motors WHERE Name='%s'" % motor[0].rstrip())
            # motor_record = cur.fetchone()
            # self.rated_speed = motor_record[33]
            # self.brake_holding_torque = motor_record[36]
            # if self.rated_speed:
                # self.rated_speed = float(self.rated_speed)
            # self.rated_power_output = motor_record[34]
            # if self.rated_power_output:
                # self.rated_power_output = float(self.rated_power_output)
            # self.gear_ratio = motor_record[35]
            # if self.gear_ratio:
                # self.gear_ratio = int(self.gear_ratio)
            # else:
                # self.gear_ratio = 1
            # if self.brake_holding_torque:
                # self.brake_holding_torque = float(self.brake_holding_torque)
        self.rated_speed = 1
        self.brake_holding_torque = 1
        self.rated_power_output = 1
        self.rated_peak_torque =1 

        load_inertia = (moving_mass+payload+CoilMass)#*(screw_lead/(2*np.pi))**2  # kg*m^2
        #screw_inertia = float(self.ui.stage_param_txt_4.text())#(7700*np.pi*screw_diameter**4*screw_length)/32  # kg*m^2
        #reflected_inertia = (load_inertia+screw_inertia)/(0.9*self.gear_ratio)+motor_inertia  # kg*m^2
        #load_torque = (np.sin(incline_angle) * (moving_mass + payload) * 9.81)# \
                      # *np.ones_like(v)  # N
        #bearing_friction_torque = (bearing_friction + .0015 * np.cos(incline_angle) * (moving_mass + payload) * 9.81) \
        #    * v_nonzero
        incline_force = np.sin(incline_angle) * load_inertia * 9.81
        #print(incline_force)
        total_static_reflected_torque = (incline_force + bearing_friction)  # N*m
        #print(total_static_reflected_torque)
        torque = total_static_reflected_torque + (load_inertia*np.array(a)/1000)  # N*m
        # for element in a:
            # print(element)
        #print(torque)
        '''
        print("------------------------------------------------------------")
        print("load_inertia =" +str(load_inertia))
        print("incline force =" +str(incline_force))
        # print("screw_inertia =" +str(screw_inertia))
        # print("reflected_inertia =" + str(reflected_inertia))
        # print("load_torque =" + str(load_torque))
        # print("bearing friction_torque =" +str(bearing_friction_torque))
        print("total_static_reflected_torque =" +str(total_static_reflected_torque))
        print("torque =" + str(torque)) 
        '''
        # this bit shifts the torque required closer to zero by the holding torque for all portions of the torque
        # array during which the brake is on.
        # if 1 in b:
            # torque_sign = np.sign(torque)
            # torque = abs(torque)-np.array(b)*self.brake_holding_torque
            # torque[torque < 0] = 0
            # torque = torque*torque_sign
        self.peak_torque = np.max(abs(torque))  # N*m
        self.rms_torque = np.sqrt((1/t[-1])*np.trapz(torque**2, t, .0001))  # N*m
        #print(np.max(abs(np.array(v))))
        self.peak_motor_speed = np.max(abs(np.array(v)))  # deg/sec
        self.sto_decel = self.peak_motor_speed/.450*(np.pi/180)  # rad/sec^2 - hard coded 450 msec decel for STO
        self.sto_torque = np.max(total_static_reflected_torque) + self.sto_decel  # N*m
        self.sto_current = self.sto_torque/ForceConst  # A
        self.peak_current = self.peak_torque/ForceConst  # A
        self.rms_current = self.rms_torque/ForceConst  # A
        #self.peak_power_output = self.peak_current**2*resistance  # W
        #-------------------------Kevin added---------------
        try:
            con = lite.connect(db_filepath)
            with con:
                cur = con.cursor()
                cur.execute("SELECT * FROM Drives WHERE Name='%s'" % self.ui.cmb_drive_select.currentText())
                drive_record = cur.fetchone()
                bus_voltage = None
                if drive_record[2] == "PWM":
                    #self.rated_power_output = self.peak_torque * self.peak_motor_speed/1000
                    self.peak_power_output1 = ForceConst  * self.rms_current * self.peak_motor_speed/1000  #calculate power output
                    print(str(resistance))
                    #print("speed is" + str(self.peak_motor_speed/1000))
                    #print("force constant is " + str(ForceConst))
                    self.rated_power_loss = 3/2 * self.rms_current**2 * resistance
                    #print("power loss is " + str(self.rated_power_loss))
                    #print("rms current is " + str(self.rms_current))
                    #print("resistance is " + str(resistance))
                    self.peak_power_output = self.peak_power_output1 + self.rated_power_loss  #Formula based on HWMAN-2141 input power no need to divide efficiency because we're interested in how much power the motor draws
                    
                else: #calculate linear amplifier case
                    if drive_record[5]:
                        input_voltage_text = self.ui.cmb_input_voltage.currentText()
                        input_voltage_text_clean = re.sub('[^\d]', '', input_voltage_text)
                        if "+/-" in input_voltage_text:
                            input_voltage = int(input_voltage_text_clean)*2
                        else:
                            input_voltage = int(input_voltage_text_clean)
                        bus_voltage = float(drive_record[5])*input_voltage
                    elif drive_record[6]:
                        bus_voltage_text = drive_record[6]
                        bus_voltage = self.convert_bus_voltage_text(bus_voltage_text)
                    elif drive_record[7]:
                        special_text = drive_record[7]
                        if not self.ui.cmb_select_bus_voltage.currentText() == "--Select--"\
                                and not self.ui.cmb_select_bus_voltage.currentText() == "1"\
                                and self.ui.cmb_select_bus_voltage.currentText():
                            cur.execute("SELECT %s FROM BusVoltages WHERE %s='%s'" %
                                        ((str(special_text) + "Bus"), str(special_text),
                                         self.ui.cmb_select_bus_voltage.currentText()))
                            bus_voltage_text = cur.fetchone()[0]
                            bus_voltage = self.convert_bus_voltage_text(bus_voltage_text)
                    self.peak_power_output = self.rms_current * int(bus_voltage)
        
        #--------------------------------------------------
            self.rms_power_output = 3/2 * self.rms_current**2 * resistance  # W Kevin added 3/2*
            self.bus_voltage_required = ((bemf*self.peak_motor_speed/1000)+self.peak_current * resistance)
            #self.peak_power_output = self.peak_current*self.bus_voltage_required  # W Kevin added
            #print("thermal resistance: " + str(thermal_resistance) + "\nrms_power_output: " +str(self.rms_power_output) + "\nambient_temp" + str(ambient_temperature))
            self.final_coil_temperature = thermal_resistance*self.rms_power_output + ambient_temperature  # C
            
            n = int(4/.00001)
            torque_squared = np.power(torque, 2)
            df = pd.DataFrame(torque_squared, pd.to_timedelta(t, unit='second'))  # time indexes torque_squared
            df = df.resample('100U').bfill()  # upsamples df to 100 microsecond - uses bfill to replace NaNs
            if t[-1]/.00001 > n:
                rm = df.rolling('4s').mean()
                self.rolling_torque = np.sqrt(rm.values)
            else:
                self.rolling_torque = self.rms_torque

            self.max_rolling_rms_current = np.nanmax(self.rolling_torque)/ForceConst  # A
            round_v = np.round(v, 2)
            round_v[round_v != 0] = 1
            #this line retrieves each point in round_v that transitions from 1 to 0 or 0 to 1
            v_transitions = np.argwhere(np.diff(round_v)).squeeze() / 100000
            if type(v_transitions) == np.float64:  # if only 1 transition, type is float - this fixes that
                if round_v[-1] == 1:
                    v_transitions = np.array([v_transitions, (len(t)-1) / 100000])
                else:
                    v_transitions = np.array([0, v_transitions])
            if not len(v_transitions) % 2 == 0:  # if odd # transitions, adds final t as last transition
                v_transitions = np.append(v_transitions, (len(t)-1) / 100000)
            v_transitions = v_transitions.reshape(-1, 2)
            vel_time = 0
            for start, stop in v_transitions:
                vel_time += (t[int(stop*100000)]-t[int(start*100000)])

            self.duty_cycle = round((vel_time/t[-1]*100), 1)

            self.ui.txt_peak_torque_required.setText(str(round(self.peak_torque, 2)) + " N")
            self.ui.txt_rms_torque.setText(str(round(self.rms_torque, 2)) + " N")
            self.ui.txt_peak_motor_speed.setText(str(round(self.peak_motor_speed, 0)) + " mm/sec")
            self.ui.txt_peak_power_output.setText(str(round(self.peak_power_output, 2)) + " W")
            self.ui.txt_rms_power_output.setText(str(round(self.rms_power_output, 2)) + " W")
            self.ui.txt_bus_voltage_required.setText(str(round(self.bus_voltage_required, 2)) + " V")
            self.ui.txt_peak_current_required.setText(str(round(self.peak_current, 2)) + " A")
            self.ui.txt_rms_current_required.setText(str(round(self.rms_current, 2)) + " A")
            self.ui.txt_final_coil_temperature.setText(str(round(self.final_coil_temperature, 2)) + " C")
            self.ui.txt_rolling_rms_current.setText(str(round(self.max_rolling_rms_current, 2)) + " A")
            self.ui.txt_duty_cycle.setText(str(self.duty_cycle) + "%")
            self.ui.txt_sto_current.setText("NA")#str(round(self.sto_current, 2)) + " A")
        except:
            msg = QtWidgets.QMessageBox()
            msg.setText("Check drive configuration.")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setWindowTitle("Error")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
            return
  
    def calc_results_dd_rotary(self):
        import re  # moved local to reduce startup time
        import pandas as pd  # moved local to reduce startup time
        v_nonzero = np.array(v)
        v_nonzero[v_nonzero != 0] = 1
        self.ui.label_36.setText("kg*m^2")
        self.ui.label_16.setText("Inertia:")
        self.ui.txt_orientation.setText("0")
        if not self.ui.txt_payload.text():
            payload = 0
        else:
            payload = float(self.ui.txt_payload.text())
        #screw_lead = float(self.ui.txt_screw_lead.text())  # m
        #screw_diameter = float(self.ui.txt_screw_diameter.text())  # m
        #screw_length = float(self.ui.txt_screw_length.text())  # m
        if not self.ui.txt_orientation.text():
            incline_angle = 0
        else:
            #print("no incline allowed on rotary")
            incline_angle = np.radians(float(self.ui.txt_orientation.text()))  # rad
        FrictionTorque = float(self.ui.stage_param_txt_1.text())
        #screw_lead = float(self.ui.stage_param_txt_5.text())
        RotationalInertia = float(self.ui.stage_param_txt_3.text())  # N
        #screw_friction = float(self.ui.stage_param_txt_3.text())*v_nonzero  # N*m
       
        
        MotorInertia = float(self.ui.motor_param_txt_1.text())  # kg*m^2
        TorqueConst = float(self.ui.motor_param_txt_2.text())  # N*m/Apk
        MotorConst = float(self.ui.motor_param_txt_3.text())
        bemf = float(self.ui.motor_param_txt_4.text())
        
        # = float(self.ui.motor_param_txt_8.text())  # Ohm
        Inductance = float(self.ui.motor_param_txt_6.text())  # H
        resistance = float(self.ui.motor_param_txt_5.text())  # Ohm
        number_of_poles = int(self.ui.motor_param_txt_8.text())
        if not self.ui.txt_ambient_temperature.text():
            ambient_temperature = 20
        else:
            ambient_temperature = float(self.ui.txt_ambient_temperature.text())  # C
        thermal_resistance = float(self.ui.motor_param_txt_7.text())  # C/W
        if self.ui.cmb_vacuum.currentText() == "Yes":
            thermal_resistance = thermal_resistance*4

        self.rated_speed = 1
        self.brake_holding_torque = 1
        self.rated_power_output = 1
        self.rated_peak_torque =1 

        load_inertia = (MotorInertia+RotationalInertia+payload)#*(screw_lead/(2*np.pi))**2  # kg*m^2
        total_static_reflected_torque = FrictionTorque
        torque = FrictionTorque + (load_inertia*np.array(a)*np.pi/180)  # N*m

        self.peak_torque = np.max(abs(torque))  # N*m
        self.rms_torque = np.sqrt((1/t[-1])*np.trapz(torque**2, t, .0001))  # N*m
        self.peak_motor_speed = np.max(abs(np.array(v)))  # deg/sec
        self.sto_decel = self.peak_motor_speed/.450*(np.pi/180)  # rad/sec^2 - hard coded 450 msec decel for STO
        self.sto_torque = np.max(total_static_reflected_torque) + self.sto_decel  # N*m
        self.sto_current = self.sto_torque/TorqueConst  # A
        self.peak_current = self.peak_torque/TorqueConst  # A
        self.rms_current = self.rms_torque/TorqueConst  # A
        #self.peak_power_output = self.peak_current**2*resistance  # W
        #-------------------------Kevin added---------------
        try:
            con = lite.connect(db_filepath)
            with con:
                cur = con.cursor()
                cur.execute("SELECT * FROM Drives WHERE Name='%s'" % self.ui.cmb_drive_select.currentText())
                drive_record = cur.fetchone()
                bus_voltage = None
                if drive_record[2] == "PWM":
                    #self.rated_power_output = self.peak_torque * self.peak_motor_speed/1000
                    self.peak_power_output1 = TorqueConst  * self.rms_current * self.peak_motor_speed/1000  #calculate output power
                    #print(str(resistance))
                    #print("speed is" + str(self.peak_motor_speed/1000))
                    #print("force constant is " + str(ForceConst))
                    self.rated_power_loss = 3/2 * self.rms_current**2 * resistance
                    self.peak_power_output = self.peak_power_output1 + self.rated_power_loss #Formula based on HWMAN-2141 input power, no need to divide efficiency because we're interested in how much power the motor draws
                    
                else: #calculate linear amplifier case
                    if drive_record[5]:
                        input_voltage_text = self.ui.cmb_input_voltage.currentText()
                        input_voltage_text_clean = re.sub('[^\d]', '', input_voltage_text)
                        if "+/-" in input_voltage_text:
                            input_voltage = int(input_voltage_text_clean)*2
                        else:
                            input_voltage = int(input_voltage_text_clean)
                        bus_voltage = float(drive_record[5])*input_voltage
                    elif drive_record[6]:
                        bus_voltage_text = drive_record[6]
                        bus_voltage = self.convert_bus_voltage_text(bus_voltage_text)
                    elif drive_record[7]:
                        special_text = drive_record[7]
                        if not self.ui.cmb_select_bus_voltage.currentText() == "--Select--"\
                                and not self.ui.cmb_select_bus_voltage.currentText() == "1"\
                                and self.ui.cmb_select_bus_voltage.currentText():
                            cur.execute("SELECT %s FROM BusVoltages WHERE %s='%s'" %
                                        ((str(special_text) + "Bus"), str(special_text),
                                         self.ui.cmb_select_bus_voltage.currentText()))
                            bus_voltage_text = cur.fetchone()[0]
                            bus_voltage = self.convert_bus_voltage_text(bus_voltage_text)
                    self.peak_power_output = self.rms_current * int(bus_voltage)
        
        #--------------------------------------------------
            self.rms_power_output = 3/2 * self.rms_current**2 * resistance # W Kevin added *3/2
            self.bus_voltage_required = ((bemf*self.peak_motor_speed/6000)+self.peak_current
                                    * np.sqrt(resistance**2
                                        )/0.866)
            self.final_coil_temperature = thermal_resistance*self.rms_power_output + ambient_temperature  # C
            self.final_coil_temperature_contineous_move = 55  # C

            n = int(4/.00001)
            torque_squared = np.power(torque, 2)
            df = pd.DataFrame(torque_squared, pd.to_timedelta(t, unit='second'))  # time indexes torque_squared
            df = df.resample('100U').bfill()  # upsamples df to 100 microsecond - uses bfill to replace NaNs
            if t[-1]/.00001 > n:
                rm = df.rolling('4s').mean()
                self.rolling_torque = np.sqrt(rm.values)
            else:
                self.rolling_torque = self.rms_torque

            self.max_rolling_rms_current = np.nanmax(self.rolling_torque)/TorqueConst  # A
            round_v = np.round(v, 2)
            round_v[round_v != 0] = 1
            #this line retrieves each point in round_v that transitions from 1 to 0 or 0 to 1
            v_transitions = np.argwhere(np.diff(round_v)).squeeze() / 100000
            if type(v_transitions) == np.float64:  # if only 1 transition, type is float - this fixes that
                if round_v[-1] == 1:
                    v_transitions = np.array([v_transitions, (len(t)-1) / 100000])
                else:
                    v_transitions = np.array([0, v_transitions])
            if not len(v_transitions) % 2 == 0:  # if odd # transitions, adds final t as last transition
                v_transitions = np.append(v_transitions, (len(t)-1) / 100000)
            v_transitions = v_transitions.reshape(-1, 2)
            vel_time = 0
            for start, stop in v_transitions:
                vel_time += (t[int(stop*100000)]-t[int(start*100000)])

            self.duty_cycle = round((vel_time/t[-1]*100), 1)

            self.ui.txt_peak_torque_required.setText(str(round(self.peak_torque, 2)) + " N*m")
            self.ui.txt_rms_torque.setText(str(round(self.rms_torque, 2)) + " N*m")
            self.ui.txt_peak_motor_speed.setText(str(round(self.peak_motor_speed, 0)) + " °/sec")
            self.ui.txt_peak_power_output.setText(str(round(self.peak_power_output, 2)) + " W")
            self.ui.txt_rms_power_output.setText(str(round(self.rms_power_output, 2)) + " W")
            self.ui.txt_bus_voltage_required.setText(str(round(self.bus_voltage_required, 2)) + " V")
            self.ui.txt_peak_current_required.setText(str(round(self.peak_current, 2)) + " A")
            self.ui.txt_rms_current_required.setText(str(round(self.rms_current, 2)) + " A")
            self.ui.txt_final_coil_temperature.setText(str(round(self.final_coil_temperature, 2)) + " C")
            #self.ui.txt_final_coil_temperature.setText(str(round(self.final_coil_temperature_contineous_move, 2)) + " C")
            self.ui.txt_rolling_rms_current.setText(str(round(self.max_rolling_rms_current, 2)) + " A")
            self.ui.txt_duty_cycle.setText(str(self.duty_cycle) + "%")
            self.ui.txt_sto_current.setText("NA")#str(round(self.sto_current, 2)) + " A")
            
        except:
            msg = QtWidgets.QMessageBox()
            msg.setText("Check drive configuration.")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setWindowTitle("Error")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
            return


    def calc_results_gd_rotary(self):
        print("Unsupported for now")
        
    def calc_results_linear_motor(self):
        import re  # moved local to reduce startup time
        import pandas as pd  # moved local to reduce startup time
        v_nonzero = np.array(v)
        v_nonzero[v_nonzero != 0] = 1
        if not self.ui.txt_payload.text():
            payload = 0
        else:
            payload = float(self.ui.txt_payload.text())
        #screw_lead = float(self.ui.txt_screw_lead.text())  # m
        #screw_diameter = float(self.ui.txt_screw_diameter.text())  # m
        #screw_length = float(self.ui.txt_screw_length.text())  # m
        if not self.ui.txt_orientation.text():
            incline_angle = 0
        else:
            incline_angle = np.radians(float(self.ui.txt_orientation.text()))  # rad
        #moving_mass = float(self.ui.motor_param_txt_6.text())
        #screw_lead = float(self.ui.stage_param_txt_5.text())
        #bearing_friction = float(self.ui.stage_param_txt_2.text())  # N
        #screw_friction = float(self.ui.stage_param_txt_3.text())*v_nonzero  # N*m
        #WedgeRatio = float(self.ui.stage_param_txt_3.text())
        #stage_param_txt
        #MotorDerate = float(self.ui.stage_param_txt_4.text())
        #NumMotors = float(self.ui.stage_param_txt_5.text())
        #print(self.ui.motor_param_txt_1.text())
        ForceConst = float(self.ui.motor_param_txt_1.text())  # kg*m^2
        MotorConst = float(self.ui.motor_param_txt_2.text())  # N*m/Apk
        bemf = float(self.ui.motor_param_txt_3.text())
        # = float(self.ui.motor_param_txt_8.text())  # Ohm
        CoilMass = float(self.ui.motor_param_txt_6.text())  # H
        resistance = float(self.ui.motor_param_txt_4.text())#/NumMotors  # Ohm
        max_temp = float(self.ui.motor_param_txt_8.text())
        #moving_mass = moving_mass + CoilMass
       # number_of_poles = int(self.ui.motor_param_txt_8.text())
        if not self.ui.txt_ambient_temperature.text():
            ambient_temperature = 20
        else:
            ambient_temperature = float(self.ui.txt_ambient_temperature.text())  # C
        thermal_resistance = float(self.ui.motor_param_txt_5.text())  # C/W
        if self.ui.cmb_vacuum.currentText() == "Yes":
            thermal_resistance = thermal_resistance*4
        self.rated_speed = 1
        self.brake_holding_torque = 1
        self.rated_power_output = 1
        self.rated_peak_torque =1 

        load_inertia = (payload+CoilMass)#*(screw_lead/(2*np.pi))**2  # kg*m^2
        #screw_inertia = float(self.ui.stage_param_txt_4.text())#(7700*np.pi*screw_diameter**4*screw_length)/32  # kg*m^2
        #reflected_inertia = (load_inertia+screw_inertia)/(0.9*self.gear_ratio)+motor_inertia  # kg*m^2
        #load_torque = (np.sin(incline_angle) * (moving_mass + payload) * 9.81)# \
                      # *np.ones_like(v)  # N
        #bearing_friction_torque = (bearing_friction + .0015 * np.cos(incline_angle) * (moving_mass + payload) * 9.81) \
        #    * v_nonzero
        incline_force = np.sin(incline_angle) * load_inertia * 9.81
        #print(incline_force)
        total_static_reflected_torque = (incline_force)  # N*m
        #print(total_static_reflected_torque)
        torque = total_static_reflected_torque + (load_inertia*np.array(a)/1000)  # N*m
        # for element in a:
            # print(element)
        #print(torque)
        # print("load_inertia =" +str(load_inertia))
        # print("screw_inertia =" +str(screw_inertia))
        # print("reflected_inertia =" + str(reflected_inertia))
        # print("load_torque =" + str(load_torque))
        # print("bearing friction_torque =" +str(bearing_friction_torque))
        # print("total_static_reflected_torque =" +str(total_static_reflected_torque))
        # print("torque =" + str(torque)) 
        # this bit shifts the torque required closer to zero by the holding torque for all portions of the torque
        # array during which the brake is on.
        # if 1 in b:
            # torque_sign = np.sign(torque)
            # torque = abs(torque)-np.array(b)*self.brake_holding_torque
            # torque[torque < 0] = 0
            # torque = torque*torque_sign
        self.peak_torque = np.max(abs(torque))  # N*m
        self.rms_torque = np.sqrt((1/t[-1])*np.trapz(torque**2, t, .0001))  # N*m
        #print(np.max(abs(np.array(v))))
        self.peak_motor_speed = np.max(abs(np.array(v)))  # deg/sec
        self.sto_decel = self.peak_motor_speed/.450*(np.pi/180)  # rad/sec^2 - hard coded 450 msec decel for STO
        self.sto_torque = np.max(total_static_reflected_torque) + self.sto_decel  # N*m
        self.sto_current = self.sto_torque/ForceConst  # A
        self.peak_current = self.peak_torque/ForceConst  # A
        self.rms_current = self.rms_torque/ForceConst  # A
        #self.peak_power_output = self.peak_current**2*resistance  # W
        #-------------------------Kevin added---------------
        try:
            con = lite.connect(db_filepath)
            with con:
                cur = con.cursor()
                cur.execute("SELECT * FROM Drives WHERE Name='%s'" % self.ui.cmb_drive_select.currentText())
                drive_record = cur.fetchone()
                bus_voltage = None
                if drive_record[2] == "PWM":
                    #self.rated_power_output = self.peak_torque * self.peak_motor_speed/1000
                    self.peak_power_output1 = ForceConst  * self.rms_current * self.peak_motor_speed/1000
                    print(str(resistance))
                    #print("speed is" + str(self.peak_motor_speed/1000))
                    #print("force constant is " + str(ForceConst))
                    self.rated_power_loss = 3/2 * self.rms_current**2 * resistance
                    self.peak_power_output = self.peak_power_output1 + self.rated_power_loss  #Formula based on HWMAN-2141, no need to divide efficiency because we're interested in how much power the motor draws
                    
                else: #calculate linear amplifier case
                    if drive_record[5]:
                        input_voltage_text = self.ui.cmb_input_voltage.currentText()
                        input_voltage_text_clean = re.sub('[^\d]', '', input_voltage_text)
                        if "+/-" in input_voltage_text:
                            input_voltage = int(input_voltage_text_clean)*2
                        else:
                            input_voltage = int(input_voltage_text_clean)
                        bus_voltage = float(drive_record[5])*input_voltage
                    elif drive_record[6]:
                        bus_voltage_text = drive_record[6]
                        bus_voltage = self.convert_bus_voltage_text(bus_voltage_text)
                    elif drive_record[7]:
                        special_text = drive_record[7]
                        if not self.ui.cmb_select_bus_voltage.currentText() == "--Select--"\
                                and not self.ui.cmb_select_bus_voltage.currentText() == "1"\
                                and self.ui.cmb_select_bus_voltage.currentText():
                            cur.execute("SELECT %s FROM BusVoltages WHERE %s='%s'" %
                                        ((str(special_text) + "Bus"), str(special_text),
                                         self.ui.cmb_select_bus_voltage.currentText()))
                            bus_voltage_text = cur.fetchone()[0]
                            bus_voltage = self.convert_bus_voltage_text(bus_voltage_text)
                    self.peak_power_output = self.rms_current * int(bus_voltage)
        
        #--------------------------------------------------
            self.rms_power_output = 3/2 * self.rms_current**2 * resistance  # W Kevin added 3/2*
            self.bus_voltage_required = ((bemf*self.peak_motor_speed/1000)+self.peak_current * resistance)
            #print("thermal resistance: " + str(thermal_resistance) + "\nrms_power_output: " +str(self.rms_power_output) + "\nambient_temp" + str(ambient_temperature))
            self.final_coil_temperature = thermal_resistance*self.rms_power_output + ambient_temperature  # C
            #print(str(self.final_coil_temperature))
            n = int(4/.00001)
            torque_squared = np.power(torque, 2)
            df = pd.DataFrame(torque_squared, pd.to_timedelta(t, unit='second'))  # time indexes torque_squared
            df = df.resample('100U').bfill()  # upsamples df to 100 microsecond - uses bfill to replace NaNs
            if t[-1]/.00001 > n:
                rm = df.rolling('4s').mean()
                self.rolling_torque = np.sqrt(rm.values)
            else:
                self.rolling_torque = self.rms_torque

            self.max_rolling_rms_current = np.nanmax(self.rolling_torque)/ForceConst  # A
            round_v = np.round(v, 2)
            round_v[round_v != 0] = 1
            #this line retrieves each point in round_v that transitions from 1 to 0 or 0 to 1
            v_transitions = np.argwhere(np.diff(round_v)).squeeze() / 100000
            if type(v_transitions) == np.float64:  # if only 1 transition, type is float - this fixes that
                if round_v[-1] == 1:
                    v_transitions = np.array([v_transitions, (len(t)-1) / 100000])
                else:
                    v_transitions = np.array([0, v_transitions])
            if not len(v_transitions) % 2 == 0:  # if odd # transitions, adds final t as last transition
                v_transitions = np.append(v_transitions, (len(t)-1) / 100000)
            v_transitions = v_transitions.reshape(-1, 2)
            vel_time = 0
            for start, stop in v_transitions:
                vel_time += (t[int(stop*100000)]-t[int(start*100000)])

            self.duty_cycle = round((vel_time/t[-1]*100), 1)

            self.ui.txt_peak_torque_required.setText(str(round(self.peak_torque, 2)) + " N")
            self.ui.txt_rms_torque.setText(str(round(self.rms_torque, 2)) + " N")
            self.ui.txt_peak_motor_speed.setText(str(round(self.peak_motor_speed, 0)) + " mm/sec")
            self.ui.txt_peak_power_output.setText(str(round(self.peak_power_output, 2)) + " W")
            self.ui.txt_rms_power_output.setText(str(round(self.rms_power_output, 2)) + " W")
            self.ui.txt_bus_voltage_required.setText(str(round(self.bus_voltage_required, 2)) + " V")
            self.ui.txt_peak_current_required.setText(str(round(self.peak_current, 2)) + " A")
            self.ui.txt_rms_current_required.setText(str(round(self.rms_current, 2)) + " A")
            self.ui.txt_final_coil_temperature.setText(str(round(self.final_coil_temperature, 2)) + " C")
            self.ui.txt_rolling_rms_current.setText(str(round(self.max_rolling_rms_current, 2)) + " A")
            self.ui.txt_duty_cycle.setText(str(self.duty_cycle) + "%")
            self.ui.txt_sto_current.setText(str(round(self.sto_current, 2)) + " A")
            
        except:
            msg = QtWidgets.QMessageBox()
            msg.setText("Check drive configuration.")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setWindowTitle("Error")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
            return
    
    def calc_results_rotary_motor(self):
        import re  # moved local to reduce startup time
        import pandas as pd  # moved local to reduce startup time
        v_nonzero = np.array(v)
        v_nonzero[v_nonzero != 0] = 1
        self.ui.label_36.setText("kg*m^2")
        self.ui.label_16.setText("Inertia:")
        self.ui.txt_orientation.setText("0")
        if not self.ui.txt_payload.text():
            payload = 0
        else:
            payload = float(self.ui.txt_payload.text())
        #screw_lead = float(self.ui.txt_screw_lead.text())  # m
        #screw_diameter = float(self.ui.txt_screw_diameter.text())  # m
        #screw_length = float(self.ui.txt_screw_length.text())  # m
        if not self.ui.txt_orientation.text():
            incline_angle = 0
        else:
            #print("no incline allowed on rotary")
            incline_angle = np.radians(float(self.ui.txt_orientation.text()))  # rad
        FrictionTorque = 0#float(self.ui.stage_param_txt_1.text())
        #screw_lead = float(self.ui.stage_param_txt_5.text())
        RotationalInertia = 0#float(self.ui.stage_param_txt_3.text())  # N
        #screw_friction = float(self.ui.stage_param_txt_3.text())*v_nonzero  # N*m
       
        
        MotorInertia = float(self.ui.motor_param_txt_1.text())  # kg*m^2
        TorqueConst = float(self.ui.motor_param_txt_2.text())  # N*m/Apk
        MotorConst = float(self.ui.motor_param_txt_3.text())
        bemf = float(self.ui.motor_param_txt_4.text())
        
        # = float(self.ui.motor_param_txt_8.text())  # Ohm
        Inductance = float(self.ui.motor_param_txt_6.text())  # H
        resistance = float(self.ui.motor_param_txt_5.text())  # Ohm
        number_of_poles = int(self.ui.motor_param_txt_8.text())
        if not self.ui.txt_ambient_temperature.text():
            ambient_temperature = 20
        else:
            ambient_temperature = float(self.ui.txt_ambient_temperature.text())  # C
        thermal_resistance = float(self.ui.motor_param_txt_7.text())  # C/W
        if self.ui.cmb_vacuum.currentText() == "Yes":
            thermal_resistance = thermal_resistance*4

        self.rated_speed = 1
        self.brake_holding_torque = 1
        self.rated_power_output = 1
        self.rated_peak_torque =1 

        load_inertia = (MotorInertia+RotationalInertia+payload)#*(screw_lead/(2*np.pi))**2  # kg*m^2
        total_static_reflected_torque = FrictionTorque
        torque = FrictionTorque + (load_inertia*np.array(a)*np.pi/180)  # N*m

        self.peak_torque = np.max(abs(torque))  # N*m
        self.rms_torque = np.sqrt((1/t[-1])*np.trapz(torque**2, t, .0001))  # N*m
        self.peak_motor_speed = np.max(abs(np.array(v)))  # deg/sec
        self.sto_decel = self.peak_motor_speed/.450*(np.pi/180)  # rad/sec^2 - hard coded 450 msec decel for STO
        self.sto_torque = np.max(total_static_reflected_torque) + self.sto_decel  # N*m
        self.sto_current = self.sto_torque/TorqueConst  # A
        self.peak_current = self.peak_torque/TorqueConst  # A
        self.rms_current = self.rms_torque/TorqueConst  # A
        #self.peak_power_output = self.peak_current**2*resistance  # W
        #-------------------------Kevin added---------------
        try:
            con = lite.connect(db_filepath)
            with con:
                cur = con.cursor()
                cur.execute("SELECT * FROM Drives WHERE Name='%s'" % self.ui.cmb_drive_select.currentText())
                drive_record = cur.fetchone()
                bus_voltage = None
                if drive_record[2] == "PWM":
                    #self.rated_power_output = self.peak_torque * self.peak_motor_speed/1000
                    self.peak_power_output1 = TorqueConst * self.rms_current * self.peak_motor_speed/1000
                    #print(str(resistance))
                    #print("speed is" + str(self.peak_motor_speed/1000))
                    #print("force constant is " + str(ForceConst))
                    self.rated_power_loss = 3/2 * self.rms_current**2 * resistance
                    self.peak_power_output = self.peak_power_output1 + self.rated_power_loss #Formula based on HWMAN-2141, no need to divide efficiency because we're interested in how much power the motor draws
                    
                else: #calculate linear amplifier case
                    if drive_record[5]:
                        input_voltage_text = self.ui.cmb_input_voltage.currentText()
                        input_voltage_text_clean = re.sub('[^\d]', '', input_voltage_text)
                        if "+/-" in input_voltage_text:
                            input_voltage = int(input_voltage_text_clean)*2
                        else:
                            input_voltage = int(input_voltage_text_clean)
                        bus_voltage = float(drive_record[5])*input_voltage
                    elif drive_record[6]:
                        bus_voltage_text = drive_record[6]
                        bus_voltage = self.convert_bus_voltage_text(bus_voltage_text)
                    elif drive_record[7]:
                        special_text = drive_record[7]
                        if not self.ui.cmb_select_bus_voltage.currentText() == "--Select--"\
                                and not self.ui.cmb_select_bus_voltage.currentText() == "1"\
                                and self.ui.cmb_select_bus_voltage.currentText():
                            cur.execute("SELECT %s FROM BusVoltages WHERE %s='%s'" %
                                        ((str(special_text) + "Bus"), str(special_text),
                                         self.ui.cmb_select_bus_voltage.currentText()))
                            bus_voltage_text = cur.fetchone()[0]
                            bus_voltage = self.convert_bus_voltage_text(bus_voltage_text)
                    self.peak_power_output = self.rms_current * int(bus_voltage)
        
        #--------------------------------------------------
            self.rms_power_output = 3/2 * self.rms_current**2 * resistance # W Kevin added *3/2
            self.rms_power_output = self.rms_current**2*resistance  # W
            self.bus_voltage_required = ((bemf*self.peak_motor_speed/6000)+self.peak_current
                                    * np.sqrt(resistance**2
                                        )/0.866)
            self.final_coil_temperature = thermal_resistance*self.rms_power_output + ambient_temperature  # C

            n = int(4/.00001)
            torque_squared = np.power(torque, 2)
            df = pd.DataFrame(torque_squared, pd.to_timedelta(t, unit='second'))  # time indexes torque_squared
            df = df.resample('100U').bfill()  # upsamples df to 100 microsecond - uses bfill to replace NaNs
            if t[-1]/.00001 > n:
                rm = df.rolling('4s').mean()
                self.rolling_torque = np.sqrt(rm.values)
            else:
                self.rolling_torque = self.rms_torque

            self.max_rolling_rms_current = np.nanmax(self.rolling_torque)/TorqueConst  # A
            round_v = np.round(v, 2)
            round_v[round_v != 0] = 1
            #this line retrieves each point in round_v that transitions from 1 to 0 or 0 to 1
            v_transitions = np.argwhere(np.diff(round_v)).squeeze() / 100000
            if type(v_transitions) == np.float64:  # if only 1 transition, type is float - this fixes that
                if round_v[-1] == 1:
                    v_transitions = np.array([v_transitions, (len(t)-1) / 100000])
                else:
                    v_transitions = np.array([0, v_transitions])
            if not len(v_transitions) % 2 == 0:  # if odd # transitions, adds final t as last transition
                v_transitions = np.append(v_transitions, (len(t)-1) / 100000)
            v_transitions = v_transitions.reshape(-1, 2)
            vel_time = 0
            for start, stop in v_transitions:
                vel_time += (t[int(stop*100000)]-t[int(start*100000)])

            self.duty_cycle = round((vel_time/t[-1]*100), 1)

            self.ui.txt_peak_torque_required.setText(str(round(self.peak_torque, 2)) + " N*m")
            self.ui.txt_rms_torque.setText(str(round(self.rms_torque, 2)) + " N*m")
            self.ui.txt_peak_motor_speed.setText(str(round(self.peak_motor_speed, 0)) + " °/sec")
            self.ui.txt_peak_power_output.setText(str(round(self.peak_power_output, 2)) + " W")
            self.ui.txt_rms_power_output.setText(str(round(self.rms_power_output, 2)) + " W")
            self.ui.txt_bus_voltage_required.setText(str(round(self.bus_voltage_required, 2)) + " V")
            self.ui.txt_peak_current_required.setText(str(round(self.peak_current, 2)) + " A")
            self.ui.txt_rms_current_required.setText(str(round(self.rms_current, 2)) + " A")
            self.ui.txt_final_coil_temperature.setText(str(round(self.final_coil_temperature, 2)) + " C")
            self.ui.txt_rolling_rms_current.setText(str(round(self.max_rolling_rms_current, 2)) + " A")
            self.ui.txt_duty_cycle.setText(str(self.duty_cycle) + "%")
            self.ui.txt_sto_current.setText(str(round(self.sto_current, 2)) + " A")
        except:
            msg = QtWidgets.QMessageBox()
            msg.setText("Check drive configuration.")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setWindowTitle("Error")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
            return


    def calc_results(self, image=False):
        """Calculates results off of acceleration array calculated in refresh_plots function.

        Args:
            image (bool): builds filename of the appropriate Limitation Current Browser image, if linear drive.
                Defaults to False.

        Returns:
            str: file path of Limitation Current Browser image, if appropriate. False if not.

        """
        import re  # moved local to reduce startup time
        import pandas as pd  # moved local to reduce startup time
        self.store_inputs()
        self.file_change()
        global a, v, t, b
        con = lite.connect(temp_filepath)
        with con:
            cur = con.cursor()
            cur.execute("SELECT * FROM Profile ORDER BY Operation ASC")
            records = cur.fetchall()
        if not self.ui.txt_ambient_temperature.text():
            ambient_temperature = 20
        else:
            ambient_temperature = float(self.ui.txt_ambient_temperature.text())  # C
        #exit function if no Stage/Motor selected or if no Profile has been defined.
        if self.ui.stage_config_input.selectAll() == ''\
                or self.ui.motor_name.text() == ""\
                or not records:
            #self.clear_results()
            return
        motor = self.ui.motor_name.text().split("-")
        #print(motor)
        motor[0] = motor[0].rstrip()
        v_nonzero = np.array(v)
        v_nonzero[v_nonzero != 0] = 1
        stageType = self.ui.txt_stage_type.text()
        motorType = self.ui.txt_motor_type.text()
        air_cooling = self.ui.cmb_aircooling.currentText()
        # print("stage type: " +stageType)
        #print(air_cooling)
        if air_cooling == "20PSI":
            print("20PSI")
            temp = self.ui.motor_smart_string.text().replace("-NC","-AC")
            print(temp)
            if temp == self.ui.motor_smart_string.text() and "-AC" not in self.ui.motor_smart_string.text():
                #Air cooling not available
                msg = QtWidgets.QMessageBox()
                msg.setText("Air Cooling Not Available on this motor")
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setWindowTitle("Invalid Entry!")
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()
                self.ui.cmb_aircooling.setCurrentIndex(0)
            elif temp == self.ui.motor_smart_string.text() and "-AC" in self.ui.motor_smart_string.text():
                    return
            else:
                self.ui.motor_smart_string.setText(temp)
                self.on_motor_change(temp)
        elif air_cooling =="No":
            temp = self.ui.motor_smart_string.text().replace("-AC","-NC")
            # if temp == self.ui.motor_name.text():
                # print("Currently is No Cooling")
                # print("Cannot change from AirCooling to No Cooling")
            if not temp == self.ui.motor_smart_string.text():
                self.ui.motor_smart_string.setText(temp)
                self.on_motor_change(temp)
        # if "-NC" in self.ui.motor_name.text():
            # print("true")
            
        if stageType == "Direct-Drive Linear":
            self.ui.label_28.setText("Peak Force Required:")
            self.ui.label_29.setText("RMS Force:")
            # self.plotWidget.canvas.ax.set_ylabel('position\n(mm)', family={'arial'}, size='large')
            # self.plotWidget.canvas.ax2.set_ylabel('velocity\n(mm/sec)', family={'arial'}, size='large')
            # self.plotWidget.canvas.ax3.set_ylabel('acceleration\n(mm/sec$^2$)', family={'arial'}, size='large')
            self.calc_results_dd_linear()
            #moving_mass = float(self.ui.stage_param_txt_1.text()
            
        elif stageType == "Screw-Drive Linear":
            # self.plotWidget.canvas.ax.set_ylabel('position\n(mm)', family={'arial'}, size='large')
            # self.plotWidget.canvas.ax2.set_ylabel('velocity\n(mm/sec)', family={'arial'}, size='large')
            # self.plotWidget.canvas.ax3.set_ylabel('acceleration\n(mm/sec$^2$)', family={'arial'}, size='large')
            self.calc_results_sd_linear()
            #moving_mass = float(self.ui.stage_param_txt_1.text()
        elif stageType == "Direct-Drive Rotary":
            #print("here")
            # self.plotWidget.canvas.ax.set_ylabel('position\n(deg)', family={'arial'}, size='large')
            # self.plotWidget.canvas.ax2.set_ylabel('velocity\n(deg/sec)', family={'arial'}, size='large')
            # self.plotWidget.canvas.ax3.set_ylabel('acceleration\n(deg/sec$^2$)', family={'arial'}, size='large')
            self.calc_results_dd_rotary()
        elif stageType == "Gear-Drive Rotary":
            self.calc_results_gd_rotary()
        elif stageType == "":
            if motorType =="Linear":
                self.calc_results_linear_motor()
            elif motorType=="Rotary":
                self.calc_results_rotary_motor()
            
        #    moving_mass = float(self.ui.txt_moving_mass.text())  # kg


        self.ui.cmb_input_voltage.setStyleSheet("")
        self.ui.btn_current_limitation_browser.setVisible(False)

        # this bit handles all the subtleties of +/- input voltages, +/- bus voltages, B/HB bus voltages,
        # and building Current Limitation Browser image filenames (for linear amps)

        image_name = []

        con = lite.connect(db_filepath)
        with con:
            cur = con.cursor()
            if stageType == "Screw-Drive Linear":
                #print(motor[0])
                cur.execute("SELECT * FROM Motors WHERE Name='%s'" % motor[0])
                motor_record = cur.fetchone()
                
                #print(motor_string)
                if motor_record==None:
                    motor_string=motor[0]+"-" + motor[1]
                    cur.execute("SELECT * FROM Motors WHERE Name='%s'" % motor_string.rstrip())
                    motor_record = cur.fetchone()
                #print(motor_record)
                if not motor_record==None:
                    max_temp = float(motor_record[8])
                    rated_peak_torque = float(motor_record[13])  # N*m
                    rated_cont_torque = float(motor_record[14])  # N*m
                    if self.ui.cmb_vacuum.currentText() == "Yes":
                        rated_cont_torque = rated_cont_torque*.5
                    
            cur.execute("SELECT * FROM Drives WHERE Name='%s'" % self.ui.cmb_drive_select.currentText())
            drive_record = cur.fetchone()
            bus_voltage = None
            if drive_record[2] == "PWM":
                if drive_record[5]:
                    input_voltage_text = self.ui.cmb_input_voltage.currentText()
                    input_voltage_text_clean = re.sub('[^\d]', '', input_voltage_text)
                    if "+/-" in input_voltage_text:
                        input_voltage = int(input_voltage_text_clean)*2
                    else:
                        input_voltage = int(input_voltage_text_clean)
                    bus_voltage = float(drive_record[5])*input_voltage
                elif drive_record[6]:
                    bus_voltage_text = drive_record[6]
                    bus_voltage = self.convert_bus_voltage_text(bus_voltage_text)
                elif drive_record[7]:
                    special_text = drive_record[7]
                    if not self.ui.cmb_select_bus_voltage.currentText() == "--Select--"\
                            and not self.ui.cmb_select_bus_voltage.currentText() == "1"\
                            and self.ui.cmb_select_bus_voltage.currentText():
                        cur.execute("SELECT %s FROM BusVoltages WHERE %s='%s'" %
                                    ((str(special_text) + "Bus"), str(special_text),
                                     self.ui.cmb_select_bus_voltage.currentText()))
                        bus_voltage_text = cur.fetchone()[0]
                        bus_voltage = self.convert_bus_voltage_text(bus_voltage_text)
                if "-HB" in self.ui.cmb_drive_select.currentText() and bus_voltage:
                    bus_voltage = bus_voltage*.5
            elif drive_record[2] == "Linear":
                if drive_record[1] == "ML10":
                    if "ML" not in self.ui.cmb_input_voltage.currentText():
                        self.ui.cmb_input_voltage.setStyleSheet("color: red")
                if drive_record[5]:
                    input_voltage_text = self.ui.cmb_input_voltage.currentText()
                    input_voltage_text_clean = re.sub('[^\d]', '', input_voltage_text)
                    if "+/-" in input_voltage_text:
                        input_voltage = int(input_voltage_text_clean)*2
                    else:
                        input_voltage = int(input_voltage_text_clean)
                    bus_voltage = float(drive_record[5])*input_voltage
                elif drive_record[6]:
                    bus_voltage_text = drive_record[6]
                    bus_voltage = self.convert_bus_voltage_text(bus_voltage_text)
                elif drive_record[7]:
                    special_text = drive_record[7]
                    if not self.ui.cmb_select_bus_voltage.currentText() == "--Select--"\
                            and not self.ui.cmb_select_bus_voltage.currentText() == "1"\
                            and self.ui.cmb_select_bus_voltage.currentText():
                        cur.execute("SELECT %s FROM BusVoltages WHERE %s='%s'" %
                                    ((str(special_text) + "Bus"), str(special_text),
                                     self.ui.cmb_select_bus_voltage.currentText()))
                        bus_voltage_text = cur.fetchone()[0]
                        bus_voltage = self.convert_bus_voltage_text(bus_voltage_text)
                if "HLe" in drive_record[1]:
                    image_name.append(drive_record[1] + "B-")
                if "XL5e10" in drive_record[1]:
                    if not self.ui.cmb_select_bus_voltage.currentText() == "--Select--"\
                            and not self.ui.cmb_select_bus_voltage.currentText() == "1"\
                            and self.ui.cmb_select_bus_voltage.currentText():
                        #print(drive_record[1])
                        #print(self.ui.cmb_select_bus_voltage.currentText())
                        image_name.append(drive_record[1]+"-"+str(int(bus_voltage/2)) + "B-")
                    else:
                        image_name.append(drive_record[1] + "-40B-")
                if "XL5e20" in drive_record[1]:
                    image_name.append(drive_record[1] + "-40B-")
                elif "ML" in drive_record[1]:
                    if "Npaq" in drive_record[1] or "Epaq" in drive_record[1]:
                        if not self.ui.cmb_select_bus_voltage.currentText() == "--Select--" \
                                and not self.ui.cmb_select_bus_voltage.currentText() == "1" \
                                and self.ui.cmb_select_bus_voltage.currentText():
                            if "24B" in special_text:
                                image_name.append("ML-24B-")
                            elif "40B" in special_text:
                                image_name.append("ML-40B-")
                            elif "48B" in special_text:
                                image_name.append("ML-48B-")
                    else:
                        if "ML" in self.ui.cmb_input_voltage.currentText():
                            if "24" in self.ui.cmb_input_voltage.currentText():
                                image_name.append("ML-24B-")
                            elif "40" in self.ui.cmb_input_voltage.currentText():
                                image_name.append("ML-40B-")
                elif "DL" in drive_record[1]:
                    if not self.ui.cmb_select_bus_voltage.currentText() == "--Select--" \
                            and not self.ui.cmb_select_bus_voltage.currentText() == "1" \
                            and self.ui.cmb_select_bus_voltage.currentText():
                        if not (bus_voltage == 20 or bus_voltage == 160 or bus_voltage == 320):
                            if "4010" in drive_record[1]:
                                image_name.append("DL4010-" + str(int(bus_voltage/2)) + "B-")
                            elif "8010" in drive_record[1]:
                                image_name.append("DL8010-" + str(int(bus_voltage/2)) + "B-")
                            elif "8020" in drive_record[1]:
                                image_name.append("DL8020-" + str(int(bus_voltage/2)) + "B-")
                elif "LAB" in drive_record[1]:
                    image_name.append("LAB-24B-")
                elif "XR3" in drive_record[1]:
                    if not self.ui.cmb_select_bus_voltage.currentText() == "--Select--" \
                            and not self.ui.cmb_select_bus_voltage.currentText() == "1" \
                            and self.ui.cmb_select_bus_voltage.currentText():
                        if not (bus_voltage == 20 or bus_voltage == 160 or bus_voltage == 320):
                            image_name.append("XSL3-" + str(int(bus_voltage/2)) + "B-")

                if image_name and not self.ui.motor_smart_string.text() == "":
                    motor_string = self.ui.motor_name.text()
                    if "BM" in motor_string:
                        if not motor_string.find(" ") == -1:
                            motor_string = motor_string[:motor_string.find(" ")]
                        elif not motor_string.find("-") == -1:
                            motor_string = motor_string[:motor_string.find("-")]
                        image_name.append(motor_string)
                    elif "MPS" in motor_string:
                        image_name.append(motor_string)
                    elif "S-" in motor_string:
                        image_name.append(motor_string[:motor_string.find(" ")])
                    else:
                        motor_string = self.ui.motor_smart_string.text() 
                        configs = motor_string.split("-")
                        if configs[0] == "BLMC" or configs[0] == "BLMUC":
                            image_name.append(configs[0] + "-" + configs[1])
                        else:
                            #print(configs[0] + "-" + configs[1] + "-" + "A")
                            image_name.append(configs[0] + "-" + configs[1] + "-A")
                    # elif "ATX" in motor_string     ---- ATX not in Current Limitation Browser

        error_text = []
        self.ui.txt_error_output.clear()
        #print(motorType)
        if stageType == "Direct-Drive Linear" or motorType=="Linear":
            max_temp = float(self.ui.motor_param_txt_8.text())
        elif stageType == "Screw-Drive Linear":
            max_temp = float(self.ui.motor_param_txt_9.text())
        elif stageType=="Direct-Drive Rotary" or motorType=="Rotary":
            max_temp = float(self.ui.motor_param_txt_9.text())
        #print("final temp " + self.ui.txt_final_coil_temperature.text()[:-2])
        # final_coil_temperature = 20
        try:
       
            final_coil_temperature = float(self.ui.txt_final_coil_temperature.text()[:-2])
        except:
            return
        if (final_coil_temperature - ambient_temperature) > 20:
            self.ui.txt_final_coil_temperature.setStyleSheet("color: red")
            error_text.append("Final Coil Temp is more than 20 C above Ambient.")
        elif final_coil_temperature > max_temp:
            self.ui.txt_final_coil_temperature.setStyleSheet("color: red")
            error_text.append("Final Coil Temp exceeds motor rating.")
        elif (final_coil_temperature - ambient_temperature) > 20 and final_coil_temperature > max_temp:
            self.ui.txt_final_coil_temperature.setStyleSheet("color: red")
            error_text.append("Final Coil Temp is more than 20 C above Ambient.")
            error_text.append("Final Coil Temp exceeds motor rating.")
        else:
            self.ui.txt_final_coil_temperature.setStyleSheet("color: rgb(0, 0, 0);")
        if stageType == "Screw-Drive Linear": #STO
            if self.peak_torque > rated_peak_torque:
                self.ui.txt_peak_torque_required.setStyleSheet("color: red")
                error_text.append("Peak Torque Required exceeds motor rating.")
            elif self.peak_torque > rated_peak_torque*.8:
                self.ui.txt_peak_torque_required.setStyleSheet("color: orange")
                error_text.append("Warning: Peak Torque Required within 80% of motor rating.")
            else:
                self.ui.txt_peak_torque_required.setStyleSheet("color: rgb(0, 0, 0);")

            if self.rms_torque > rated_cont_torque:
                self.ui.txt_rms_torque.setStyleSheet("color: red")
                error_text.append("RMS Torque Required exceeds motor rating.")
            elif self.rms_torque > rated_cont_torque*.8:
                self.ui.txt_rms_torque.setStyleSheet("color: orange")
                error_text.append("Warning: RMS Torque Required within 80% of motor rating.")
            else:
                self.ui.txt_rms_torque.setStyleSheet("color: rgb(0, 0, 0);")

        if self.ui.txt_peak_output_current.text():
            if self.peak_current > float(self.ui.txt_peak_output_current.text()):
                self.ui.txt_peak_current_required.setStyleSheet("color: red")
                error_text.append("Peak Current Required exceeds drive rating.")
            elif self.peak_current > float(self.ui.txt_peak_output_current.text())*.8:
                self.ui.txt_peak_current_required.setStyleSheet("color: orange")
                error_text.append("Warning: Peak Current Required within 80% of drive rating.")
            else:
                self.ui.txt_peak_current_required.setStyleSheet("color: rgb(0, 0, 0);")

        if self.ui.txt_continuous_output_current.text():
            if self.rms_current > float(self.ui.txt_continuous_output_current.text()):
                self.ui.txt_rms_current_required.setStyleSheet("color: red")
                error_text.append("RMS Current Required exceeds drive rating.")
            elif self.rms_current > float(self.ui.txt_continuous_output_current.text())*.8:
                self.ui.txt_rms_current_required.setStyleSheet("color: orange")
                error_text.append("Warning: RMS Current Required within 80% of drive rating.")
            else:
                self.ui.txt_rms_current_required.setStyleSheet("color: rgb(0, 0, 0);")
        if stageType == "Screw-Drive Linear":
            if self.rated_speed:
                if self.peak_motor_speed > self.rated_speed:
                    self.ui.txt_peak_motor_speed.setStyleSheet("color: red")
                    error_text.append("Peak Motor Speed exceeds motor rating.")
                else:
                    self.ui.txt_peak_motor_speed.setStyleSheet("color: rgb(0, 0, 0);")

            if self.rated_power_output:
                if self.rms_power_output > self.rated_power_output:
                    self.ui.txt_rms_power_output.setStyleSheet("color: red")
                    #print(str(self.rated_power_output))
                    error_text.append("Power Loss exceeds motor rating.") #changed from RMS Power Output to Power Loss
                else:
                    self.ui.txt_rms_power_output.setStyleSheet("color: rgb(0, 0, 0);")

        if bus_voltage:
            if self.bus_voltage_required > bus_voltage:
                self.ui.txt_bus_voltage_required.setStyleSheet("color: red")
                error_text.append("Move requires more Bus Voltage than is available.")
            elif self.bus_voltage_required > bus_voltage*.8:
                self.ui.txt_bus_voltage_required.setStyleSheet("color: orange")
                error_text.append("Warning: Move requires more than 80% of available Bus Voltage.")
            else:
                self.ui.txt_bus_voltage_required.setStyleSheet("color: rgb(0, 0, 0);")

        if error_text:
            for error in error_text:
                self.ui.txt_error_output.appendPlainText(error)

        if image_name:
            image_name.append(".jpg")
            self.ui.btn_current_limitation_browser.setVisible(True)

        if image:
            if image_name:
                # print(image_name)
                return "".join(image_name)
            else:
                return False

    def new(self):
        """Creates New file for user. First checks if current file is saved."""
        global filepath
        global temp_filepath
        save_state = None

        if filepath:
            con = lite.connect(filepath)
            with con:
                cur = con.cursor()
                cur.execute("SELECT SaveState FROM Save")
                save_state = cur.fetchone()[0]

        if save_state == "Not Saved" or not filepath:
            msg = QtWidgets.QMessageBox()
            msg.setText("Would you like to first save changes to current file?")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setWindowTitle("Save Before Close?")
            msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No |
                                   QtWidgets.QMessageBox.Cancel)
            reply = msg.exec_()
            if reply == QtWidgets.QMessageBox.Yes:
                self.save()
            elif reply == QtWidgets.QMessageBox.Cancel:
                return

        self.clear_results()
        self.ui.stage_config_input.selectAll()
        self.ui.stage_config_input.del_()
        self.ui.motor_name.setText("")
        self.ui.cmb_drive_select.setCurrentIndex(0)
        self.ui.cmb_select_bus_voltage.setCurrentIndex(0)
        self.ui.txt_payload.clear()
        self.ui.txt_orientation.clear()
        self.ui.txt_ambient_temperature.clear()
        self.ui.cmb_vacuum.setCurrentIndex(0)
        self.ui.cmb_input_voltage.setCurrentIndex(0)
        self.ui.btn_current_limitation_browser.setVisible(False)
        self.ui.cmb_aircooling.setCurrentIndex(0)
        self.ui.txt_stage_type.setText("")

        date_string = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-4]
        if not getattr(sys, 'frozen', False):
            temp_filepath = dir_path + r"\Temp Files\\" + date_string + ".amszr"
        else:
            temp_filepath = pf_path + r"\Temp Files\\" + date_string + ".amszr"
        filepath = None

        # create new temp file to work with
        con = lite.connect(temp_filepath)
        with con:
            cur = con.cursor()
            cur.execute(
                "CREATE TABLE IF NOT EXISTS [Profile](id INTEGER PRIMARY KEY, Operation INTEGER, Type TEXT, Parameters TEXT,"
                " Brake TEXT)")
            cur.execute("CREATE TABLE IF NOT EXISTS [Save] (id INTEGER PRIMARY KEY, SaveState TEXT, Time DATETIME)")
            cur.execute(
                "CREATE TABLE IF NOT EXISTS [Inputs] (id INTEGER PRIMARY KEY, Stage TEXT, Motor TEXT, Drive TEXT,"
                " BusVoltage TEXT, Payload TEXT, Orientation TEXT, Temperature TEXT, Vacuum TEXT, Voltage TEXT)")

        self.refresh_plot()
        self.db = Database()
        self.model = Model(self)
        self.ui.list_motion.setModel(self.model)
        self.calc_results()

    def save(self):
        """Saves current file.

        Copies current temp file over Save File. Sets Save State to 'Saved'.

        """
        from shutil import copyfile  # local import to reduce startup time
        import time  # local import to reduce startup time
        global filepath

        if len(sys.argv) < 2 and not filepath:
            filepath = QtWidgets.QFileDialog.getSaveFileName(filter="Sizer (*.amszr)")[0]
            if not filepath:
                return
        elif not filepath:
            filepath = str(sys.argv[1])

            con = lite.connect(filepath)
            with con:
                cur = con.cursor()
                cur.execute("SELECT SaveState From Save")
                save_state = cur.fetchone()[0]
                if save_state == "Saved":
                    return

        copyfile(temp_filepath, filepath)

        while not os.access(filepath, os.W_OK):
            time.sleep(.1)
        con = lite.connect(filepath)
        with con:
            cur = con.cursor()
            cur.execute("INSERT OR IGNORE INTO Save (id, SaveState, Time) VALUES (1, 'Saved', '%s')"
                        % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            cur.execute("UPDATE Save SET SaveState='Saved', Time='%s' WHERE id=1"
                        % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        con.commit()

    def saveAs(self):
        """Saves current file to new path via File Dialog."""
        from shutil import copyfile  # local import to reduce startup time
        import time  # local import to reduce startup time
        global filepath

        cancel_filepath = filepath
        filepath = QtWidgets.QFileDialog.getSaveFileName(filter="Sizer (*.amszr)")[0]
        if not filepath:
            filepath = cancel_filepath
            return
        copyfile(temp_filepath, filepath)

        while not os.access(filepath, os.W_OK):
            time.sleep(.1)
        con = lite.connect(filepath)
        with con:
            cur = con.cursor()
            cur.execute("INSERT OR IGNORE INTO Save (id, SaveState, Time) VALUES (1, 'Saved', '%s')"
                        % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
            cur.execute("UPDATE Save SET SaveState='Saved', Time='%s' WHERE id=1"
                        % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        con.commit()

    def print(self):
        """Creates PDF of current sizer information"""
        from reportlab.lib.pagesizes import letter  # moved local reduce startup time
        from reportlab.pdfgen import canvas  # moved local reduce startup time
        from reportlab.pdfbase import pdfmetrics, ttfonts  # moved local reduce startup time
        from lxml import html
        import requests
        import re
        global dir_path

        con = lite.connect(temp_filepath)
        with con:
            cur = con.cursor()
            cur.execute("SELECT * FROM Profile ORDER BY Operation ASC")
            records = cur.fetchall()
        
        msg = QtWidgets.QMessageBox()
        msg.setText("Print functionality not supported! Updated website references expected Fall 2021")
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setWindowTitle("Print Function Unsupported")
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.exec_()
        return        
        # exit function if no Stage/Motor selected or if no Profile has been defined.
        if self.ui.stage_config_input.selectAll == ''\
                or self.ui.motor_name.text() == ""\
                or not records:
            msg = QtWidgets.QMessageBox()
            msg.setText("Stage, Motor, and Motion Profile must all be defined to print results. "
                        "Please specify these items and try again.")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setWindowTitle("Print Error")
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
            return

        output_file = QtWidgets.QFileDialog.getSaveFileName(filter="PDF (*.pdf")[0]
        if not output_file:
            return

        if not getattr(sys, 'frozen', False):
            logo = "AerotechLogo.png"
        else:
            logo = resource_path("AerotechLogo.png")

        pdfmetrics.registerFont(ttfonts.TTFont('Open Sans', resource_path('fonts/OpenSans-Regular.ttf')))
        pdfmetrics.registerFont(ttfonts.TTFont('Saira', resource_path('fonts/Saira-Regular.ttf')))
        pdfmetrics.registerFont(ttfonts.TTFont('Saira Bold', resource_path('fonts/Saira-Bold.ttf')))

        pdf = canvas.Canvas(output_file, pagesize=letter)  # note pdf is 612 px wide x 792 px high

        # logo in header with line under it
        logo_w = 2555/12
        logo_h = 424/12
        pdf.drawImage(logo, 612-logo_h-logo_w, 792-logo_h*1.5, width=logo_w, height=logo_h)
        pdf.setLineWidth(.7)
        pdf.line(612/2, 792-logo_h*1.75, 612-logo_h*.5, 792-logo_h*1.75)

        # section headings
        pdf.setFont('Saira Bold', 22)
        pdf.drawString(40, 792 - 90, "Motion")
        pdf.drawString(40, 792 - 370, "Stage")
        pdf.drawString(250, 792 - 370, "Motor")
        pdf.drawString(450, 792 - 370, "Drive")
        pdf.drawString(40, 792 - 570, "Application")
        pdf.drawString(250, 792 - 570, "Results")

        # add plot to pdf
        date_string = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-4]
        if not getattr(sys, 'frozen', False):
            plot_path = dir_path + r"\Temp Files\\" + "print_plot" + date_string + ".png"  # saves in temp file dir
        else:
            plot_path = pf_path + r"\Temp Files\\" + "print_plot" + date_string + ".png"  # saves in temp file dir
        self.plotWidget.canvas.fig.savefig(plot_path, dpi=150)  # specify dpi to make sure it looks good
        pdf.drawImage(plot_path, 40, 792 - 350, 512, 250)

        # add stage, motor, and drive selections
        pdf.setFont('Open Sans', 14)
        #print(self.ui.stage_config_input.text())
        motor = self.ui.motor_name.text().split("(")
        motor = motor[0].rstrip()
        pdf.drawString(40, 792 - 390, self.ui.stage_config_input.text().strip())
        pdf.drawString(250, 792 - 390, motor)
        pdf.drawString(450, 792 - 390, self.ui.cmb_drive_select.currentText())

        # add hyperlinks
        con = lite.connect(db_filepath)
        with con:
            cur = con.cursor()
            cur.execute("SELECT * FROM Drives WHERE Name='%s'" % self.ui.cmb_drive_select.currentText())
            drive_record = cur.fetchone()
            drive_url = str(drive_record[8])
            drive_img = str(drive_record[9])
        
            # cur.execute("SELECT * FROM Motors WHERE Name='%s'" % self.ui.motor_name.text())
            # motor_record = cur.fetchone()
            # motor_url = str(motor_record[29])        i
            # motor_img = str(motor_record[37])
            # cur.execute("SELECT * FROM Stages WHERE Name='%s'" % self.ui.cmb_stage_select.currentText())
            # stage_record = cur.fetchone()       
            # stage_url = str(stage_record[40])
            # stage_img = str(stage_record[44])
        if not getattr(sys, 'frozen', False):
            img_path = dir_path + r"\Temp Files\\" # saves in temp file dir
        else:
            img_path = pf_path + r"\Temp Files\\"   # saves in temp file dir
            
        motor = self.ui.motor_name.text().split("(")
        motor = motor[0].rstrip()
        self.config_sizer = ConfigSizer()
        self.config_options = QtSql.QSqlTableModel(db = self.config_sizer.data)
        self.config_options.setTable(motor + "_TemplateSpecs")
        self.config_options.select()
        self.config_options.setFilter("SpecName LIKE 'URL'")
        self.config_options.select()
        if not self.config_options.rowCount() == 0:
            page = requests.get(self.config_options.record(0).value("Value"))
            #print(self.config_options.record(0).value("Value"))
            html = page.text
            #print(html)
            pat = re.compile(r'<\s*img [^>]*src="([^"]+)')
            img = pat.findall(html)
            motor_url="None"
            motor_img="None"
            #print(img)
            for image in img:
                if image.endswith("1000x1000-resize-ffffff.jpg"):
                    with open(img_path + 'motor.jpg', 'wb') as outf:
                        data = requests.get("https://www.aerotech.com" + image).content
                        outf.write(data)
                    motor_url = str(self.config_options.record(0).value("Value"))
                    motor_img = 'motor.jpg'
                elif image.endswith("1000x1000-resize-ffffff.png"):
                    with open(img_path+'motor.png', 'wb') as outf:
                        data = requests.get("https://www.aerotech.com" + image).content
                        outf.write(data)   
                    motor_url = str(self.config_options.record(0).value("Value"))
                    motor_img = 'motor.png'                
        
        stage = self.ui.stage_config_input.text().strip()
        self.config_options.setTable(stage + "_TemplateSpecs")
        self.config_options.select()
        self.config_options.setFilter("SpecName LIKE 'URL'")
        self.config_options.select()
        
        if not self.config_options.rowCount() == 0:
            page = requests.get(self.config_options.record(0).value("Value"))
            html = page.text
            #print(html)
            pat = re.compile(r'<\s*img [^>]*src="([^"]+)')
            img = pat.findall(html)
            for image in img:
                stage_url="None"
                stage_img="None"
                #print(image)
                if image.endswith("1000x1000-resize-ffffff.jpg"):
                    with open(img_path+'stage.jpg', 'wb') as outf:
                        data = requests.get("https://www.aerotech.com" + image).content
                        outf.write(data)   
                    stage_url = str(self.config_options.record(0).value("Value"))
                    stage_img = 'stage.jpg'
                elif image.endswith("1000x1000-resize-ffffff.png"):
                    with open(img_path+'stage.png', 'wb') as outf:
                        data = requests.get("https://www.aerotech.com" + image).content
                        outf.write(data)   
                    stage_url = str(self.config_options.record(0).value("Value"))
                    stage_img = 'stage.png'
            #print(img)
                    
        else:
            stage_url = "None"
            stage_img = "None"
        pdf.setFont('Open Sans', 11)
        pdf.setFillColorRGB(0.0234375, 0.26953125, 0.67578125)  # only accepts 0-1... so this is 6/256, 69/256, 173/256
        pdf.drawString(40, 792 - 405, "link")
        pdf.linkURL(stage_url, (40, 792 - 410, 60, 792 - 395), relative=0, thickness=0)
        if not motor_url == "None":
            pdf.drawString(250, 792 - 405, "link")
            pdf.linkURL(motor_url, (250, 792 - 410, 270, 792 - 395), relative=0, thickness=0)
        if not drive_url == "None":
            pdf.drawString(450, 792 - 405, "link")
            pdf.linkURL(drive_url, (450, 792 - 410, 470, 792 - 395), relative=0, thickness=0)

        # add images
        if not stage_img == "None":
            pdf.drawImage(img_path+stage_img, 40, 792 - 550, width=150, height=150,
                          preserveAspectRatio=True, anchor='c')
        if not motor_img == "None":
            pdf.drawImage(img_path+motor_img, 250, 792 - 550, width=150, height=150,
                          preserveAspectRatio=True, anchor='c')
        if not drive_img == "None":
            pdf.drawImage(resource_path("imgs/" + drive_img), 450, 792 - 550, width=150, height=150,
                          preserveAspectRatio=True, anchor='c')

        # add app info
        pdf.setFont('Open Sans', 12)
        pdf.setFillColorRGB(0, 0, 0)
        if str(self.ui.txt_payload.text()) == "":
            pdf.drawString(40, 792 - 590, "Payload: 0 kg")
        else:
            pdf.drawString(40, 792 - 590, "Payload: " + str(self.ui.txt_payload.text()) + " kg")
        if str(self.ui.txt_orientation.text()) == "" or str(self.ui.txt_orientation.text()) == "0":
            pdf.drawString(40, 792 - 607, "Orientation: Horizontal")
        elif str(self.ui.txt_orientation.text()) == "90":
            pdf.drawString(40, 792 - 607, "Orientation: Vertical")
        else:
            pdf.drawString(40, 792 - 607, "Orientation: " + str(self.ui.txt_orientation.text()) + " deg")
        if str(self.ui.txt_ambient_temperature.text()) == "":
            pdf.drawString(40, 792 - 624, "Ambient Temp: 20 C")
        else:
            pdf.drawString(40, 792 - 624, "Ambient Temp: " + str(self.ui.txt_ambient_temperature.text()) + " C")
        pdf.drawString(40, 792 - 641, "Vacuum?: " + self.ui.cmb_vacuum.currentText())
        pdf.drawString(40, 792 - 658, "Input Voltage: " + self.ui.cmb_input_voltage.currentText())

        def set_color(pdf, style_sheet):
            if "color: red" in style_sheet:
                pdf.setFillColorRGB(1, 0, 0)
            elif "color: orange" in style_sheet:
                pdf.setFillColorRGB(1, .64, 0)
            else:
                pdf.setFillColorRGB(0, 0, 0)
            return

        # add results
        set_color(pdf, self.ui.txt_peak_torque_required.styleSheet())
        pdf.drawString(250, 792 - 590, "Peak Torque: " + str(self.ui.txt_peak_torque_required.text()))
        set_color(pdf, self.ui.txt_rms_torque.styleSheet())
        pdf.drawString(250, 792 - 607, "RMS Torque: " + str(self.ui.txt_rms_torque.text()))
        set_color(pdf, self.ui.txt_bus_voltage_required.styleSheet())
        pdf.drawString(250, 792 - 624, "Bus Voltage: " + str(self.ui.txt_bus_voltage_required.text()))
        set_color(pdf, self.ui.txt_peak_power_output.styleSheet())
        pdf.drawString(250, 792 - 641, "Peak Power: " + str(self.ui.txt_peak_power_output.text()))
        set_color(pdf, self.ui.txt_rms_power_output.styleSheet())
        pdf.drawString(250, 792 - 658, "RMS Power: " + str(self.ui.txt_rms_power_output.text()))
        set_color(pdf, self.ui.txt_duty_cycle.styleSheet())
        pdf.drawString(250, 792 - 675, "Duty Cycle: " +
                       str(round(float(self.ui.txt_duty_cycle.text()
                                       [:self.ui.txt_duty_cycle.text().find("%")]))) + "%")
        set_color(pdf, self.ui.txt_peak_motor_speed.styleSheet())
        pdf.drawString(400, 792 - 590, "Peak Motor Speed: " +
                       str((self.ui.txt_peak_motor_speed.text()
                                       )))
        set_color(pdf, self.ui.txt_peak_current_required.styleSheet())
        pdf.drawString(400, 792 - 607, "Peak Current: " + str(self.ui.txt_peak_current_required.text()))
        set_color(pdf, self.ui.txt_rms_current_required.styleSheet())
        pdf.drawString(400, 792 - 624, "RMS Current: " + str(self.ui.txt_rms_current_required.text()))
        set_color(pdf, self.ui.txt_final_coil_temperature.styleSheet())
        pdf.drawString(400, 792 - 641, "Final Coil Temp: " + str(self.ui.txt_final_coil_temperature.text()))
        set_color(pdf, self.ui.txt_rolling_rms_current.styleSheet())
        pdf.drawString(400, 792 - 658, "Max Rolling RMS Current: " + str(self.ui.txt_rolling_rms_current.text()))
        set_color(pdf, self.ui.txt_sto_current.styleSheet())
        pdf.drawString(400, 792 - 675, "STO Current: " + str(self.ui.txt_sto_current.text()))
        pdf.setFont('Open Sans', 10)
        pdf.setFillColorRGB(0, 0, 0)
        if str(self.ui.txt_error_output.toPlainText()) == "":
            pdf.drawString(250, 792 - 692, "No errors or warnings.")
        else:
            text_object = pdf.beginText(250, 792 - 692)
            text_object.textLines(str(self.ui.txt_error_output.toPlainText()))
            pdf.drawText(text_object)

        pdf.showPage()
        pdf.save()

    def open(self, path=None):
        """Opens existing file. Checks if current file is saved.

        Args:
            path (str, optional): string of full filepath to be opened. Only used when this function is invoked due
                to application being launched from user double-clicking .bszr file. Defaults to None.

        """
        from shutil import copyfile  # local import to reduce startup time
        global filepath
        global temp_filepath
        save_state = None

        if not path:
            if filepath:
                con = lite.connect(filepath)
                with con:
                    cur = con.cursor()
                    cur.execute("SELECT SaveState FROM Save")
                    save_state = cur.fetchone()[0]

            if save_state == "Not Saved" or not filepath:
                msg = QtWidgets.QMessageBox()
                msg.setText("Would you like to first save changes to current file?")
                msg.setWindowTitle("Save Before Close?")
                msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No |
                                       QtWidgets.QMessageBox.Cancel)
                msg.exec_()
                if msg == QtWidgets.QMessageBox.Yes:
                    self.save()
                elif msg == QtWidgets.QMessageBox.Cancel:
                    return

            cancel_filepath = filepath
            filepath = QtWidgets.QFileDialog.getOpenFileName(filter="Sizer (*.amszr)")[0]
            if not filepath:
                filepath = cancel_filepath
                return
            date_string = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-4]
            if not getattr(sys, 'frozen', False):
                temp_filepath = dir_path + r"\Temp Files\\" + date_string + ".amszr"
            else:
                temp_filepath = pf_path + r"\Temp Files\\" + date_string + ".amszr"
            copyfile(filepath, temp_filepath)
        else:
            filepath = path
            date_string = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")[:-4]
            if not getattr(sys, 'frozen', False):
                temp_filepath = dir_path + r"\Temp Files\\" + date_string + ".amszr"
            else:
                temp_filepath = pf_path + r"\Temp Files\\" + date_string + ".amszr"
            copyfile(filepath, temp_filepath)

        self.refresh_plot()
        self.configured = True
        self.clear_results()
        self.ui.stage_config_input.selectAll()
        self.ui.stage_config_input.del_()
        self.ui.motor_name.setText("")
        self.ui.cmb_drive_select.setCurrentIndex(0)
        self.ui.cmb_select_bus_voltage.setCurrentIndex(0)
        self.ui.txt_payload.clear()
        self.ui.txt_orientation.clear()
        self.ui.txt_ambient_temperature.clear()
        self.ui.cmb_vacuum.setCurrentIndex(0)
        self.ui.cmb_input_voltage.setCurrentIndex(0)
        self.ui.cmb_aircooling.setCurrentIndex(0)

        con = lite.connect(filepath)
        with con:
            cur = con.cursor()
            cur.execute("SELECT * FROM Inputs")
            inputs = cur.fetchone()
        #print(inputs)
        # index = self.ui.stage_config_input.findText(inputs[1])
        #print(inputs[1])
        self.ui.stage_smart_string.setText(inputs[1])
        motor= inputs[2]#.split("-")
        stage = inputs[1].split("-")
        if inputs[1] !="":
            if (stage[0].endswith("SL") or stage[0].endswith("SLE")) and stage[0].startswith("PRO"):
                if stage[0].endswith("SLE"):
                    stage[0] = stage[0][:-3]
                else:
                    stage[0] = stage[0][:-2]
            self.ui.stage_config_input.setText(stage[0])
            #self.ui.motor_name.setText(inputs[2])
            #print(inputs[1])
            motor,motorType,motor_spec_names,motor_spec_vals,stage,stageType,stage_spec_names,stage_spec_vals,stage_config =PopupConfig.return_values(stage =inputs[1])
            #print(stageType)
            
            self.on_stage_change(stage,stageType,stage_spec_names,stage_spec_vals,stage_config)
            self.on_motor_change(motor)#,motorType,motor_spec_names,motor_spec_vals)
            self.refresh_plot()
        else: 
            motor,motorType,motor_spec_names,motor_spec_vals,stage,stageType,stage_spec_names,stage_spec_vals,stage_config =PopupConfig.return_values(stage =inputs[2])
            self.on_motor_change(inputs[2])#,motorType,motor_spec_names,motor_spec_vals)
            self.refresh_plot()
        #print("stage type: " + stageType)
        #print(motor)

        #sleep(5)
        # if index >= 0:
            # self.ui.stage_config_input.setCurrentIndex(index)
        # index = self.ui.stage_config_input.findText(inputs[2])
        # if index >= 0:
            # self.ui.cmb_motor_select.setCurrentIndex(index)
        index = self.ui.cmb_drive_select.findText(inputs[3])
        if index >= 0:
            self.ui.cmb_drive_select.setCurrentIndex(index)
        index = self.ui.cmb_select_bus_voltage.findText(inputs[4])
        if index >= 0:
            self.ui.cmb_select_bus_voltage.setCurrentIndex(index)
        if inputs[5]:
            self.ui.txt_payload.setText(inputs[5])
        if inputs[6]:
            self.ui.txt_orientation.setText(inputs[6])
        if inputs[7]:
            self.ui.txt_ambient_temperature.setText(inputs[7])
        index = self.ui.cmb_vacuum.findText(inputs[8])
        if index >= 0:
            self.ui.cmb_vacuum.setCurrentIndex(index)
        index = self.ui.cmb_input_voltage.findText(inputs[9])
        if index >= 0:
            self.ui.cmb_input_voltage.setCurrentIndex(index)
        if "-AC" in inputs[2]:
            self.ui.cmb_aircooling.setCurrentIndex(1)

        self.db = Database()
        self.model = Model(self)
        self.ui.list_motion.setModel(self.model)
        self.ui.list_motion.selectRow(self.model.rowCount() - 1)
        self.calc_results()

    def closeEvent(self, event):
        """Overwrites default closeEvent behavior to inject save-before-exit? dialog."""
        global filepath
        save_state = None

        if filepath:
            con = lite.connect(filepath)
            with con:
                cur = con.cursor()
                cur.execute("SELECT SaveState FROM Save")
                save_state = cur.fetchone()[0]

        if save_state == "Not Saved" or not filepath:
            msg = QtWidgets.QMessageBox()
            msg.setText("Would you like to first save changes to current file?")
            msg.setWindowTitle("Save Before Close?")
            msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No |
                                   QtWidgets.QMessageBox.Cancel)
            reply = msg.exec_()
            if reply == QtWidgets.QMessageBox.Yes:
                self.save()
                event.accept()
            elif reply == QtWidgets.QMessageBox.No:
                event.accept()
            elif reply == QtWidgets.QMessageBox.Cancel:
                event.ignore()

    def file_change(self):
        """Sets Save State to 'Not Saved'. Runs on every input change and profile change."""
        if filepath:
            con = lite.connect(filepath)
            with con:
                cur = con.cursor()
                cur.execute("UPDATE Save SET SaveState = 'Not Saved', Time = '%s'"
                            % datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                con.commit()

    def store_inputs(self):
        """Stores inputs in temp file. Runs on every input change"""
        con = lite.connect(temp_filepath)
        with con:
            cur = con.cursor()
            cur.execute("INSERT OR IGNORE INTO Inputs (id, Stage, Motor, Drive, BusVoltage, Payload, Orientation,"
                        " Temperature, Vacuum, Voltage) VALUES (1,?,?,?,?,?,?,?,?,?)",
                        (self.ui.stage_smart_string.text(), self.ui.motor_smart_string.text(),
                         self.ui.cmb_drive_select.currentText(), self.ui.cmb_select_bus_voltage.currentText(),
                         self.ui.txt_payload.text(), self.ui.txt_orientation.text(),
                         self.ui.txt_ambient_temperature.text(), self.ui.cmb_vacuum.currentText(),
                         self.ui.cmb_input_voltage.currentText()))
            cur.execute("UPDATE Inputs SET Stage=?, Motor=?, Drive=?, BusVoltage=?, Payload=?, Orientation=?,"
                        " Temperature=?, Vacuum=?, Voltage=?",
                        (self.ui.stage_smart_string.text(), self.ui.motor_smart_string.text(),
                         self.ui.cmb_drive_select.currentText(), self.ui.cmb_select_bus_voltage.currentText(),
                         self.ui.txt_payload.text(), self.ui.txt_orientation.text(),
                         self.ui.txt_ambient_temperature.text(), self.ui.cmb_vacuum.currentText(),
                         self.ui.cmb_input_voltage.currentText()))
        con.commit()

    def show_current_limitation_browser(self):
        """Makes calls to set Current Limitation Browser button to Visible and passes image filename."""
        image = self.calc_results(image=True)
        if image:
            Image(image=image)

    def convert_bus_voltage_text(self, text):
        """Cleans bus voltage input.

        Args:
            text (str): bus voltage as a string (+/-40 or 60).

        Returns:
            int: bus voltage scaled by 2 if +/- is in string. Nothing if text is empty string.

        """
        if text:
            if "+/-" in text:
                bus_voltage = int(text.replace('+/-', ''))*2
            else:
                bus_voltage = int(text)
            return bus_voltage
        else:
            print("text = None")
            return

    def clear_results(self):
        """Clears text from all result text fields."""
        #print("Clearing Results")
        self.ui.txt_peak_torque_required.clear()
        self.ui.txt_rms_torque.clear()
        self.ui.txt_peak_motor_speed.clear()
        self.ui.txt_peak_power_output.clear()
        self.ui.txt_rms_power_output.clear()
        self.ui.txt_bus_voltage_required.clear()
        self.ui.txt_peak_current_required.clear()
        self.ui.txt_rms_current_required.clear()
        self.ui.txt_final_coil_temperature.clear()
        self.ui.txt_duty_cycle.clear()
        self.ui.txt_rolling_rms_current.clear()
        self.ui.txt_sto_current.clear()
        self.ui.txt_error_output.clear()
        self.ui.stage_smart_string.setText("")
        self.ui.stage_param_txt_1.setText("")
        self.ui.stage_param_txt_2.setText("")
        self.ui.stage_param_txt_3.setText("")
        self.ui.stage_param_txt_4.setText("")
        self.ui.stage_param_txt_5.setText("")
        self.ui.stage_param_txt_6.setText("")
        #self.ui.motor_name.setText("")
        self.ui.txt_motor_type.setText("")
        self.ui.txt_stage_type.setText("")
        self.ui.motor_param_txt_1.setText("")
        self.ui.motor_param_txt_2.setText("")
        self.ui.motor_param_txt_3.setText("")
        self.ui.motor_param_txt_4.setText("")
        self.ui.motor_param_txt_5.setText("")
        self.ui.motor_param_txt_6.setText("")
        self.ui.motor_param_txt_7.setText("")
        self.ui.motor_param_txt_8.setText("")

    def bus_voltage_visible(self):
        """Displays or hides Bus Voltage drop-down as appropriate."""
        drive = self.ui.cmb_drive_select.currentText()
        self.db_sizer = DatabaseSizer()
        #con.close()
        if drive:
            #DatabaseSizer()
            con = lite.connect(db_filepath)
            with con:
                cur = con.cursor()
                cur.execute("SELECT * FROM Drives WHERE Name='%s'" % drive)
                drive_record = cur.fetchone()
                #print(drive_record)
            if drive_record[7] == None:
                self.ui.cmb_select_bus_voltage.clear()
                self.ui.lbl_select_bus_voltage.setVisible(False)
                self.ui.cmb_select_bus_voltage.setVisible(False)
            else:
                self.ui.lbl_select_bus_voltage.setVisible(True)
                self.ui.cmb_select_bus_voltage.setVisible(True)
                self.model_bus_voltage = QtSql.QSqlTableModel(self, db=self.db_sizer.data)
                self.model_bus_voltage.setTable("BusVoltages")                
                filter_string = str(drive_record[7]) + " NOT NULL"
                self.model_bus_voltage.setFilter(filter_string)
                self.model_bus_voltage.select()
                self.ui.cmb_select_bus_voltage.setModel(self.model_bus_voltage)
                bus_voltage_dictionary = {
                    'Npaq': 1,
                    'NpaqMR': 3,
                    'Npaq6U': 5,
                    'Epaq': 7,
                    'EpaqMR': 9,
                    'XR3': 11,
                    'XL5e': 13,
                    'ML':15
                }
                self.ui.cmb_select_bus_voltage.setModelColumn(bus_voltage_dictionary[drive_record[7]])

    def set_units(self):
        #print(self.ui.txt_stage_type.text())
        self.stage_type=self.ui.txt_stage_type.text()
        #print(self.stage_type)

        """Grabs units from master db and sets labels accordingly."""

    def show_dwell_dialog(self, duration=None, id=None):
        """Calls appropriate popup class and retrieves user values. Checks validity. Calls for plot and calc updates.

        Args:
            duration (str, optional): duration in seconds, passed if called via Edit Profile function. Defaults to None.
            id (str, optional): row id of selected move, passed if called via Edit Profile function. Defaults to None.

        """
        if not duration:
            dwell_duration, ok = PopupDwell.return_values()
        else:
            dwell_duration, ok = PopupDwell.return_values(duration=duration)
        if not ok:
            return
        if self.invalid_motion_profile("dwell"):
            return
        if ok:
            if not dwell_duration or float(dwell_duration) <= 0:
                msg = QtWidgets.QMessageBox()
                msg.setText("Please specify a valid Dwell Duration. "
                            "Blank, zero, and negative values are not acceptable. Please try again.")
                msg.setWindowTitle("Invalid Profile!")
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()
                return
            param = "duration=" + dwell_duration + ";"
            con = lite.connect(temp_filepath)
            with con:
                cur = con.cursor()
                if not id:
                    cur.execute("SELECT COUNT (id) FROM Profile")
                    op = cur.fetchone()[0] + 1
                    cur.execute("INSERT INTO Profile (Operation, Type, Parameters) VALUES (?,?,?)", (op, "Dwell", param))
                else:
                    cur.execute("UPDATE Profile SET Parameters=? WHERE id=?", (param, str(id)))
            con.commit()
            self.file_change()
            self.refresh_plot()
            self.model = Model(self)
            self.ui.list_motion.setModel(self.model)
            self.ui.list_motion.selectRow(self.model.rowCount()-1)
            self.calc_results()

    def show_inertia_calc(self, inertia=None):
    
        if not inertia:
            inertia,ok = PopupInertiaCalc.return_values()
            if not ok:
                return
            print(ok)
        else:
            inertia,ok = PopupInertiaCalc.return_values(inertia=inertia,completed=False)
        if ok:
            print("function okay")
            self.ui.txt_payload.setText(str(round(inertia,6)))
            self.calc_results()
        if not ok:
            return
        self.file_change()
        self.refresh_plot()
        self.model = Model(self)
        
        
    
    def show_decel_to_zero_dialog(self, rate=None, ramp_type=None, stage_type=None, motor_type=None, id=None):
        """Calls appropriate popup class and retrieves user values. Checks validity. Calls for plot and calc updates.

        Args:
            rate (str, optional): decel rate in mm/s^2, passed if called via Edit Profile function. Defaults to None.
            ramp_type (str, optional): ramp type, passed if called via Edit Profile function. Defaults to None.
            id (str, optional): row id of selected move, passed if called via Edit Profile function. Defaults to None.

        """
        stage_type = self.ui.txt_stage_type.text()
        motor_type = self.ui.txt_motor_type.text()
        if not rate:
            decel_rate, decel_type, stage_type, motor_type, ok = PopupDecelToZero.return_values(stage_type=stage_type,motor_type=motor_type)
            if not ok:
                return
            if self.invalid_motion_profile("decel to zero"):
                return
        else:
            decel_rate, decel_type, stage_type, ok = PopupDecelToZero.return_values(rate=rate, ramp_type=ramp_type, stage_type=stage_type, motor_type=motor_type)
        if ok:
            if not decel_rate or float(decel_rate) <= 0:
                msg = QtWidgets.QMessageBox()
                msg.setText("Please specify a valid Decel Rate. "
                            "Blank, zero, and negative values are not acceptable. Please try again.")
                msg.setWindowTitle("Invalid Profile!")
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()
                return
            param = "decel_rate=" + decel_rate + ";decel_type=" + decel_type + ";"
            con = lite.connect(temp_filepath)
            with con:
                cur = con.cursor()
                if not id:
                    cur.execute("SELECT COUNT (id) FROM Profile")
                    op = cur.fetchone()[0] + 1
                    cur.execute("INSERT INTO Profile (Operation, Type, Parameters) VALUES (?,?,?)", (op, "Decel to Zero", param))
                else:
                    cur.execute("UPDATE Profile SET Parameters=? WHERE id=?", (param, str(id)))
            con.commit()
            self.file_change()
            self.refresh_plot()
            self.model = Model(self)
            self.ui.list_motion.setModel(self.model)
            self.ui.list_motion.selectRow(self.model.rowCount()-1)
            self.calc_results()
        else:
            return

    def show_accel_decel_dialog(self, rate=None, vel=None, ramp_type=None, stage_type=None, motor_type=None, id=None):
        """Calls appropriate popup class and retrieves user values. Checks validity. Calls for plot and calc updates.

        Args:
            rate (str, optional): ramp rate in mm/s^2, passed if called via Edit Profile function. Defaults to None.
            vel (str, optional): velocity in mm/s, passed if called via Edit Profile function. Defaults to None.
            ramp_type (str, optional): ramp type, passed if called via Edit Profile function. Defaults to None.
            id (str, optional): row id of selected move, passed if called via Edit Profile function. Defaults to None.

        """
        stage_type = self.ui.txt_stage_type.text()
        motor_type = self.ui.txt_motor_type.text()
        if not rate:
            accel_decel_rate, velocity, accel_decel_type, stage_type, motor_type, ok = PopupAccelDecel.return_values(stage_type=stage_type, motor_type=motor_type)
            if accel_decel_type == "Sinusoidal":
                accel_decel_rate = str(float(accel_decel_rate))  #deleted a redundent *1.57 here
        else:
            accel_decel_rate, velocity, accel_decel_type, stage_type, motor_type, ok = PopupAccelDecel.return_values(rate=rate, vel=vel,
                                                                                             ramp_type=ramp_type,stage_type=stage_type,motor_type=motor_type)
        if not ok:
            return

        if vel and velocity == vel:
            pass
        else:
            if self.invalid_motion_profile("accel decel", desired_v=velocity):
                return
        if ok:
            if not accel_decel_rate or not velocity or float(accel_decel_rate) <= 0:
                msg = QtWidgets.QMessageBox()
                msg.setText("Please specify a valid Acceleration Rate and Velocity. "
                            "Blank, zero, and negative values are not acceptable for Acceleration Rate - blank values "
                            "are not acceptable for Velocity. Please try again.")
                msg.setWindowTitle("Invalid Profile!")
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()
                return
            param = "accel_decel_rate=" + accel_decel_rate + ";velocity=" + velocity + ";accel_decel_type=" + \
                    accel_decel_type + ";"
            con = lite.connect(temp_filepath)
            with con:
                cur = con.cursor()
                if not id:
                    cur.execute("SELECT COUNT (id) FROM Profile")
                    op = cur.fetchone()[0] + 1
                    cur.execute("INSERT INTO Profile (Operation, Type, Parameters) VALUES (?,?,?)",
                                (op, "Accel / Decel", param))
                else:
                    cur.execute("UPDATE Profile SET Parameters=? WHERE id=?", (param, str(id)))
            con.commit()
            self.file_change()
            self.refresh_plot()
            self.model = Model(self)
            self.ui.list_motion.setModel(self.model)
            self.ui.list_motion.selectRow(self.model.rowCount()-1)
            self.calc_results()

    def show_constant_velocity_dialog(self, distance=None, vel=None, stage_type=None, motor_type=None, id=None):
        """Calls appropriate popup class and retrieves user values. Checks validity. Calls for plot and calc updates.

        Args:
            distance (str, optional): distance in mm, passed if called via Edit Profile function. Defaults to None.
            vel (str, optional): velocity in mm/s, passed if called via Edit Profile function. Defaults to None.
            id (str, optional): row id of selected move, passed if called via Edit Profile function. Defaults to None.

        """
        global v
        stage_type = self.ui.txt_stage_type.text()
        motor_type = self.ui.txt_motor_type.text()
        if not distance:
            constant_distance, constant_velocity, stage_type, motor_type, ok = PopupConstantVelocity.return_values(vel_value=v[-1],stage_type=stage_type,motor_type=motor_type)
            if not ok:
                return
            if self.invalid_motion_profile("constant velocity"):
                return
        else:
            constant_distance, constant_velocity, stage_type, motor_type, ok = PopupConstantVelocity.return_values(vel_value=vel,
                                                                                           distance=distance,stage_type=stage_type,motor_type=motor_type)
        if ok:
            if not constant_distance or float(constant_distance) <= 0:
                msg = QtWidgets.QMessageBox()
                msg.setText("Please specify a valid Distance. "
                            "Blank, zero, and negative values are not acceptable. Please try again.")
                msg.setWindowTitle("Invalid Profile!")
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()
                return
            param = "constant_distance=" + constant_distance + ";constant_velocity=" + constant_velocity + ";"
            con = lite.connect(temp_filepath)
            with con:
                cur = con.cursor()
                if not id:
                    cur.execute("SELECT COUNT (id) FROM Profile")
                    op = cur.fetchone()[0] + 1
                    cur.execute("INSERT INTO Profile (Operation, Type, Parameters) VALUES (?,?,?)",
                                (op, "Constant Velocity", param))
                else:
                    cur.execute("UPDATE Profile SET Parameters=? WHERE id=?", (param, str(id)))
            con.commit()
            self.file_change()
            self.refresh_plot()
            self.model = Model(self)
            self.ui.list_motion.setModel(self.model)
            self.ui.list_motion.selectRow(self.model.rowCount()-1)
            self.calc_results()
        else:
            return

    def show_point_to_point_dialog(self, distance=None, vel=None, accel=None, decel=None, ramp_type=None, stage_type=None, motor_type=None, id=None):
        """Calls appropriate popup class and retrieves user values. Checks validity. Calls for plot and calc updates.

        Args:
            distance (str, optional): distance in mm, passed if called via Edit Profile function. Defaults to None.
            vel (str, optional): velocity in mm/s, passed if called via Edit Profile function. Defaults to None.
            accel (str, optional): accel in mm/s^2, passed if called via Edit Profile function. Defaults to None.
            decel (str, optional): decel in mm/s^2, passed if called via Edit Profile function. Defaults to None.
            ramp_type (str, optional): ramp type, passed if called via Edit Profile function. Defaults to None.
            id (str, optional): row id of selected move, passed if called via Edit Profile function. Defaults to None.

        """
        stage_type = self.ui.txt_stage_type.text()
        motor_type = self.ui.txt_motor_type.text()
        #if stage_type = "Direct-Drive Rotary":
            
        if not distance:
            point_distance, point_velocity, point_accel, point_decel, point_accel_type, stage_type, motor_type,\
              ok = PopupPointToPoint.return_values(stage_type=stage_type,motor_type=motor_type)
        else:
            point_distance, point_velocity, point_accel, point_decel, point_accel_type, stage_type, motor_type, \
            ok = PopupPointToPoint.return_values(distance=distance, vel=vel, accel=accel, decel=decel,
                                                 ramp_type=ramp_type,stage_type=stage_type,motor_type=motor_type)
        if ok:
            if not point_distance or not point_velocity or not point_accel or not point_decel or float(point_accel) <= 0 \
                    or float(point_decel) <= 0:
                msg = QtWidgets.QMessageBox()
                msg.setText("Please specify a valid Distance, Velocity, Accel Rate, and Decel Rate. "
                            "Blank, zero, and negative values are not acceptable for Rates - blank values are "
                            "not acceptable for Distance and Velocity. Please try again.")
                msg.setWindowTitle("Invalid Profile!")
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()
                return
            if not np.sign(float(point_distance)) == np.sign(float(point_velocity)):
                msg = QtWidgets.QMessageBox()
                msg.setText("Please specify a valid Profile . "
                            "The sign of Distance and Velocity must agree. Please try again.")
                msg.setWindowTitle("Invalid Profile!")
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()
                return
            param = "point_distance=" + point_distance + ";point_velocity=" + point_velocity + ";point_accel=" + \
                    point_accel + ";point_decel=" + point_decel + ";point_accel_type=" + point_accel_type + ";"
            con = lite.connect(temp_filepath)
            with con:
                cur = con.cursor()
                if not id:
                    cur.execute("SELECT COUNT (id) FROM Profile")
                    op = cur.fetchone()[0] + 1
                    cur.execute("INSERT INTO Profile (Operation, Type, Parameters) VALUES (?,?,?)",
                                (op, "Point to Point", param))
                else:
                    cur.execute("UPDATE Profile SET Parameters=? WHERE id=?", (param, str(id)))
            con.commit()
            self.file_change()
            self.refresh_plot()
            self.model = Model(self)
            self.ui.list_motion.setModel(self.model)
            self.ui.list_motion.selectRow(self.model.rowCount()-1)
            self.calc_results()
        else:
            return
  
    def show_popup_config_dialog(self, config, motor=None, motorType=None, motor_spec_names=None, motor_spec_vals=None, stage=None, stageType=None, stage_spec_names=None, stage_spec_vals=None,stage_config=None):
        self.clear_results()
        if config=="stage":
            if stage == "":
                print("no stage to configure")
                return
            else:
                motor,motorType,motor_spec_names,motor_spec_vals,stage,stageType,stage_spec_names,stage_spec_vals,stage_config = PopupConfig.return_values(stage = stage)
                self.file_change()
                self.model = Model(self)
                self.ui.list_motion.setModel(self.model)
                self.ui.list_motion.selectRow(self.model.rowCount()-1)
                #print(str(stage_spec_vals))

        else:
            if self.ui.txt_stage_type != "":
                if (self.ui.txt_stage_type == "Direct-Drive Linear" and self.getMotorType(self.motor) == "Rotary") or \
                (self.ui.txt_stage_type=="Direct-Drive Rotary" and self.getMotorType(self.motor) =="Linear") or (self.ui.txt_stage_type=="Screw-Drive Linear" and self.getMotorType(self.motor)=="Linear"): 
                    msg = QtWidgets.QMessageBox()
                    msg.setText("Invalid motor stage combination! Please use linear motors with linear stages and rotary motors with rotary stages except for ballscrew stages.")
                    msg.setWindowTitle("Invalid Entry!")
                    msg.setIcon(QtWidgets.QMessageBox.Warning)
                    msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                    msg.exec_()
                    return ""
                    
            motor,motorType,motor_spec_names,motor_spec_vals,stage,stageType,stage_spec_names,stage_spec_vals,stage_config = PopupConfig.return_values(stage = self.motor) 

            self.model = Model(self)
            self.ui.list_motion.setModel(self.model)
            self.ui.list_motion.selectRow(self.model.rowCount()-1)
            self.ui.motor_name.setText(stage_config)   
            self.on_motor_change(stage_config)
            self.file_change()
            self.refresh_plot()
            return stage_config
        return stage_spec_vals

    def show_spec_display(self,config):
        if config=="stage" and self.ui.stage_smart_string.text()=="":
            msg = QtWidgets.QMessageBox()
            msg.setText("Stage not configured!")
            msg.setWindowTitle("Invalid Entry!")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
            return
        if config=="motor" and self.ui.motor_smart_string.text()=="":
            msg = QtWidgets.QMessageBox()
            msg.setText("Motor not configured!")
            msg.setWindowTitle("Invalid Entry!")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
            return
        ok = PopupSpecDisplay.return_values(config=config)
        if not ok:
            return

    def delete_profile(self):
        """Deletes selected motion profile. First checks if deletion will result in valid profile."""
        try:
            index = self.ui.list_motion.selectionModel().currentIndex()
            op = index.sibling(index.row(), 0).data()
            msg_delete = QtWidgets.QMessageBox()
            msg_delete.setText("Are you sure you want to delete this move?")
            msg_delete.setWindowTitle("Confirm Delete")
            msg_delete.setStandardButtons(QtWidgets.QMessageBox.Yes|QtWidgets.QMessageBox.Cancel)
            response = msg_delete.exec_()
            if response == QtWidgets.QMessageBox.Cancel:
                return
            con = lite.connect(temp_filepath)
            with con:
                cur = con.cursor()
                cur.execute("SELECT * FROM Profile WHERE Operation=%s" % op)
                temp_record = cur.fetchone()
                cur.execute("DELETE FROM Profile WHERE Operation=%s" % op)
                con.commit()
                ok, msg_text = self.refresh_plot()
                if not ok:
                    msg = QtWidgets.QMessageBox()
                    msg.setText("Cannot delete this move:\n\n" + msg_text)
                    msg.setWindowTitle("Invalid Profile!")
                    msg.setIcon(QtWidgets.QMessageBox.Warning)
                    msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                    msg.exec_()
                    cur.execute("INSERT INTO Profile (Operation, Type, Parameters, Brake) VALUES(?,?,?,?)", temp_record[1:])
                cur.execute("SELECT * FROM Profile ORDER BY Operation ASC")
                records = cur.fetchall()
                for i, record in enumerate(records):
                    cur.execute("UPDATE Profile SET Operation=? WHERE id=?", [i + 1, record[0]])  # renumber Operation
                con.commit()
            self.file_change()
            self.refresh_plot()
            self.model = Model(self)
            self.ui.list_motion.setModel(self.model)
            self.ui.list_motion.selectRow(self.model.rowCount()-1)
            self.calc_results()
        except:
            msg = QtWidgets.QMessageBox()
            msg.setText("No move profile is selected.")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setWindowTitle("Invalid Profile!")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
            return

    def move_profile(self, direction):
        """Moves profile up or down table depending on direction clicked.

        Args:
            direction (str): 'up' or 'down' - coded in to each button.

        """
        index = self.ui.list_motion.selectionModel().currentIndex()
        op = index.sibling(index.row(), 0).data()
        con = lite.connect(temp_filepath)
        with con:
            cur = con.cursor()
            cur.execute("SELECT id FROM Profile WHERE Operation=%s" % op)
            record = cur.fetchone()
            move_id = record[0]
            if direction == "up":
                if op == 1:
                    return
                cur.execute("UPDATE Profile SET Operation=? WHERE id=?", [(op - 1.5), move_id])
            elif direction == "down":
                cur.execute("UPDATE Profile SET Operation=? WHERE id=?", [(op + 1.5), move_id])
            else:
                print("uh oh direction")
            con.commit()
            self.file_change()
            ok, msg_text = self.refresh_plot()
            if not ok:
                if direction == "up":
                    cur.execute("UPDATE Profile SET Operation=? WHERE id=?", [(op + 1.5), move_id])
                elif direction == "down":
                    cur.execute("UPDATE Profile SET Operation=? WHERE id=?", [(op - 1.5), move_id])
                else:
                    print("uh oh direction")
                con.commit()
                msg = QtWidgets.QMessageBox()
                msg.setText(msg_text)
                msg.setWindowTitle("Invalid Profile!")
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()
                return
            else:
                cur.execute("SELECT * FROM Profile ORDER BY Operation ASC")
                records = cur.fetchall()
                for i, record in enumerate(records):
                    cur.execute("UPDATE Profile SET Operation=? WHERE id=?", [i + 1, record[0]])  #renumber Operation
                con.commit()
                self.file_change()
                self.refresh_plot()
                self.model = Model(self)
                self.ui.list_motion.setModel(self.model)
                self.ui.list_motion.selectRow(self.model.rowCount() - 1)
                self.calc_results()

    def edit_profile(self):
        """Edit currently selected move. Calls appropriate popup and fills with current params."""
        import re  # moved local to reduce startup time
        index = self.ui.list_motion.selectionModel().currentIndex()
        op = index.sibling(index.row(), 0).data()
        con = lite.connect(temp_filepath)
        try:
            with con:
                cur = con.cursor()
                cur.execute("SELECT * FROM Profile WHERE Operation=%s" % op)
                record = cur.fetchone()
                param = record[3]
                motion_type = record[2]
            values = re.findall(r'=(.*?);', param)
            if motion_type == "Dwell":
                duration = values[0]
                self.show_dwell_dialog(duration=duration, id=record[0])
            elif motion_type == "Point to Point":
                point_distance = values[0]
                point_velocity = values[1]
                point_accel = values[2]
                point_decel = values[3]
                point_accel_type = values[4]
                self.show_point_to_point_dialog(distance=point_distance, vel=point_velocity, accel=point_accel,
                                                decel=point_decel, ramp_type=point_accel_type, stage_type=self.getStage(), id=record[0])
            elif motion_type == "Constant Velocity":
                constant_distance = values[0]
                constant_velocity = values[1]
                self.show_constant_velocity_dialog(distance=constant_distance, vel=constant_velocity, stage_type=self.getStage(), id=record[0])
            elif motion_type == "Decel to Zero":
                decel_rate = values[0]
                decel_type = values[1]
                self.show_decel_to_zero_dialog(rate=decel_rate, ramp_type=decel_type, stage_type=self.getStage(), id=record[0])
            elif motion_type == "Accel / Decel":
                accel_rate = values[0]
                velocity = values[1]
                accel_type = values[2]
                self.show_accel_decel_dialog(rate=accel_rate, vel=velocity, ramp_type=accel_type, stage_type=self.getStage(), id=record[0])
                
                #Start Kevin's new edit
        except:
            msg = QtWidgets.QMessageBox()
            msg.setText("You don't have any move profile.")
            msg.setWindowTitle("Invalid Profile!")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
            return

    def brake_profile(self):
        """Calls Brake popup and then refreshes plot and results."""
        index = self.ui.list_motion.selectionModel().currentIndex()
        move_id = None
        if self.ui.txt_stage_type.text() == "Screw-Drive Linear":
            if index:
                op = index.sibling(index.row(), 0).data()
                con = lite.connect(temp_filepath)
                with con:
                    cur = con.cursor()
                    cur.execute("SELECT id FROM Profile WHERE Operation=%s" % op)
                    record = cur.fetchone()
                    move_id = record[0]
            if move_id:
                PopupBrake(id=move_id)
            else:
                PopupBrake()
            self.refresh_plot()
            self.model = Model(self)
            self.ui.list_motion.setModel(self.model)
            self.ui.list_motion.selectRow(self.model.rowCount() - 1)
            self.calc_results()
        else:
            msg = QtWidgets.QMessageBox()
            msg.setText("Cannot add Brake to unsupported Stage!")
            msg.setWindowTitle("Invalid Entry!")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
            

    def invalid_motion_profile(self, move_type, desired_v=None):
        """Determines if desired motion profile is valid or not.

        Invalid profiles include:
            - dwelling when preceding velocity is not zero.
            - attempting to accel/decel to the current velocity
            - a 0 mm/s constant velocity call

        Args:
            move_type (str): specifies which kind of move is attempting to be added.
            desired_v (str, optional): the desired velocity entered by user in the Accel/Decel popup. Defaults to None.

        Returns:
            bool: True is profile is valid, False if not.

        """
        global v

        if move_type == "accel decel":
            if round(v[-1], 2) == round(float(desired_v), 2):
                msg = QtWidgets.QMessageBox()
                msg.setText("Cannot add this motion profile - the velocity is already %s." % desired_v)
                msg.setWindowTitle("Invalid Entry!")
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()
                return True
        if round(v[-1], 1) == 0:
            if move_type == "decel to zero":
                msg = QtWidgets.QMessageBox()
                msg.setText("Cannot add this motion profile - the velocity is already 0.")
                msg.setWindowTitle("Invalid Entry!")
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()
                return True
            elif move_type == "constant velocity":
                msg = QtWidgets.QMessageBox()
                msg.setText("Cannot add this motion profile - the velocity is currently 0.")
                msg.setWindowTitle("Invalid Entry!")
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()
                return True
        else:
            # print(v[-1]-.001)
            #print(round(v[-1],2))
            #print(v[len(v)-1000:])
            if move_type == "dwell" and round(v[-1]-0.0001,1)!=0:
                # print(v[-1])
                # print("here")
                msg = QtWidgets.QMessageBox()
                msg.setText("Cannot add this motion profile - the velocity must be zero to add dwell.")
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setWindowTitle("Invalid Entry!")
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()
                return True

        return False
    
    def getStage(self):
        return self.ui.txt_stage_type.text()
    def refresh_plot(self):
        """Overwrites global accel, vel, time, and brake arrays with new values with Profile table is changed.

        These arrays are stored in global variables so that they do not need to be needlessly recalculated if
        inputs are changed that do not effect the motion profile. Since this function relies on numerical integration,
        it is fairly computational intensive, especially as a profile gets longer.

        Returns:
            bool: True if no problems with profile. False otherwise.
            str: error message / status.

        """
        import re  # moved local to reduce startup time
        from matplotlib import rc  # moved local to reduce startup time
        import scipy.integrate as sint  # moved local to reduce startup time
        global a, v, t, b
        con = lite.connect(temp_filepath)
        with con:
            cur = con.cursor()
            cur.execute("SELECT * FROM Profile ORDER BY Operation ASC")
            records = cur.fetchall()

        t = np.array([0])
        p = [0]
        v = [0]
        a = [0]
        b = [0]
        dt = .00001  # array interval - decrease for more accurate results, increase for faster calc time
        label_font = 'arial'
        p_color = '#1A3D6D'
        a_color = 'xkcd:gunmetal'
        linewidth = 2.5
        rc('font', **{'family': 'arial'})
        self.stage_type = self.ui.txt_stage_type.text()
        self.motor_type = self.ui.txt_motor_type.text()
        if not records:
            self.plotWidget.canvas.ax.clear()
            self.plotWidget.canvas.ax2.clear()
            self.plotWidget.canvas.ax3.clear()

            self.plotWidget.canvas.ax.plot(t, p, color=p_color, linewidth=linewidth)
            self.plotWidget.canvas.ax2.plot(t, v, linewidth=linewidth)
            self.plotWidget.canvas.ax3.plot(t, a, color=a_color, linewidth=linewidth)
            #print("stage type: " +self.ui.txt_stage_type.text())
            #stage_type = self.set_units()
            # stageType = ""
            
            #   print("stage type: " + self.stage_type)
           
                # stageType = self.ui.txt_stage_type.text()
            #print("stage type: " +stage_type)
            
            self.plotWidget.canvas.ax.set_xticklabels(labels=self.plotWidget.canvas.ax.get_xticklabels(),
                                                      visible=False)
            self.plotWidget.canvas.ax.set_xticks([])
            
            self.plotWidget.canvas.ax2.set_xticklabels(labels=self.plotWidget.canvas.ax2.get_xticklabels(),
                                                       visible=False)
            self.plotWidget.canvas.ax2.set_xticks([])
            
            self.plotWidget.canvas.ax3.set_xlabel('Time (s)', family=[label_font], size='large')

            self.plotWidget.canvas.draw()
            return True, "Empty"

        # this for loop builds the a, t, and b arrays one move at a time, appending each loop.
        for record in records:
            motion_type = record[2]
            if motion_type == "Dwell":
                # print(v[-1]-1*10^-5)
                if round(v[-1]-.0001, 1) != 0:
                    # print("failed conditional")
                    return False, "Velocity must be zero prior to dwell."
                param = str(record[3])
                values = re.findall(r'=(.*?);', param)  # uses regex to parse param into individual values.
                duration = float(values[0])
                t = np.append(t, [t[-1] + dt, t[-1] + duration])
                #new_dwell_zero = np.zeros(int(duration))
                #a.append(new_dwell_zero)
                a.extend([0, 0])
                if record[4] == "Yes":
                    # new_b = np.ones(2)
                    b.extend([1, 1])
                else:
                    # new_b = np.zeros(2)
                    b.extend([0, 0])
                    #b.append(new_dwell_zero)
                # b = b + new_b.tolist()
            elif motion_type == "Accel / Decel":
                # print("a/d-----")
                param = str(record[3])
                values = re.findall(r'=(.*?);', param)  # uses regex to parse param into individual values.
                accel_rate = float(values[0])
                velocity = float(values[1])
                if round(v[-1], 2) == round(velocity, 2):  # rounded number to account for rounding errors
                    # inherent in numerical methods
                    return False, "Accel / Decel not required - already at desired velocity."
                accel_decel_type = values[2]
                move_sign = np.sign(velocity - v[-1])
                if accel_decel_type == "Linear":
                    new_t = np.arange((t[-1] + dt), (t[-1] + ((velocity - v[-1])/(accel_rate*move_sign)) + dt), dt)
                    t = np.append(t, new_t)
                    new_a = np.ones_like(new_t)*accel_rate*move_sign
                    a = a + new_a.tolist()
                elif accel_decel_type == "Sinusoidal":
                    accel_rate = accel_rate*1.57
                    t_i = t[-1]
                    t_f = (abs(velocity-v[-1])/abs(accel_rate))*(np.pi/2)  # total time of accel/decel
                    new_t = np.arange((t_i + dt), (t_i + t_f + dt), dt)
                    t = np.append(t, new_t)
                    new_a = move_sign*accel_rate*np.sin((np.pi/t_f)*(new_t-t_i))
                    a = a + new_a.tolist()
                elif accel_decel_type == "S Curve":
                    accel_rate = accel_rate*1.333
                    t_i = t[-1]
                    t_f = abs(velocity-v[-1])/abs(accel_rate/2)
                    new_t = np.arange((t_i + dt), (t_i + t_f + dt), dt)
                    t = np.append(t, new_t)
                    new_a1 = (2*move_sign*accel_rate*(new_t[:len(new_t)//2]-t_i))/t_f
                    new_a2 = move_sign*accel_rate*(1-(2*((new_t[len(new_t)//2:]-t_i)-t_f/2))/t_f)
                    a = a + new_a1.tolist() + new_a2.tolist()
                else:
                    print("uh oh Accel / Decel")
                new_b = np.zeros_like(new_t)
                b = b + new_b.tolist()

            elif motion_type == "Constant Velocity":
                if round(v[-1], 1) == 0:
                    return False, "Velocity cannot be zero prior to constant velocity move."
                # print("cv----")
                param = str(record[3])
                values = re.findall(r'=(.*?);', param)  # uses regex to parse param into individual values.
                constant_distance = float(values[0])
                constant_velocity = v[-1]
                t_f = constant_distance/constant_velocity
                # t = np.append(t, t[-1]+t_f)
                # a.append(0)
                t = np.append(t, [t[-1] + dt, t[-1] + t_f])
                a.extend([0, 0])
                new_b = np.zeros(2)
                b = b + new_b.tolist()
            elif motion_type == "Decel to Zero":
                if round(v[-1], 2) == 0:  # rounded number to account for rounding errors inherent in numerical methods
                    return False, "Decel to Zero not required - preceding velocity is already zero."
                # print("dtz")
                param = str(record[3])
                values = re.findall(r'=(.*?);', param)  # uses regex to parse param into individual values.
                decel_rate = float(values[0])
                decel_type = values[1]
                velocity = 0
                move_sign = np.sign(velocity - v[-1])
                if decel_type == "Linear":
                    #print(t[-1]+dt)
                    #print(t[-1]+((velocity - v[-1]) / (decel_rate * move_sign)) + 2*dt)
                    new_t = np.arange((t[-1] + dt), (t[-1] + ((velocity - v[-1]) / (decel_rate * move_sign)) + 1*dt), dt)
                    t = np.append(t, new_t)
                    new_a = np.ones_like(new_t) * decel_rate * move_sign
                    a = a + new_a.tolist()
                    #print(new_t)
                    #print(new_a)
                    # print(v[-1])
                elif decel_type == "Sinusoidal":
                    decel_rate = decel_rate*1.57
                    t_i = t[-1]
                    t_f = (abs(velocity - v[-1]) / abs(decel_rate)) * (np.pi / 2)  # total time of accel/decel
                    new_t = np.arange((t_i + dt), (t_i + t_f + dt), dt)
                    t = np.append(t, new_t)
                    new_a = move_sign * decel_rate * np.sin((np.pi / t_f) * (new_t - t_i))
                    a = a + new_a.tolist()
                elif decel_type == "S Curve":
                    decel_rate=decel_rate*1.333
                    t_i = t[-1]
                    t_f = abs(velocity - v[-1]) / abs(decel_rate / 2)
                    new_t = np.arange((t_i + dt), (t_i + t_f + dt), dt)
                    t = np.append(t, new_t)
                    new_a1 = (2 * move_sign * decel_rate * (new_t[:len(new_t) // 2] - t_i)) / t_f
                    new_a2 = move_sign * decel_rate * (1 - (2 * ((new_t[len(new_t) // 2:] - t_i) - t_f / 2)) / t_f)
                    a = a + new_a1.tolist() + new_a2.tolist()
                else:
                    print("uh oh Decel to Zero")
                new_b = np.zeros_like(new_t)
                b = b + new_b.tolist()
            elif motion_type == "Point to Point":
                # print("ptp")
                param = str(record[3])
                values = re.findall(r'=(.*?);', param)  # uses regex to parse param into individual values.
                point_distance = float(values[0])
                point_velocity = float(values[1])
                point_accel = float(values[2])
                point_decel = float(values[3])
                point_accel_type = values[4]
                move_sign = np.sign(point_distance)
                t_i = t[-1]
                if point_accel_type == "Linear":
                    t1 = abs((point_velocity-v[-1])/point_accel)
                    p1 = .5*abs((point_velocity-v[-1])*t1)*move_sign
                    t3 = abs(point_velocity/point_decel)
                    p3 = .5*abs(point_velocity*t3)*move_sign
                    if abs(p1)+abs(p3) > abs(point_distance):  # enter here if constant velocity will not be achieved
                        point_velocity = \
                            ((v[-1]/point_accel) -
                             (np.sqrt(2*point_accel*abs(point_distance)+2*point_decel*abs(point_distance)-v[-1]**2))
                             / (np.sqrt(point_accel)*np.sqrt(point_decel))) / \
                            ((1/point_accel)+(1/point_decel))*move_sign
                        t1 = abs((point_velocity - v[-1]) / point_accel)
                        t3 = abs(point_velocity / point_decel)
                        p2 = 0
                    else:  # else calculate
                        p2 = move_sign*(abs(point_distance) - abs(p1) - abs(p3))
                    t2 = abs(p2)/abs(point_velocity)
                    new_t1 = np.arange((t_i + dt), (t_i + t1), dt)
                    if t2 == 0:
                        new_t2 = np.array([])
                    else:
                        new_t2 = np.array([(t_i + t1 + dt), (t_i + t1 + t2)])
                    new_t3 = np.arange((t_i + t1 + t2 + dt), (t_i + t1 + t2 + t3), dt)
                    t = np.concatenate((t, new_t1, new_t2, new_t3), axis=0)
                    new_a1 = np.ones_like(new_t1) * point_accel * move_sign
                    if t2 == 0:
                        new_a2 = np.array([])
                    else:
                        new_a2 = np.zeros(2)
                    new_a3 = np.ones_like(new_t3) * point_decel * move_sign * -1
                    a = a + new_a1.tolist() + new_a2.tolist() + new_a3.tolist()
                elif point_accel_type == "Sinusoidal":
                    point_accel = point_accel*1.57
                    point_decel = point_decel*1.57
                    t1 = (abs(point_velocity-v[-1])/abs(point_accel))*(np.pi/2)
                    p1 = (point_accel * t1 ** 2)/np.pi
                    t3 = (abs(point_velocity) / abs(point_decel)) * (np.pi / 2)
                    p3 = (point_decel * t3 ** 2) / np.pi
                    if abs(p1)+abs(p3) > abs(point_distance):  # enter here if constant velocity will not be achieved
                        point_velocity = \
                            abs((((2*np.sqrt(4*point_accel*point_distance+np.pi*point_decel*point_distance-np.pi
                                             * v[-1]**2))/np.sqrt(point_accel*point_decel))
                                 - ((np.pi*v[-1])/point_accel))/((-np.pi/point_accel)-4/point_decel))
                        t1 = (abs(point_velocity - v[-1]) / abs(point_accel)) * (np.pi / 2)
                        t3 = (abs(point_velocity) / abs(point_decel)) * (np.pi / 2)
                        p2 = 0
                    else:
                        p2 = move_sign * (abs(point_distance) - abs(p1) - abs(p3))
                    t2 = p2 / point_velocity
                    new_t1 = np.arange((t_i + dt), (t_i + t1), dt)
                    if t2 == 0:
                        new_t2 = np.array([])
                    else:
                        new_t2 = np.array([(t_i + t1 + dt), (t_i + t1 + t2)])
                    new_t3 = np.arange((t_i + t1 + t2 + dt), (t_i + t1 + t2 + t3), dt)
                    t = np.concatenate((t, new_t1, new_t2, new_t3), axis=0)
                    new_a1 = move_sign * point_accel * np.sin((np.pi / t1) * (new_t1 - t_i))
                    if t2 == 0:
                        new_a2 = np.array([])
                    else:
                        new_a2 = np.zeros(2)
                    new_a3 = -1 * move_sign * point_decel * np.sin((np.pi / t3) * (new_t3 - t_i - t1 - t2))
                    a = a + new_a1.tolist() + new_a2.tolist() + new_a3.tolist()
                elif point_accel_type == "S Curve":
                    point_accel = point_accel*1.333
                    point_decel = point_decel*1.333
                    t1 = abs(point_velocity - v[-1]) / abs(point_accel / 2)
                    p1 = (point_accel * t1 ** 2)/4
                    t3 = abs(point_velocity)/abs(point_decel / 2)
                    p3 = (point_decel * t3 ** 2)/4
                    if abs(p1) + abs(p3) > abs(point_distance):  # enter here if constant velocity will not be achieved
                        point_velocity = \
                            abs(((v[-1]/point_accel)
                                 - (np.sqrt(point_accel*point_distance+point_decel*point_distance-v[-1]**2)
                                    / np.sqrt(point_accel*point_decel)))/((1/point_accel)+(1/point_decel)))
                        t1 = abs(point_velocity - v[-1]) / abs(point_accel / 2)
                        t3 = abs(point_velocity) / abs(point_decel / 2)
                        p2 = 0
                    else:
                        p2 = move_sign * (abs(point_distance) - abs(p1) - abs(p3))
                    t2 = p2 / point_velocity
                    new_t1 = np.arange((t_i + dt), (t_i + t1), dt)
                    if t2 == 0:
                        new_t2 = np.array([])
                    else:
                        new_t2 = np.array([(t_i + t1 + dt), (t_i + t1 + t2)])
                    new_t3 = np.arange((t_i + t1 + t2 + dt), (t_i + t1 + t2 + t3), dt)
                    t = np.concatenate((t, new_t1, new_t2, new_t3), axis=0)
                    new_a1A = (2 * move_sign * point_accel * (new_t1[:len(new_t1) // 2] - t_i)) / t1
                    new_a1B = move_sign * point_accel * (1 - (2 * ((new_t1[len(new_t1) // 2:] - t_i) - t1 / 2))/t1)
                    if t2 == 0:
                        new_a2 = np.array([])
                    else:
                        new_a2 = np.zeros(2)
                    new_a3A = -1*(2 * move_sign * point_decel * (new_t3[:len(new_t3) // 2] - t_i - t1 - t2)) / t3
                    new_a3B = -1*move_sign * point_decel * (
                                1 - (2 * ((new_t3[len(new_t3) // 2:] - t_i - t1 - t2) - t3 / 2)) / t3)
                    a = a + new_a1A.tolist() + new_a1B.tolist() + new_a2.tolist() + new_a3A.tolist()\
                        + new_a3B.tolist()
                else:
                    print("uh oh")
                new_b1 = np.zeros_like(new_t1)
                new_b2 = np.zeros_like(new_t2)
                new_b3 = np.zeros_like(new_t3)
                b = b + new_b1.tolist() + new_b2.tolist() + new_b3.tolist()
            else:
                print("uh oh")
        #start = time.perf_counter()
            v = sint.cumtrapz(a, t, initial=0)
        # print("Velocity: ", time.perf_counter()-start)
        # start = time.perf_counter()
        p = sint.cumtrapz(v, t, initial=0)
        # print("Position: ", time.perf_counter() - start)

        # this line retrieves each point in b that transitions from 1 to 0 or 0 to 1
        brake_transitions = np.argwhere(np.diff(b)).squeeze()/100000
        if type(brake_transitions) == np.float64:  # if only 1 transition, type is float - this fixes that
            brake_transitions = np.array([brake_transitions, (len(t)-1) / 100000])
        if not len(brake_transitions) % 2 == 0:  # if # transitions, adds final t as last transition
            brake_transitions = np.append(brake_transitions, (len(t)-1) / 100000)
        brake_transitions = brake_transitions.reshape(-1, 2)

        #update the plots
        self.plotWidget.canvas.ax.clear()
        self.plotWidget.canvas.ax2.clear()
        self.plotWidget.canvas.ax3.clear()

        self.plotWidget.canvas.ax.plot(t, p, color=p_color, linewidth=linewidth)
        self.plotWidget.canvas.ax2.plot(t, v, linewidth=linewidth)
        self.plotWidget.canvas.ax3.plot(t, a, color=a_color, linewidth=linewidth)
        self.ui.txt_stage_type.textChanged.connect(self.set_units)
        #print("stage type: " +self.stage_type)
        if self.stage_type!="":
            if self.stage_type == "Direct-Drive Rotary":
                self.plotWidget.canvas.ax.set_ylabel('position\n(deg)', family={'arial'}, size='large')
                self.plotWidget.canvas.ax2.set_ylabel('velocity\n(deg/sec)', family={'arial'}, size='large')
                self.plotWidget.canvas.ax3.set_ylabel('acceleration\n(deg/sec$^2$)', family={'arial'}, size='large')
            else:
                self.plotWidget.canvas.ax.set_ylabel('position\n(mm)', family={'arial'}, size='large')
                self.plotWidget.canvas.ax2.set_ylabel('velocity\n(mm/sec)', family={'arial'}, size='large')
                self.plotWidget.canvas.ax3.set_ylabel('acceleration\n(mm/sec$^2$)', family={'arial'}, size='large')
        else:
            #print("where I should be")
            #print("motor type before conditional" + self.motor_type)
            if self.motor_type == "Rotary":
                #print("motor type: " +self.motor_type)
                self.plotWidget.canvas.ax.set_ylabel('position\n(deg)', family={'arial'}, size='large')
                self.plotWidget.canvas.ax2.set_ylabel('velocity\n(deg/sec)', family={'arial'}, size='large')
                self.plotWidget.canvas.ax3.set_ylabel('acceleration\n(deg/sec$^2$)', family={'arial'}, size='large')           
            else:
                self.plotWidget.canvas.ax.set_ylabel('position\n(mm)', family={'arial'}, size='large')
                self.plotWidget.canvas.ax2.set_ylabel('velocity\n(mm/sec)', family={'arial'}, size='large')
                self.plotWidget.canvas.ax3.set_ylabel('acceleration\n(mm/sec$^2$)', family={'arial'}, size='large')
        #self.plotWidget.canvas.ax.set_ylabel('position\n(mm)', family={label_font}, size='large')
        self.plotWidget.canvas.ax.set_xticklabels(labels=self.plotWidget.canvas.ax.get_xticklabels(),
                                                  visible=False)
        self.plotWidget.canvas.ax.set_xticks([])
       # self.plotWidget.canvas.ax2.set_ylabel('velocity\n(mm/sec)', family={label_font}, size='large')
        self.plotWidget.canvas.ax2.set_xticklabels(labels=self.plotWidget.canvas.ax2.get_xticklabels(),
                                                   visible=False)
        self.plotWidget.canvas.ax2.set_xticks([])
        #self.plotWidget.canvas.ax3.set_ylabel('acceleration\n(mm/sec$^2$)', family={label_font}, size='large')
        self.plotWidget.canvas.ax3.set_xlabel('Time (s)', family=[label_font], size='large')

        for start, stop in brake_transitions:
            self.plotWidget.canvas.ax.axvspan(t[int(start*100000)], t[int(stop*100000)], facecolor='gray', alpha=0.25)
            self.plotWidget.canvas.ax.axvline(t[int(start*100000)], c='gray', zorder=0, alpha=0.5)
            self.plotWidget.canvas.ax.axvline(t[int(stop*100000)], c='gray', zorder=0, alpha=0.5)
            self.plotWidget.canvas.ax2.axvspan(t[int(start*100000)], t[int(stop*100000)], facecolor='gray', alpha=0.25)
            self.plotWidget.canvas.ax2.axvline(t[int(start*100000)], c='gray', zorder=0, alpha=0.5)
            self.plotWidget.canvas.ax2.axvline(t[int(stop*100000)], c='gray', zorder=0, alpha=0.5)
            self.plotWidget.canvas.ax3.axvspan(t[int(start*100000)], t[int(stop*100000)], facecolor='gray', alpha=0.25)
            self.plotWidget.canvas.ax3.axvline(t[int(start*100000)], c='gray', zorder=0, alpha=0.5)
            self.plotWidget.canvas.ax3.axvline(t[int(stop*100000)], c='gray', zorder=0, alpha=0.5)

        self.plotWidget.canvas.draw()

        return True, "No Problems"

    def on_stage_change(self,stage,stageType,stage_spec_names,stage_spec_vals,stage_config):
        """Updates Stage properties when drop-down is changed. Calcs new results.

        Args:
            stage (str): newly selected Stage from drop-down.

        """
        self.readProducts()
        self.stage = self.ui.stage_config_input.text()
        stage = self.ui.stage_config_input.text()
        self.ui.stage_smart_string.setText(stage_config)
        #print("stage" + stage)
        #print(stage_spec_names)
        #print(stage_spec_vals)
        stageType = self.getStageType(stage)
        #print(stage)
        # print("stage type " + stageType)
        # if  stage == "":
            # return
            #self.show_popup_config_dialog()
        self.store_inputs()
        #print(stage_spec_vals)
        if stage == "":
            # self.clear_results()
            return
        elif stage_spec_vals==[]:
            return
        # con = lite.connect(db_filepath)
        # with con:
            # cur = con.cursor()
            # cur.execute("SELECT * FROM Stages WHERE Name='%s'" % stage)
            # record = cur.fetchone()
        if stageType == "sd_linear":
            self.ui.label_36.setText("kg")
            self.ui.label_16.setText("Payload:")
            self.ui.txt_stage_type.setText("Screw-Drive Linear")
            MovMass = round(stage_spec_vals[stage_spec_names.index("MovingMass")],2)
            BearFriction = stage_spec_vals[stage_spec_names.index("LinearFrictionForce")]
            ScrewFriction = stage_spec_vals[stage_spec_names.index("ScrewFriction")]
            ScrewInertia = stage_spec_vals[stage_spec_names.index("ScrewInertia")]
            ScrewLead = stage_spec_vals[stage_spec_names.index("ScrewLead")]/1000
            try:
                FoldFriction = stage_spec_vals[stage_spec_names.index("FoldbackFriction")]
            except ValueError as error:
                FoldFriction=0
                #return
            #WedgeRatio = stage_spec_vals[stage_spec_names.index("WedgeRatio")]
            self.ui.stage_param_txt_1.setText(str(round(MovMass,2)))
            self.ui.stage_param_txt_2.setText(str(BearFriction))
            self.ui.stage_param_txt_3.setText(str(ScrewFriction))
            self.ui.stage_param_txt_4.setText(str(ScrewInertia))
            self.ui.stage_param_txt_5.setText(str(ScrewLead))
            self.ui.stage_param_txt_6.setText(str(FoldFriction))
            
            self.ui.stage_param_label_1.setText("Moving Mass")
            self.ui.stage_param_label_2.setText("Bearing Friction")
            self.ui.stage_param_label_3.setText("Screw Friction")
            self.ui.stage_param_label_4.setText("Screw Inertia")
            self.ui.stage_param_label_5.setText("Screw Lead")
            self.ui.stage_param_label_6.setText("Foldback Fricton")
            
            self.ui.stage_units_label_1.setText("kg")
            self.ui.stage_units_label_2.setText("N")
            self.ui.stage_units_label_3.setText("N-m")
            self.ui.stage_units_label_4.setText("kg-m-m")
            self.ui.stage_units_label_5.setText("m/rev")
            self.ui.stage_units_label_6.setText("N-m")
            #self.ui.stage_param_txt_6.setText(str(MovMass))
            #self.ui.txt_bearing_friction.setText(str(BearFriction))
            #self.ui.txt_screw_friction.setText(str(ScrewFriction))
            #self.ui.txt_screw_diameter.setText(record[6])
            #self.ui.txt_screw_length.setText(record[7])
            #self.ui.txt_screw_lead.setText(str(ScrewLead))
        elif stageType == "dd_linear":
            #print("direct drive")
            self.ui.label_36.setText("kg")
            self.ui.label_16.setText("Payload:")
            #print(str(stage_spec_vals))
            MovMass = stage_spec_vals[stage_spec_names.index("MovingMass")]
            BearFriction = stage_spec_vals[stage_spec_names.index("LinearFrictionForce")]
            WedgeRatio = stage_spec_vals[stage_spec_names.index("WedgeRatio")]
            MotorCurrentDerateFactor = stage_spec_vals[stage_spec_names.index("MotorCurrentDerateFactor")]
            NumMotors = stage_spec_vals[stage_spec_names.index("NumMotors")]
            #print(str(NumMotors))
            
            self.ui.txt_stage_type.setText("Direct-Drive Linear")
        
            self.ui.stage_param_txt_1.setText(str(round(MovMass,2)))
            self.ui.stage_param_txt_2.setText(str(BearFriction))
            self.ui.stage_param_txt_3.setText(str(WedgeRatio))
            self.ui.stage_param_txt_4.setText(str(MotorCurrentDerateFactor))
            self.ui.stage_param_txt_5.setText(str(NumMotors))
            self.ui.stage_param_txt_6.setVisible(False)
            
            self.ui.stage_param_label_1.setText("Moving Mass")
            self.ui.stage_param_label_2.setText("Bearing Friction")
            self.ui.stage_param_label_3.setText("Wedge Ratio")
            self.ui.stage_param_label_4.setText("Motor Derate")
            self.ui.stage_param_label_5.setText("# Motors")
            self.ui.stage_param_label_6.setVisible(False)
            
            self.ui.stage_units_label_1.setText("kg")
            self.ui.stage_units_label_2.setText("N")
            self.ui.stage_units_label_3.setText("")
            self.ui.stage_units_label_4.setText("")
            self.ui.stage_units_label_5.setText("")
            self.ui.stage_units_label_6.setVisible(False)
        elif stageType == "dd_rotary":
            self.ui.label_36.setText("kg*m^2")
            self.ui.label_16.setText("Inertia:")
            FrictionTorque = stage_spec_vals[stage_spec_names.index("FrictionTorque")]
            MotorCurrentDerateFactor = stage_spec_vals[stage_spec_names.index("MotorCurrentDerateFactor")]
            RotationalInertia = stage_spec_vals[stage_spec_names.index("RotationalInertia")]
            
            #Added try method here.  Otherwise #motor will not show up for 
            #linear stages after configuring rotary stages.  
            try:
                NumMotors = stage_spec_vals[stage_spec_names.index("NumMotors")] 
            except ValueError as error:
                NumMotors = 1.0
            
            
            self.ui.txt_stage_type.setText("Direct-Drive Rotary")
        
            self.ui.stage_param_txt_1.setText(str(FrictionTorque))
            self.ui.stage_param_txt_2.setText(str(MotorCurrentDerateFactor))
            self.ui.stage_param_txt_3.setText(str(RotationalInertia))
            self.ui.stage_param_txt_4.setVisible(False)
            #self.ui.stage_param_txt_5.setVisible(False)
            self.ui.stage_param_txt_5.setText(str(NumMotors))
            self.ui.stage_param_txt_6.setVisible(False)
            
            self.ui.stage_param_label_1.setText("Friction Torque")
            self.ui.stage_param_label_2.setText("Motor Derate")
            self.ui.stage_param_label_3.setText("Rotational Inertia")
            self.ui.stage_param_label_4.setVisible(False)
            #self.ui.stage_param_label_5.setVisible(False)
            self.ui.stage_param_label_5.setText("# Motors")
            self.ui.stage_param_label_6.setVisible(False)
            
            self.ui.stage_units_label_1.setText("N-m")
            self.ui.stage_units_label_2.setText("")
            self.ui.stage_units_label_3.setText("kg-m-m")
            self.ui.stage_units_label_4.setVisible(False)
            #self.ui.stage_units_label_5.setVisible(False)
            self.ui.stage_units_label_5.setText("")
            self.ui.stage_units_label_6.setVisible(False)
            
        elif stageType == "gd_rotary":
            print("Unsupported for now")
            self.ui.stage_config_input.setText("")
            self.ui.motor_param_txt_1.setText()
            return
        # if stage in self.dd_linear_stages:
            # stageType = "dd_linear"
        # elif stage in self.sd_linear_stages:
            # stageType = "sd_linear"
        # elif stage in self.dd_rotary_stages:
            # stageType = "dd_rotary"
        # elif stage in self.gd_rotary_stages:
            # stageType = "gd_rotary"
        # self.ui.txt_moving_mass.setText(record[5])
        # self.ui.txt_bearing_friction.setText(record[13])
        # self.ui.txt_screw_friction.setText(record[14])
        # self.ui.txt_screw_diameter.setText(record[6])
        # self.ui.txt_screw_length.setText(record[7])
        # self.ui.txt_screw_lead.setText(record[10])
        # index = self.ui.cmb_motor_select.findText(record[43])
        # if index >= 0:
            # self.ui.stage.setCurrentIndex(index)
        if not  self.ui.motor_param_txt_1.text() == "":
            self.calc_results()
    

    def on_motor_change(self,motor):#,motorType,motor_spec_names,motor_spec_vals):
        """Updates Motor properties when drop-down is changed. Calcs new results.

        Args:
            motor (str): newly selected Motor from drop-down.

        """
        try:
            self.config_sizer = ConfigSizer()
            self.readProducts()
            # temp = motor.split("(")
            # motorString = temp[0]
            # temp2 = temp[1].split("\"")
            # motorString = motorString + temp2[1]
            # self.ui.motor_name.setText(motor)
            self.ui.motor_smart_string.setText(motor)
            
    
            motor_spec_names=[]
            motor_spec_vals=[]
            motor_spec_units=[]
            # print(motorType)
            # print(motor_spec_names)
            # print(motor_spec_vals)
            # if self.configured:
            #print("configured")
            motors = motor.split("-")
            if motors[0].endswith("_Specs"):
                motors[0] = motors[0][:-6] 
            # print(motors)
            #combine = ""
            motorType = self.getMotorType(motors[0].rstrip())
            if "Motor" in motors:
                index = motors.index("Motor")
                combine = motors[index]
                del motors[index]
                while index >1:
                    combine = motors[index-1] + "-" +combine
                    del motors[index-1]
                    index=index-1
                    
                    
                motors[0] = motors[0] +"-" + combine
                #del motors[1:index]
                motorType = self.getMotorType(motors[0].rstrip())
                
            # print(motors)
            Inp_names = []
            Inp_vals = []
            #Inp_units=[]
            self.isStepper = False
            #print(motors)
            self.config_options = QtSql.QSqlTableModel(db = self.config_sizer.data)
            self.config_options.setTable(motors[0].rstrip() + "_TemplateSpecs")
            self.config_options.select()
            if self.config_options.rowCount()==0:
                self.config_options.setTable(motors[0]+"-"+motors[1]+"_TemplateSpecs")
                self.config_options.select()
            self.config_options.setFilter("SpecName LIKE 'IsStepper'")
            self.config_options.select()
            #print(self.config_options.record(0).value("Value"))
            if self.config_options.record(0).value("Value") == '1.0':
                self.isStepper = True
            #print(motors[0].rstrip() + "_Inputs")
            #print(self.isStepper)
            self.config_options.setTable(motors[0].rstrip() + "_TemplateSpecs")
            self.config_options.select()
            #print("sheet has " + str(self.config_options.rowCount()))
            if self.isStepper:
                msg = QtWidgets.QMessageBox()
                msg.setText("Cannot size stepper motors, exiting configuration")
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setWindowTitle("Invalid Entry!")
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()
                self.clear_results()
                return
            i=0
            tblName = motors[0].rstrip()
            while self.config_options.rowCount() == 0 and i+1 < len(motors):
                #print("database is incorrect")
                #print(motors[0].rstrip() + "-" + motors[1].rstrip() + "_Inputs")
                tblName = tblName + "-" + motors[i+1].rstrip()
                #print(tblName)
                self.config_options.setTable(tblName+ "_TemplateSpecs")
                self.config_options.select()
                del motors[i+1]
                #print(self.config_options.rowCount())
                if self.config_options.rowCount()>0:
                    motors[0] = tblName#motors[0].rstrip() + "-" + motors[1].rstrip()
                    motorType = self.getMotorType(motors[0])
                    #del motors[1:i+1]
                #i=i+1
                # print("sheet has " + str(self.config_options.rowCount()))
            #print(motors[0])
            self.config_options.setTable(motors[0].rstrip() + "_Inputs")
            self.ui.motor_name.setText(motors[0])
            duplicate = False
            DupAcct = 0
            if len(motors[1:])!=len(set(motors[1:])):
                duplicate = True
            #print(duplicate)
            i=1 #changed from i=1
            print("length of motor string" + str(len(motors)))
            for config in motors[1:]:#and i+1 < len(motors)-1:
                # print("config = " + config)
                self.config_options.setFilter("Value LIKE '-"+ config + "'")
                self.config_options.select()
                # print(self.config_options.rowCount())
                #if config == "AC":
                    
                if self.config_options.rowCount() ==0 and i+1 < len(motors) and config != "AC":
                    config = config + "-" + motors[i+1]
                    motors[i] = config
                    # print("Updated config = " + config)
                    self.config_options.setFilter("Value LIKE '-" + config + "'")
                    self.config_options.select()
                    del motors[i+1]
                    # print(len(motors))
                # print(self.config_options.rowCount())
                if self.config_options.rowCount != 0:
                    Inp_vals.append("-"+config)
                if self.config_options.rowCount() >1 and duplicate == True:
                    #print("duplicates found")
                    Inp_names.append(self.config_options.record(DupAcct).value("Input Name"))
                    DupAcct = DupAcct +1
                else:
                    #print("no dups, adding " + str(self.config_options.record(0).value("Input Name")))
                    if config == "AC" and self.config_options.record(0).value("Input Name") is None:
                        Inp_names.append("Air Cooling")
                    else:
                        Inp_names.append(self.config_options.record(0).value("Input Name"))
                i=i+1
                
            self.config_options.select()
            # print(motors)
            # print(motorType)
            self.config_options.setTable(motors[0].rstrip() + "_Conditions")
            self.config_options.select()
            if not len(motors) == 1:
                #print("configure motor")
                
                
                
                
                
                # temp = motors[1].split(",")
                # filter = ""
                # full_filter =""
                # print(temp)
                # for item in temp:
                    # item = item.split(":")
                    # print(item)
                    # if item[1].endswith(")"):
                        # item[1]= item[1].rstrip(")")
                    # Inp_names.append(item[0].strip(" "))
                    # Inp_vals.append(item[1][2:-1])
                #print("Below are the input names for selecting rules")
                #print(Inp_names)
                #print(Inp_vals)
                self.config_options.setFilter("\"Input Name\" LIKE \'" + Inp_names[0] + "' AND Value Like '" + Inp_vals[0] + "'")
                self.config_options.select()
                startRules = []
                correctedRules = []
                for i in range(self.config_options.rowCount()): #added -1
                    startRules.append(self.config_options.record(i).value("Rule Id"))
                #print(startRules)
                for rule in startRules:
                    flag = True
                    self.config_options.setFilter("\"Rule Id\" LIKE " + str(rule))
                    self.config_options.select()
                    #print("#cols " + str(self.config_options.rowCount()))
                    #print(rule)
                    if self.config_options.rowCount() == 1:
                        correctedRules.append(rule)
                    else:###Generate list of input for each rule and then determine which rules match the configuration.
                        i=0
                        
                        for i in range(self.config_options.rowCount()): #added -1
                            inputName = self.config_options.record(i).value("Input Name")
                            inputVal = self.config_options.record(i).value("Value")
                            # print("Input Val " + inputVal)
                            j=0
                            
                            while flag and j<len(Inp_names):
                                if Inp_names[j] == inputName:
                                    #print(inputName)
                                    #print(Inp_vals[j])
                                    
                                    if inputName == "Air Cooling":
                                        if Inp_vals[j] == "-AC":
                                            # Aircooling
                                            if self.config_options.record(i).value("Operator") == 'Not Equal' and inputVal == "-NC":
                                                #correctedRules.append(rule)
                                                flag=True
                                                #print("aircooling")
                                            elif self.config_options.record(i).value("Operator") == 'Equal' and inputVal =="-AC":
                                                flag=True
                                                #print("aircooling") 
                                            else:
                                                flag =False
                                        else:
                                            if self.config_options.record(i).value("Operator") == 'Not Equal' or inputVal == "-AC":
                                                #print("no aircooling")
                                                flag=False
                                            #elif self.config_options.record(i).value("Operator")=='
                                    elif Inp_vals[j] == inputVal:
                                        if i == self.config_options.rowCount()-1:  #must keep this -1 for corrected motor information
                                            correctedRules.append(rule)
                                            #print("corrected rule " + str(rule))
                                    else:
                                        #print("doesn't match: " + str(inputVal) + str(Inp_vals[j]))
                                        flag =False
                                j=j+1
                #print(correctedRules)
                # for i in range(len(Inp_names)):
                    # full_filter = full_filter + "(\"Input Name\" LIKE \'" + Inp_names[i] + "' AND Operator LIKE 'Equal' AND Value LIKE '" + Inp_vals[i] + "') OR "
                # filter = filter + "(\"Input Name\" LIKE \'" + Inp_names[0] + "' AND Operator LIKE 'Equal' AND Value LIKE '" + Inp_vals[0] + "') AND "
                # filter = filter[0:-5]
                # full_filter = full_filter[0:-4]
                # print(full_filter)
                
                # self.config_options.setFilter(filter)
                # self.config_options.select()
                # rules =[]
                # action_rule_id= []
                # for i in range(self.config_options.rowCount()):
                    # rules.append(self.config_options.record(i).value("Rule Id"))
                    # print(rules[i])
                    # self.config_options.setFilter("\"Rule Id\" LIKE '" + str(rules[i]) + "' AND (" + full_filter + ")")
                    # self.config_options.select()
                    # if self.config_options.rowCount != 0:
                        # action_rule_id.append(rules[i])
                        
                    # firstVal="Rule Id"
                    # secondVal ="Value"
                    # first = self.config_options.record(i).value(firstVal)
                    # second = self.config_options.record(i).value(secondVal)
                    # if isinstance(first,int):
                        # print(firstVal +": " + str(first) + "\n" + secondVal +": "+ second + "\n")
                    # elif isinstance(second,int):
                        # print(firstVal +": " + first + "\n" + secondVal +": "+ str(second) + "\n")
                    # else:
                        # print(firstVal +": " + first + "\n" + secondVal +": "+ second + "\n")
                        
                        
                # print("These are after determining all the configured rules")
                # print(correctedRules)
                self.config_options.setTable(motors[0].rstrip() + "_TemplateSpecs")
                self.config_options.select()
                
                if len(motor_spec_names) ==0: 
                    for i in range(self.config_options.rowCount()): 
                        motor_spec_names.append(self.config_options.record(i).value("SpecName"))
                        motor_spec_vals.append(self.config_options.record(i).value("Value"))
                        motor_spec_units.append(self.config_options.record(i).value("Units"))
                
                        
                self.config_options.setTable(motors[0].rstrip() + "_Actions")
                for rule in correctedRules:
                    
                    for i in range(len(motor_spec_names)): 
                        target = motor_spec_names[i]
                        #print(str(target))
                        self.config_options.setFilter("\"Rule Id\" LIKE '" + str(rule) + "' AND Target LIKE '" + target + "'")
                        self.config_options.select()
                        if self.config_options.rowCount() != 0:
                            #print(str(rule))
                            #print(self.config_options.record(0).value("Value"))
                            motor_spec_vals[i] = self.config_options.record(0).value("Value")
            else:
                #print("no configure motor")
                
                
                #print(motor.rstrip())
                self.config_options.setTable(motor.rstrip() + "_TemplateSpecs")
                self.config_options.select()
                
                if len(motor_spec_names) ==0: 
                    for i in range(self.config_options.rowCount()): 
                        motor_spec_names.append(self.config_options.record(i).value("SpecName"))
                        motor_spec_vals.append(self.config_options.record(i).value("Value"))
                        motor_spec_units.append(self.config_options.record(i).value("Units"))
                #self.printTable("SpecName","Value")
                #print(self.config_options.rowCount())
                for i in range(len(motor_spec_names)):
                    target = motor_spec_names[i]
                    #print(target)
                    self.config_options.setFilter("SpecName LIKE '" + target + "'")
                    self.config_options.select()
                    if self.config_options.rowCount() != 0:
                        # print("Value = " + self.config_options.record(0).value("Value"))
                        motor_spec_vals[i] = self.config_options.record(0).value("Value")
            #print(rules)
            #file = open(resource_path("motor_specs.txt"),"w",encoding="utf-8")
            if not getattr(sys, 'frozen', False):
                spec_path = dir_path + r"\Temp Files\\" + "motor_specs.txt"  # saves in temp file dir
            else:
                spec_path = pf_path + r"\Temp Files\\" + "motor_specs.txt"  # saves in temp file dir
            file = open(spec_path, "w",encoding="utf-8")
            i=0
            for i in range(len(motor_spec_names)):
                file.write(str(motor_spec_names[i])+"**" + str(motor_spec_vals[i])+"**"+str(motor_spec_units[i])+"\n")
               
            file.close()
            #print("Motor Type" + motorType)
            # print(motor_spec_names)
            # print(motor_spec_vals)
            # print(motorType)
            
            # if "-NC" in self.ui.motor_name.text():
                # print("true")
            
            self.store_inputs()
            if motor == "":
                #
                # print("Motor test below")
                # self.clear_results()
                # self.ui.txt_motor_inertia.clear()
                # self.ui.txt_torque_constant.clear()
                # self.ui.txt_motor_constant.clear()
                # self.ui.txt_bemf.clear()
                # self.ui.txt_resistance.clear()
                # self.ui.txt_inductance.clear()
                # self.ui.txt_thermal_resistance.clear()
                # self.ui.txt_number_of_poles.clear()
                return
            con = lite.connect(db_filepath)
            with con:
                cur = con.cursor()
                cur.execute("SELECT * FROM Motors WHERE Name='%s'" % motor)
                record = cur.fetchone()
            if motorType == "Linear":
                self.ui.txt_motor_type.setText("Linear")
                self.ui.label_36.setText("kg")
                self.ui.label_16.setText("Payload:")
                if not self.ui.txt_ambient_temperature.text():
                    ambient_temperature = 20
                else:
                    ambient_temperature = float(self.ui.txt_ambient_temperature.text())  # C
                PkForce = motor_spec_vals[motor_spec_names.index("PeakForce")]
                ContForce = float(motor_spec_vals[motor_spec_names.index("ContStallForce")]) #got rid of float()
                ForceConst = motor_spec_vals[motor_spec_names.index("ForceConstantPeak")]
                MotorConst = float(motor_spec_vals[motor_spec_names.index("MotorConstant")]) ##got rid of float()
                BEMF = motor_spec_vals[motor_spec_names.index("BackEmfConstant")] 
                Resist = motor_spec_vals[motor_spec_names.index("ResistanceAt25C")]
                # print(self.ui.stage_param_txt_5.text())
    
                MaxTemp = motor_spec_vals[motor_spec_names.index("MaxTemp")]
                #print("Motor Constant" + str(MotorConst))
                #print("Max Temp" + str(MaxTemp))
                #print("Ambient Temp" + str(ambient_temperature))
                #print("Continuous Force" + str(ContForce))
                if self.ui.stage_param_txt_5.text() != "":
                    HotCoilResist = float(motor_spec_vals[motor_spec_names.index("ResistanceAtMaxTemp")])/ float(self.ui.stage_param_txt_5.text())
                    ThermalResist = round(MotorConst*MotorConst*(float(MaxTemp)-ambient_temperature)/(ContForce*ContForce)/ float(self.ui.stage_param_txt_5.text())**2,2)
                else:
                    HotCoilResist = float(motor_spec_vals[motor_spec_names.index("ResistanceAtMaxTemp")])
                    ThermalResist = round(MotorConst*MotorConst*(float(MaxTemp)-ambient_temperature)/(ContForce*ContForce)/ 1,2)
                #print("Thermal Resistance" + str(ThermalResist))
               
                CoilMass = motor_spec_vals[motor_spec_names.index("MovingMass")]
                if CoilMass == "":
                    CoilMass = 0
                CoilLength = motor_spec_vals[motor_spec_names.index("CoilLength")]
                if CoilLength == "":
                    CoilLength =0
                #self.ui.txt_motor_inertia.setText(MotorInertia)
                self.ui.motor_param_txt_1.setText(str(ForceConst))
                self.ui.motor_param_txt_2.setText(str(MotorConst))
                self.ui.motor_param_txt_3.setText(str(BEMF))
                self.ui.motor_param_txt_4.setText(str(HotCoilResist))
                self.ui.motor_param_txt_5.setText(str(ThermalResist))
                self.ui.motor_param_txt_6.setText(str(CoilMass))
                self.ui.motor_param_txt_7.setText(str(CoilLength))
                self.ui.motor_param_txt_8.setText(str(MaxTemp))
                self.ui.motor_param_txt_9.setVisible(False)
                self.ui.motor_param_txt_9.setText(str(MaxTemp))
                self.ui.motor_param_txt_10.setText(str(PkForce))
                self.ui.motor_param_txt_11.setText(str(ContForce))
                
                self.ui.motor_param_label_1.setText("Force Constant")
                self.ui.motor_param_label_2.setText("Motor Constant")
                self.ui.motor_param_label_3.setText("Back EMF")
                self.ui.motor_param_label_4.setText("Hot Coil Resistance")
                self.ui.motor_param_label_5.setText("Thermal Resistance")
                self.ui.motor_param_label_6.setText("Coil Mass")
                self.ui.motor_param_label_7.setText("Coil Length")
                self.ui.motor_param_label_8.setText("Max Temp")
                self.ui.motor_param_label_9.setVisible(False)
                self.ui.motor_param_label_9.setText("Max Temp") 
                self.ui.motor_param_label_10.setText("Peak Force")
                self.ui.motor_param_label_11.setText("Continuous Force")
                
                self.ui.motor_units_label_1.setText("N/Apk")
                self.ui.motor_units_label_2.setText("N/√W")
                self.ui.motor_units_label_3.setText("V/(m/s)")
                self.ui.motor_units_label_4.setText("Ω")
                self.ui.motor_units_label_5.setText("°C/W")
                self.ui.motor_units_label_6.setText("kg")
                self.ui.motor_units_label_7.setText("mm")
                self.ui.motor_units_label_8.setText("°C")
                self.ui.motor_units_label_9.setVisible(False)
                self.ui.motor_units_label_10.setText("N")
                self.ui.motor_units_label_11.setText("N")
            elif motorType == "Rotary":
                # print("rotary")
                if self.ui.txt_stage_type.text()=="":
                    self.ui.label_36.setText("kg*m^2")
                    self.ui.label_16.setText("Inertia:")
                self.ui.txt_motor_type.setText("Rotary")
                if not self.ui.txt_ambient_temperature.text():
                    ambient_temperature = 20
                else:
                    ambient_temperature = float(self.ui.txt_ambient_temperature.text())  # C
                PkTorque = motor_spec_vals[motor_spec_names.index("PeakTorque")]
                ContTorque = motor_spec_vals[motor_spec_names.index("ContStallTorque")]
                TorqueConst = motor_spec_vals[motor_spec_names.index("TorqueConstantPeak")]
                MotorConst = motor_spec_vals[motor_spec_names.index("MotorConstant")]
                MaxTemp = motor_spec_vals[motor_spec_names.index("MaxTemp")]
                BEMF = motor_spec_vals[motor_spec_names.index("BackEmfConstant")]
                Resist = motor_spec_vals[motor_spec_names.index("ResistanceAt25C")]
                HotCoilResist = motor_spec_vals[motor_spec_names.index("ResistanceAtMaxTemp")]
                # print("Motor Constant" + str(MotorConst))
                # print("Max Temp" + str(MaxTemp))
                # print("Ambient Temp" + str(ambient_temperature))
                # print("Continuous Force" + str(ContTorque))
                if self.isStepper is False:
                    ThermalResist = round(float(MotorConst)*float(MotorConst)*(float(MaxTemp)-25)/ float(ContTorque)**2,2)
                try:
                    MotorInertia = motor_spec_vals[motor_spec_names.index("RotationalInertia")]
                except ValueError:
                    MotorInertia = 0
                try:
                    NumPoles = int(float(motor_spec_vals[motor_spec_names.index("NumPoles")]))
                except ValueError:
                    NumPoles = 0
                if MotorInertia=='':
                    #print("Motor Inertia" +MotorInertia)
                    MotorInertia=0
                if MotorInertia is None:
                    MotorInertia=0
                
                Inductance = round(float(motor_spec_vals[motor_spec_names.index("Inductance")])/1000,5)
                
                self.ui.motor_param_txt_1.setText(str(MotorInertia))
                self.ui.motor_param_txt_2.setText(str(TorqueConst))
                self.ui.motor_param_txt_3.setText(str(MotorConst))
                self.ui.motor_param_txt_4.setText(str(BEMF))
                self.ui.motor_param_txt_5.setText(str(Resist))
                self.ui.motor_param_txt_6.setText(str(Inductance))
                if self.isStepper is False:
                    self.ui.motor_param_txt_7.setText(str(ThermalResist))
                self.ui.motor_param_txt_8.setText(str(NumPoles))
                self.ui.motor_param_txt_9.setVisible(True)
                self.ui.motor_param_txt_9.setText(str(MaxTemp))
                self.ui.motor_param_txt_10.setText(str(PkTorque))
                self.ui.motor_param_txt_11.setText(str(ContTorque))
                
                
                self.ui.motor_param_label_1.setText("Motor Inertia")
                self.ui.motor_param_label_2.setText("Torque Constant")
                self.ui.motor_param_label_3.setText("Motor Constant")
                self.ui.motor_param_label_4.setText("Back EMF")
                self.ui.motor_param_label_5.setText("Resistance")
                self.ui.motor_param_label_6.setText("Inductance")
                self.ui.motor_param_label_7.setText("Thermal Resistance")
                self.ui.motor_param_label_8.setText("Number of Poles")
                self.ui.motor_param_label_9.setVisible(True)
                self.ui.motor_param_label_9.setText("Max Temp")      
                self.ui.motor_param_label_10.setText("Peak Torque")  
                self.ui.motor_param_label_11.setText("Continuous Torque")  
                
    
                self.ui.motor_units_label_1.setText("kg-m-m")
                self.ui.motor_units_label_2.setText("N-m/A(pk)")
                self.ui.motor_units_label_3.setText("N/√W")
                self.ui.motor_units_label_4.setText("Vpk/krpm")
                self.ui.motor_units_label_5.setText("Ω")
                self.ui.motor_units_label_6.setText("H")
                self.ui.motor_units_label_7.setText("°C/W")
                self.ui.motor_units_label_8.setText("")
                self.ui.motor_units_label_9.setVisible(True)
                self.ui.motor_units_label_9.setText("°C")
                self.ui.motor_units_label_10.setText("N-m")
                self.ui.motor_units_label_11.setText("N-m")
            self.calc_results()
        except:
            msg = QtWidgets.QMessageBox()
            msg.setText("Failed to confiure a stage")
            msg.setIcon(QtWidgets.QMessageBox.Warning)
            msg.setWindowTitle("Error Configuration!")
            msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
            msg.exec_()
            return

    def on_drive_change(self, drive):
        """Updates Drive properties when drop-down is changed. Calcs new results.

        Args:
            drive (str): newly selected Drive from drop-down.

        """
        self.store_inputs()
        if drive:
            con = lite.connect(db_filepath)
            with con:
                cur = con.cursor()
                cur.execute("SELECT * FROM Drives WHERE Name='%s'" % drive)
                record = cur.fetchone()

            self.ui.txt_peak_output_current.setText(record[3])
            self.ui.txt_continuous_output_current.setText(record[4])
            self.ui.cmb_select_bus_voltage.setCurrentIndex(self.ui.cmb_select_bus_voltage.findText("--Select--"))
            self.calc_results()

            self.bus_voltage_visible()

    def on_bus_change(self, bus):
        """Calcs new results when Bus Voltage is changed.

        Args:
            bus (str): newly selected Bus Voltage from drop-down.

        """
        self.store_inputs()
        if bus == "--Select--":
            return

        self.calc_results()


def main():
    """Main Application."""
    app = QtWidgets.QApplication(sys.argv)
    if not getattr(sys, 'frozen', False):
        pixmap = QtGui.QPixmap('splash.png', 'PNG')
    else:
        pixmap = QtGui.QPixmap(resource_path('splash.png'), 'PNG')
    splash_screen = QtWidgets.QSplashScreen(pixmap)
    splash_screen.show()
    application = App()
    application.show()
    splash_screen.finish(application)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()