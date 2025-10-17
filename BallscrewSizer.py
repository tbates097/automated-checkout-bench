from PyQt5 import QtWidgets, QtSql, QtGui, QtCore
from PyQt5.QtCore import pyqtSlot
from PyQt5.QtWidgets import QCompleter
from mainwindow import Ui_MainWindow
from popup_config_window import Ui_Dialog as popup_config
from popup_spec_display import Ui_Dialog as popup_spec_display
import sys
import os
import time
import re
import sqlite3 as lite
import datetime
import numpy as np
import traceback
# Suppress matplotlib backend messages
import matplotlib
matplotlib.use('Qt5Agg')
import matplotlib.pyplot as plt
plt.ioff()  # Turn off interactive mode
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as Canvas

# Version 1.08
# global definitions---------------------------------------

if not getattr(sys, 'frozen', False):
    dir_path = os.getcwd()
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
    db_filepath = os.path.join(dir_path,"ballscrew_sizer.db")  # use this when running in python
else:
    db_filepath = resource_path('ballscrew_sizer.db')  # change to this before deploying as .exe

if not getattr(sys, 'frozen', False):
    config_filepath = os.path.join(dir_path,"master.db")  # use this when running in python
else:
    config_filepath = resource_path('master.db')  # change to this before deploying as .exe

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
        
        # Setup the UI
        self.setupUi(self)

        self.spec_names = []
        self.spec_vals = []
        self.smart_string = ""

        # Disconnect default PyQt5 connections and replace them with our custom functions
        try:
            self.buttonBox.accepted.disconnect()
            self.buttonBox.rejected.disconnect()
        except TypeError:
            print("No default signals to disconnect.")

        # Connect buttons to our custom functions
        self.buttonBox.accepted.connect(self.handle_accept)
        self.buttonBox.rejected.connect(self.handle_reject)

    def handle_accept(self):
        self.configured = True
        if not self.isVisible():
            print("⚠️ WARNING: handle_accept was triggered AFTER exec_() returned!")

        self.accept()  # Ensure dialog is accepted

    def handle_reject(self):
        """Detect if reject() is being called too soon."""
        
        # Print a stack trace to see where reject() is being triggered from
        import traceback
        traceback.print_stack()
        
        self.configured = False
        self.reject()

    def reset_state(self):
        """Reset dialog state before showing."""
        self.configured = False
        self.spec_names = []
        self.spec_vals = []
        self.smart_string = ""

    def closeEvent(self, event):
        """Detect if the dialog is closing unexpectedly and print a stack trace."""
        print("❌ closeEvent called! Preventing premature closure.")
        
        # Print a stack trace to see where the close request is coming from
        traceback.print_stack()

        # Prevent closing unless user explicitly clicks OK or Cancel
        if not self.configured:
            print("Preventing premature closure. Dialog remains open.")
            event.ignore()
        else:
            print("Allowing closure.")
            event.accept()
    
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
                
    def return_values(parent = None, stage = None):
        stage = stage.rstrip()
        if parent is None:
            parent = QtWidgets.QApplication.instance()
        if hasattr(parent, 'dialog') and parent.dialog:
            print("⚠️ Deleting previous dialog instance to avoid reuse.")
            parent.dialog.deleteLater()
            del parent.dialog
        parent.dialog = PopupConfig(None, stage)
        dialog=parent.dialog
        dialog.reset_state()
        QtWidgets.QApplication.processEvents()
        dialog.setWindowModality(QtCore.Qt.ApplicationModal)
        dialog.setModal(True)

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
            dialog.setDBTable(dialog.inputs_app,dialog.stage)
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
            temp = dialog.stage 
            if dialog.stage.endswith("-Lower"):
                dialog.axis = 1
                temp = dialog.stage.replace("-Lower","")
            if dialog.stage.endswith("-Upper"):
                dialog.axis = 2
                temp = dialog.stage.replace("-Upper","")
            configs = temp.split("-")
            testAgainst = ["MPS50SL","ECO115SL","ECO165SL","ECO225SL"]
            planarCheck = ["PlanarDL","PlanarDLA","ATS3600","MPS50SV","MPS75SV","ANT95V","ANT130V","CCS130DR"]
            configs[1:] = ["-" + config for config in configs[1:]]
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
                dialog.checkRules(configs[1:], configs[0])
          
            dialog.setVisible(False)
       
        dialog.motor,dialog.mtr_spec_names,dialog.mtr_spec_vals,dialog.mtr_spec_dtype = dialog.getMotor()

        time.sleep(1)  # Give time to see if something else is closing it
        #loop = QtCore.QEventLoop()
        #dialog.finished.connect(loop.quit)
        result = dialog.exec_()
        #loop.exec_()  # Show the dialog and block until the user interacts

        dialog.setDBTable(dialog.inputs_app,stage)
        dialog.config_options.select()
        smart_string = []

        # if dialog.configured is False:
        config_selections = {}

        for idx, config in enumerate(dialog.config_boxes):
            dialog.config_options.select()
            if config.currentText() != "":
                dialog.config_options.setFilter("\"Value Description\" LIKE '" + config.currentText().rstrip() + "'")
                dialog.config_options.select()
                if dialog.config_options.rowCount() != 0:
                    value = str(dialog.config_options.record(0).value("Value"))
                    # Only add if the input name exists for this index
                    if idx < len(dialog.config_inputs):
                        config_selections[dialog.config_inputs[idx]] = value
    
        motor_smart_string=""
        stage_config = stage
        for item in smart_string:
            stage_config = stage_config + item
        if dialog.axis == 1 and not stage_config.endswith("-Lower"):
            stage_config = stage_config + "-Lower"
        if dialog.axis == 2 and not stage_config.endswith("-Upper"):
            stage_config = stage_config + "-Upper"
        configs =[]
        if dialog.motor != "":
            motorConfig= dialog.motor.split(" ",1)
            if len(motorConfig) > 1:
                configs = re.findall(r'"(.*?)"', motorConfig[1])
                motor_smart_string = motorConfig[0]
                dialog.setDBTable(dialog.inputs_app,motorConfig[0])
                dialog.config_options.select()
                if motorConfig[0].endswith("_Specs"):
                    motorConfig[0]= motorConfig[0][:-6]
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
        # Show the dialog and wait for the result
        spec_names = dialog.spec_names
        spec_vals = dialog.spec_vals
        smart_string = smart_string
        param_dict = dict(zip(spec_names, spec_vals))

        del dialog
        if result == QtWidgets.QDialog.Accepted:
            return config_selections, param_dict
        else:
            print('Cancelled')
            return None, None, None

class App(QtWidgets.QMainWindow):
    """Main Window"""
    def __init__(self):
        super(App, self).__init__()
        """Initialize all UI elements, mostly linking buttons to functions and tables to sources."""
  
    def show_popup_config_dialog(self, stage=None):
        #self.clear_results()
        if stage == "":
            print("no stage to configure")
            return
        else:
            # Call return_values and handle the result
            result = PopupConfig.return_values(stage=stage)
            if not result:  # Check if configuration was canceled
                print("Configuration canceled. Waiting for user inputs.")
                return

            # Extract configuration values
            smart_string = result
            #self.file_change()
            #self.model = Model(self)
            #self.ui.list_motion.setModel(self.model)
            #self.ui.list_motion.selectRow(self.model.rowCount()-1)
        return smart_string

    