import multiprocessing
from multiprocessing import Process, Pipe
import time
from logger import Logger




if __name__ == '__main__':
    parent_conn, child_conn = Pipe(duplex=False)
    logger = Logger()
    adcToLog, adcHeader = logger.init(print)
    # Only continue if import was successful
    if logger.logEnbl is True:
        logger.checkName()
        # Print Settings
        logger.settingsOutput(print)
        # Run Logging
        # self.logThread = threading.Thread(target=self.logger.log, args=(adcToLog,adcHeader))
        # self.logThread.start()
        event = multiprocessing.Event()
        logProcess = Process(target=logger.log, args=(adcToLog, adcHeader, event, child_conn))
        logProcess.start()
    time.sleep(1)
    while True:
        print(parent_conn.recv())
    p.join()
