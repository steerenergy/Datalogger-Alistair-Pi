# This is the main Raspberry Pi Logging Script
# It has 3 sections: 1. Import, 2. Print Settings, 3. Log These are called at the bottom of the program
# 1. Calls the init() function which loads config by calling generalImport() and are lettingsImport().
# General settings (dictionary) and input specific settings (as objects) creating a list of pins to log
# 2. Iterates through lists and nicely formats and prints data
# 3. Setup logging (time interval etc.) then iterate through devices, grab data and save to CSV until stopped.

# Import Packages/Modules
import queue
import time
from datetime import datetime, timedelta
from collections import OrderedDict
import configparser
import functools
# Uncomment below for real adc (if running on Pi)
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from adafruit_ads1x15.ads1x15 import Mode
import busio
import board
# Uncomment below for fake adc simulation if using a PC
#from AnalogInFake import AnalogIn as AnalogIn
#import ADS1115Fake as ADS

import csv
import threading
import shutil
import os

import file_rw
import logObjects as lgOb
import databaseOp as db
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import os
from decimal import Decimal
import numpy as np
import gui


# Initial Import and Setup
def init():
    # Flag for multithreaded (GUI) use to be triggered to stop logging loop
    global logEnbl
    logEnbl = True
    # dataRate of the A/D (see the ADS1115 datasheet for more info)
    global dataRate
    dataRate = 860
    # List of pins to be logged and the list containing the logging functions
    global adcToLog
    adcToLog = []
    global adcHeader
    adcHeader = []

    global adcValuesCompl
    adcValuesCompl = []
    # Log object used to hold general settings, config file and log data
    global logComp
    logComp = lgOb.LogMeta()
    # Create the I2C bus
    global i2c
    i2c = busio.I2C(board.SCL, board.SDA, frequency=1000000)
    #i2c = "fake"
    # A/D Setup - Create 4 Global instances of ADS1115 ADC (16-bit) according to Adafruit Libraries
    # (Objective 7)
    global adc0
    global adc1
    global adc2
    global adc3
    adc0 = ADS.ADS1115(i2c, address=0x48, mode=Mode.CONTINUOUS, data_rate=dataRate)
    adc1 = ADS.ADS1115(i2c, address=0x49, mode=Mode.CONTINUOUS, data_rate=dataRate)
    adc2 = ADS.ADS1115(i2c, address=0x4a, mode=Mode.CONTINUOUS, data_rate=dataRate)
    adc3 = ADS.ADS1115(i2c, address=0x4b, mode=Mode.CONTINUOUS, data_rate=dataRate)


    # Run Code to import general information
    # (Objective 7)
    generalImport()
    # Run code to import input settings
    # (Objective 8)
    inputImport()



# Import General Settings
# (Objective 7)
def generalImport():
    print("Configuring General Settings... ", end="", flush=True)
    global logComp
    try:
        # Gets the most recent log metadata from the database
        logComp = db.GetRecentMetaData()
        print("Success!")
    # Need to implement check in case retrieval is not possible
    except ValueError:
        print("ERROR - Have you sent over a log config.")
        global logEnbl
        logEnbl = False


