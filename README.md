# Datalogger-Alistair-Pi
The Steer Energy Datalogger application which runs on a Raspberry Pi 3B+ and interfaces with Adafruit ADS1115 Analog to Digital Converters.

## Table of Contents
* [General info](#general-info)
* [Technologies](#technologies)
* [Installation](#installation)
* [Development](#development)
* [Issues](#issues)

## General Info
This project is a Python application which handles reading data from Adafruit ADS1115 Analog to Digital Converters connected to the Pi via the I2C bus and storing that data in .csv files on the Pi. It can be interfaced with using the Pi's touchscreen (all Steer Energy Dataloggers have 7" touchscreens) or by using the UI application [here](https://github.com/steerenergy/Datalogger-Alistair-UI).

## Technologies
This project was written mainly in Python 3.8.8 and was created with:
* PyCharm 2021.2 (Community Edition)
* SQLite Version 3.35.4
* Raspberry Pi 3B+ with OS Raspbian GNU/Linux 10 (buster)
* Adafruit ADS1115 Analog to Digital Converters

## Installation
You can install the project by going onto a Raspberry Pi 3B+ terminal and using 'git clone https://github.com/steerenergy/Datalogger-Alistair-Pi.git' to clone the Github repository into a location of your choosing. Then you can start the application using 'python3 main.py' to begin the logger. More details on installation can be found in the Technical Documentation and the RPI Setup Guide. Ask NickRyanSteer or Alistair-L-R if you want the documentation.

## Development
If you wish to develop this project, you will need to be added to the steerenergy organisation and you will need to speak to Alistair-L-R or NickRyanSteer to get the required documents. **Note: It is unlikely this project will need development unless Steer Energy directly ask for it and have a need for further development.**

## Issues
If you encounter an issue whilst using the application, please report the issue [here](https://github.com/steerenergy/Datalogger-Alistair-UI/issues) and we will try to fix it as soon as possible. In your report, please include these details if applicable:
* The version of the software
* Error messages - screenshots ideal
* Screenshots/Photos to show issues
* Any data/config files used in the testing
* Steps to reproduce the issue
* 'piError.log' for a Logger Issue

Any questions, message Alistair-L-R
Happy Logging!
