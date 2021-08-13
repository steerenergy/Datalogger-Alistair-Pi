import socket
import time

import databaseOp as db
import logObjects as lgOb
from queue import Queue
from multiprocessing import Event
from datetime import datetime
from threading import Thread
from decimal import Decimal
import file_rw


class TcpClient():

    def __init__(self, client_socket, address, connTcp, exitTcp):
        self.client_socket = client_socket
        self.address = address
        self.connTcp = connTcp
        self.exitTcp = exitTcp
        self.dataQueue = Queue()
        self.quitEvent = Event()
        self.listener = Thread(target=self.TcpListen, args=())
        self.listener.daemon = True
        self.listener.start()
        self.user = ""


    # Used to send TCP data to client
    def TcpSend(self, data):
        self.client_socket.send(bytes(data + "\u0004", "utf-8"))



    def TcpListen(self):
        buffer = ""
        try:
            while self.quitEvent.is_set() is False:
                data = []
                if buffer != "":
                    data.append(buffer)
                    buffer = ""
                # Timeout?
                bytes = self.client_socket.recv(2048)
                if bytes == b'':
                    raise ConnectionAbortedError
                for line in bytes.decode("utf-8").split("\u0004"):
                    data.append(line)
                if data[-1] != "":
                    buffer = data[-1]
                for i in range(0, len(data) - 1):
                    self.dataQueue.put(data[i].strip("\u0004"))
        except BlockingIOError:
            """No data sent yet"""
        except ConnectionError or ConnectionResetError or ConnectionAbortedError:
            # Log forced disconnect i.e. if the user program is not closed properly
            self.quitEvent.set()
            logWrite(self.address[0] + " disconnected.")
        return


    # Used to received TCP data
    # Returns the TCP data decoded using utf-8 to a string format
    def TcpReceive(self):
        while self.exitTcp.is_set() is False and self.quitEvent.is_set() is False:
            if self.dataQueue.empty() is False:
                response = self.dataQueue.get()
                return response
            time.sleep(0.001)
        #self.TcpSend("Close")
        raise ConnectionAbortedError


    # Receive Config Data from client
    # (Objective 5.1)
    def ReceiveConfig(self):
        # Create new ConfigFile to store config data in
        newConfig = lgOb.ConfigFile()
        rows = []
        # Receive all 16 rows of config data
        while len(rows) < 16:
            data = self.TcpReceive()
            rows.append(data.split('\u001f'))
        logWrite("Config Received")
        # Iterate through rows of data
        # One row contains settings for one Pin
        for i in range(0, 16):
            newPin = lgOb.Pin()
            newPin.id = rows[i][0]
            newPin.name = rows[i][1]
            newPin.enabled = True if rows[i][2] == 'True' else False
            newPin.fName = rows[i][3]
            newPin.inputType = rows[i][4]
            newPin.gain = rows[i][5]
            newPin.scaleMin = rows[i][6]
            newPin.scaleMax = rows[i][7]
            newPin.units = rows[i][8]
            newPin.m = rows[i][9]
            newPin.c = rows[i][10]
            newConfig.pinList.append(newPin)
        return newConfig


    # Receive Log meta data from client
    # (Objective 5.1)
    def ReceiveLogMeta(self):
        metadata = self.TcpReceive().split('\u001f')
        # Create new LogMeta object to hold data
        newLog = lgOb.LogMeta()
        newLog.project = metadata[0]
        newLog.work_pack = metadata[1]
        newLog.job_sheet = metadata[2]
        newLog.name = metadata[3]
        newLog.date = metadata[4]
        newLog.time = metadata[5]
        newLog.loggedBy = metadata[6]
        newLog.downloadedBy = metadata[7]
        newLog.description = metadata[8]
        newLog.test_number = db.GetTestNumber(newLog.name)
        logWrite("Metadata received")

        # Receive all config settings using ReceiveConfig()
        newLog.config = self.ReceiveConfig()
        # try:
        #    newLog.id = db.GetIdNameNum(newLog.name,newLog.test_number)
        # except ValueError:
        try:
            newLog.id = db.GetRecentId()
            # Write log data and config data to database
            if db.CheckDataTable(newLog.id) is False:
                if newLog.name != db.GetName(newLog.id):
                    newLog.test_number += 1
                db.UpdateLog(newLog)
            else:
                newLog.id += 1
                newLog.test_number += 1
                db.WriteLog(newLog)
            file_rw.WriteLogConfig(newLog, newLog.name)
        except:
            newLog.id = 1
            newLog.test_number = 1
            db.WriteLog(newLog)
        file_rw.WriteLogConfig(newLog, newLog.name)


        self.connTcp.send("Print")
        self.connTcp.send("\nConfig for " + newLog.name + " received.")
        for pin in newLog.config.pinList:
            if pin.enabled is True:
                self.connTcp.send("Print")
                self.connTcp.send(
                "Pin {} set to log {}. I: {} G: {} SMin: {} SMax: {}".format(pin.id, pin.fName, pin.inputType, pin.gain,
                                                                             pin.scaleMin, pin.scaleMax))
        return


    # Used to check whether a log name has been used before
    # Makes sure users don't accidentally create logs with the same name
    def CheckName(self):
        name = self.TcpReceive()
        # Check database for name
        if db.CheckName(name) is True:
            self.TcpSend("Name exists")
        else:
            self.TcpSend("Name does not exist")
        return


    # Gets the most recent config from the database
    # Sends the config to the users computer
    # (Objective 2)
    def GetRecentConfig(self):
        try:
            # Gets log metadata stored in config
            values = db.ReadConfigMeta(db.GetRecentId())
        except ValueError:
            # If no logs have been logged, there will be no recent interval or config
            self.TcpSend("No Config Found")
            return
        # Retrieves config data from database
        # (Objective 2.1)
        path = db.GetConfigPath(db.GetRecentId())
        recentConfig = file_rw.ReadLogConfig(path)
        # Sends the metadata to the user computer
        for value in values:
            self.TcpSend(str(value))
        # Writes the Pin data to a data packet string
        for pin in recentConfig.pinList:
            packet = ""
            packet += str(pin.id) + '\u001f'
            packet += pin.name + '\u001f'
            packet += str(pin.enabled) + '\u001f'
            packet += pin.fName + '\u001f'
            packet += pin.inputType + '\u001f'
            packet += str(pin.gain) + '\u001f'
            packet += str(pin.scaleMin) + '\u001f'
            packet += str(pin.scaleMax) + '\u001f'
            packet += pin.units
            # Send packet to client
            # (Objective 2.2)
            self.TcpSend(packet)
        # Confirm to client the all config data has been sent
        self.TcpSend("EoConfig")


    # Retrieves logs that haven't been downloaded by a user
    # (Objective 3)
    def GetLogsToDownload(self):
        try:
            # Searches database for logs not downloaded by <user>
            # (Objective 3.1)
            #logs = db.FindNotDownloaded(self.user)
            logs = db.SearchLog({"downloaded_by" : '%' + self.user + '%'})
        except ValueError:
            self.TcpSend("No Logs To Download")
            return
        # For each log not downloaded, send the client the id, name and date of the log
        # (Objective 3.1)
        for log in logs:
            self.TcpSend(str(log[0]) + '\u001f' + log[1] + '\u001f' + str(log[2]) + '\u001f' + log[3] + '\u001f'
                        + str(log[4]) + '\u001f' + str(log[5]) + '\u001f' + str(log[6])
                        + '\u001f' + log[7] + '\u001f' + str(log[8]))
            # Set the log to downloaded as the user has downloaded/had the chance to download
            # db.SetDownloaded(log[0], user)
        self.TcpSend("EoT")
        if self.TcpReceive() != "Logs":
            return
        # Handles sending the requested logs
        # (Objectives 3.2 and 3.3)
        self.SendLogs()


    # Used to receive log requests from the client
    # Reads them from the database and sends them to the client
    # (Objectives 3.2 and 3.3)
    def SendLogs(self):
        # Receive the id's of the logs the user wants to download
        requestedLogs = self.TcpReceive().split('\u001f')
        if requestedLogs == ['No_Logs_Requested']:
            self.TcpSend("All_Sent")
            return
        # Hold logs to be sent to the client in a queue
        logQueue = Queue()
        allRead = Event()
        # Create a new thread for sending logs to the client
        streamer = Thread(target=self.streamLog, args=(logQueue, allRead))
        streamer.setDaemon(True)
        streamer.start()
        # Read each requested log and add to the queue of logs to be sent
        # (Objective 3.2)
        for log in requestedLogs:
            # path = db.GetDataPath(log)
            # TcpSend(client_socket,path)
            db.SetDownloaded(log, self.user)
            logMeta = db.ReadLog(log)
            logQueue.put(logMeta)
        allRead.set()
        # Wait until logQueue is empty and all logs have been sent
        # Also will close streamLog thread
        logQueue.join()
        self.TcpSend("All_Sent")


    # This is used to send logs in the logQueue to the client
    # (Objectives 3.3 and 4.3)
    def streamLog(self, logQueue, allRead):
        while allRead.is_set() is False or logQueue.unfinished_tasks > 0:
            # Dequeue one log from the log queue
            logMeta = logQueue.get()
            # Write the metadata to a packet and send to client
            metaData = (str(logMeta.id) + '\u001f' + str(logMeta.project) + '\u001f'
                        + str(logMeta.work_pack) + '\u001f' + str(logMeta.job_sheet)
                        + '\u001f' + logMeta.name + '\u001f' + str(logMeta.test_number)
                        + '\u001f' + str(logMeta.date) + '\u001f' + str(logMeta.time)
                       +'\u001f'+ logMeta.loggedBy + '\u001f' + logMeta.downloadedBy
                        + '\u001f' + logMeta.description)
            self.TcpSend(metaData)
            self.TcpSend("EoMeta")
            # Write data for each pin to a packet and send them to client
            for pin in logMeta.config.pinList:
                pinData = (str(pin.id) + '\u001f' + pin.name + '\u001f'
                            + str(pin.enabled) + '\u001f' + pin.fName + '\u001f'
                            + pin.inputType + '\u001f' + str(pin.gain) + '\u001f'
                            + str(pin.scaleMin) + '\u001f'+ str(pin.scaleMax) + '\u001f'
                            + pin.units + '\u001f'
                            + str(f"{Decimal(pin.m):.14f}").rstrip('0').rstrip('.') + '\u001f'
                            + str(f"{Decimal(pin.c):.14f}").rstrip('0').rstrip('.'))
                self.TcpSend(pinData)
            self.TcpSend("EoConfig")
            self.TcpSend(db.GetDataPath(logMeta.id))
            logQueue.task_done()


    # Starts a log from a TCP command
    # (Objective 14)
    def StartLog(self):
        # Sends command to the GUI to start log
        self.connTcp.send("Start")
        response = self.connTcp.recv()
        self.TcpSend(response)


    # Stops a log from a TCP command
    # (Objective 14)
    def StopLog(self):
        # Sends command to the GUI to start log
        self.connTcp.send("Stop")
        response = self.connTcp.recv()
        self.TcpSend(response)


    # Receives name, date and user values from client and searches for a log
    # Allows client to download the logs returned from the search
    # (Objectives 4 and 6)
    def SearchLog(self):
        # Receive values from client
        values = self.TcpReceive().split('\u001f')
        # Hold database query arguments in args dictionary
        args = {}
        if values[0] != "":
            args["name"] = '%' + values[0] + '%'
        if values[1] != "":
            args["date"] = '%' + values[1] + '%'
        if values[2] != "":
            args["logged_by"] = values[2]
        if values[3] != "":
            args["project"] = values[3]
        if values[4] != "":
            args["work_pack"] = values[4]
        if values[5] != "":
            args["job_sheet"] = values[5]
        if values[6] != "":
            args["description"] = '%' + values[6] + '%'
        if values[7] != "":
            args["downloaded_by"] = '%' + self.user + '%'

        try:
            # Searches database using arguments sent from user
            # Returns the id, name and date of matching logs
            # (Objectives 4.1 and 6.1)
            logs = db.SearchLog(args)
        except ValueError:
            self.TcpSend("No Logs Match Criteria")
            return
        # Sends id, name, test number, date, project, work_pack, job_sheet and size to the client
        # (Objectives 4.2 and 6.2)
        for log in logs:
            self.TcpSend((str(log[0]) + '\u001f' + log[1] + '\u001f' + str(log[2]) + '\u001f' + log[3] + '\u001f'
                                + str(log[4]) + '\u001f' + str(log[5]) + '\u001f' + str(log[6])
                                + '\u001f' + log[7] + '\u001f' + str(log[8])))
        self.TcpSend("EoT")
        # Determines whether the user is requesting for just a config or all log data
        request = self.TcpReceive()
        if request == "Config":
            # Sends config to client
            # (Objective 6.3)
            self.SendConfig()
        elif request == "Logs":
            # Sends logs to client
            # (Objective 4.3)
            self.SendLogs()


    # Used to send config data to the client
    # (Objective 6.3)
    def SendConfig(self):
        requestedConfig = self.TcpReceive().split('\u001f')[0]
        if requestedConfig == 'No_Logs_Requested':
            self.TcpSend("Config_Sent")
            return
        # Read config data from database
        # interval = db.ReadInterval(requestedConfig)
        # description = db.ReadDescription(requestedConfig)
        values = db.ReadConfigMeta(requestedConfig)
        config = file_rw.ReadLogConfig(db.GetConfigPath(requestedConfig))
        for value in values:
            self.TcpSend(str(value))
        # Write data for each Pin to packet and send each packet to client
        for pin in config.pinList:
            pinData = (str(pin.id) + '\u001f' + pin.name + '\u001f' + str(pin.enabled) + '\u001f' + pin.fName + '\u001f'
                       + pin.inputType + '\u001f' + str(pin.gain) + '\u001f' + str(pin.scaleMin) + '\u001f'
                       + str(pin.scaleMax) + '\u001f' + pin.units + '\u001f' + str(Decimal(pin.m)) + '\u001f' + str(Decimal(pin.c)))
            self.TcpSend(pinData)
        # Confirm to client that all data is sent
        self.TcpSend("Config_Sent")


    def ExportDatabase(self):
        info, data = db.GetDatabase()

        columns = ""
        for line in info:
            columns += str(line[1]) + "\u001f"
        self.TcpSend(columns.rstrip("\u001f"))

        self.TcpSend(str(len(data)))
        for row in data:
            line = ""
            for value in row:
                line += str(value) + "\u001f"
            self.TcpSend(line.rstrip("\u001f"))


    # Sends commands to client (more used for interfacing with powershell
    def PrintHelp(self):
        self.TcpSend("Available Commands:")
        self.TcpSend("Recent_Logs_To_Download - Get logs user has not yet downloaded")
        self.TcpSend("Request_Recent_Config - Get the most recent config from Logger")
        self.TcpSend("Upload_Config - Upload config to Logger")
        self.TcpSend("Check_Name - Checks Log name not already in use")
        self.TcpSend("Start_Log - Starts a log")
        self.TcpSend("Stop_Log - Stops a log")
        self.TcpSend("Search_Log - Search for and download a log")
        self.TcpSend("Change_User - Change which user is using the session")
        self.TcpSend("Export_Database - Returns all the data in the database")
        self.TcpSend("Help - Display this message")
        self.TcpSend("Quit - Disconnect from Logger")


    def ChangeUser(self):
        user = self.TcpReceive()
        if user != "Closed":
            self.user = self.TcpReceive()


    # Client interfaces with logger using commands sent using TCP
    # Subroutine receives incoming commands from client
    # (Objective 1.3)
    def CommandHandler(self):
        try:
            self.user = self.TcpReceive()
            if self.user == "Quit":
                logWrite(self.address[0] + " quitting.")
                self.quitEvent.set()
            while self.quitEvent.is_set() is False and self.exitTcp.is_set() is False:
                command = self.TcpReceive()
                # Log command sent
                logWrite(self.address[0] + " " + command)
                # Command compared to known commands and appropriate subroutine executed
                # (Objective 1.3)
                if command == "Recent_Logs_To_Download":
                    self.GetLogsToDownload()
                elif command == "Request_Recent_Config":
                    self.GetRecentConfig()
                elif command == "Upload_Config":
                    self.ReceiveLogMeta()
                # elif command == "Check_Name":
                #    CheckName(client_socket,dataQueue, exitTcp)
                elif command == "Start_Log":
                    self.StartLog()
                elif command == "Stop_Log":
                    self.StopLog()
                elif command == "Search_Log":
                    self.SearchLog()
                elif command == "Change_User":
                    self.ChangeUser()
                elif command == "Export_Database":
                    self.ExportDatabase()
                elif command == "Help":
                    self.PrintHelp()
                elif command == "Quit":
                    logWrite(self.address[0] + " quitting.")
                    self.quitEvent.set()
                else:
                    self.TcpSend("Command not recognised\n")
        except ConnectionAbortedError or ConnectionError or ConnectionResetError or BrokenPipeError:
            self.quitEvent.set()
            # Log forced disconnect i.e. if the user program is not closed properly
            logWrite(self.address[0] + " disconnected.")
        self.quitEvent.set()
        self.client_socket.shutdown(socket.SHUT_RDWR)
        self.listener.join()
        self.client_socket.close()
        logWrite(self.address[0] + " thread closed.")
        return


