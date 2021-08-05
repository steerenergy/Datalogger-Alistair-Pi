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
def TcpSend(clientsocket, data):
    #response = ""
    # Send data until client confirms it has been received
    #while response != "Received":
    #    # Data is encoded as bytes using utf-8
    #    clientsocket.send(bytes(data, "utf-8"))
    #    response = clientsocket.recv(2048).decode("utf-8").strip("\n")
    clientsocket.send(bytes(data + "\n", "utf-8"))
    #time.sleep(0.001)


def TcpListen(clientsocket,address,dataQueue, quit):
    buffer = ""
    try:
        while quit.is_set() == False:
            data = []
            if buffer != "":
                data.append(buffer)
            for line in clientsocket.recv(2048).decode("utf-8").split("\n"):
                data.append(line)
            if data[-1] != "":
                buffer = data[-1]
            for i in range(0, len(data) - 1):
                dataQueue.put(data[i].strip("\n"))
    except ConnectionError or ConnectionResetError or ConnectionAbortedError:
        # Log forced disconnect i.e. if the user program is not closed properly
        quit.set()
        logWrite(address[0] + " disconnected.")
    return




# Used to received TCP data
# Returns the TCP data decoded usign utf-8 to a string format
def TcpReceive(clientsocket, dataQueue, exitTcp):
    while exitTcp.is_set() == False:
        if (dataQueue.empty() == False):
            response = dataQueue.get()
            return response
        time.sleep(0.001)
    TcpSend(clientsocket,"Close")
    raise ConnectionAbortedError



# Receive Config Data from client
# (Objective 5.1)
def ReceiveConfig(clientsocket,dataQueue, exitTcp):
    # Create new ConfigFile to store config data in
    newConfig = lgOb.ConfigFile()
    rows = []
    # Receive all 16 rows of config data
    while len(rows) < 16:
        data = TcpReceive(clientsocket, dataQueue, exitTcp)
        rows.append(data.split(','))
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
def ReceiveLogMeta(clientsocket,dataQueue, connTcp, exitTcp):
    metadata = TcpReceive(clientsocket, dataQueue, exitTcp).split(',')
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
    newLog.config = ReceiveConfig(clientsocket,dataQueue, exitTcp)
    #try:
    #    newLog.id = db.GetIdNameNum(newLog.name,newLog.test_number)
    #except ValueError:
    newLog.id = db.GetRecentId()
    # Write log data and config data to database
    if db.CheckDataTable(newLog.id) == False:
        if newLog.name != db.GetName(newLog.id):
            newLog.test_number += 1
        db.UpdateLog(newLog)
    else:
        newLog.id += 1
        newLog.test_number += 1
        db.WriteLog(newLog)
    file_rw.WriteLogConfig(newLog,newLog.name)

    connTcp.send("Print")
    connTcp.send("\nConfig for " + newLog.name + " received.")
    for pin in newLog.config.pinList:
        if pin.enabled == True:
            connTcp.send("Print")
            connTcp.send("Pin {} set to log {}. I: {} G: {} SMin: {} SMax: {}".format(pin.id,pin.fName,pin.inputType,pin.gain,pin.scaleMin,pin.scaleMax))
    return


# Used to check whether a log name has been used before
# Makes sure users don't accidentally create logs with the same name
def CheckName(clientsocket,dataQueue, exitTcp):
    name = TcpReceive(clientsocket, dataQueue, exitTcp)
    # Check database for name
    if db.CheckName(name) == True:
        TcpSend(clientsocket, "Name exists")
    else:
        TcpSend(clientsocket, "Name does not exist")
    return


