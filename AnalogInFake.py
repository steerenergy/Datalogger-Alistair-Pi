# SPDX-FileCopyrightText: 2018 Carter Nelson for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`analog_in`
==============================
AnalogIn for single-ended and
differential ADC readings.
* Author(s): Carter Nelson, adapted from MCP3xxx original by Brent Rubell
"""

import random
import time

_ADS1X15_DIFF_CHANNELS = {(0, 1): 0, (0, 3): 1, (1, 3): 2, (2, 3): 3}
_ADS1X15_PGA_RANGE = {2 / 3: 6.144, 1: 4.096, 2: 2.048, 4: 1.024, 8: 0.512, 16: 0.256}


class AnalogIn:
    """AnalogIn Mock Implementation for ADC Reads."""

    def __init__(self, ads, positive_pin,gain):
        """AnalogIn
        :param ads: The ads object.
        :param ~digitalio.DigitalInOut positive_pin: Required pin for single-ended.
        :param ~digitalio.DigitalInOut negative_pin: Optional pin for differential reads.
        """
        self._ads = ads
        self._pin_setting = positive_pin
        self._gain = gain

    @property
    def value(self):
        """Returns the value of an ADC pin as an integer."""
        return random.randint(0, 32767)