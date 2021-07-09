import multiprocessing
import queue
import tcpServer as tcp
import gui
import logger as logPi
from threading import Thread
import multiprocessing as mp



print("Starting application.")
commandQueue = queue.Queue()
# Create thread for TCP server to run on
# This is so TCP connections can be processed separate from the GUI
serverThread = Thread(target=tcp.run, args=(commandQueue,))
serverThread.daemon = True
serverThread.start()
print("ServerThread starting")

#logger = logPi.Logger()
#logger.run()
# Start the GUI
gui.run(commandQueue)