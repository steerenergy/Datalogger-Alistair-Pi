import socket
import queue
import time
from threading import Thread


def listener (client_socket,dataQueue):
    while True:
        data = client_socket.recv(2048).decode("utf-8").split("\n")
        for i in range(0,len(data) -1):
            dataQueue.put(data[i].strip("\n"))


def new_client(client_socket, address):
    dataQueue = queue.Queue()
    listenThread = Thread(target=listener, args=(client_socket,dataQueue))
    listenThread.daemon = True
    listenThread.start()
    while True:
        time.sleep(1)
        data = dataQueue.get()
        print(data)



serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
# Bind the socket to the logger IP address and port 13000
serversocket.bind(("0.0.0.0", 13001))
serversocket.listen(5)
# Accept connections forever until program is terminated
while True:
    # Accept connections from outside
    (client_socket, address) = serversocket.accept()
    # Create new thread to deal with new client
    # This allows multiple clients to connect at once
    # (Objective 1.2)
    worker = Thread(target=new_client, args=(client_socket, address))
    worker.daemon = True
    worker.start()
    # Log Connection
    print("@" + address[0] + " connected.")
