# NOTE - TESTING PURPOSES ONlY
# This script is for testing code when the pi isn't available

# Pins
P0 = 0
P1 = 1
P2 = 2
P3 = 3


class ADS1115:
    """Base functionality for ADS1x15 analog to digital converters."""

    def __init__(
        self,
        i2c,
        gain=1,
        data_rate=None,
        mode=0x0000,
        address=0x48,
    ):
        # pylint: disable=too-many-arguments
        self._last_pin_read = None
        self.buf = bytearray(3)
        self._data_rate = self._gain = self._mode = None
        self.gain = gain
        self.data_rate = data_rate
        self.mode = mode
        self.i2c_device = (i2c, address)


class Mode:
    """An enum-like class representing possible ADC operating modes."""

    # See datasheet "Operating Modes" section
    # values here are masks for setting MODE bit in Config Register
    # pylint: disable=too-few-public-methods
    CONTINUOUS = 0x0000
    SINGLE = 0x0100

# This is the code that is run when the program is loaded.
# If the module were to be imported, the code inside the if statement would not run.
if __name__ == "__main__":
    # Warning that logger will not work
    print("\nWARNING - This script cannot be run directly."
          "\nPlease run 'main.py' to start the logger, or use the desktop icon.\n")
    # Script will exit
