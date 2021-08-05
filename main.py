import tcpServer
import gui
from threading import Thread
from multiprocessing import Pipe, Event

if __name__ == '__main__':
    print("Starting application.")
    # Setup communication between gui and tcp server
    connGui, connTcp = Pipe()
    exitTcp = Event()
    # Create thread for TCP server to run on
    # This is so TCP connections can be processed separate from the GUI
    serverThread = Thread(target=tcpServer.run, args=(connTcp, exitTcp))
    serverThread.daemon = True
    serverThread.start()
    print("ServerThread starting")

    # Start the GUI
    gui.run(connGui, exitTcp)
