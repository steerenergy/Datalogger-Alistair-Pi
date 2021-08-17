# This uses tkinter which is a really common multi-platform GUI
# Script connects to logger.py and acts a front end to it

import logging
import databaseOp as db
import pandas as pd
from pathlib import Path
import time
from datetime import datetime
import threading
from tkinter import *
from tkinter import ttk
from tkinter import font, messagebox
import socket
from logger import Logger
import matplotlib.pyplot as plt
from multiprocessing import Process, Array, Event, Pipe
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import sys


# Set up GUI controls and functions
class WindowTop(Frame):
    # Main Window - Init function contains all elements of layout
    def __init__(self, master=None, connGui=Pipe(), exitTcp=Event()):
        # This is class inheritance
        Frame.__init__(self, master)
        # Setting self.master = master window
        self.master = master

        # Changing the title of our master widget
        self.master.title("Steer Energy Data Logger V2.1.3")
        self.pack()

        # Create Layout Frames
        self.topFrame = Frame(master)
        self.topFrame.pack(expand=1, fill=BOTH, side=LEFT)
        self.liveDataFrame = Frame(master)
        self.liveDataFrame.pack(expand=1, fill=BOTH, side=RIGHT)

        # Title Text
        self.title = Label(self.topFrame, text="Log Ctrl:", font=bigFont)
        self.title.pack()

        # Start/Stop Logging Button
        self.logButton = Button(self.topFrame, text="Start Logging", height=3, width=11, command=self.logToggle,
                                font=bigFont)
        self.logButton.pack(padx=5)

        # Quit Button
        self.quitButton = Button(self.topFrame, text="Quit", height=3, width=11, command=self.onClose, font=bigFont)
        self.quitButton.pack(padx=5)

        # Textbox/Graph Button
        self.switchButton = Button(self.topFrame, text="Switch\nDisplay", height=3, width=11,
                                   command=self.switchDisplay, font=bigFont)
        self.switchButton.pack(padx=5)

        # Live Data Title
        self.liveTitle = Label(self.liveDataFrame, text="Live Data:", font=bigFont)
        self.liveTitle.pack(side=TOP)

        # Live Data Scroll Bar
        self.liveDataScrollBar = Scrollbar(self.liveDataFrame)
        self.liveDataScrollBar.pack(side=RIGHT, fill=Y)

        # Live Data Text Box
        self.liveDataText = Text(self.liveDataFrame, width=68, yscrollcommand=self.liveDataScrollBar.set,
                                 font=smallFont, state='disabled')
        self.liveDataText.pack()
        self.textBox = True

        # Config ScrollBar
        self.liveDataScrollBar.config(command=self.liveDataText.yview)

        # Checkbox for AutoScroll
        self.autoScrollEnable = IntVar()
        self.autoScroll = Checkbutton(self.topFrame, text="AutoScroll", variable=self.autoScrollEnable, font=bigFont)
        self.autoScroll.select()
        self.autoScroll.pack(side=BOTTOM)

        # Holds the number of lines in the textbox (updated after each print)
        self.textIndex = None
        # Determines the max number of lines on the tkinter GUI at any given point.
        self.textThreshold = 250

        # Create variables used for log process
        # Note: these are initialised when logging starts
        # Otherwise only one log can be performed
        self.logProcess = None
        self.stop = None
        self.values = None

        # Will later hold liveDataThread
        self.liveDataThread = None

        # Live Data Graph
        self.liveFigure = plt.Figure(figsize=(6, 5), dpi=100)
        self.ax1 = self.liveFigure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.liveFigure, self.liveDataFrame)
        self.canvas.draw()

        # Combo box for selecting which channel to graph
        self.channelSelect = ttk.Combobox(self.topFrame, values=["None"])
        self.channelSelect.current(0)
        self.channelSelect['state'] = 'disabled'
        self.channelSelect.pack(pady=(10, 10))

        # Create instance of the logger class
        self.logger = Logger()

        # Start commandHandler, which handles communication between TCP server and GUI
        self.after(1000, self.commandHandler, connGui)

        # Pass exitTcp event to GUI so server can be closed from GUI
        self.exitTcp = exitTcp


    # Contains functions for the start/stop logging buttons
    def logToggle(self):
        # Starting Logging
        if self.logButton['text'] == "Start Logging":
            # Disable Log Button
            self.logButton['state'] = 'disabled'
            # Update button.
            # We need the change to happen now, rather than at the end of the function (in root.mainloop)
            self.logButton.update()
            # Clear Text Output
            self.liveDataText['state'] = 'normal'
            self.liveDataText.delete(1.0, END)
            # Remove history from RAM (to avoid memory leak)
            self.liveDataText.edit_reset()
            self.liveDataText['state'] = 'disabled'
            # Scroll to Bottom of Blank Box
            self.liveDataText.see(END)
            # Initialise logger class
            # Any errors with importing log metadata and config data will occur here
            # adcToLog stores AnalogIn objects which are used to get data from the ads1115 pins
            # adcHeader stores the name of pins being logged
            self.logger.init(self.textboxOutput)
            # Only continue if settings import was successful
            if self.logger.logEnbl is True:
                # Check log test number is free to use
                # If not, the test number for this log is incremented
                self.logger.checkTestNumber()
                # Print Settings to Live Data Textbox
                self.logger.settingsOutput(self.textboxOutput)
                # Setup variables for starting log in separate process
                # stop event controls stopping of the log process
                self.stop = Event()
                # values array stores a copy of the most recent values logged
                # Used by the live data output to retrieve the data
                self.values = Array('f',self.logger.logComp.enabled, lock=True)
                # Setup and start log process
                self.logProcess = Process(target=self.logger.log, args=(self.stop, self.values))
                self.logProcess.start()
            # If settings import fails, stop the log startup
            # The reason for failure will be displayed to user in the Live Data Textbox
            else:
                self.logger.logEnbl = False
                # Change Button Text
                self.logButton.config(text="Start Logging")
                # Re-enable Button
                self.logButton['state'] = 'normal'
                return
            # Startup Live Data Thread which handles displaying live data to user
            self.liveDataThread = threading.Thread(target=self.liveData, args=())
            self.liveDataThread.daemon = True
            self.liveDataThread.start()
            # Change Button Text and re-enable
            self.logButton.config(text="Finish Logging")
            self.logButton['state'] = 'normal'
        # Stopping Logging
        else:
            # Disable button
            self.logButton['state'] = 'disabled'
            # Print button status
            self.textboxOutput("\nStopping Logger")
            # Change logEnbl variable to false which stops the loop in the live data thread
            self.logger.logEnbl = False
            # Set stop Event to stop logProcess
            self.stop.set()
            # Check to see if logProcess and liveDataThread have ended
            self.logProcess.join()
            self.logThreadStopCheck()

    # Is triggered when 'Stop Logging' ic clicked and is called until liveDataThread is dead
    # If liveDataThread has finished the 'start logging' button is changed and enabled
    # Else, the function is triggered again after a certain period of time
    def logThreadStopCheck(self):
        if self.liveDataThread.is_alive() is False:
            # Change Button Text
            self.logButton.config(text="Start Logging")
            # Tell user logging has stopped
            self.textboxOutput("Logging Stopped - Success!")
            # Check that logged data is of good quality
            self.DataCheck()
            # Re-enable Button
            self.logButton['state'] = 'normal'
        else:
            # Repeat the process after a certain period of time.
            # Note that time.sleep isn't used here. This is Crucial to why this has been done
            # The timer works independently to the main thread, allowing the print statments to be processed
            # This stops the program freezing if logThread is trying to print but the GUI is occupied so it can't
            self.after(100, self.logThreadStopCheck)

    # Used to output text to the Live Data Textbox
    # Is used as a parameter for logger functions so they can output to the textbox
    def textboxOutput(self, inputStr, flush=False):
        # Enable, write data, delete unnecessary data, disable
        # Used to print data to Live Data Textbox
        self.liveDataText['state'] = 'normal'
        # If flush is True, don't add newline after inputString
        if flush == False:
            inputStr += "\n"
        # Insert inputStr at the end of the current text data
        self.liveDataText.insert(END, inputStr)
        # If over a certain amount of lines, delete all lines from the top up to a threshold
        self.textIndex = float(self.liveDataText.index('end'))
        if self.textIndex > self.textThreshold:
            self.liveDataText.delete(1.0, self.textIndex - self.textThreshold)
            # Remove history from RAM (to avoid memory Leak
            self.liveDataText.edit_reset()
        self.liveDataText['state'] = 'disabled'
        # If autoscroll is enabled, then scroll to bottom
        if self.autoScrollEnable.get() == 1:
            self.liveDataText.see(END)


    # Handles program close
    # Make sure logging finishes before program closes
    # Also signals TCP server to close any exisiting connections
    def onClose(self):
        errorLogger = logging.getLogger('error_logger')
        try:
            # If logger is running, ask user if they really want to close
            if self.logger.logEnbl is True:
                close = messagebox.askokcancel("Close",
                                               "Logging has not be finished. Are you sure you want to quit?")
                if close:
                    # If yes, stop logging first before closing
                    self.logToggle()
                    # Signal to TCP server to close connections
                    self.exitTcp.set()
                    root.destroy()
                    errorLogger.info("\nGUI Closed Successfully")
            else:
                # Signal to TCP server to close connections
                self.exitTcp.set()
                root.destroy()
                errorLogger.info("\nGUI Closed Successfully")
        # If logger has never been run, logger.logEnbl will not exist
        # In this case, close normally
        except AttributeError:
            # Signal to TCP server to close connections
            self.exitTcp.set()
            root.destroy()
            errorLogger.info("\nGUI Closed Successfully")


    # Toggles between the textbox and live graph being displayed
    def switchDisplay(self):
        if self.textBox == True:
            # Unpack textbox and scrollbar
            self.liveDataText.pack_forget()
            self.liveDataScrollBar.pack_forget()
            # Change title
            self.liveTitle['text'] = "Live Graph"
            # Pack graph canvas
            self.canvas.get_tk_widget().pack()
            # Set textBox to false so program knows graph is displayed
            self.textBox = False
        else:
            # Unpack graph canvas
            self.canvas.get_tk_widget().pack_forget()
            # Change title
            self.liveTitle['text'] = "Live Data"
            # Pack textbox and scrollbar
            self.liveDataScrollBar.pack(side=RIGHT, fill=Y)
            self.liveDataText.pack()
            # Set textBox to true so program knows textbox is displayed
            self.textBox = True

    # Live Data Output
    # Function is run in separate thread to ensure it doesn't interfere with GUI operations
    def liveData(self):
        # Setup variables used for data output
        adcHeader = []
        pinDict = {}
        # Set up variables for creating a live graph
        timeData = []
        logData = []
        # Reset graph drop down menu
        self.channelSelect['values'] = []

        # Always start logging with the textbox shown as it prints the current settings
        if self.textBox == False:
            self.switchDisplay()

        # Print start of live data to user
        self.textboxOutput("Live Data:\n")
        # Get values of pins being logged from self.logger.logComp
        adcHeaderPrint = ""
        for pin in self.logger.logComp.config:
            if pin.enabled == True:
                # Add pin to graph drop down menu
                self.channelSelect['values'] = (*self.channelSelect['values'], pin.fName)
                # Add pin to adcHeader
                adcHeader.append(pin.name)
                # Add pin m and c values to pinDict for data conversion
                pinDict[pin.name] = [pin.m, pin.c]
                # Add a list to logData to store pinData for graphing
                logData.append([])
                # Add name and units to the header output
                adcHeaderPrint += ("|{:>3}{:>5}".format(pin.name, pin.units))
        # Set drop down menu select item to the first pin and enable
        self.channelSelect.current(0)
        self.channelSelect['state'] = 'enabled'
        # Print the heading with all the pins
        self.textboxOutput("{}|".format(adcHeaderPrint))
        # Print a nice horizontal line so it all looks pretty
        self.textboxOutput("-" * (9 * self.logger.logComp.enabled + 1))

        # Create buffer to store previous data
        # Used to detect whether new data has been logged or not
        buffer = [0] * self.logger.logComp.enabled

        # Don't print live data when logging has not started
        while not self.logger.logEnbl or 0 in self.values[:]:
            pass

        # When data has arrived, set startTime and drawTime for live graph
        startTime = time.perf_counter()
        drawTime = 0

        # Live data loop, outputs live data to graph or textbox for as long as the log runs
        while self.logger.logEnbl == True:
            # Get most recent logged data
            currentVals = self.values[:]
            # If data is new, output data
            if currentVals != buffer:
                buffer = currentVals
                ValuesPrint = ""
                # Create a nice string to print with the values in
                # Only prints data that is being logged
                timeData.append(round(time.perf_counter() - startTime, 2))
                for no, val in enumerate(currentVals):
                    # Get the name of the pin so it can be used with pinDict
                    pinName = adcHeader[no]
                    # Calculate converted value using pinDict m and c values
                    convertedVal = val * pinDict[pinName][0] + pinDict[pinName][1]
                    # Append converted value to the list for the pin in logData
                    logData[no].append(convertedVal)
                    # Add converted value to the string being printed
                    ValuesPrint += ("|{:>8}".format(round(convertedVal, 2)))
                # Print data to textbox
                self.textboxOutput("{}|".format(ValuesPrint))
                # If graph is showing, update graph
                # Otherwise don't as it reduces overhead
                if self.textBox is False:
                    # Get current pin/channel select to graph
                    channel = self.channelSelect.current()
                    # Get minimum length so that yData and xData are the same length
                    length = min(len(timeData), len(logData[channel]))
                    # Update yData and xData which are plotted on live graph
                    yData = logData[channel][:length]
                    xData = timeData[:length]
                    # Clear axis, plot new data and set grid to true
                    self.ax1.clear()
                    self.ax1.plot(xData, yData)
                    self.ax1.grid()

                    # Graph is redrawn a maximum of once per second
                    # If graph is due to be redrawn, redraw graph
                    if (time.perf_counter() - drawTime) > max(1, self.logger.logComp.time):
                        try:
                            # Redraw graph
                            self.canvas.draw_idle()
                            # Update drawTime
                            drawTime = time.perf_counter()
                        except IndexError:
                            # If graph cannot be drawn, ignore as not fatal
                            # Graph will be updated during next redraw
                            """Drawing failed, this doesn't matter as graph will be drawn next time"""
                    # Only store 1000 data points for time and pin data to avoid memory leak
                    if len(timeData) > 1000:
                        timeData = timeData[-1000:]
                        for i in range(0, len(logData)):
                            logData[i] = logData[i][-1000:]
            # Sleep so that while loop is not run too quickly
            # Otherwise screen judders
            time.sleep(0.01)
        # At the end of a log, disable graph drop down menu
        self.channelSelect['values'] = [self.channelSelect['values'][self.channelSelect.current()]]
        self.channelSelect['state'] = 'disabled'


    # This function handles commmands from the TCP server
    # It is run periodically every 0.1 seconds
    def commandHandler(self, connGui):
        # If there are no commands to process, return
        if connGui.poll() == False:
            self.after(100, self.commandHandler, connGui)
            return
        # Receive command from Pipe
        command = connGui.recv()

        if command == "Start":
            # If the logger is not running, start logger and tell TCP server
            if self.logger.logEnbl == False:
                self.logToggle()
                connGui.send("Logger started")
            # If logger is already running, tell TCP server
            else:
                connGui.send("Logger already running")
        elif command == "Stop":
            # If the logger is running, stop logger and tell TCP server
            if self.logger.logEnbl == True:
                self.logToggle()
                connGui.send("Logger stopped")
            # If the logger is not running, tell TCP server
            else:
                connGui.send("Logger not running")
        elif command == "Print":
            # Prints the next data in the Pipe to the Live Data Textbox
            self.textboxOutput(connGui.recv())
        elif command == "BindFailed":
            # If there is a bind error when starting TCP server, alert user
            errorLogger = logging.getLogger('error_logger')
            messagebox.showerror("Error", "Server connection already in use.\n"
                                          "Please make sure only one instance of the logger is running at one time.")
            # This error occurs when something is already bound to port 13000
            # Program cannot work so close program
            # It is up to user to check for multiple instances of the program and close them as necessary
            self.exitTcp.set()
            root.destroy()
            errorLogger.info("\nGUI Closed Successfully")
        self.after(100, self.commandHandler, connGui)


    # Used at the end of a log to check quality of logged data
    def DataCheck(self):
        self.textboxOutput("\nLog Quality Info:")
        # Get the path of the logged raw data
        path = Path(db.GetDataPath(self.logger.logComp.id))
        # Read data in DataFrame
        data = pd.read_csv(path)
        # Count the number of lines logger
        numLines = data['Time Interval (seconds)'].count()
        self.textboxOutput("Logged {} lines of data".format(numLines))

        # Setup variables for calculating time interval accuracy
        differences = 0
        times = data['Time Interval (seconds)']
        prev = 0
        incorrect = 0
        for time in times:
            # Calculate time interval between two consecutive points
            difference = round(float(time) - prev, 1)
            # If time interval is incorrect, increment incorrect by 1
            if difference != self.logger.logComp.time:
                incorrect += 1
            differences += (difference)
            prev = float(time)
        # Output number of incorrect time intervals
        self.textboxOutput("{} lines had a time interval not equal to {}".format(incorrect,self.logger.logComp.time))
        average = differences / numLines
        # Output average time interval
        self.textboxOutput("Average time interval: {}".format(average))


