from machine import ADC
from micropython import const
from machine import mem32
from math import log

_maxReading = 0xFFFF
_zeroC = 273.15          # 0 degrees C in Kelvin
_T0 = _zeroC + 25.0       # reference point temperature
_ntc_beta = 3984             # from the NTC datasheet

class thermometer:
    def __init__(self):
            # disable the default pull-down on IO pad used for ADC0
        PADS_GPIO26 = const(0x4001c06c)
        mem32[PADS_GPIO26] = mem32[PADS_GPIO26] & 0xfffffff3

            # set up ADC channel 0 to monitor temperature
            # The NTC temperature sensor forms part of a resistive divider
            # feeding ADC channel 0. NTC is lower resistor of the divider,
            # while a fixed resistor matching the NTC Ro, connected to
            # the ADC reference is used for the upper resistor
        self.temp_adc = ADC(0)

    # routine to convert ADC reading to temperature
    # using simplified Steinhart-Hart equation
    def readTemperature(self) :
            # calculate the resistor ratio from the ADC reading
        reading = self.temp_adc.read_u16()
        R_overR0 = 1.0/(float(_maxReading) / float(reading) - 1.0)


        temp_K = 1.0 / (1.0/_T0 + log(R_overR0)/_ntc_beta)
        temp_C = temp_K - _zeroC
        F = 1.8*temp_C + 32
        return temp_C