# Import Input Settings
# (Objective 8)
def inputImport():
    # Load logEnbl variable
    global logEnbl
    print("Configuring Input Settings... ", end="", flush=True)
    # For all sections but general, parse the data from config.C
    # Create a new object for each one. The init method of the class then imports all the data as instance variables
    try:
        global logComp
        # Gets the most recent config data from the database
        logComp.config_path = db.GetConfigPath(db.GetRecentId())
        logComp.config = file_rw.ReadLogConfig(logComp.config_path)

        global adc0
        global adc1
        global adc2
        global adc3
        # ADC Pin Map List - created now the gain information has been grabbed.
        # This gives the list of possible functions that can be run to grab data from a pin.
        global adcPinMap
        adcPinMap = {
            "0AX": {
                "0A0": AnalogIn(ads=adc0, gain=logComp.config.pinList[0].gain, positive_pin=ADS.P0),
                "0A1": AnalogIn(ads=adc0, gain=logComp.config.pinList[1].gain, positive_pin=ADS.P1),
                "0A2": AnalogIn(ads=adc0, gain=logComp.config.pinList[2].gain, positive_pin=ADS.P2),
                "0A3": AnalogIn(ads=adc0, gain=logComp.config.pinList[3].gain, positive_pin=ADS.P3)
            },
            "1AX": {
                "1A0": AnalogIn(ads=adc1, gain=logComp.config.pinList[4].gain, positive_pin=ADS.P0),
                "1A1": AnalogIn(ads=adc1, gain=logComp.config.pinList[5].gain, positive_pin=ADS.P1),
                "1A2": AnalogIn(ads=adc1, gain=logComp.config.pinList[6].gain, positive_pin=ADS.P2),
                "1A3": AnalogIn(ads=adc1, gain=logComp.config.pinList[7].gain, positive_pin=ADS.P3)
            },
            "2AX": {
                "2A0": AnalogIn(ads=adc2, gain=logComp.config.pinList[8].gain, positive_pin=ADS.P0),
                "2A1": AnalogIn(ads=adc2, gain=logComp.config.pinList[9].gain, positive_pin=ADS.P1),
                "2A2": AnalogIn(ads=adc2, gain=logComp.config.pinList[10].gain, positive_pin=ADS.P2),
                "2A3": AnalogIn(ads=adc2, gain=logComp.config.pinList[11].gain, positive_pin=ADS.P3)
            },
            "3AX": {
                "3A0": AnalogIn(ads=adc3, gain=logComp.config.pinList[12].gain, positive_pin=ADS.P0),
                "3A1": AnalogIn(ads=adc3, gain=logComp.config.pinList[13].gain, positive_pin=ADS.P1),
                "3A2": AnalogIn(ads=adc3, gain=logComp.config.pinList[14].gain, positive_pin=ADS.P2),
                "3A3": AnalogIn(ads=adc3, gain=logComp.config.pinList[15].gain, positive_pin=ADS.P3)
            }
        }
        # Run code to choose which pins to be logged.
        for pin in logComp.config.pinList:
            if pin.enabled == True:
                adcToLog.append(adcPinMap[pin.name[0] + "AX"][pin.name])
                adcHeader.append(pin.name)
            else:
                pass
        print("Success!")

        # Check to see at least 1 input is enabled
        # (Objective 8.1)
        if len(adcToLog) == 0:
            print("\nERROR - No Inputs set to Log! Please enable at least one input and try again")
            logEnbl = False

    # Exception raised when no config returned from database
    except ValueError:
        print("ERROR - Failed to read Input Settings - Have you sent over a log config")
        logEnbl = False


# Output Current Settings
# (Objective 9)
def settingsOutput():
    global logComp
    global guiFrame
    guiFrame.channelSelect['values'] = ["None"]
    # Print General Settings then Input Settings
    print("\nCurrent General Settings:")
    metaData = logComp.GetMeta()
    # Iterate through the metadata and print each key and value
    for key in metaData:
        print("{}: {}".format(key.title(), metaData[key]))
    print("\nCurrent Input Settings: (Settings Hidden for Disabled Inputs)")
    x = 0
    print("-" * 67)
    # Top Row Headings
    print(
        "|{:>2}|{:>4}|{:>5}|{:>10}|{:>10}|{:>4}|{:>14}|{:>9}|".format("No", "Name", "Enbl", "F.Name", "Input Type",
                                                                      "Gain", "Scale", "Unit"))
    print("-" * 67)
    # Print input settings for each Pin
    for pin in logComp.config.pinList:
        # Only print full settings if that channel is enabled
        x += 1
        if pin.enabled == True:
            print("|{:>2}|{:>4}|{:>5}|{:>10}|{:>10}|{:>4}|{:>7}{:>7}|{:>9}|".format(x, pin.name,
                                                                                    str(pin.enabled),
                                                                                    pin.fName,
                                                                                    pin.inputType,
                                                                                    pin.gain,
                                                                                    pin.scaleMin,
                                                                                    pin.scaleMax,
                                                                                    pin.units))
            # Add channel to dropdown menu for live graphing
            # (Objective 17)
            guiFrame.channelSelect['values'] = (*guiFrame.channelSelect['values'], pin.fName)
        # If channel not enabled
        else:
            print("|{:>2}|{:>4}|{:>5}|{:>10}|{:>10}|{:>4}|{:>7}{:>7}|{:>9}|".format(x, pin.name,
                                                                                    str(pin.enabled),
                                                                                    "-",
                                                                                    "-",
                                                                                    "-",
                                                                                    "-",
                                                                                    "-",
                                                                                    "-"))