# Setup error logging
def errorLoggingSetup():
    # Used to set logger
    errorLogger = logging.getLogger('error_logger')
    # Select min level of severity to log
    errorLogger.setLevel(logging.INFO)
    # create file handler which logs even debug messages
    fh = logging.FileHandler('piError.log')
    fh.setLevel(logging.INFO)
    errorLogger.addHandler(fh)
    # Print Top Line to make it easy to identify new instance of program
    errorLogger.info("\n\n{}\nNEW INSTANCE OF LOGGER GUI @ {}\n{}\n".format('-' * 75, datetime.now(), '-' * 75))


# Function called every time a line of an error is written to sys.stderr
# Redirects them from the (invisible) console to the log file
# Note: - Function may be called once per error (if error originates in a separate thread)
# or several times until error is written.
def stderrRedirect(buf):
    # Setup error logging
    errorLogger = logging.getLogger('error_logger')
    # Print Stderr to error logger with a timestamp
    for line in buf.rstrip().splitlines():
        errorLogger.error("{}  - {}".format(datetime.now(), line.rstrip()))
    # Show Message Box in Program to warn user of error - note several may appear for a given error
    messagebox.showerror("Error", "More Unhandled Exceptions! Check piError.log"
                                  "\nNote: This message may appear several times for a given error")


