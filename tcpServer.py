import socket
import time

import databaseOp as db
import logObjects as lgOb
import queue
from multiprocessing import Event
from datetime import datetime
from threading import Thread
from decimal import Decimal
import file_rw


# Used to send TCP data to client
def TcpSend(client_socket, data):
    client_socket.send(bytes(data + "\u0004", "utf-8"))


def TcpListen(client_socket, address, dataQueue, quitEvent):
    buffer = ""
    try:
        while not quitEvent.is_set():
            data = []
            if buffer != "":
                data.append(buffer)
            for line in client_socket.recv(2048).decode("utf-8").split("\u0004"):
                data.append(line)
            if data[-1] != "":
                buffer = data[-1]
            for i in range(0, len(data) - 1):
                dataQueue.put(data[i].strip("\u0004"))
    except ConnectionError or ConnectionResetError or ConnectionAbortedError:
        # Log forced disconnect i.e. if the user program is not closed properly
        quitEvent.set()
        logWrite(address[0] + " disconnected.")
    return


# Used to received TCP data
# Returns the TCP data decoded using utf-8 to a string format
def TcpReceive(client_socket, dataQueue, exitTcp):
    while exitTcp.is_set() is False:
        if (dataQueue.empty() is False):
            response = dataQueue.get()
            return response
        time.sleep(0.001)
    TcpSend(client_socket, "Close")
    raise ConnectionAbortedError


# Receive Config Data from client
# (Objective 5.1)
def ReceiveConfig(client_socket, dataQueue, exitTcp):
    # Create new ConfigFile to store config data in
    newConfig = lgOb.ConfigFile()
    rows = []
    # Receive all 16 rows of config data
    while len(rows) < 16:
        data = TcpReceive(client_socket, dataQueue, exitTcp)
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
def ReceiveLogMeta(client_socket, dataQueue, connTcp, exitTcp):
    metadata = TcpReceive(client_socket, dataQueue, exitTcp).split('\u001f')
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
    newLog.config = ReceiveConfig(client_socket, dataQueue, exitTcp)
    # try:
    #    newLog.id = db.GetIdNameNum(newLog.name,newLog.test_number)
    # except ValueError:
    try:
        newLog.id = db.GetRecentId()
    except:
        newLog.id = 1
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

    connTcp.send("Print")
    connTcp.send("\nConfig for " + newLog.name + " received.")
    for pin in newLog.config.pinList:
        if pin.enabled is True:
            connTcp.send("Print")
            connTcp.send(
                "Pin {} set to log {}. I: {} G: {} SMin: {} SMax: {}".format(pin.id, pin.fName, pin.inputType, pin.gain,
                                                                             pin.scaleMin, pin.scaleMax))
    return


# Used to check whether a log name has been used before
# Makes sure users don't accidentally create logs with the same name
def CheckName(client_socket, dataQueue, exitTcp):
    name = TcpReceive(client_socket, dataQueue, exitTcp)
    # Check database for name
    if db.CheckName(name) is True:
        TcpSend(client_socket, "Name exists")
    else:
        TcpSend(client_socket, "Name does not exist")
    return


# Gets the most recent config from the database
# Sends the config to the users computer
# (Objective 2)
def GetRecentConfig(client_socket):
    try:
        # Gets log metadata stored in config
        values = db.ReadConfigMeta(db.GetRecentId())
    except ValueError:
        # If no logs have been logged, there will be no recent interval or config
        TcpSend(client_socket, "No Config Found")
        return
    # Retrieves config data from database
    # (Objective 2.1)
    path = db.GetConfigPath(db.GetRecentId())
    recentConfig = file_rw.ReadLogConfig(path)
    # Sends the interval to the user computer
    for value in values:
        TcpSend(client_socket, str(value))
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
        TcpSend(client_socket, packet)
    # Confirm to client the all config data has been sent
    TcpSend(client_socket, "EoConfig")


# Retrieves logs that haven't been downloaded by a user
# (Objective 3)
def GetLogsToDownload(client_socket, dataQueue, exitTcp, user):
    try:
        # Searches database for logs not downloaded by <user>
        # (Objective 3.1)
        logs = db.FindNotDownloaded(user)
    except ValueError:
        TcpSend(client_socket, "No Logs To Download")
        return
    # For each log not downloaded, send the client the id, name and date of the log
    # (Objective 3.1)
    for log in logs:
        TcpSend(client_socket, (str(log[0]) + '\u001f' + log[1] + '\u001f' + str(log[2]) + '\u001f' + log[3] + '\u001f'
                                + str(log[4]) + '\u001f' + str(log[5]) + '\u001f' + str(log[6]) + '\u001f' + str(log[7])))
        # Set the log to downloaded as the user has downloaded/had the chance to download
        # db.SetDownloaded(log[0], user)
    TcpSend(client_socket, "EoT")
    if TcpReceive(client_socket, dataQueue, exitTcp) != "Logs":
        return
    # Handles sending the requested logs
    # (Objectives 3.2 and 3.3)
    SendLogs(client_socket, dataQueue, exitTcp, user)


