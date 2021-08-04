from queue import Queue

# Holds data about a single pin/channel
class Pin():
    id = 0
    name = ""
    enabled = False
    fName = ""
    inputType = ""
    gain = 0
    scaleMin = 0
    scaleMax = 0
    units = ""
    m = 0
    c = 0

    def __init__(self):
        self.id = 0
        self.name = ""
        self.enabled = False
        self.fName = ""
        self.inputType = ""
        self.gain = 0
        self.scaleMin = 0
        self.scaleMax = 0
        self.units = ""
        self.m = 0
        self.c = 0


# Acts as a configfile, holding information about all the pins/channels
class ConfigFile():
    pinList = []
    enabled = 0

    def __init__(self):
        self.pinList = []
        self.enabled = 0

    # Used to return a Pin object from their name
    def GetPin(self,name):
        for pin in self.pinList:
            if pin.name == name:
                return pin

    def SetEnabled(self):
        for pin in self.pinList:
            if pin.enabled:
                self.enabled += 1


# Holds the logged data for a log
class LogData():

    def __init__(self):
        self.timeStamp = []
        self.time = []
        # rawData and convData are lists which contain lists
        # Each list inside corresponds to data from a single pin/channel
        self.rawData = []
        self.convData = []
        self.tcpQueue = Queue()

    # Initialises the rawData and convData by populating them with empty lists
    def InitRawConv(self,pinNum):
        for i in range(0,pinNum):
            self.rawData.append([])
            self.convData.append([])

    # Used to add one value to each rawData column
    def AddRawData(self, values):
        i = 0
        for value in values:
            self.rawData[i].append(value)
            i += 1

    # Used to add one value to each convData column
    def AddConvData(self, values):
        i = 0
        for value in values:
            self.convData[i].append(value)
            i += 1

    # Gets the most recent data from the rawData column
    def GetLatest(self):
        row = []
        for column in self.rawData:
            row.append(column[-1])
        return row


# Holds all data about a log
# Contains a ConfigFile and LogData object
class LogMeta():

    def __init__(self):
        self.id = 0
        self.project = 0
        self.work_pack = 0
        self.job_sheet = 0
        self.name = ""
        self.test_number = 0
        self.date = ""
        self.time = 0
        self.loggedBy = ""
        self.downloadedBy = ""
        self.config = ConfigFile()
        self.logData = LogData()
        self.config_path = ""
        self.data_path = ""
        self.size = 0
        self.description = ""

    def GetMeta(self):
        values = {}
        values['id'] = self.id
        values['project'] = self.project
        values['work pack'] = self.work_pack
        values['job sheet'] = self.job_sheet
        values['name'] = self.name
        values['test number'] = self.test_number
        values['date'] = self.date
        values['time interval'] = self.time
        values['logged by'] = self.loggedBy
        values['downloaded by'] = self.downloadedBy
        values['description'] = self.description
        return values
