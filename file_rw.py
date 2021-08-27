# This file contains functions that interact with the raw and config files
# Reading, writing and renaming operations happens here
# Writing raw data happens in logger.py instead due to separate processes

import logObjects as lgOb
import databaseOp as db
import configparser
from decimal import Decimal
import os
import os.path
from os import path


# Read config data in from a config file
def ReadLogConfig(path):
    # Setup config parser and read config file
    config = configparser.ConfigParser()
    config.read(path)
    configData = []
    # For each pin section, create a pin object and add to configData
    for idx, section in enumerate(config.sections()):
        if section != 'General':
            pin = lgOb.Pin()
            pin.id = idx
            pin.name = section
            pin.enabled = config[section].getboolean('enabled')
            pin.fName = config[section]['friendlyName']
            pin.inputType = config[section]['inputtype']
            pin.gain = config[section].getint('gain')
            pin.scaleMin = config[section].getfloat('scalelow')
            pin.scaleMax = config[section].getfloat('scalehigh')
            pin.units = config[section]['unit']
            # Only add m and c if they are in the config
            if "m" in config[section] and "c" in config[section]:
                pin.m = config[section].getfloat('m')
                pin.c = config[section].getfloat('c')
            configData.append(pin)
    if configData == []:
        raise FileNotFoundError
    return configData


# Write config data to file
def WriteLogConfig(log,name):
    # Create files and outbox directories if they don't exist
    os.makedirs(os.path.dirname("files/outbox/conf{}.ini".format(name)), exist_ok=True)
    # Create new config file with name of log as the name
    with open("files/outbox/conf{}.ini".format(name),"w") as configfile:
        # Write general settings
        file_data = ""
        file_data += "[General]\n"
        file_data += "timeinterval = " + str(log.time) + "\n"
        file_data += "name = " + log.name + "\n"
        file_data += "description = " + log.description + "\n"
        file_data += "project = " + str(log.project) + "\n"
        file_data += "workpack = " + str(log.work_pack) + "\n"
        file_data += "jobsheet = " + str(log.job_sheet) + "\n\n"
        # Iterate through each Pin and write the data for that Pin
        for pin in log.config:
            file_data += "[" + pin.name + "]\n"
            file_data += "enabled = " + str(pin.enabled) + "\n"
            file_data += "friendlyname = " + pin.fName + "\n"
            file_data += "inputtype = " + pin.inputType + "\n"
            file_data += "gain = " + str(pin.gain) + "\n"
            file_data += "scalelow = " + str(pin.scaleMin) + "\n"
            file_data += "scalehigh = " + str(pin.scaleMax) + "\n"
            file_data += "unit = " + pin.units + "\n"
            file_data += "m = " + str(pin.m) + "\n"
            file_data += "c = " + str(pin.c) + "\n\n"
        # Write data to file
        configfile.write(file_data)
    # Update config path in database to reflect file just written
    db.UpdateConfigPath(log.id, "files/outbox/conf{}.ini".format(name))
    return


# Rename a config
# This happens after a log, where the name is changed to reflect the timestamp
def RenameConfig(path,timestamp):
    # Create the newpath and replace the old name with the new name
    newpath = "files/outbox/conf{}.ini".format(timestamp)
    os.rename(src=path,dst=newpath)


# Used to check if a raw data file exists for a log
def CheckData(rawpath):
    # If the file exists, return the path of the file
    if path.exists(rawpath):
        return rawpath
    else:
        return ""


# Returns the length in lines of a raw data file
# Used to set size for a log in the database
def GetSize(path):
    lineNum = 0
    with open(path, "r") as file:
        line = file.readline()
        # Read lines until reached the end of the file
        while line != "":
            lineNum += 1
            line = file.readline()
    return lineNum

# This is the code that is run when the program is loaded.
# If the module were to be imported, the code inside the if statement would not run.
if __name__ == "__main__":
    # Warning that logger will not work
    print("\nWARNING - This script cannot be run directly."
          "\nPlease run 'main.py' to start the logger, or use the desktop icon.\n")
    # Script will exit
