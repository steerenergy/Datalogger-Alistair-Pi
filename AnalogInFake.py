# NOTE - DELETE/Rename WHEN RUNNING ON PI!
# This script is for testing code when the pi isn't available
# It will simply return a number regardless of the pin
import time
import random




class AnalogIn:

    def __init__(self, ads, positive_pin, negative_pin=None):
        """AnalogIn
        :param ads: The ads object.
        :param ~digitalio.DigitalInOut positive_pin: Required pin for single-ended.
        :param ~digitalio.DigitalInOut negative_pin: Optional pin for differential reads.
        """
        self._ads = ads
        self._pin_setting = positive_pin
        self._negative_pin = negative_pin
        self.is_differential = False

    def value(self):
        time.sleep(0.005)
        # return "P:{} N{}".format(pin, x)
        return random.randint(0, 32767)
