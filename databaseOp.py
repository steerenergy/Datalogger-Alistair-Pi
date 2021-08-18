# This script handles all interactions with the database
# It contains functions which other scripts can use to interact with the database

import sqlite3
import file_rw
import logObjects as lgOb

# Global database variable holds the path to database
database = r"logs.db"

# Creates the main table in the database if it doesn't already exist
# Also checks that all entries have raw data paths and sizes
# If any don't, it will attempt to find them
def setupDatabase():
    global database
    # SQL statement to create main table
    # This table will hold all the log meta data
    sql_create_main_table = """CREATE TABLE IF NOT EXISTS main (
                                        id integer PRIMARY KEY NOT NULL,
                                        project integer NOT NULL DEFAULT 0,
                                        work_pack integer NOT NULL DEFAULT 0,
                                        job_sheet integer NOT NULL DEFAULT 0,
                                        name text NOT NULL,
                                        test_number integer NOT NULL DEFAULT 0,
                                        date text,
                                        time real NOT NULL,
                                        logged_by text,
                                        downloaded_by text,
                                        config text,
                                        data text,
                                        size integer,
                                        description text);"""
    # Connect to database and execute SQL statement
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    cur.execute(sql_create_main_table)
    conn.commit()

    # Scan through database and find any entries missing logData
    # Try to find data file and update
    rows = cur.execute("SELECT id, date FROM main WHERE data is NULL;").fetchall()
    if rows != None:
        for row in rows:
            path = file_rw.CheckData(row[1])
            if path != "":
                UpdateDataPath(row[0],path)

    # Find entries with data and no size and update size
    rows = cur.execute("SELECT id FROM main WHERE data is NOT NULL AND size is NULL;").fetchall()
    if rows != None:
        for row in rows:
            UpdateSize(row[0],file_rw.GetSize(GetDataPath(row[0])))
    conn.close()
    return


# Write new log metadata to the main database table
def WriteLog(newLog):
    global database
    # Get list of values to write
    valuesList = [newLog.name, newLog.time, newLog.loggedBy,
                  newLog.description, newLog.project,
                  newLog.work_pack, newLog.job_sheet, newLog.test_number]
    sql_insert_metadata = """INSERT INTO main (name, time, logged_by, description, project, work_pack, job_sheet, test_number)
                                        VALUES(?,?,?,?,?,?,?,?);"""
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    # Execute sql statement and commit
    cur.execute(sql_insert_metadata, valuesList)
    conn.commit()
    conn.close()
    return


# Updates log entry, used when config uploaded and no data has yet been logged for most recent entry
# Stops multiple config uploads clogging database with dud entries
def UpdateLog(newLog):
    global database
    # This can probably be optimised, do if have time
    valuesList = [newLog.name, newLog.time, newLog.loggedBy,
                  newLog.description, newLog.project,
                  newLog.work_pack, newLog.job_sheet, newLog.test_number, newLog.id]
    sql_insert_metadata = """UPDATE main 
                             SET name = ?, time = ?, logged_by = ?, description = ?, project = ?, work_pack = ?, job_sheet = ?, test_number = ?
                             WHERE id = ?;"""
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    # Execute sql statement and commit
    cur.execute(sql_insert_metadata, valuesList)
    conn.commit()
    conn.close()


# Gets the Id for the most recent log from the database
def GetRecentId():
    global database
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    # Most recent id will be the largest as it increments for each new log
    cur.execute("SELECT MAX(id) FROM main;")
    logId = cur.fetchone()[0]
    # If no logs are in the database, through an error
    # Error is caught by code which called GetRecentId()
    if logId == None:
        raise ValueError
    conn.close()
    return logId


# Gets the most recent log meta data
# Used in GeneralImport on new log start
def GetRecentMetaData():
    id = GetRecentId()
    global database
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    # Execute statement to get relevant meta data from database
    row = cur.execute("SELECT id, project, work_pack, job_sheet, name, test_number, time, logged_by, description FROM main WHERE id = ?;",[id]).fetchone()
    # If no log exists, throw error which is caught
    if row == []:
        raise ValueError
    # Create new logMeta object from retrieved data
    logMeta = lgOb.LogMeta()
    logMeta.id = row[0]
    logMeta.project = row[1]
    logMeta.work_pack = row[2]
    logMeta.job_sheet = row[3]
    logMeta.name = row[4]
    logMeta.test_number = row[5]
    logMeta.time = row[6]
    logMeta.loggedBy = row[7]
    logMeta.description = row[8]
    conn.close()
    return logMeta


# Sets a log to downloaded once a user has downloaded
def SetDownloaded(id,user):
    global database
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    # Get the current value for downloaded_by
    downloaded = cur.execute("SELECT downloaded_by FROM main WHERE id = ?;",[id]).fetchone()[0]
    if downloaded is None:
        downloaded = ""
    # If the user is not already set to downloaded, add user
    # Otherwise repetitions can be caused
    if user not in downloaded:
        # Update row to include the username in the downloaded_by field
        cur.execute("UPDATE main SET downloaded_by = downloaded_by || \';\' || ? WHERE id = ?;", [user, str(id)])
        conn.commit()
    conn.close()
    return


# Check if a raw data entry already exists for a log
# Used to make sure there are no dud entries and complete entries are not overwritten
def CheckDataTable(id):
    global database
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    # Returns the data entry for the specific log id
    data_exists = cur.execute("SELECT data FROM main WHERE id = ?;",[id]).fetchone()
    conn.close()
    # If nothing is returned, the log doesn't have a data entry
    if data_exists[0] == None:
        return False
    # If something is returned, there is a data entry
    else:
        return True


