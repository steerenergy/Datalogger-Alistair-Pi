import tcpServer as tcp
import gui
from threading import Thread


print("Starting application.")
# Create thread for TCP server to run on
# This is so TCP connections can be processed separate from the GUI
serverThread = Thread(target=tcp.run, args=())
serverThread.daemon = True
serverThread.start()
print("ServerThread starting")
# Start the GUI
gui.run()