# Gets the most recent config from the database
# Sends the config to the users computer
# (Objective 2)
def GetRecentConfig(clientsocket):
    try:
        # (Objective 2.1)
        db.GetRecentInterval()
    except ValueError:
        # If no logs have been logged, there will be no recent interval or config
        TcpSend(clientsocket, "No Config Found")
        return
    # Retrieves config data from database
    # (Objective 2.1)
    values = db.ReadConfigMeta(db.GetRecentId())
    path = db.GetConfigPath(db.GetRecentId())
    recentConfig = file_rw.ReadLogConfig(path)
    # Sends the interval to the user computer
    for value in values:
        TcpSend(clientsocket, str(value))
    # Writes the Pin data to a data packet string
    for pin in recentConfig.pinList:
        packet = ""
        packet += str(pin.id) + ','
        packet += pin.name + ','
        packet += str(pin.enabled) + ','
        packet += pin.fName + ','
        packet += pin.inputType + ','
        packet += str(pin.gain) + ','
        packet += str(pin.scaleMin) + ','
        packet += str(pin.scaleMax) + ','
        packet += pin.units
        # Send packet to client
        # (Objective 2.2)
        TcpSend(clientsocket, packet)
    # Confirm to client the all config data has been sent
    TcpSend(clientsocket, "EoConfig")


# Retrieves logs that haven't been downloaded by a user
# (Objective 3)
def GetLogsToDownload(clientsocket,dataQueue, exitTcp):
    TcpSend(clientsocket, "Send_User")
    user = TcpReceive(clientsocket, dataQueue, exitTcp)
    try:
        # Searches database for logs not downloaded by <user>
        # (Objective 3.1)
        logs = db.FindNotDownloaded(user)
    except ValueError:
        TcpSend(clientsocket, "No Logs To Download")
        return
    # For each log not downloaded, send the client the id, name and date of the log
    # (Objective 3.1)
    for log in logs:
        TcpSend(clientsocket, (str(log[0]) + ',' + log[1] + ',' + str(log[2]) + ',' + log[3] + ','
                               + str(log[4]) + ',' + str(log[5]) + ',' + str(log[6]) +  ',' + str(log[7])))
        # Set the log to downloaded as the user has downloaded/had the chance to download
        #db.SetDownloaded(log[0], user)
    TcpSend(clientsocket, "EoT")
    if TcpReceive(clientsocket, dataQueue, exitTcp) != "Logs":
        return
    # Handles sending the requested logs
    # (Objectives 3.2 and 3.3)
    SendLogs(clientsocket,dataQueue, exitTcp, user)


# Used to receive log requests from the client
# Reads them from the database and sends them to the client
# (Objectives 3.2 and 3.3)
def SendLogs(clientsocket,dataQueue, exitTcp, user=""):
    # Receive the id's of the logs the user wants to download
    requestedLogs = TcpReceive(clientsocket, dataQueue, exitTcp).split(",")
    if requestedLogs == ['No_Logs_Requested']:
        TcpSend(clientsocket, "All_Sent")
        return
    # Hold logs to be sent to the client in a queue
    logQueue = queue.Queue()
    # Create a new thread for sending logs to the client
    streamer = Thread(target=streamLog, args=(logQueue, clientsocket))
    streamer.setDaemon(True)
    streamer.start()
    # Read each requested log and add to the queue of logs to be sent
    # (Objective 3.2)
    for log in requestedLogs:
        #path = db.GetDataPath(log)
        #TcpSend(clientsocket,path)
        db.SetDownloaded(log[0], user)
        logMeta = db.ReadLog(log)
        logQueue.put(logMeta)
    # Wait until logQueue is empty and all logs have been sent
    # Also will close streamLog thread
    logQueue.join()
    TcpSend(clientsocket, "All_Sent")


