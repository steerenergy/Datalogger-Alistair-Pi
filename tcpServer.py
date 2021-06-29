import socket
import databaseOp as db
import logObjects as lgOb
import queue
import logger
from datetime import datetime
from threading import Thread
from decimal import Decimal


# Used to send TCP data to client
def TcpSend(clientsocket, data):
    response = ""
    # Send data until client confirms it has been received
    while response != "Received":
        # Data is encoded as bytes using utf-8
        clientsocket.send(bytes(data, "utf-8"))
        response = clientsocket.recv(2048).decode("utf-8").strip("\n")


# Used to received TCP data
# Returns the TCP data decoded usign utf-8 to a string format
def TcpReceive(clientsocket):
    response = clientsocket.recv(2048).decode("utf-8").strip("\n")
    # Confirm to client that data was received
    clientsocket.send(b"Received")
    return response


# Receive Config Data from client
# (Objective 5.1)
def ReceiveConfig(clientsocket):
    # Create new ConfigFile to store config data in
    newConfig = lgOb.ConfigFile()
    rows = []
    # Receive all 16 rows of config data
    while len(rows) < 16:
        data = TcpReceive(clientsocket)
        rows.append(data.split(','))
    print("@Config Received")
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
def ReceiveLogMeta(clientsocket):
    metadata = TcpReceive(clientsocket).split(',')
    # Create new LogMeta object to hold data
    newLog = lgOb.LogMeta()
    newLog.name = metadata[0]
    newLog.date = metadata[1]
    newLog.time = metadata[2]
    newLog.loggedBy = metadata[3]
    newLog.downloadedBy = metadata[4]
    print("@Metadata received")
    # Receive all config settings using ReceiveConfig()
    newLog.config = ReceiveConfig(clientsocket)
    newLog.logData = lgOb.LogData()
    # Write log data and config data to database
    db.WriteLog(newLog)
    db.WriteConfig(newLog.config)
    return


# Used to check whether a log name has been used before
# Makes sure users don't accidentally create logs with the same name
def CheckName(clientsocket):
    name = TcpReceive(clientsocket)
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
        interval = db.GetRecentInterval()
    except ValueError:
        # If no logs have been logged, there will be no recent interval or config
        TcpSend(clientsocket, "No Config Found")
        return
    # Retrieves config data from database
    # (Objective 2.1)
    recentConfig = db.GetRecentConfig()
    # Sends the interval to the user computer
    intervalStr = str(interval)
    # (Objective 2.2)
    TcpSend(clientsocket, intervalStr)
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
def GetLogsToDownload(clientsocket):
    TcpSend(clientsocket, "Send_User")
    user = TcpReceive(clientsocket)
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
        TcpSend(clientsocket, (str(log[0]) + ',' + log[1] + ',' + log[2]))
        # Set the log to downloaded as the user has downloaded/had the chance to download
        db.SetDownloaded(log[0], user)
    TcpSend(clientsocket, "EoT")
    if TcpReceive(clientsocket) != "Logs":
        return
    # Handles sending the requested logs
    # (Objectives 3.2 and 3.3)
    SendLogs(clientsocket)


# Used to receive log requests from the client
# Reads them from the database and sends them to the client
# (Objectives 3.2 and 3.3)
def SendLogs(clientsocket):
    # Receive the id's of the logs the user wants to download
    requestedLogs = TcpReceive(clientsocket).split(",")
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
        metaData = (str(logMeta.id) + ',' + logMeta.name + ',' + str(logMeta.date) + ',' + str(logMeta.time) + ','
                    + logMeta.loggedBy + ',' + logMeta.downloadedBy)
        TcpSend(clientsocket, metaData)
        TcpSend(clientsocket, "EoMeta")
        # Write data for each pin to a packet and send them to client
        for pin in logMeta.config.pinList:
            pinData = (str(pin.id) + ',' + pin.name + ',' + str(pin.enabled) + ',' + pin.fName + ','
                       + pin.inputType + ',' + str(pin.gain) + ',' + str(pin.scaleMin) + ','
                       + str(pin.scaleMax) + ',' + pin.units + ','
                       + str(f"{Decimal(pin.m):.10f}") + ',' + str(f"{Decimal(pin.c):.10f}"))
            TcpSend(clientsocket, pinData)
        TcpSend(clientsocket, "EoConfig")
        # Write data for each row to a packet and send to client
        for i in range(0, len(logMeta.logData.timeStamp)):
            rowData = logMeta.logData.timeStamp[i] + ','
            rowData += str(logMeta.logData.time[i]) + ','
            for column in logMeta.logData.rawData:
                rowData += str(f"{Decimal(column[i]):.14f}") + ','
            for column in logMeta.logData.convData:
                rowData += str(f"{Decimal(column[i]):.14f}") + ','
            TcpSend(clientsocket, rowData[:-1])
        TcpSend(clientsocket, "EoLog")
        # Let queue know that log has been sent
        logQueue.task_done()


# Starts a log from a TCP command
# (Objective 14)
def StartLog(clientsocket):
    try:
        if logger.logEnbl == True:
            TcpSend(clientsocket, "Logger already enabled.")
        else:
            # Sends command to the GUI to start log
            print("[ToggleLog]")
            TcpSend(clientsocket, "Log started.")
    except AttributeError:
        print("[ToggleLog]")
        TcpSend(clientsocket, "Log started.")


