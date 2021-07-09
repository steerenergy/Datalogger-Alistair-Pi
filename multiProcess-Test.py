import multiprocessing
from multiprocessing import Process, Pipe
import time
from logger import Logger


def f(conn):
    startTime = time.perf_counter()
    timeElapsed = 0
    while timeElapsed < 20:
        conn.send([timeElapsed, None, 'hello'])
        time.sleep(0.1)
        timeElapsed = time.perf_counter() - startTime
    conn.close()

if __name__ == '__main__':
    parent_conn, child_conn = Pipe(duplex=False)
    logger = Logger()
    adcToLog, adcHeader = logger.init()
    # Only continue if import was successful
    if logger.logEnbl is True:
        logger.checkName()
        # Print Settings
        logger.settingsOutput()
        # Run Logging
        # self.logThread = threading.Thread(target=self.logger.log, args=(adcToLog,adcHeader))
        # self.logThread.start()
        event = multiprocessing.Event()
        logProcess = Process(target=logger.log, args=(adcToLog, adcHeader, event, child_conn))
        logProcess.start()
    time.sleep(1)
    while True:
        print(parent_conn.recv())   # prints "[42, None, 'hello']"
    p.join()