# Reads metadata for config
# Used when sending config data to client
def ReadConfigMeta(id):
    global database
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    # Retrieves time interval, description, name, project, work_pack and job_sheet
    values = cur.execute("SELECT time, description, name, project, work_pack, job_sheet FROM main WHERE id = ?;",[id]).fetchone()
    conn.close()
    # If description is None, set to empty string
    if values[1] == None:
        values[1] = ""
    return values


# Updates the date entry for the log after the log is complete
def AddDate(timestamp,id):
    global database
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    # Updates date of log to the datetime when the log was started
    cur.execute("UPDATE main SET date = ? WHERE id = ?;", [timestamp,str(id)])
    conn.commit()
    conn.close()
    return


# Searches for a log using arguments specified by user
# Used when Downloading a log or config from Pi
def SearchLog(args):
    global database
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    # sql statement is dynamically built using arguments
    sql = "SELECT id, name, test_number, date, project, work_pack, job_sheet, description, size FROM main WHERE "
    # values stores argument values to be passed into sql statement when executed
    values = []
    # Uses args dictionary to dynamically generate SQL query
    for key in args.keys():
        if key == "date" or key == "name" or key == "description":
            sql += key + " LIKE ? AND "
            values.append(args[key])
        elif key == "downloaded_by":
            sql += key + " NOT LIKE ? AND "
            values.append(args[key])
        else:
            sql += key + " = ? AND "
            values.append(args[key])
    # Add data is NOT NULL to make sure only logs with datafiles can be downloaded
    sql += "data IS NOT NULL;"
    # Fetch all logs that match query
    logs = cur.execute(sql,values).fetchall()
    # If no logs found, throw error which is caught
    conn.close()
    if logs == []:
        raise ValueError
    return logs


# Reads full log from the database
# Used for downloading logs from Pi
def ReadLog(id):
    global database
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    logMeta = lgOb.LogMeta()
    # Get the metadata for the log from main table
    row = cur.execute('SELECT id, project, work_pack, job_sheet, name, test_number, date, time, ' +
                      'logged_by, data, config, description FROM main WHERE id = ?;',[str(id)]).fetchone()
    # Create new logMeta from data
    logMeta.id = row[0]
    logMeta.project = row[1]
    logMeta.work_pack = row[2]
    logMeta.job_sheet = row[3]
    logMeta.name = row[4]
    logMeta.test_number = row[5]
    logMeta.date = row[6]
    logMeta.time = row[7]
    logMeta.loggedBy = row[8]
    logMeta.data_path = row[9]
    logMeta.config_path = row[10]
    logMeta.description = row[11]
    if logMeta.description == None:
        logMeta.description = ""
    # Get config data for log
    logMeta.config = file_rw.ReadLogConfig(logMeta.config_path)
    conn.close()
    return logMeta


# Updates the config path of a log
def UpdateConfigPath(id,path):
    global database
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    # Updates the path in the database to match the actual file
    cur.execute("UPDATE main SET config = ? WHERE id = ?;", [path, str(id)])
    conn.commit()
    conn.close()
    return


# Returns the path of the config file for a specific log
def GetConfigPath(id):
    global database
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    path = cur.execute("SELECT config FROM main WHERE id = ?;", [str(id)]).fetchone()[0]
    conn.commit()
    conn.close()
    return path


# Returns the path of the data file for a specific log
def GetDataPath(id):
    global database
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    path = cur.execute("SELECT data FROM main WHERE id = ?;", [str(id)]).fetchone()[0]
    conn.commit()
    conn.close()
    return path


# Updates the data path of a log
def UpdateDataPath(id,path):
    global database
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    # Updates the path in the database to match the actual file
    cur.execute("UPDATE main SET data = ? WHERE id = ?;", [path, str(id)])
    conn.commit()
    conn.close()
    return


# Updates the size entry to match the actual file size of data
def UpdateSize(id,size):
    global database
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    cur.execute("UPDATE main SET size = ? WHERE id = ?;", [size, str(id)])
    conn.commit()
    conn.close()
    return


# Returns the highest test number for a given log name
# Used in automatically incrementing test number
def GetTestNumber(name):
    global database
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    # Retrieves all current test numbers for that name
    numbers = cur.execute("SELECT test_number FROM main WHERE name = ?;",[str(name)]).fetchall()
    max_num = 0
    # Finds the maximum number for that name
    for num in numbers:
        if int(num[0]) > max_num:
            max_num = int(num[0])
    conn.close()
    # If no logs have the name, this will return 0
    return max_num


# Gets the name of a log from an id
# Used during config upload
def GetName(id):
    global database
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    name = cur.execute("SELECT name FROM main WHERE id = ?;",[id]).fetchone()
    conn.close()
    return name[0]


# Retrieves the table information for main table and all the data stored in main
# Used to export a copy of the database for the user
def GetDatabase():
    global database
    conn = sqlite3.connect(database)
    cur = conn.cursor()
    # Get info about main table e.g. column headings, column data types, etc.
    info = cur.execute("PRAGMA TABLE_INFO(main)").fetchall()
    # Get all data inside main
    data = cur.execute("SELECT * FROM main").fetchall()
    conn.close()
    return info, data

# This is the code that is run when the program is loaded.
# If the module were to be imported, the code inside the if statement would not run.
if __name__ == "__main__":
    # Warning that logger will not work
    print("\nWARNING - This script cannot be run directly."
          "\nPlease run 'main.py' to start the logger, or use the desktop icon.\n")
    # Script will exit