# Stops a log from a TCP command
# (Objective 14)
def StopLog(clientsocket):
    try:
        if logger.logEnbl == True:
            # Sends command to the GUI to stop log
            print("[ToggleLog]")
            TcpSend(clientsocket, "Log stopped.")
        else:
            TcpSend(clientsocket, "Logger not running.")
    except AttributeError:
        TcpSend(clientsocket, "Logger not running.")


# Receives name, date and user values from client and searches for a log
# Allows client to download the logs returned from the search
# (Objectives 4 and 6)
def SearchLog(clientsocket):
    # Receive values from client
    values = TcpReceive(clientsocket).split(',')
    # Hold database query arguments in args dictionary
    args = {}
    if values[0] != "":
        args["name"] = values[0]
    if values[1] != "":
        args["date"] = '%' + values[1] + '%'
    if values[2] != "":
        args["logged_by"] = values[2]

    try:
        # Searches database using arguments sent from user
        # Returns the id, name and date of matching logs
        # (Objectives 4.1 and 6.1)
        logs = db.SearchLog(args)
    except ValueError:
        TcpSend(clientsocket, "No Logs Match Criteria")
        return
    # Sends id, name and date to the client
    # (Objectives 4.2 and 6.2)
    for log in logs:
        TcpSend(clientsocket, (str(log[0]) + ',' + log[1] + ',' + log[2]))
    TcpSend(clientsocket, "EoT")
    # Determines whether the user is requesting for just a config or all log data
    request = TcpReceive(clientsocket)
    if request == "Config":
        # Sends config to client
        # (Objective 6.3)
        SendConfig(clientsocket)
    elif request == "Logs":
        # Sends logs to client
        # (Objective 4.3)
        SendLogs(clientsocket)


# Used to send config data to the client
# (Objective 6.3)
def SendConfig(clientsocket):
    requestedConfig = TcpReceive(clientsocket)
    if requestedConfig == 'No_Logs_Requested':
        TcpSend(clientsocket, "Config_Sent")
        return
    # Read config data from database
    interval = db.ReadInterval(requestedConfig)
    config = db.ReadConfig(requestedConfig)
    TcpSend(clientsocket, str(interval))
    # Write data for each Pin to packet and send each packet to client
    for pin in config.pinList:
        pinData = (str(pin.id) + ',' + pin.name + ',' + str(pin.enabled) + ',' + pin.fName + ','
                   + pin.inputType + ',' + str(pin.gain) + ',' + str(pin.scaleMin) + ','
                   + str(pin.scaleMax) + ',' + pin.units + ',' + str(Decimal(pin.m)) + ',' + str(Decimal(pin.c)))
        TcpSend(clientsocket, pinData)
    # Confirm to cliet that all data is sent
    TcpSend(clientsocket, "Config_Sent")


# Client interfaces with logger using commands sent using TCP
# Subroutine receives incoming commands from client
# (Objective 1.3)
def new_client(clientsocket, address):
    quit = False
    try:
        while quit == False:
            command = TcpReceive(clientsocket)
            # Log command sent
            print("@" + address[0] + " " + command)
            # Command compared to known commands and appropriate subroutine executed
            # (Objective 1.3)
            if command == "Recent_Logs_To_Download":
                GetLogsToDownload(clientsocket)
            elif command == "Request_Recent_Config":
                GetRecentConfig(clientsocket)
            elif command == "Upload_Config":
                ReceiveLogMeta(clientsocket)
            elif command == "Check_Name":
                CheckName(clientsocket)
            elif command == "Start_Log":
                StartLog(clientsocket)
            elif command == "Stop_Log":
                StopLog(clientsocket)
            elif command == "Search_Log":
                SearchLog(clientsocket)
            elif command == "Quit":
                print("@" + address[0] + " quitting.")
                quit = True
            else:
                TcpSend(clientsocket, "Command not recognised\n")
    except ConnectionAbortedError:
        # Log forced disconnect i.e. if the user program is not closed properly
        print("@" + address[0] + " disconnected.")
    return


# This function sets up the TCP server and client thread
# (Objectives 1.1 and 1.2)
def run():
    # Create new TCP server log
    with open("tcpLog.txt", "w") as file:
        file.write("New TCP Log Created at " + str(datetime.now()) + '\n')

    # Create database if it doesn't exist
    db.setupDatabase()
    # Create an INET, STREAMing socket for the TCP server
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Bind the socket to the logger IP address and port 13000
    # (Objective 1.1)
    serversocket.bind(("0.0.0.0", 13000))
    print("@" + socket.gethostname())
    # Start listening on the server socket
    serversocket.listen(5)
    print("@Awaiting Connection...")

    # Accept connections forever until program is terminated
    while True:
        # Accept connections from outside
        (clientsocket, address) = serversocket.accept()
        # Create new thread to deal with new client
        # This allows multiple clients to connect at once
        # (Objective 1.2)
        worker = Thread(target=new_client, args=(clientsocket, address))
        worker.start()

        # Log Connection
        print("@" + address[0] + " connected.")


# Initiates the tcpServer if it has been run without using main.py
if __name__ == "__main__":
    print("\nWARNING - running this script directly will not start the gui "
          "\nIf you want to use the Pi's touchscreen program, run 'main.py' instead\n")
    # Run server as per normal setup
    run()
