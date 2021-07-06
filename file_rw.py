import logObjects as lgOb
import databaseOp as db
import configparser
from decimal import Decimal
import os

def ReadLogData(path,log):

    adcHeader = []
    for pin in log.config.pinList:
        if pin.enabled == True:
            adcHeader.append(pin.name)

    log.logData = lgOb.LogData()
    log.logData.InitRawConv(len(adcHeader))
    with open(path, "r") as data:
        # Skip over header line
        data.readline()
        line = data.readline().split(",")
        # Read each line and add data to logData object
        while line != ['']:
            log.logData.timeStamp.append(line[0])
            log.logData.time.append(float(line[1]))
            values = line[2:]
            rawData = []
            convData = []
            for no, value in enumerate(values):
                rawData.append(float(value))
                pinName = adcHeader[no]
                # Convert rawData using config settings
                convertedVal = float(value) * log.config.GetPin(pinName).m + log.config.GetPin(pinName).c
                convData.append(convertedVal)
            log.logData.AddRawData(rawData)
            log.logData.AddConvData(convData)
            line = data.readline().split(",")
    return log.logData


def ReadLogConfig(path):
    config = configparser.ConfigParser()
    config.read(path)
    log = lgOb.LogMeta()
    log.config = lgOb.ConfigFile()
    log.name = config['General']['name']
    log.time = Decimal(config['General']['timeinterval'])

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
            if "m" in config[section] and "c" in config[section]:
                pin.m = config[section].getfloat('m')
                pin.c = config[section].getfloat('c')
            log.config.pinList.append(pin)

    return log.config


def WriteLogConfig(log,name):
    ## Create files and outbox directories if they don't exist
    os.makedirs(os.path.dirname("files/outbox/conf{}.ini".format(name)), exist_ok=True)
    # Create new config file with timestamp of log as the name
    with open("files/outbox/conf{}.ini".format(name),"w") as configfile:
        file_data = ""
        file_data += "[General]\n"
        file_data += "timeinterval = " + str(log.time) + "\n"
        file_data += "name = " + log.name + "\n\n"

        # Iterate through each Pin and write the data for that Pin
        for pin in log.config.pinList:
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
        configfile.write(file_data)
    db.UpdateConfigPath(db.GetRecentId(), "files/outbox/conf{}.ini".format(name))


def RenameConfig(path,timestamp):
    newpath = "files/outbox/conf{}.ini".format(timestamp)
    os.rename(src=path,dst=newpath)