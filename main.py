import multiprocessing
import queue
import time

import tcpServer as tcp
import gui
import logger as logPi
from threading import Thread
import multiprocessing as mp
from multiprocessing import Pipe, Event


if __name__ == '__main__':
    #mp.set_start_method('spawn')
    print("Starting application.")
    connGui, connTcp = Pipe()
    #exitTcp = Event()
    # Create thread for TCP server to run on
    # This is so TCP connections can be processed separate from the GUI
    #serverThread = Thread(target=tcp.run, args=(connTcp,exitTcp))
    serverThread = Thread(target=tcp.run, args=(connTcp,))
    serverThread.daemon = True
    serverThread.start()
    print("ServerThread starting")

    # logger = logPi.Logger()
    # logger.run()
    # Start the GUI
    #gui.run(connGui,exitTcp)
    gui.run(connGui)