def logWrite(data):
    with open("tcpLog.txt", "a") as file:
        file.write(str(datetime.now()) + ": " + data + '\n')


# This function sets up the TCP server and client thread
# (Objectives 1.1 and 1.2)
def run(connTcp, exitTcp):
    # Create new TCP server log
    with open("tcpLog.txt", "a") as file:
        file.write("\n\n" + ("-" * 75))
        file.write("\nNew TCP Log Created at " + str(datetime.now()) + '\n')

    # Create database if it doesn't exist
    db.setupDatabase()
    # Create an INET, STREAMing socket for the TCP server
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.settimeout(0)
    #server_socket.settimeout(10)
    # Bind the socket to the logger IP address and port 13000
    # (Objective 1.1)
    try:
        server_socket.bind(("0.0.0.0", 13000))
        logWrite(socket.gethostname())
    except OSError:
        connTcp.send("BindFailed")
        return
    # Start listening on the server socket
    server_socket.listen(5)
    logWrite("Awaiting Connection...")

    # Accept connections forever until program is terminated
    while exitTcp.is_set() is False:
        try:
            # Accept connections from outside
            (client_socket, address) = server_socket.accept()
            client_socket.settimeout(None)
            # Create new thread to deal with new client
            # This allows multiple clients to connect at once
            # (Objective 1.2)
            new_client = TcpClient(client_socket, address, connTcp, exitTcp)
            worker = Thread(target=new_client.CommandHandler, args=())
            worker.start()

            # Log Connection
            logWrite(address[0] + " connected.")
        except:
            """No incoming connection"""
    logWrite("Server closed")



# Initiates the tcpServer if it has been run without using main.py
if __name__ == "__main__":
    print("\nWARNING - running this script directly will not start the gui "
          "\nIf you want to use the Pi's touchscreen program, run 'main.py' instead\n")
    # Run server as per normal setup
    run(connTcp=None, exitTcp=None)