# Initialises GUI
def run(connGui, exitTcp):
    # PROGRAM START #
    # Start Error Logging
    errorLoggingSetup()

    # Warn Users of error locations if starting from console
    print("Warning - all stderr output from this point onwards is logged in piError.log")
    # Redirect all stderr to text file, unless in development environment
    # If you want errors to be printed to console, change "Alistair-Laptop" to name of your computer
    if socket.gethostname() != "Alistair-Laptop":
        sys.stderr.write = stderrRedirect

    global root
    # Create Tkinter Instance
    root = Tk()

    # Set Window Icon
    img = PhotoImage(file='icon.png')
    root.tk.call('wm', 'iconphoto', root._w, img)

    # Size of the window (Uncomment for Full Screen)
    try:
        root.wm_attributes('-zoomed', 1)
    # Error occurs with the above on non-Pi (dev) computer
    # Catch error and start up GUI in standard window size
    except TclError:
        pass
    # Fonts
    global bigFont
    bigFont = font.Font(family="Helvetica", size=16, weight=font.BOLD)
    global smallFont
    smallFont = font.Font(family="Courier", size=11)

    # Create instance of GUI
    app = WindowTop(root, connGui=connGui, exitTcp=exitTcp)

    # Ensure when the program quits, it quits gracefully - e.g. stopping the log first
    root.protocol("WM_DELETE_WINDOW", app.onClose)

    # Tkinter Mainloop in charge of making the gui do everything
    root.mainloop()


# This is the code that is run when the program is loaded.
# If the module were to be imported, the code inside the if statement would not run.
# Calls the init() function and then the log() function
if __name__ == "__main__":
    # Warning about lack of server
    print("\nWARNING - running this script directly will not start the server "
          "\nIf you need to use the user program to communicate with the Pi, use 'main.py'\n")
    # Run logger as per normal setup
    # connGui and exitTcp don't exist as they are created by main.py
    run(connGui=None,exitTcp=None)
