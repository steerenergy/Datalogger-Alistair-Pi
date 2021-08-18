# NOTE - TESTING PURPOSES ONlY
# This script is for testing code when the pi isn't available
# It will simply return a number regardless of the pin

import random

_ADS1X15_DIFF_CHANNELS = {(0, 1): 0, (0, 3): 1, (1, 3): 2, (2, 3): 3}
_ADS1X15_PGA_RANGE = {2 / 3: 6.144, 1: 4.096, 2: 2.048, 4: 1.024, 8: 0.512, 16: 0.256}


class AnalogIn:

    def __init__(self, ads, positive_pin, gain):
        self._ads = ads
        self._pin_setting = positive_pin
        self._gain = gain

    @property
    def value(self):
        """Returns the value of an ADC pin as an integer."""
        return random.randint(0, 32767)

# This is the code that is run when the program is loaded.
# If the module were to be imported, the code inside the if statement would not run.
if __name__ == "__main__":
    # Warning that logger will not work
    print("\nWARNING - This script cannot be run directly."
          "\nPlease run 'main.py' to start the logger, or use the desktop icon.\n")
    # Script will exit
