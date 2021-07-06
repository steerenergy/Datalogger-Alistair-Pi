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


i2c = busio.I2C(board.SCL, board.SDA, frequency=1000000)
dataRate = 860

adc0 = ADS.ADS1115(i2c, address=0x48, mode=Mode.CONTINUOUS, data_rate=dataRate)
adc1 = ADS.ADS1115(i2c, address=0x49, mode=Mode.CONTINUOUS, data_rate=dataRate)
adc2 = ADS.ADS1115(i2c, address=0x4a, mode=Mode.CONTINUOUS, data_rate=dataRate)
adc3 = ADS.ADS1115(i2c, address=0x4b, mode=Mode.CONTINUOUS, data_rate=dataRate)

adcPinMap = {
            "0AX": {
                "0A0": [AnalogIn(ads=adc0, gain=1, positive_pin=ADS.P0)],
                "0A1": [AnalogIn(ads=adc0, gain=1, positive_pin=ADS.P1)],
                "0A2": [AnalogIn(ads=adc0, gain=1, positive_pin=ADS.P2)],
                "0A3": [AnalogIn(ads=adc0, gain=1, positive_pin=ADS.P3)]
            },
            "1AX": {
                "1A0": [AnalogIn(ads=adc1, gain=1, positive_pin=ADS.P0)],
                "1A1": [AnalogIn(ads=adc1, gain=1, positive_pin=ADS.P1)],
                "1A2": [AnalogIn(ads=adc1, gain=1, positive_pin=ADS.P2)],
                "1A3": [AnalogIn(ads=adc1, gain=1, positive_pin=ADS.P3)]
            },
            "2AX": {
                "2A0": [AnalogIn(ads=adc2, gain=1, positive_pin=ADS.P0)],
                "2A1": [AnalogIn(ads=adc2, gain=1, positive_pin=ADS.P1)],
                "2A2": [AnalogIn(ads=adc2, gain=1, positive_pin=ADS.P2)],
                "2A3": [AnalogIn(ads=adc2, gain=1, positive_pin=ADS.P3)]
            },
            "3AX": {
                "3A0": [AnalogIn(ads=adc3, gain=1, positive_pin=ADS.P0)],
                "3A1": [AnalogIn(ads=adc3, gain=1, positive_pin=ADS.P1)],
                "3A2": [AnalogIn(ads=adc3, gain=1, positive_pin=ADS.P2)],
                "3A3": [AnalogIn(ads=adc3, gain=1, positive_pin=ADS.P3)]
            }
        }


pins = []
for pin in adcPinMap["0AX"].values():
    pins.append(pin)


startTime = time.perf_counter()
while True:
    for pin in pins:
        timeElapsed = time.perf_counter() - startTime
        print("{}: {}".format(timeElapsed,pin[0].value))