from multiprocessing import Process, Pipe
import time


def f(conn):
    startTime = time.perf_counter()
    timeElapsed = 0
    while timeElapsed < 20:
        conn.send([timeElapsed, None, 'hello'])
        time.sleep(0.1)
        timeElapsed = time.perf_counter() - startTime
    conn.close()

if __name__ == '__main__':
    parent_conn, child_conn = Pipe()
    p = Process(target=f, args=(child_conn,))
    p.start()
    time.sleep(1)
    while True:
        print(parent_conn.recv())   # prints "[42, None, 'hello']"
    p.join()