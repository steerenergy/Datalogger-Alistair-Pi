# This file handles TCP connections into the logger
# Is run separately to the GUI but can communicate using Pipe

import socket
import time
import databaseOp as db
import logObjects as lgOb
from queue import Queue
from multiprocessing import Event, Lock
from datetime import datetime
from threading import Thread
from decimal import Decimal
import file_rw


class TcpClient():
    # Initialise new Client
    def __init__(self, client_socket, address, connTcp, exitTcp, lock):
        # Store socket and address
        self.client_socket = client_socket
        self.address = address
        # Store Pipe and Event for communicating with GUI
        self.connTcp = connTcp
        self.exitTcp = exitTcp
        # Store Event for locking Pipe to stop multiple client threads using it at once
        self.lock = lock
        # Setup dataQueue and quitEvent for client connection
        self.dataQueue = Queue()
        self.quitEvent = Event()
        # Setup and start listener thread to receive data in parallel to processing
        self.listener = Thread(target=self.TcpListen, args=())
        self.listener.daemon = True
        self.listener.start()
        # Setup user variable
        self.user = ""


    # Used to send TCP data to client
    # Errors will be caught by commandHandler
    def TcpSend(self, data):
        if not self.quitEvent.is_set():
            self.client_socket.send(bytes(data + "\u0004", "utf-8"))


    # Receives data from client
    # Runs in a separate thread so data is received ASAP
    def TcpListen(self):
        buffer = ""
        try:
            # Whilst connection is not set to be closed, listen for incoming data
            while self.quitEvent.is_set() is False:
                data = []
                # Receive data
                bytes = self.client_socket.recv(2048)
                if bytes == b'':
                    raise ConnectionAbortedError
                # Split separate packets by "\u0004" delimiter
                for line in bytes.decode("utf-8").split("\u0004"):
                    # If there is data in buffer, prepend to line
                    if buffer != "":
                        data.append(buffer + line)
                        buffer = ""
                    else:
                        data.append(line)
                # If packet has been split, store in buffer
                if data[-1] != "":
                    buffer = data[-1]
                # Add all but last packet to dataQueue
                for i in range(0, len(data) - 1):
                    self.dataQueue.put(data[i].strip("\u0004"))
        # Catch any errors due to unexpected disconnect, etc.
        except ConnectionError or ConnectionResetError or ConnectionAbortedError:
            # Log forced disconnect and close client connection
            self.quitEvent.set()
            #logWrite(self.address[0] + " disconnected.")
        return


    # Used to get received TCP data from dataQueue
    def TcpReceive(self):
        # Make sure that connection is supposed to be ongoing
        while self.exitTcp.is_set() is False and self.quitEvent.is_set() is False:
            # If dataQueue is empty, wait and try again
            if self.dataQueue.empty() is False:
                # Get data from dataQueue and return
                response = self.dataQueue.get()
                return response
            time.sleep(0.001)
        # If loop is quit due to exitTcp or quitEvent, throw error to close connection
        raise ConnectionAbortedError


    # Receive Config Data from client
    def ReceiveConfig(self):
        # Create new list to store config pins in
        newConfig = []
        rows = []
        # Receive all 16 rows of config data
        while len(rows) < 16:
            data = self.TcpReceive()
            rows.append(data.split('\u001f'))
        logWrite(self.address[0] + " Config Received")
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
            newConfig.append(newPin)
        return newConfig


    # Receive Log meta data from client
    def ReceiveLogMeta(self):
        metadata = self.TcpReceive().split('\u001f')
        # Create new LogMeta object to hold data
        newLog = lgOb.LogMeta()
        newLog.project = metadata[0]
        newLog.work_pack = metadata[1]
        newLog.job_sheet = metadata[2]
        newLog.name = metadata[3]
        newLog.time = metadata[4]
        newLog.loggedBy = metadata[5]
        newLog.description = metadata[6]
        # Get the current test number for the name
        # If there are no logs with the name, returns 0
        newLog.test_number = db.GetTestNumber(newLog.name)
        logWrite(self.address[0] + " Metadata received")

        # Receive all config settings using ReceiveConfig()
        newLog.config = self.ReceiveConfig()

        try:
            newLog.id = db.GetRecentId()
            # If most recent entry doesn't have data set, write new config there
            # Makes sure emtpy entries don't fill up database
            if db.CheckDataTable(newLog.id) is False:
                # If log name has changed, increment test number to correct number
                if newLog.name != db.GetName(newLog.id):
                    newLog.test_number += 1
                db.UpdateLog(newLog)
            # If most recent entry does have data set, increment the id and test number and write new entry
            else:
                newLog.id += 1
                newLog.test_number += 1
                db.WriteLog(newLog)
        # Exception occurs when there are no logs in the database
        # Catch and write log with id 1 and test number 1
        except ValueError:
            newLog.id = 1
            newLog.test_number = 1
            db.WriteLog(newLog)
        # Write the config settings to a file on the Pi
        file_rw.WriteLogConfig(newLog, newLog.name)
        # Instruct the GUI to print the config settings received
        self.connTcp.send("Print")
        self.connTcp.send("\nConfig for " + newLog.name + " received.")
        self.connTcp.send("Print")
        self.connTcp.send("Time interval: {}".format(newLog.time))
        for pin in newLog.config:
            if pin.enabled is True:
                # Print settings for each pin enabled
                self.connTcp.send("Print")
                self.connTcp.send(
                "Pin {} set to log {}. I: {} G: {} SMin: {} SMax: {}".format(pin.id, pin.fName, pin.inputType, pin.gain,
                                                                             pin.scaleMin, pin.scaleMax))
        return


    # Gets the most recent config from the database
    # Sends the config to the users computer
    def GetRecentConfig(self):
        try:
            # Gets log metadata from database
            values = db.ReadConfigMeta(db.GetRecentId())
            # Retrieves config data from database
            path = db.GetConfigPath(db.GetRecentId())
            if path == None:
                raise FileNotFoundError
            recentConfig = file_rw.ReadLogConfig(path)
        # Catch error when no logs in database
        except ValueError:
            # If no logs have been logged, there will be no recent interval or config
            self.TcpSend("No Config Found")
            return
        except FileNotFoundError:
            # If the config file cannot be found, tell user
            self.TcpSend("No Config Found")
            db.DatabaseCheck()
            return
        # Sends the metadata to the users computer
        for value in values:
            self.TcpSend(str(value))
        # Writes the Pin data to a data packet string
        for pin in recentConfig:
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
            # Send Pin data packet to client
            self.TcpSend(packet)
        logWrite(self.address[0] + " Sent config " + path)
        return


    # Used to receive log requests from the client
    # Reads them from the database and sends them to the client
    def SendLogs(self):
        # Receive the id's of the logs the user wants to download
        requestedLogs = self.TcpReceive().split('\u001f')
        if requestedLogs == ['No_Logs_Requested']:
            self.TcpSend(str(0))
            logWrite(self.address[0] + " no logs requested")
            return
        # Hold logs to be sent to the client in a queue
        logQueue = Queue()
        allRead = Event()
        # Create a new thread for sending logs to the client
        streamer = Thread(target=self.streamLog, args=(logQueue, allRead))
        streamer.setDaemon(True)
        streamer.start()
        # Send number of logs being sent
        self.TcpSend(str(len(requestedLogs)))
        # Read each requested log and add to the queue of logs to be sent
        for log in requestedLogs:
            db.SetDownloaded(log, self.user)
            try:
                logMeta = db.ReadLog(log)
                logQueue.put(logMeta)
            except FileNotFoundError:
                db.DatabaseCheck()
                logMeta = lgOb.LogMeta(name=db.GetName(log),config="Not_Found")
                logQueue.put(logMeta)
        allRead.set()
        # Wait until logQueue is empty and all logs have been sent
        # Also will close streamLog thread
        logQueue.join()


    # This is used to send logs in the logQueue to the client
    def streamLog(self, logQueue, allRead):
        while allRead.is_set() is False or logQueue.unfinished_tasks > 0:
            # Dequeue one log from the log queue
            logMeta = logQueue.get()
            if logMeta.config == "Not_Found":
                self.TcpSend("Config_Not_Found")
                self.TcpSend("Config for {} not found, skipping download.".format(logMeta.name))
                logQueue.task_done()
            else:
                # Write the metadata to a packet and send to client
                metaData = (str(logMeta.id) + '\u001f' + str(logMeta.project) + '\u001f'
                            + str(logMeta.work_pack) + '\u001f' + str(logMeta.job_sheet)
                            + '\u001f' + logMeta.name + '\u001f' + str(logMeta.test_number)
                            + '\u001f' + str(logMeta.date) + '\u001f' + str(logMeta.time)
                            +'\u001f'+ logMeta.loggedBy + '\u001f' + str(logMeta.data_path)
                            + '\u001f' + logMeta.description)
                self.TcpSend(metaData)
                # Write data for each pin to a packet and send them to client
                for pin in logMeta.config:
                    pinData = (str(pin.id) + '\u001f' + pin.name + '\u001f'
                                + str(pin.enabled) + '\u001f' + pin.fName + '\u001f'
                                + pin.inputType + '\u001f' + str(pin.gain) + '\u001f'
                                + str(pin.scaleMin) + '\u001f'+ str(pin.scaleMax) + '\u001f'
                                + pin.units + '\u001f'
                                + str(f"{Decimal(pin.m):.14f}").rstrip('0').rstrip('.') + '\u001f'
                                + str(f"{Decimal(pin.c):.14f}").rstrip('0').rstrip('.'))
                    self.TcpSend(pinData)
                logWrite(self.address[0] + " Sent log " + logMeta.name + " " + str(logMeta.test_number))
                logQueue.task_done()


    # Starts a log from a TCP command
    def StartLog(self):
        # Sends command to the GUI to start log
        self.connTcp.send("Start")
        # Sends GUI response back to client
        response = self.connTcp.recv()
        self.TcpSend(response)
        logWrite(self.address[0] + (" Logger Response: ") + response)


    # Stops a log from a TCP command
    def StopLog(self):
        while self.lock.is_set():
            pass
        self.lock.set()
        # Sends command to the GUI to start log
        self.connTcp.send("Stop")
        # Sends GUi response back to client
        response = self.connTcp.recv()
        lock = False
        self.TcpSend(response)
        logWrite(self.address[0] + (" Logger Response: ") + response)


    # Receives search criteria from client and searches for a log
    # Allows client to download the logs returned from the search
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
            # Returns the id, name, test number, date, project, work pack, job sheet and size of matching logs
            logs = db.SearchLog(args)
        # If no logs match criteria, let client know
        except ValueError:
            self.TcpSend("No Logs Match Criteria")
            return

        # Send number of logs being sent to client
        self.TcpSend(str(len(logs)))
        # Sends id, name, test_number, date, project, work_pack, job_sheet and size to the client
        for log in logs:
            self.TcpSend((str(log[0]) + '\u001f' + log[1] + '\u001f' + str(log[2]) + '\u001f' + log[3] + '\u001f'
                                + str(log[4]) + '\u001f' + str(log[5]) + '\u001f' + str(log[6])
                                + '\u001f' + str(log[7]) + '\u001f' + str(log[8])))
        # Determines whether the user is requesting for just a config or all log data
        request = self.TcpReceive()
        if request == "Config":
            # Sends config to client
            self.SendConfig()
        elif request == "Logs":
            # Sends logs to client
            self.SendLogs()
        return


    # Used to send config data to the client
    def SendConfig(self):
        # If more than one config has been received, only send the first one
        requestedConfig = self.TcpReceive().split('\u001f')[0]
        if requestedConfig == 'No_Logs_Requested':
            self.TcpSend("Config_Sent")
            return
        # Read config metadata from database
        values = db.ReadConfigMeta(requestedConfig)
        try:
            # Read config pin data from file
            config = file_rw.ReadLogConfig(db.GetConfigPath(requestedConfig))
        except FileNotFoundError:
            self.TcpSend("No_Config_Found")
            db.DatabaseCheck()
            return
        # Send config metadata to client
        for value in values:
            self.TcpSend(str(value))
        # Write data for each Pin to packet and send each packet to client
        for pin in config:
            pinData = (str(pin.id) + '\u001f' + pin.name + '\u001f' + str(pin.enabled) + '\u001f' + pin.fName + '\u001f'
                       + pin.inputType + '\u001f' + str(pin.gain) + '\u001f' + str(pin.scaleMin) + '\u001f'
                       + str(pin.scaleMax) + '\u001f' + pin.units + '\u001f' + str(Decimal(pin.m)) + '\u001f' + str(Decimal(pin.c)))
            self.TcpSend(pinData)
        logWrite(self.address[0] + " Sent config " + db.GetConfigPath(requestedConfig))
        return


    # Sends a copy of all the data in the database to the client
    def ExportDatabase(self):
        # Get column info and row data from database
        info, data = db.GetDatabase()
        # Send column headers to client
        columns = ""
        for line in info:
            columns += str(line[1]) + "\u001f"
        self.TcpSend(columns.rstrip("\u001f"))
        # Sends number of rows of data to client
        self.TcpSend(str(len(data)))
        # Send each row of data to client
        for row in data:
            line = ""
            for value in row:
                line += str(value) + "\u001f"
            self.TcpSend(line.rstrip("\u001f"))
        logWrite(self.address[0] + " Database Exported")
        return


    # Sends list of commands to client (used for interfacing with powershell or other CLI)
    def PrintHelp(self):
        self.TcpSend("Available Commands:")
        self.TcpSend("Request_Recent_Config - Get the most recent config from Logger")
        self.TcpSend("Upload_Config - Upload config to Logger")
        self.TcpSend("Start_Log - Starts a log")
        self.TcpSend("Stop_Log - Stops a log")
        self.TcpSend("Search_Log - Search for and download a log")
        self.TcpSend("Change_User - Change which user is using the session")
        self.TcpSend("Export_Database - Returns all the data in the database")
        self.TcpSend("Help - Display this message")
        self.TcpSend("Quit - Disconnect from Logger")


    # Allows user to be changed without restarting session
    def ChangeUser(self):
        user = self.TcpReceive()
        # Only change self.user if a username is sent
        # Closed is sent when user doesn't change username on the client application
        if user != "Closed":
            self.user = self.TcpReceive()
        logWrite(self.address[0] + " user changed to " + self.user)


    # Client interfaces with logger using commands sent using TCP
    # Subroutine receives incoming commands from client and handles them
    def CommandHandler(self):
        try:
            # Whilst connection is not set to be closed, listen for commands
            while self.quitEvent.is_set() is False and self.exitTcp.is_set() is False:
                command = self.TcpReceive()
                # Log what command was sent
                logWrite(self.address[0] + " " + command)
                # Compare command to known commands and execute appropriate subroutine
                if command == "Request_Recent_Config":
                    self.GetRecentConfig()
                elif command == "Upload_Config":
                    self.ReceiveLogMeta()
                elif command == "Start_Log":
                    self.StartLog()
                elif command == "Stop_Log":
                    self.lock.aquire()
                    self.StopLog()
                    self.lock.release()
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
                    # Note: This is only really relevant for CLI interactions with server
                    self.TcpSend("Command not recognised")
        except ConnectionAbortedError or ConnectionError or ConnectionResetError or BrokenPipeError:
            self.quitEvent.set()
            # Log forced disconnect i.e. if the user program is not closed properly
            logWrite(self.address[0] + " disconnected.")
        # Make sure quitEvent is set
        self.quitEvent.set()
        # Shutdown and close socket, and join listener thread to save resources
        try:
            self.client_socket.shutdown(socket.SHUT_RDWR)
            self.listener.join()
            self.client_socket.close()
        # Sometimes if client_socket is shutdown automatically before client_socket.shutdown is called,
        # OS error Socket Endpoint not Connected is thrown
        # If so, close socket and join listener
        except OSError:
            self.client_socket.close()
            self.listener.join()
        # Log that thread has been closed
        logWrite(self.address[0] + " thread closed.")
        return


