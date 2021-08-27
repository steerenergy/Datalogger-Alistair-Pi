# Starting point for Alistair's logger
# This sets up communication between the TCP server and the GUI
# It also starts the TCP server and GUI in separate threads

import tcpServer
import gui
from threading import Thread
from multiprocessing import Pipe, Event

# This stops errors occurring when creating a new process for logging
# Makes sure TCP/GUI initialisation only occurs when running main for the first time
if __name__ == '__main__':
    print("Starting application.")
    # TCP server and GUI use a Pipe to communicate
    # exitTcp Event is used to shutdown TCP server when the GUI is closed
    connGui, connTcp = Pipe()
    exitTcp = Event()
    # Create thread for TCP server to run on
    # This is so TCP connections can be processed separate from the GUI
    serverThread = Thread(target=tcpServer.run, args=(connTcp, exitTcp))
    serverThread.start()
    print("ServerThread starting")

    # Start the GUI in this thread
    gui.run(connGui, exitTcp)