# Used to receive log requests from the client
# Reads them from the database and sends them to the client
# (Objectives 3.2 and 3.3)
def SendLogs(client_socket, dataQueue, exitTcp, user):
    # Receive the id's of the logs the user wants to download
    requestedLogs = TcpReceive(client_socket, dataQueue, exitTcp).split('\u001f')
    if requestedLogs == ['No_Logs_Requested']:
        TcpSend(client_socket, "All_Sent")
        return
    # Hold logs to be sent to the client in a queue
    logQueue = queue.Queue()
    # Create a new thread for sending logs to the client
    streamer = Thread(target=streamLog, args=(logQueue, client_socket))
    streamer.setDaemon(True)
    streamer.start()
    # Read each requested log and add to the queue of logs to be sent
    # (Objective 3.2)
    for log in requestedLogs:
        # path = db.GetDataPath(log)
        # TcpSend(client_socket,path)
        db.SetDownloaded(log, user)
        logMeta = db.ReadLog(log)
        logQueue.put(logMeta)
    # Wait until logQueue is empty and all logs have been sent
    # Also will close streamLog thread
    logQueue.join()
    TcpSend(client_socket, "All_Sent")


# This is used to send logs in the logQueue to the client
# (Objectives 3.3 and 4.3)
def streamLog(logQueue, client_socket):
    while True:
        # Dequeue one log from the log queue
        logMeta = logQueue.get()
        # Write the metadata to a packet and send to client
        metaData = (str(logMeta.id) + '\u001f' + str(logMeta.project) + '\u001f'
                    + str(logMeta.work_pack) + '\u001f' + str(logMeta.job_sheet)
                    + '\u001f' + logMeta.name + '\u001f' + str(logMeta.test_number)
                    + '\u001f' + str(logMeta.date) + '\u001f' + str(logMeta.time)
                    +'\u001f'+ logMeta.loggedBy + '\u001f' + logMeta.downloadedBy
                    + '\u001f' + logMeta.description)
        TcpSend(client_socket, metaData)
        TcpSend(client_socket, "EoMeta")
        # Write data for each pin to a packet and send them to client
        for pin in logMeta.config.pinList:
            pinData = (str(pin.id) + '\u001f' + pin.name + '\u001f'
                       + str(pin.enabled) + '\u001f' + pin.fName + '\u001f'
                       + pin.inputType + '\u001f' + str(pin.gain) + '\u001f'
                       + str(pin.scaleMin) + '\u001f'+ str(pin.scaleMax) + '\u001f'
                       + pin.units + '\u001f'
                       + str(f"{Decimal(pin.m):.14f}").rstrip('0').rstrip('.') + '\u001f'
                       + str(f"{Decimal(pin.c):.14f}").rstrip('0').rstrip('.'))
            TcpSend(client_socket, pinData)
        TcpSend(client_socket, "EoConfig")
        TcpSend(client_socket, db.GetDataPath(logMeta.id))
        logQueue.task_done()


# Starts a log from a TCP command
# (Objective 14)
def StartLog(client_socket, connTcp):
    # Sends command to the GUI to start log
    connTcp.send("Start")
    response = connTcp.recv()
    TcpSend(client_socket, response)


# Stops a log from a TCP command
# (Objective 14)
def StopLog(client_socket, connTcp):
    # Sends command to the GUI to start log
    connTcp.send("Stop")
    response = connTcp.recv()
    TcpSend(client_socket, response)


# Receives name, date and user values from client and searches for a log
# Allows client to download the logs returned from the search
# (Objectives 4 and 6)
def SearchLog(client_socket, dataQueue, exitTcp, user):
    # Receive values from client
    values = TcpReceive(client_socket, dataQueue, exitTcp).split('\u001f')
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

    try:
        # Searches database using arguments sent from user
        # Returns the id, name and date of matching logs
        # (Objectives 4.1 and 6.1)
        logs = db.SearchLog(args)
    except ValueError:
        TcpSend(client_socket, "No Logs Match Criteria")
        return
    # Sends id, name, test number, date, project, work_pack, job_sheet and size to the client
    # (Objectives 4.2 and 6.2)
    for log in logs:
        TcpSend(client_socket, (str(log[0]) + '\u001f' + log[1] + '\u001f' + str(log[2]) + '\u001f' + log[3] + '\u001f'
                                + str(log[4]) + '\u001f' + str(log[5]) + '\u001f' + str(log[6]) + '\u001f' + str(log[7])))
    TcpSend(client_socket, "EoT")
    # Determines whether the user is requesting for just a config or all log data
    request = TcpReceive(client_socket, dataQueue, exitTcp)
    if request == "Config":
        # Sends config to client
        # (Objective 6.3)
        SendConfig(client_socket, dataQueue, exitTcp)
    elif request == "Logs":
        # Sends logs to client
        # (Objective 4.3)
        SendLogs(client_socket, dataQueue, exitTcp, user)