# Handles writing data to tcpLog.txt
def logWrite(data):
    # Open tcpLog.txt and append data to newline
    with open("tcpLog.txt", "a") as file:
        file.write(str(datetime.now()) + ": " + data + '\n')


# This function sets up the TCP server and client thread
def run(connTcp, exitTcp):
    # Create new section in tcpLog.txt
    with open("tcpLog.txt", "a") as file:
        file.write("\n\n" + ("-" * 75))
        file.write("\nNew TCP Log Created at " + str(datetime.now()) + '\n')

    # Create and setup database
    # Note: If database already exists, this won't recreate the database
    db.setupDatabase()
    # Create an INET, STREAMing socket for the TCP server
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Set timeout to 0 so that sever_socket.accept() doesn't hang
    # This means the while loop can exit properly when exitTcp is set
    server_socket.settimeout(0)
    # Bind the socket to the logger IP address and port 13000
    try:
        server_socket.bind(("0.0.0.0", 13000))
        logWrite(socket.gethostname())
    # If bind fails due to port 13000 being in use, tell GUI to alert user and close program
    except OSError:
        connTcp.send("BindFailed")
        return
    # Start listening on the server socket
    server_socket.listen(5)
    logWrite("Awaiting Connection...")

    lock = Lock()
    # Accept connections until program is terminated
    while exitTcp.is_set() is False:
        try:
            # Accept connections from outside
            (client_socket, address) = server_socket.accept()
            client_socket.settimeout(None)
            # Create new thread to deal with new client
            # This allows multiple clients to connect at once
            new_client = TcpClient(client_socket, address, connTcp, exitTcp, lock)
            # Receive username
            user = new_client.TcpReceive()
            # If this is a test connection, close connection
            if user != "Quit":
                new_client.user = user
                worker = Thread(target=new_client.CommandHandler, args=())
                worker.start()
            else:
                logWrite(new_client.address[0] + " quitting.")
                new_client = None

            # Log Connection
            logWrite(address[0] + " connected.")
        except:
            # Timeout hit meaning no incoming connection at that instant
            # This is fine as it means exitTcp.is_set() is constantly being checked
            # While loop is therefore able to close correctly when program closed
            """No incoming connection"""
    logWrite("Server closed")


# This is the code that is run when the program is loaded.
# If the module were to be imported, the code inside the if statement would not run.
if __name__ == "__main__":
    # Warning that logger will not work
    print("\nWARNING - This script cannot be run directly."
          "\nPlease run 'main.py' to start the logger, or use the desktop icon.\n")
    # Script will exit
