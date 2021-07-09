import sys
from pathlib import Path
import pandas as pd


path = Path(sys.argv[1])

data = pd.read_csv(path)

numLines = data.items().count()

differences = 0

times = data['Time (seconds)']
prev = 0
for time in times:
    differences += (int(time) - prev)
    prev = int(time)

average = differences/numLines
print(average)
