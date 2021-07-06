# Import Packages/Modules
import queue
import time
from datetime import datetime, timedelta
from collections import OrderedDict
import configparser
import functools
# Uncomment below for real adc (if running on Pi)
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from adafruit_ads1x15.ads1x15 import Mode
import busio
import board
# Uncomment below for fake adc simulation if using a PC
#from AnalogInFake import AnalogIn as AnalogIn
#import ADS1115Fake as ADS

import csv
import threading
import shutil
import os

import file_rw
import logObjects as lgOb
import databaseOp as db
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import os
from decimal import Decimal
import numpy as np
import gui

def ADCReader(pins,name):
    startTime = time.perf_counter()
    with open("worker{}test.csv".format(name),"w") as file:
        worker_writer = csv.writer(file, dialect="excel", delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        while True:
            for pin in pins:
                timeElapsed = time.perf_counter() - startTime
                worker_writer.writerow([timeElapsed] + [pin[0].value])


def run():
    i2c = busio.I2C(board.SCL, board.SDA, frequency=1000000)
    dataRate = 860

    adc0 = ADS.ADS1115(i2c, address=0x48, mode=Mode.CONTINUOUS, data_rate=dataRate)
    adc1 = ADS.ADS1115(i2c, address=0x49, mode=Mode.CONTINUOUS, data_rate=dataRate)
    adc2 = ADS.ADS1115(i2c, address=0x4a, mode=Mode.CONTINUOUS, data_rate=dataRate)
    adc3 = ADS.ADS1115(i2c, address=0x4b, mode=Mode.CONTINUOUS, data_rate=dataRate)

    adcPinMap = {
        "0AX": {
            "0A0": [AnalogIn(ads=adc0, gain=1, positive_pin=ADS.P0), 0],
            "0A1": [AnalogIn(ads=adc0, gain=1, positive_pin=ADS.P1), 1],
            "0A2": [AnalogIn(ads=adc0, gain=1, positive_pin=ADS.P2), 2],
            "0A3": [AnalogIn(ads=adc0, gain=1, positive_pin=ADS.P3), 3]
        },
        "1AX": {
            "1A0": [AnalogIn(ads=adc1, gain=1, positive_pin=ADS.P0), 4],
            "1A1": [AnalogIn(ads=adc1, gain=1, positive_pin=ADS.P1), 5],
            "1A2": [AnalogIn(ads=adc1, gain=1, positive_pin=ADS.P2), 6],
            "1A3": [AnalogIn(ads=adc1, gain=1, positive_pin=ADS.P3), 7]
        },
        "2AX": {
            "2A0": [AnalogIn(ads=adc2, gain=1, positive_pin=ADS.P0), 8],
            "2A1": [AnalogIn(ads=adc2, gain=1, positive_pin=ADS.P1), 9],
            "2A2": [AnalogIn(ads=adc2, gain=1, positive_pin=ADS.P2), 10],
            "2A3": [AnalogIn(ads=adc2, gain=1, positive_pin=ADS.P3), 11]
        },
        "3AX": {
            "3A0": [AnalogIn(ads=adc3, gain=1, positive_pin=ADS.P0), 12],
            "3A1": [AnalogIn(ads=adc3, gain=1, positive_pin=ADS.P1), 13],
            "3A2": [AnalogIn(ads=adc3, gain=1, positive_pin=ADS.P2), 14],
            "3A3": [AnalogIn(ads=adc3, gain=1, positive_pin=ADS.P3), 15]
        }
    }
    for name,adc in adcPinMap.items():
        if name != "3AX":
            pins = []
            for pin in adc.values():
                pins.append(pin)
            worker = threading.Thread(target=ADCReader,args=(pins,name))
            worker.daemon = True
            worker.start()


    startTime = time.perf_counter()
    with open("test.csv","w") as file:
        writer = csv.writer(file, dialect="excel", delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        while True:
            for pin in adcPinMap["3AX"].values():
                timeElapsed = time.perf_counter() - startTime
                writer.writerow([timeElapsed] + [pin[0].value])

if __name__ == "__main__":
    run()