# Logging Script
# (Objective 11)
def log():
    global logComp
    global adcHeader
    global adcToLog
    # Set Time Interval
    # (Objective 11.2)
    timeInterval = float(logComp.time)
    # Find the length of what each row will be in the CSV (from which A/D are being logged)
    csvRows = len(adcToLog)
    # Set up list to be printed to CSV
    adcValues = [0] * csvRows
    # Get timestamp for filename
    timeStamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    # Update date on database
    # (Objective 11.1)
    db.AddDate(timeStamp,logComp.id)
    file_rw.RenameConfig(logComp.config_path,timeStamp)
    logComp.date = timeStamp

    # FILE MANAGEMENT
    print("\nDisk Usage:")
    # Get Users Remaining Disk Space - (Convert it from Bytes into MegaBytes)
    remainingSpace = (shutil.disk_usage(os.path.realpath('/'))[2] / 1e6)
    # Output space - rounding to a nice number
    print("Current Free Disk Space: {} MB".format(round(remainingSpace, 2)))

    # Calculate amount of time left for logging
    # Find out Size (in MB) of Each Row
    rowMBytes = 7 / 1e6
    # Find amount of MB written each second
    MBEachSecond = (rowMBytes * csvRows) / timeInterval
    # Calculate time remaining using free space
    timeRemSeconds = remainingSpace / MBEachSecond
    # Add time in seconds to current datetime to give data it will run out of space
    timeRemDate = datetime.now() + timedelta(0, timeRemSeconds)
    print("With the current config, you will run out of space on approximately: {}"
          "\nIf you need more space, use the UI to download previous logs and delete them on the Pi."
          .format(timeRemDate.strftime("%Y-%m-%d %H:%M:%S")))

    # Write config data to archive folder
    # (Objective 10)
    #WriteConfig(timeStamp)

    # CSV - Create/Open CSV file and print headers
    #with open('files/outbox/raw{}.csv'.format(timeStamp), 'w', newline='') as csvfile:
    #    writer = csv.writer(csvfile, dialect="excel", delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
    #    writer.writerow(['Date/Time', 'Time Interval (seconds)'] + adcHeader)
    #    print("\nStart Logging...\n")

        # Start live data thread
        # (Objective 12)
    #    dataThread = threading.Thread(target=liveData)
    #    dataThread.start()

        # Set startTime (method used ignores changes in system clock time)
    #    startTime = time.perf_counter()

        # Beginning of reading script
    #    while logEnbl is True:
            # Get time and send to Log
    #        currentDateTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    #        timeElapsed = round(time.perf_counter() - startTime, 2)

            # (Objective 11.3)
    #        for currentPin, channel in enumerate(adcToLog):
                # Get Raw data from A/D, and add to adcValues list corresponding to the current pin
    #            adcValues[currentPin] = channel.value

            # Export Data to Spreadsheet inc current datetime and time elapsed
            # (Objective 11.4)
    #        writer.writerow([currentDateTime] + [timeElapsed] + adcValues)
            # Copy list for data output and reset list values (so we can see if code fails)
    #        global adcValuesCompl
    #        adcValuesCompl = adcValues
    #        adcValues = [0] * csvRows

            # Work out time delay needed until next set of values taken based on user given value
            # (Using some clever maths)
            # (objective 11.2)
    #        timeDiff = (time.perf_counter() - startTime)
    #        time.sleep(timeInterval - (timeDiff % timeInterval))
        # Wait until live data thread is finished
    #    dataThread.join()
    # CSV - Create/Open CSV file and print headers
    with open('files/outbox/raw{}.csv'.format(timeStamp), 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, dialect="excel", delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['Date/Time', 'Time Interval (seconds)'] + adcHeader)
        print("\nStart Logging...\n")
        #dataThread = threading.Thread(target=liveData)
        #dataThread.start()

        startTime = time.perf_counter()
        while logEnbl is True:
            # Get time and send to Log
            currentDateTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            timeElapsed = round(time.perf_counter() - startTime, 2)

            # Export Data to Spreadsheet inc current datetime and time elapsed
            for idx, pin in enumerate(adcToLog):
                adcValues[idx] = pin.value
            writer.writerow([currentDateTime] + [timeElapsed] + adcValues)
            # Copy list for data output and reset list values (so we can see if code fails)
            global adcValuesCompl
            adcValuesCompl = adcValues
            adcValues = [0] * csvRows

            # Work out time delay needed until next set of values taken based on user given value
            # (Using some clever maths)
            # (objective 11.2)
            timeDiff = (time.perf_counter() - startTime)
            time.sleep(timeInterval - (timeDiff % timeInterval))
    db.UpdateDataPath(logComp.id,"files/outbox/raw{}.csv".format(timeStamp))



