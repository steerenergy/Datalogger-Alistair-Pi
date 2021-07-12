import sys
from pathlib import Path
import pandas as pd


path = Path(sys.argv[1])

data = pd.read_csv(path)

print(data.head())

numLines = data['Time Interval (seconds)'].count()
print(numLines)

differences = 0

times = data['Time Interval (seconds)']
prev = 0
for time in times:
    difference = round(float(time) - prev,1)
    if difference != 0.1:
        print(str(prev) + "  " + str(time) + " " + str(difference))
    differences += (difference)
    prev = float(time)

average = differences/numLines
print(average)
