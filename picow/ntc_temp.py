from machine import ADC
from micropython import const
from machine import mem32
from math import log

_maxReading = 0xFFFF        # this could be increased to reflect voltage drop to ADC
_zeroC = 273.15             # 0 degrees C in Kelvin
_T0 = _zeroC + 25.0         # reference point temperature
_ntc_beta = 3984            # from the NTC datasheet
_mu = 4                     # low-pass filter coefficient (2^-_mu)

class thermometer:
    def __init__(self):
            # set up ADC channel 0 to monitor temperature
            # disable the default pull-down on IO pad used for ADC0
        PADS_GPIO26 = const(0x4001c06c)
        mem32[PADS_GPIO26] = mem32[PADS_GPIO26] & 0xfffffff3

            # The NTC temperature sensor forms part of a resistive divider
            # that feeds the ADC input. The NTC is lower resistor of the divider
            # while the upper is a fixed value matching the NTC Ro connected
            # to the ADC reference voltage.
        self.temp_adc = ADC(0)

            # The ADC has noise that causes the temperature reading to bounce around
            # average_adc holds U16.16 value
        self.average_adc = self.temp_adc.read_u16() << 16

    def readADC(self) :     # IIR filter
        self.average_adc += ((self.temp_adc.read_u16()<<16)-self.average_adc) >> _mu
        return (self.average_adc+0x7fff)>>16

    # routine to convert ADC reading to temperature
    # using simplified Steinhart-Hart equation
    def readTemperature(self) :
            # calculate the resistor ratio from the ADC reading
#       reading = self.temp_adc.read_u16()
#       R_overR0 = 1.0/(float(_maxReading) / float(reading) - 1.0)
        R_overR0 = 1.0/(float(_maxReading) / float(self.readADC()) - 1.0)

        temp_K = 1.0 / (1.0/_T0 + log(R_overR0)/_ntc_beta)
        temp_C = temp_K - _zeroC
        F = 1.8*temp_C + 32
        return temp_C
