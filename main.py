import multiprocessing
import queue
import atexit
import time

import tcpServer as tcp
import gui
import logger as logPi
from threading import Thread
import multiprocessing as mp
from multiprocessing import Pipe, Event


def Exit(exit):
    exit.set()
    time.sleep(1)


if __name__ == '__main__':
    #mp.set_start_method('spawn')
    print("Starting application.")
    connGui, connTcp = Pipe()
    exit = Event()
    atexit.register(Exit,(exit))
    # Create thread for TCP server to run on
    # This is so TCP connections can be processed separate from the GUI
    serverThread = Thread(target=tcp.run, args=(connTcp,exit))
    serverThread.daemon = True
    serverThread.start()
    print("ServerThread starting")

    # logger = logPi.Logger()
    # logger.run()
    # Start the GUI
    gui.run(connGui)
