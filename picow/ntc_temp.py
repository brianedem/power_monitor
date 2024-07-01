from machine import ADC
from micropython import const
from machine import mem32
from math import log

class thermometer:
    def _init_(self):
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
    def readTemperature() :
            # calculate the resistor ratio from the ADC reading
        reading = temp_adc.read_u16()
        maxReading = 0xFFFF
        R_overR0 = 1.0/(float(maxReading) / float(reading) - 1.0)

        zeroC = 273.15          # 0 degrees C in Kelvin
        T0 = zeroC + 25.0       # reference point temperature
        ntc_beta = 3984             # from the NTC datasheet

        temp_K = 1.0 / (1.0/T0 + log(R_overR0)/ntc_beta)
        temp_C = temp_K - zeroC
        F = 1.8*temp_C + 32
        return temp_C
