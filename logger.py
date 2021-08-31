# This is the main Raspberry Pi Logging Script
# It has 3 sections: 1. Import, 2. Print Settings, 3. Log These are called at the bottom of the program
# 1. Calls the init() function which loads config by calling generalImport() and are lettingsImport().
# General settings (dictionary) and input specific settings (as objects) creating a list of pins to log
# 2. Iterates through lists and nicely formats and prints data
# 3. Setup logging (time interval etc.) then iterate through devices, grab data and save to CSV until stopped.

# Import Packages/Modules
import time
from datetime import datetime, timedelta
# Tries to import modules for Pi
try:
    import adafruit_ads1x15.ads1115 as ADS
    from adafruit_ads1x15.analog_in import AnalogIn
    from adafruit_ads1x15.ads1x15 import Mode
    import busio
    import board
# If on a laptop/dev computer, above will fail
# Import fake dev modules instead
except:
    from AnalogInFake import AnalogIn as AnalogIn
    import ADS1115Fake as ADS
    from adafruit_ads1x15.ads1x15 import Mode
import csv
import shutil
import file_rw
import logObjects as lgOb
import databaseOp as db
import os
from multiprocessing import Value, Event
import psutil


class Logger():

    def __init__(self):
        # Flag for multithreaded (GUI) to see if error has occurred during import
        self.logEnbl = False
        # Log object used to hold metadata and config data for log
        self.logComp = lgOb.LogMeta()
        # Stores names of pins set to log
        self.adcHeaders = []
        # Stores AnalogIn objects of pins set to log
        self.adcToLog = []


    # Initial Import and Setup
    def init(self, printFunc):
        self.logEnbl = True
        # dataRate of the A/D (see the ADS1115 datasheet for more info)
        dataRate = 860

        # Create the I2C bus
        try:
            i2c = busio.I2C(board.SCL, board.SDA, frequency=1000000)
        except:
            i2c = "fake"
        # A/D Setup - Create 4 Global instances of ADS1115 ADC (16-bit) according to Adafruit Libraries
        # ValueError thrown if board not connected
        # Not fatal as you could only be logging on one board
        try:
            adc0 = ADS.ADS1115(i2c, address=0x48, mode=Mode.SINGLE, data_rate=dataRate)
        except ValueError:
            adc0 = ""
        try:
            adc1 = ADS.ADS1115(i2c, address=0x49, mode=Mode.SINGLE, data_rate=dataRate)
        except ValueError:
            adc1 = ""
        try:
            adc2 = ADS.ADS1115(i2c, address=0x4a, mode=Mode.SINGLE, data_rate=dataRate)
        except ValueError:
            adc2 = ""
        try:
            adc3 = ADS.ADS1115(i2c, address=0x4b, mode=Mode.SINGLE, data_rate=dataRate)
        except ValueError:
            adc3 = ""

        # Store list of boards
        adcs = [adc0,adc1,adc2,adc3]
        # Run Code to import general metadata
        self.generalImport(printFunc)
        # Run code to import input settings
        self.inputImport(adcs, printFunc)


    # Import General Settings
    def generalImport(self, printFunc):
        printFunc("Configuring General Settings... ", flush=True)
        try:
            # Gets the most recent log metadata from the database
            self.logComp = db.GetRecentMetaData()
            printFunc("Success!\n")
        # If there is no data in database, alert user and stop log
        except ValueError:
            printFunc("ERROR - Have you sent over a log config.")
            self.logEnbl = False


    # Import Input Settings for pins
    def inputImport(self,adcs,printFunc):
        printFunc("Configuring Input Settings... ", flush=True)
        try:
            # Gets the most recent config filepath from the database
            self.logComp.config_path = db.GetConfigPath(db.GetRecentId())
            self.logComp.config = file_rw.ReadLogConfig(self.logComp.config_path)

            # List of pins to be logged and the list containing the logging functions
            self.adcHeader = []
            self.adcToLog = []
            # ADC Pin Map List - created now the gain information has been grabbed.
            # This gives the list of AnalogIn objects used to retrieve data from a pin
            pinDict = {0: ADS.P0, 1: ADS.P1, 2: ADS.P2, 3: ADS.P3}
            adcPinMap = {}
            # Dynamically create adcPinMap depending on the boards connected
            for idx, adc in enumerate(adcs):
                tempDict = {}
                if adc != "":
                    for i in range(0,4):
                        tempDict["{}A{}".format(idx,i)] = AnalogIn(ads=adc, positive_pin=pinDict[i], gain=self.logComp.config[4 * idx + i].gain)
                    adcPinMap["{}AX".format(idx)] = tempDict

            # Run code to find pins set to logged.
            for pin in self.logComp.config:
                if pin.enabled == True:
                    self.adcToLog.append(adcPinMap[pin.name[0] + "AX"][pin.name])
                    self.adcHeader.append(pin.name)
                else:
                    pass

            # Check to see at least 1 input is enable
            if len(self.adcToLog) == 0:
                printFunc("\nERROR - No Inputs set to Log! Please enable at least one input and try again")
                self.logEnbl = False
            else:
                printFunc("Success!")
            self.logComp.SetEnabled()

        # Exception raised when no config returned from database
        except ValueError:
            printFunc("ERROR - Failed to read Input Settings - Have you sent over a log config")
            self.logEnbl = False
        # Exception raised when there is a pin set to log on a board that isn't connected
        except KeyError:
            printFunc("ERROR - Couldn't find ADC board")
            printFunc("Check boards are connected correctly and pins are set for the connected boards.")
            self.logEnbl = False
        # If file doesn't exist, alert user and stop log
        except TypeError:
            printFunc("ERROR - Failed to read Input Settings - Have you sent over a log config")
            self.logEnbl = False
        except FileNotFoundError:
            printFunc("ERROR - Failed to read Input Settings - Have you sent over a log config")
            db.DatabaseCheck()
            self.logEnbl = False


            # Checks that log test number hasn't already been used
    # This is to stop database collisions if logger is rerun without uploading a new config
    def checkTestNumber(self):
        # Check that the most recent log has no data file
        # If it does, increment the id and test number by one, and create a new database entry
        if db.CheckDataTable(str(self.logComp.id)) == True:
            self.logComp.id += 1
            self.logComp.test_number = db.GetTestNumber(self.logComp.name) + 1
            # Write new log entry to database
            db.WriteLog(self.logComp)
            # Write copy of config settings under new log name
            file_rw.WriteLogConfig(self.logComp, self.logComp.name)


    # Output Current Settings
    def settingsOutput(self,printFunc):
        # Print General Settings then Input Settings
        printFunc("\nCurrent General Settings:")
        metaData = self.logComp.GetMeta()
        # Iterate through the relevant metadata and print each key and value
        for key in metaData:
            printFunc("{}: {}".format(key.title(), metaData[key]))
        printFunc("\nCurrent Input Settings: (Settings Hidden for Disabled Inputs)")
        printFunc("-" * 67)
        # Top Row Headings
        printFunc(
            "|{:>2}|{:>4}|{:>5}|{:>10}|{:>10}|{:>4}|{:>14}|{:>9}|".format("No", "Name", "Enbl", "F.Name", "Input Type",
                                                                          "Gain", "Scale", "Unit"))
        printFunc("-" * 67)
        # Print input settings for each Pin
        for pin in self.logComp.config:
            # Only print full settings if that channel is enabled
            if pin.enabled == True:
                printFunc("|{:>2}|{:>4}|{:>5}|{:>10}|{:>10}|{:>4}|{:>7}{:>7}|{:>9}|".format(pin.id, pin.name,
                                                                                        str(pin.enabled),
                                                                                        pin.fName,
                                                                                        pin.inputType,
                                                                                        pin.gain,
                                                                                        pin.scaleMin,
                                                                                        pin.scaleMax,
                                                                                        pin.units))
            # If channel not enabled
            else:
                printFunc("|{:>2}|{:>4}|{:>5}|{:>10}|{:>10}|{:>4}|{:>7}{:>7}|{:>9}|".format(pin.id, pin.name,
                                                                                        str(pin.enabled),
                                                                                        "-",
                                                                                        "-",
                                                                                        "-",
                                                                                        "-",
                                                                                        "-",
                                                                                        "-"))
        # FILE MANAGEMENT
        printFunc("\nDisk Usage:")
        # Get Users Remaining Disk Space - (Convert it from Bytes into MegaBytes)
        remainingSpace = (shutil.disk_usage(os.path.realpath('/'))[2] / 1e6)
        # Output space - rounding to a nice number
        printFunc("Current Free Disk Space: {} MB".format(round(remainingSpace, 2)))

        # Calculate amount of time left for logging
        # Find out Size (in MB) of Each Row
        rowMBytes = 7 / 1e6
        # Find amount of MB written each second
        MBEachSecond = (rowMBytes * self.logComp.enabled) / self.logComp.time
        # Calculate time remaining using free space
        timeRemSeconds = remainingSpace / MBEachSecond
        # Add time in seconds to current datetime to give data it will run out of space
        timeRemDate = datetime.now() + timedelta(0, timeRemSeconds)
        printFunc("With the current config, you will run out of space on approximately: {}"
              "\nIf you need more space, use the UI to download previous logs and delete them on the Pi."
            .format(timeRemDate.strftime("%Y-%m-%d %H:%M:%S")))
        printFunc("\nStart Logging...\n")


    # Logging Script
    # Normally this function is run in a separate process to everything else
    # This is to make sure that logging is consistent, accurate and unaffected by GUI slowdowns.
    def log(self, logEnbl, values, readOnce):
        # Sets the priority of the process higher
        p = psutil.Process(os.getpid())
        try:
            p.nice(psutil.IOPRIO_CLASS_RT)
        # If run on a non-linux computer, this is needed instead
        except:
            p.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
        # Get Time Interval
        timeInterval = float(self.logComp.time)
        # Find the length of what each row will be in the CSV (from which pins are being logged)
        csvRows = len(self.adcToLog)
        # Set up list to be printed to CSV
        adcValues = [0] * csvRows
        # Get timestamp for filename
        timeStamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        # CSV - Create/Open CSV file and print headers
        with open('files/outbox/raw{}.csv'.format(timeStamp), 'w', newline='') as csvfile:
            # Create csv writer
            writer = csv.writer(csvfile, dialect="excel", delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
            writer.writerow(['Date/Time', 'Time Interval (seconds)'] + self.adcHeader)
            # Set start time use for calculating time interval and sleeping script for correct time
            startTime = time.perf_counter()
            # While set to log, log data
            # Event is set by GUI when log is toggled
            while not logEnbl.is_set():
                try:
                    # Get current datetime and time elapsed from start
                    currentDateTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
                    timeElapsed = round(time.perf_counter() - startTime, 2)
                    # Export Data to Spreadsheet inc current datetime and time elapsed
                    # Set values array for live data output
                    for idx, pin in enumerate(self.adcToLog):
                        adcValues[idx] = pin.value
                        values[idx] = pin.value
                    writer.writerow([currentDateTime] + [timeElapsed] + adcValues)
                    if (readOnce.is_set() == False):
                        readOnce.set()
                    # Reset list values (so we can see if code fails)
                    adcValues = [0] * csvRows
                except OSError:
                    pass
                # Work out time delay needed until next set of values taken based on user given value
                # (Using some clever maths)
                timeDiff = (time.perf_counter() - startTime)
                time.sleep(timeInterval - (timeDiff % timeInterval))

        self.logComp.date = timeStamp
        # Update date on database
        db.AddDate(self.logComp.date,self.logComp.id)
        # Update config file
        self.logComp.config_path = db.GetConfigPath(self.logComp.id)
        file_rw.RenameConfig(self.logComp.config_path,self.logComp.date)
        db.UpdateConfigPath(self.logComp.id,"files/outbox/conf{}.ini".format(self.logComp.date))
        # Add path of raw data to database entry
        db.UpdateDataPath(self.logComp.id,"files/outbox/raw{}.csv".format(self.logComp.date))
        # Add size of log to database entry
        db.UpdateSize(self.logComp.id,file_rw.GetSize(db.GetDataPath(self.logComp.id)))



    # Contains functions for running of logger
    # Starts the initialisation process
    # This is done by GUI normally
    def run(self, printFunc):
        # Load Config Data and Setup
        self.init(printFunc)
        # Only continue if import was successful
        if self.logEnbl is True:
            self.checkTestNumber()
            # Print Settings
            self.settingsOutput(printFunc)
            # Run Logging
            self.log()
        else:
            self.logEnbl = False


# This is the code that is run when the program is loaded.
# If the module were to be imported, the code inside the if statement would not run.
if __name__ == "__main__":
    # Warning that logger will not work
    print("\nWARNING - This script cannot be run directly."
          "\nPlease run 'main.py' to start the logger, or use the desktop icon.\n")
    # Script will exit