# Used to send config data to the client
# (Objective 6.3)
def SendConfig(client_socket, dataQueue, exitTcp):
    requestedConfig = TcpReceive(client_socket, dataQueue, exitTcp).split('\u001f')[0]
    if requestedConfig == 'No_Logs_Requested':
        TcpSend(client_socket, "Config_Sent")
        return
    # Read config data from database
    # interval = db.ReadInterval(requestedConfig)
    # description = db.ReadDescription(requestedConfig)
    values = db.ReadConfigMeta(requestedConfig)
    config = file_rw.ReadLogConfig(db.GetConfigPath(requestedConfig))
    for value in values:
        TcpSend(client_socket, str(value))
    # Write data for each Pin to packet and send each packet to client
    for pin in config.pinList:
        pinData = (str(pin.id) + '\u001f' + pin.name + '\u001f' + str(pin.enabled) + '\u001f' + pin.fName + '\u001f'
                   + pin.inputType + '\u001f' + str(pin.gain) + '\u001f' + str(pin.scaleMin) + '\u001f'
                   + str(pin.scaleMax) + '\u001f' + pin.units + '\u001f' + str(Decimal(pin.m)) + '\u001f' + str(Decimal(pin.c)))
        TcpSend(client_socket, pinData)
    # Confirm to client that all data is sent
    TcpSend(client_socket, "Config_Sent")


# Sends commands to client (more used for interfacing with powershell
def PrintHelp(client_socket):
    TcpSend(client_socket, "Available Commands:")
    TcpSend(client_socket, "Recent_Logs_To_Download - Get logs user has not yet downloaded")
    TcpSend(client_socket, "Request_Recent_Config - Get the most recent config from Logger")
    TcpSend(client_socket, "Upload_Config - Upload config to Logger")
    TcpSend(client_socket, "Check_Name - Checks Log name not already in use")
    TcpSend(client_socket, "Start_Log - Starts a log")
    TcpSend(client_socket, "Stop_Log - Stops a log")
    TcpSend(client_socket, "Search_Log - Search for and download a log")
    TcpSend(client_socket, "Help - Display this message")
    TcpSend(client_socket, "Quit - Disconnect from Logger")


# Client interfaces with logger using commands sent using TCP
# Subroutine receives incoming commands from client
# (Objective 1.3)
def new_client(client_socket, address, connTcp, exitTcp):
    quitEvent = Event()
    dataQueue = queue.Queue()
    listener = Thread(target=TcpListen, args=(client_socket, address, dataQueue, quitEvent))
    listener.daemon = True
    listener.start()
    try:
        user = TcpReceive(client_socket,dataQueue,exitTcp)
        while quitEvent.is_set() is False and exitTcp.is_set() is False:
            command = TcpReceive(client_socket, dataQueue, exitTcp)
            # Log command sent
            logWrite(address[0] + " " + command)
            # Command compared to known commands and appropriate subroutine executed
            # (Objective 1.3)
            if command == "Recent_Logs_To_Download":
                GetLogsToDownload(client_socket, dataQueue, exitTcp, user)
            elif command == "Request_Recent_Config":
                GetRecentConfig(client_socket)
            elif command == "Upload_Config":
                ReceiveLogMeta(client_socket, dataQueue, connTcp, exitTcp)
            # elif command == "Check_Name":
            #    CheckName(client_socket,dataQueue, exitTcp)
            elif command == "Start_Log":
                StartLog(client_socket, connTcp)
            elif command == "Stop_Log":
                StopLog(client_socket, connTcp)
            elif command == "Search_Log":
                SearchLog(client_socket, dataQueue, exitTcp, user)
            elif command == "Help":
                PrintHelp(client_socket)
            elif command == "Quit":
                logWrite(address[0] + " quitting.")
                quitEvent.set()
            else:
                TcpSend(client_socket, "Command not recognised\n")
    except ConnectionAbortedError or ConnectionError or ConnectionResetError:
        quitEvent.set()
        # Log forced disconnect i.e. if the user program is not closed properly
        logWrite(address[0] + " disconnected.")
    listener.join()
    client_socket.shutdown(socket.SHUT_RDWR)
    client_socket.close()
    logWrite(address[0] + " thread closed.")
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
    # Bind the socket to the logger IP address and port 13000
    # (Objective 1.1)
    server_socket.bind(("0.0.0.0", 13000))
    logWrite(socket.gethostname())
    # Start listening on the server socket
    server_socket.listen(5)
    logWrite("Awaiting Connection...")

    # Accept connections forever until program is terminated
    while True:
        # Accept connections from outside
        (client_socket, address) = server_socket.accept()
        # Create new thread to deal with new client
        # This allows multiple clients to connect at once
        # (Objective 1.2)

        worker = Thread(target=new_client, args=(client_socket, address, connTcp, exitTcp))
        worker.start()

        # Log Connection
        logWrite(address[0] + " connected.")


# Initiates the tcpServer if it has been run without using main.py
if __name__ == "__main__":
    print("\nWARNING - running this script directly will not start the gui "
          "\nIf you want to use the Pi's touchscreen program, run 'main.py' instead\n")
    # Run server as per normal setup
    run(connTcp=None, exitTcp=None)
