# Holds data about a single ads1115 pin/channel
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


# Holds metadata and config about a log
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

    # Returns the metadata printed at the start of a log
    def GetMeta(self):
        values = {'id': self.id, 'project': self.project, 'work pack': self.work_pack, 'job sheet': self.job_sheet,
                  'name': self.name, 'test number': self.test_number, 'time interval': self.time,
                  'logged by': self.loggedBy, 'description': self.description}
        return values

    # Used to return the Pin object corresponding to a name
    def GetPin(self,name):
        for pin in self.config:
            if pin.name == name:
                return pin

    # Set enabled to the number of pins enabled
    def SetEnabled(self):
        for pin in self.config:
            if pin.enabled:
                self.enabled += 1


# This is the code that is run when the program is loaded.
# If the module were to be imported, the code inside the if statement would not run.
if __name__ == "__main__":
    # Warning that logger will not work
    print("\nWARNING - This script cannot be run directly."
          "\nPlease run 'main.py' to start the logger, or use the desktop icon.\n")
    # Script will exit