"""
# Writes the config data for the log to archive folder
# (Objective 10)
def WriteConfig(timestamp):
    global logComp
    # Create files and outbox directories if they don't exist
    os.makedirs(os.path.dirname("files/outbox/conf{}.ini".format(timestamp)), exist_ok=True)
    # Create new config file with timestamp of log as the name
    with open("files/outbox/conf{}.ini".format(timestamp),"w") as configfile:
        file_data = ""
        file_data += "[General]\n"
        file_data += "timeinterval = " + str(logComp.time) + "\n"
        file_data += "name = " + logComp.name + "\n\n"

        # Iterate through each Pin and write the data for that Pin
        for pin in logComp.config.pinList:
            file_data += "[" + pin.name + "]\n"
            file_data += "enabled = " + str(pin.enabled) + "\n"
            if pin.enabled == True:
                file_data += "friendlyname = " + pin.fName + "\n"
                file_data += "inputtype = " + pin.inputType + "\n"
                file_data += "gain = " + str(pin.gain) + "\n"
                file_data += "scalelow = " + str(pin.scaleMin) + "\n"
                file_data += "scalehigh = " + str(pin.scaleMax) + "\n"
                file_data += "unit = " + pin.units + "\n"
                file_data += "m = " + str(pin.m) + "\n"
                file_data += "c = " + str(pin.c) + "\n\n"
            # If a Pin is not enabled, use these values in the config
            else:
                file_data += "friendlyname = Edit Me\n"
                file_data += "inputtype = Edit Me\n"
                file_data += "gain = 1\n"
                file_data += "scalelow = 0.0\n"
                file_data += "scalehigh = 0.0\n"
                file_data += "unit = Edit Me\n\n"
        configfile.write(file_data)
"""


"""
# Read logged data from CSV and upload to database
# (Objective 13)
def uploadData():
    global logComp
    global adcHeader
    # Create a logData object to store logged data
    logComp.logData = lgOb.LogData()
    logComp.logData.InitRawConv(len(adcHeader))
    # Read logged CSV
    # (Objective 13.1)
    with open("files/outbox/raw{}.csv".format(logComp.date),"r") as data:
        # Skip over header line
        data.readline()
        line = data.readline().split(",")
        # Read each line and add data to logData object
        while line != ['']:
            logComp.logData.timeStamp.append(line[0])
            logComp.logData.time.append(float(line[1]))
            values = line[2:]
            rawData = []
            convData = []
            for no, value in enumerate(values):
                rawData.append(float(value))
                pinName = adcHeader[no]
                # Convert rawData using config settings
                convertedVal = float(value) * logComp.config.GetPin(pinName).m + logComp.config.GetPin(pinName).c
                convData.append(convertedVal)
            logComp.logData.AddRawData(rawData)
            logComp.logData.AddConvData(convData)
            line = data.readline().split(",")

    # Create list of headers for the database
    headerList = ["\'Date/Time\'","\'Time Interval (seconds)\'"]
    for pin in logComp.config.pinList:
        if pin.enabled == True:
            headerList.append("\'" + pin.name + "\'")
    for pin in logComp.config.pinList:
        if pin.enabled == True:
            headerList.append("\'" + pin.fName + "|" + pin.name + "|" + pin.units + "\'")

    # Write logged data to database
    # (Objective 13.2)
    db.WriteLogData(logComp, headerList)
"""


# Contains functions for normal run of logger
# Starts the initialisation process
def run(frame):
    global guiFrame
    guiFrame = frame
    # Load Config Data and Setup
    init()
    # Only continue if import was successful
    if logEnbl is True:
        global logComp
        # Check that the most recent log has no data table
        # If it does, create a new log in the database from the loaded in settings
        if db.CheckDataTable(str(logComp.id)) == True:
            # Give new log entry a new name by adding a number on the end
            # If there is already a number, increment the number by 1
            try:
                nameNum = int(logComp.name.split(' ')[-1])
                nameNum += 1
                logComp.name = (' ').join(logComp.name.split(' ')[:-1]) + " " + str(nameNum)
            except ValueError:
                nameNum = 1
                logComp.name = logComp.name + " " + str(nameNum)
            logComp.id += 1
            # Write new log entry to database
            db.WriteLog(logComp)
            file_rw.WriteLogConfig(logComp,logComp.name)
        # Print Settings
        settingsOutput()
        # Run Logging
        log()
    else:
        frame.logToggle()


# This is the code that is run when the program is loaded.
# If the module were to be imported, the code inside the if statement would not run.
# Calls the init() function and then the log() function
if __name__ == "__main__":
    # Warning about lack of CSV
    print("\nWARNING - running this script directly may produce a blank CSV. "
          "\nIf you need data to be recorded, use 'gui.py'\n")
    # Run logger as per normal setup
    run()