# This is used to send logs in the logQueue to the client
# (Objectives 3.3 and 4.3)
def streamLog(logQueue, clientsocket):
    while True:
        # Dequeue one log from the log queue
        logMeta = logQueue.get()
        # Write the metadata to a packet and send to client
        metaData = (str(logMeta.id) + ','  + str(logMeta.project) + ',' + str(logMeta.work_pack) + ',' + str(logMeta.job_sheet) + ','
                    + logMeta.name + ',' + str(logMeta.test_number) + ',' + str(logMeta.date) + ',' + str(logMeta.time) + ','
                    + logMeta.loggedBy + ',' + logMeta.downloadedBy + ',' + logMeta.description)
        TcpSend(clientsocket, metaData)
        TcpSend(clientsocket, "EoMeta")
        # Write data for each pin to a packet and send them to client
        for pin in logMeta.config.pinList:
            pinData = (str(pin.id) + ',' + pin.name + ',' + str(pin.enabled) + ',' + pin.fName + ','
                       + pin.inputType + ',' + str(pin.gain) + ',' + str(pin.scaleMin) + ','
                       + str(pin.scaleMax) + ',' + pin.units + ','
                       + str(f"{Decimal(pin.m):.14f}").rstrip('0').rstrip('.') + ',' + str(f"{Decimal(pin.c):.14f}").rstrip('0').rstrip('.'))
            TcpSend(clientsocket, pinData)
        TcpSend(clientsocket, "EoConfig")
        TcpSend(clientsocket, db.GetDataPath(logMeta.id))
        # Write data for each row to a packet and send to client
        #for i in range(0, len(logMeta.logData.timeStamp)):
        #    rowData = logMeta.logData.timeStamp[i] + ','
        #    rowData += str(logMeta.logData.time[i]) + ','
        #    for column in logMeta.logData.rawData:
        #        rowData += str(f"{Decimal(column[i]):.14f}").rstrip('0').rstrip('.') + ','
        #    for column in logMeta.logData.convData:
        #        rowData += str(f"{Decimal(column[i]):.14f}").rstrip('0').rstrip('.') + ','
        #    TcpSend(clientsocket, rowData[:-1])
        #TcpSend(clientsocket, "EoLog")
        #row = logMeta.logData.tcpQueue.get()
        #while row != "Exit":
        #    TcpSend(clientsocket,row)
        #    row = logMeta.logData.tcpQueue.get()
        #TcpSend(clientsocket, "EoLog")
        # Let queue know that log has been sent
        logQueue.task_done()


# Starts a log from a TCP command
# (Objective 14)
def StartLog(clientsocket, connTcp):
    # Sends command to the GUI to start log
    connTcp.send("Start")
    response = connTcp.recv()
    TcpSend(clientsocket, response)


# Stops a log from a TCP command
# (Objective 14)
def StopLog(clientsocket, connTcp):
    # Sends command to the GUI to start log
    connTcp.send("Stop")
    response = connTcp.recv()
    TcpSend(clientsocket, response)


# Receives name, date and user values from client and searches for a log
# Allows client to download the logs returned from the search
# (Objectives 4 and 6)
def SearchLog(clientsocket,dataQueue, exitTcp):
    # Receive values from client
    values = TcpReceive(clientsocket, dataQueue, exitTcp).split(',')
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
        TcpSend(clientsocket, "No Logs Match Criteria")
        return
    # Sends id, name, test number, date, project, workpack, jobsheet and size to the client
    # (Objectives 4.2 and 6.2)
    for log in logs:
        TcpSend(clientsocket, (str(log[0]) + ',' + log[1] + ',' + str(log[2]) + ',' + log[3] + ','
                               + str(log[4]) + ',' + str(log[5]) + ',' + str(log[6]) +  ',' + str(log[7])))
    TcpSend(clientsocket, "EoT")
    # Determines whether the user is requesting for just a config or all log data
    request = TcpReceive(clientsocket, dataQueue, exitTcp)
    if request == "Config":
        # Sends config to client
        # (Objective 6.3)
        SendConfig(clientsocket,dataQueue, exitTcp)
    elif request == "Logs":
        # Sends logs to client
        # (Objective 4.3)
        SendLogs(clientsocket,dataQueue, exitTcp)


# Used to send config data to the client
# (Objective 6.3)
def SendConfig(clientsocket,dataQueue, exitTcp):
    requestedConfig = TcpReceive(clientsocket, dataQueue, exitTcp).split(",")[0]
    if requestedConfig == 'No_Logs_Requested':
        TcpSend(clientsocket, "Config_Sent")
        return
    # Read config data from database
    #interval = db.ReadInterval(requestedConfig)
    #description = db.ReadDescription(requestedConfig)
    values = db.ReadConfigMeta(requestedConfig)
    config = file_rw.ReadLogConfig(db.GetConfigPath(requestedConfig))
    for value in values:
        TcpSend(clientsocket,str(value))
    # Write data for each Pin to packet and send each packet to client
    for pin in config.pinList:
        pinData = (str(pin.id) + ',' + pin.name + ',' + str(pin.enabled) + ',' + pin.fName + ','
                   + pin.inputType + ',' + str(pin.gain) + ',' + str(pin.scaleMin) + ','
                   + str(pin.scaleMax) + ',' + pin.units + ',' + str(Decimal(pin.m)) + ',' + str(Decimal(pin.c)))
        TcpSend(clientsocket, pinData)
    # Confirm to cliet that all data is sent
    TcpSend(clientsocket, "Config_Sent")


