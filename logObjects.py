# Holds data about a single pin/channel
class Pin():

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


# Holds all data about a log
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
        self.config = []
        self.enabled = 0
        self.config_path = ""
        self.data_path = ""
        self.size = 0
        self.description = ""

    def GetMeta(self):
        values = {'id': self.id, 'project': self.project, 'work pack': self.work_pack, 'job sheet': self.job_sheet,
                  'name': self.name, 'test number': self.test_number, 'date': self.date, 'time interval': self.time,
                  'logged by': self.loggedBy, 'downloaded by': self.downloadedBy, 'description': self.description}
        return values

    # Used to return a Pin object from their name
    def GetPin(self,name):
        for pin in self.config:
            if pin.name == name:
                return pin

    def SetEnabled(self):
        for pin in self.config:
            if pin.enabled:
                self.enabled += 1


"""
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
"""