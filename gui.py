# This uses tkinter which is a really common multi-platform GUI
# Script connects to logger.py and acts a front end to it

import logging
import os
import queue
import time
from datetime import datetime
import threading
from threading import Thread
from tkinter import *
from tkinter import ttk
from tkinter import font, messagebox

import socket

from logger import Logger
import matplotlib.pyplot as plt
from multiprocessing import Process, Array, Event, Pipe
import matplotlib.animation as animation
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

        # Redirect normal print commands to textbox on GUI
        # sys.stdout.write = self.redirector

        # Holds the number of lines in the textbox (updated after each print)
        self.textIndex = None
        # Determines the max number of lines on the tkinter GUI at any given point.
        self.textThreshold = 250

        # Create variables used for log process
        # Note, these are initialised when logging starts
        # Otherwise only one log can be performed
        self.logProcess = None
        self.stop = None
        self.receiver, self.sender = None, None
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
        self.channelSelect.pack(pady=(10, 10))

        # Create instance of the logger class
        self.logger = Logger()

        self.after(1000, self.commandHandler, connGui)

        self.tcpExit = exitTcp

    # Contains functions for the start/stop logging buttons
    # (Objective 14)
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
            # Load and Start Logger thread
            # Load Config Data and Setup
            adcToLog, adcHeader = self.logger.init(self.textboxOutput)
            # Only continue if import was successful
            if self.logger.logEnbl is True:
                self.logger.checkName()
                # Print Settings
                self.logger.settingsOutput(self.textboxOutput)
                # Run Logging
                self.stop = Event()
                self.receiver, self.sender = Pipe(duplex=False)
                self.values = Array('f',self.logger.logComp.config.enabled, lock=True)
                self.logProcess = Process(target=self.logger.log, args=(adcToLog, adcHeader, self.stop, self.values))
                self.logProcess.start()
            else:
                self.logger.logEnbl = False
                # Change Button Text
                self.logButton.config(text="Start Logging")
                # Re-enable Button
                self.logButton['state'] = 'normal'
                return
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
            # Change logEnbl variable to false which stops the loop in logThread and subsequently the live data
            self.logger.logEnbl = False
            self.logThreadStopCheck()
            self.stop.set()
            # Check to see if logThread has ended
            self.logProcess.join()

    # Is triggered when 'Stop Logging' ic clicked and is called until logThread is dead
    # If logThread has finished the 'start logging' button is changed and enabled
    # Else, the function is triggered again after a certain period of time
    def logThreadStopCheck(self):
        if self.liveDataThread.is_alive() is False:
            self.logProcess.close()
            # Change Button Text
            self.logButton.config(text="Start Logging")
            # Tell user logging has stopped
            self.textboxOutput("Logging Stopped - Success!")
            # Re-enable Button
            self.logButton['state'] = 'normal'
        else:
            # Repeat the process after a certain period of time.
            # Note that time.sleep isn't used here. This is Crucial to why this has been done
            # The timer works independently to the main thread, allowing the print statments to be processed
            # This stops the program freezing if logThread is trying to print but the GUI is occupied so it can't
            self.after(100, self.logThreadStopCheck)

    # This redirects all print statements from console to the textbox in the GUI.
    # Note - errors will be displayed in terminal still
    # It essentially redefines what the print statement does
    # (Objectives 15 and 19)
    def textboxOutput(self, inputStr, flush=False):
        # Enable, write data, delete unnecessary data, disable
        # Used to print data to GUI screen
        # (Objective 19.1)
        self.liveDataText['state'] = 'normal'
        if flush == False:
            inputStr += "\n"
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

    # Make sure logging finishes before program closes
    def onClose(self):
        errorLogger = logging.getLogger('error_logger')
        try:
            if self.logger.logEnbl is True:
                close = messagebox.askokcancel("Close",
                                               "Logging has not be finished. Are you sure you want to quitEvent?")
                if close:
                    self.logToggle()
                    self.tcpExit.set()
                    root.destroy()
                    errorLogger.info("\nGUI Closed Successfully")
            else:
                self.tcpExit.set()
                root.destroy()
                errorLogger.info("\nGUI Closed Successfully")
        # If logger has never been run, logger.logEnbl will not exist
        except AttributeError:
            self.tcpExit.set()
            root.destroy()
            errorLogger.info("\nGUI Closed Successfully")

    # Toggles between the textbox and live graph being displayed
    # (Objective 16)
    def switchDisplay(self):
        if self.textBox == True:
            self.liveDataText.pack_forget()
            self.liveDataScrollBar.pack_forget()
            self.liveTitle['text'] = "Live Graph"
            self.canvas.get_tk_widget().pack()
            self.textBox = False
        else:
            self.canvas.get_tk_widget().pack_forget()
            self.liveDataScrollBar.pack(side=RIGHT, fill=Y)
            self.liveDataText.pack()
            self.liveTitle['text'] = "Live Data"
            self.textBox = True

    # Live Data Output
    # Function is run in separate thread to ensure it doesn't interfere with logging
    def liveData(self):
        adcHeader = []
        self.channelSelect['values'] = []
        pinDict = {}

        # Set up variables for creating a live graph
        timeData = []
        logData = []

        # Always start logging with the textbox shown as it prints the current settings
        if self.textBox == False:
            self.switchDisplay()
        # Setup data buffer to hold most recent data
        self.textboxOutput("Live Data:\n")
        # Print header for all pins being logged
        adcHeaderPrint = ""

        for pin in self.logger.logComp.config.pinList:
            if pin.enabled == True:
                self.channelSelect['values'] = (*self.channelSelect['values'], pin.fName)
                adcHeader.append(pin.name)
                pinDict[pin.name] = [pin.m, pin.c]
                logData.append([])
                adcHeaderPrint += ("|{:>3}{:>5}".format(pin.name, pin.units))
        self.channelSelect.current(0)
        #for i in range(0, self.logger.logComp.config.enabled):
        #    logData.append([])
        #for pin in self.logger.logComp.config.pinList:
        #    if pin.enabled:

        self.textboxOutput("{}|".format(adcHeaderPrint))
        # Print a nice vertical line so it all looks pretty
        self.textboxOutput("-" * (9 * self.logger.logComp.config.enabled + 1))
        buffer = []
        # Don't print live data when adcValuesCompl doesn't exist. Also if logging is stopped, exit loop
        # while len(logComp.logData.timeStamp) == 0 and logEnbl is True:
        #    pass
        while not self.logger.logEnbl:
            pass

        # Livedata Loop - Loops Forever until LogEnbl is False (controlled by GUI)
        startTime = time.perf_counter()
        drawTime = 0
        buffer = [0] * self.logger.logComp.config.enabled
        while self.logger.logEnbl == True:
            # Get Complete Set of Logged Data
            # If Data is different to that in the buffer
            # (Objective 18.1)
            # current = self.logger.adcValuesCompl
            #while self.receiver.poll():
            currentVals = self.values[:]
            if currentVals != buffer:
                # buffer = logComp.logData.GetLatest()
                buffer = currentVals
                ValuesPrint = ""
                # Create a nice string to print with the values in
                # Only prints data that is being logged
                timeData.append(round(time.perf_counter() - startTime, 2))
                for no, val in enumerate(currentVals):
                    # Get the name of the pin so it can be used to find the adc object
                    pinName = adcHeader[no]
                    # Calculate converted value
                    convertedVal = val * pinDict[pinName][0] + pinDict[pinName][1]
                    logData[no].append(convertedVal)
                    # Add converted value to the string being printed
                    ValuesPrint += ("|{:>8}".format(round(convertedVal, 2)))
                # Print data to textbox
                # (Objective 18.2)
                self.textboxOutput("{}|".format(ValuesPrint))
                if self.textBox is False:
                    channel = self.channelSelect.current()
                    length = min(len(timeData), len(logData[channel]))
                    # Update yData and xData which are plotted on live graph
                    yData = logData[channel][:length]
                    xData = timeData[:length]
                    self.ax1.clear()
                    self.ax1.plot(xData, yData)
                    self.ax1.grid()

                    if (time.perf_counter() - drawTime) > max(1, self.logger.logComp.time):
                        try:
                            self.canvas.draw_idle()
                            drawTime = time.perf_counter()
                        except IndexError:
                            """Drawing failed, this doesn't matter as graph will be drawn next time"""

                    if len(timeData) > 1000:
                        timeData = timeData[-1000:]
                        for i in range(0, len(logData)):
                            logData[i] = logData[i][-1000:]
            time.sleep(0.01)


    def commandHandler(self, connGui):
        if connGui.poll() == False:
            self.after(100, self.commandHandler, connGui)
            return
        command = connGui.recv()
        if command == "Start":
            if self.logger.logEnbl == False:
                self.logToggle()
                connGui.send("Logger started")
            else:
                connGui.send("Logger already running")
        elif command == "Stop":
            if self.logger.logEnbl == True:
                self.logToggle()
                connGui.send("Logger stopped")
            else:
                connGui.send("Logger not running")
        elif command == "Print":
            self.textboxOutput(connGui.recv())
        elif command == "BindFailed":
            errorLogger = logging.getLogger('error_logger')
            messagebox.showerror("Error", "Server connection already in use.\n"
                                          "Please make sure only one instance of the logger is running at one time.")
            self.tcpExit.set()
            root.destroy()
            errorLogger.info("\nGUI Closed Successfully")
        self.after(100, self.commandHandler, connGui)


# Setup error logging
# (Objective 19.3)
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


def run(connGui, exitTcp):
    # PROGRAM START #
    # Start Error Logging
    errorLoggingSetup()

    # Warn Users of error locations
    print("Warning - all stderr output from this point onwards is logged in piError.log")
    # Redirect all stderr to text file. Comment the next line out for errors to be written to the console
    # Replace string with development computer hostname
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
    except:
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
    # Warning about lack of CSV
    print("\nWARNING - running this script directly will not start the server "
          "\nIf you need to use the user program to communicate with the Pi, use 'main.py'\n")
    # Run logger as per normal setup
    run(connGui=None, exit=None)