# Sends commands to client (more used for interfacing with powershell
def PrintHelp(cliensocket):
    TcpSend(cliensocket,"Available Commands:")
    TcpSend(cliensocket, "Recent_Logs_To_Download - Get logs user has not yet downloaded")
    TcpSend(cliensocket, "Request_Recent_Config - Get the most recent config from Logger")
    TcpSend(cliensocket, "Upload_Config - Upload config to Logger")
    TcpSend(cliensocket, "Check_Name - Checks Log name not already in use")
    TcpSend(cliensocket, "Start_Log - Starts a log")
    TcpSend(cliensocket, "Stop_Log - Stops a log")
    TcpSend(cliensocket, "Search_Log - Search for and download a log")
    TcpSend(cliensocket, "Help - Display this message")
    TcpSend(cliensocket, "Quit - Disconnect from Logger")


# Client interfaces with logger using commands sent using TCP
# Subroutine receives incoming commands from client
# (Objective 1.3)
def new_client(clientsocket, address, connTcp, exitTcp):
    quit = Event()
    dataQueue = queue.Queue()
    listener = Thread(target=TcpListen,args=(clientsocket,address,dataQueue, quit))
    listener.daemon = True
    listener.start()
    try:
        while quit.is_set() == False and exitTcp.is_set() == False:
            command = TcpReceive(clientsocket, dataQueue, exitTcp)
            # Log command sent
            logWrite(address[0] + " " + command)
            # Command compared to known commands and appropriate subroutine executed
            # (Objective 1.3)
            if command == "Recent_Logs_To_Download":
                GetLogsToDownload(clientsocket,dataQueue, exitTcp)
            elif command == "Request_Recent_Config":
                GetRecentConfig(clientsocket)
            elif command == "Upload_Config":
                ReceiveLogMeta(clientsocket,dataQueue, connTcp, exitTcp)
            #elif command == "Check_Name":
            #    CheckName(clientsocket,dataQueue, exitTcp)
            elif command == "Start_Log":
                StartLog(clientsocket, connTcp)
            elif command == "Stop_Log":
                StopLog(clientsocket, connTcp)
            elif command == "Search_Log":
                SearchLog(clientsocket,dataQueue, exitTcp)
            elif command == "Help":
                PrintHelp(clientsocket)
            elif command == "Quit":
                logWrite(address[0] + " quitting.")
                quit.set()
            else:
                TcpSend(clientsocket, "Command not recognised\n")
    except ConnectionAbortedError or ConnectionError or ConnectionResetError:
        quit.set()
        # Log forced disconnect i.e. if the user program is not closed properly
        logWrite(address[0] + " disconnected.")
    listener.join()
    clientsocket.shutdown(socket.SHUT_RDWR)
    clientsocket.close()
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
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Bind the socket to the logger IP address and port 13000
    # (Objective 1.1)
    serversocket.bind(("0.0.0.0", 13000))
    logWrite(socket.gethostname())
    # Start listening on the server socket
    serversocket.listen(5)
    logWrite("Awaiting Connection...")

    # Accept connections forever until program is terminated
    while True:
        # Accept connections from outside
        (clientsocket, address) = serversocket.accept()
        # Create new thread to deal with new client
        # This allows multiple clients to connect at once
        # (Objective 1.2)

        worker = Thread(target=new_client, args=(clientsocket, address, connTcp, exitTcp))
        worker.start()

        # Log Connection
        logWrite(address[0] + " connected.")


# Initiates the tcpServer if it has been run without using main.py
if __name__ == "__main__":
    print("\nWARNING - running this script directly will not start the gui "
          "\nIf you want to use the Pi's touchscreen program, run 'main.py' instead\n")
    # Run server as per normal setup
    run(connTcp=None, exitTcp=None)
