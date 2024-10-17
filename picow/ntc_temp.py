from machine import ADC, Pin
from micropython import const
from machine import mem32
import math
import mlogging as logging

log = logging.getLogger(__name__)

_maxReading = 0xFFFF        # this could be increased to reflect voltage drop to ADC
_zeroC = 273.15             # 0 degrees C in Kelvin
_T0 = _zeroC + 25.0         # reference point temperature
_mu = 4                     # low-pass filter coefficient (2^-_mu)
_ntc_beta = 3984            # from the NTC datasheet
_shorted = 0x1000
_open    = 0xF000

            # The NTC temperature sensor forms part of a resistive divider
            # that feeds the ADC input. The NTC is lower resistor of the divider
            # while the upper is a fixed value matching the NTC Ro connected
            # to the ADC reference voltage.
            #
            # The ADC has noise that causes the temperature reading to bounce around
            # adc_filter holds filtered value as U16.16

class thermometer:
    def __init__(self, config):
            # set up ADC channel 0 to monitor temperature
        self.temp_adc = ADC(Pin(26))

            # make measurement with internal pull-up enabled
        p = Pin(26, Pin.IN, Pin.PULL_UP)
        puv = self.temp_adc.read_u16()

            # make measurement with internal pull-down enabled
        p = Pin(26, Pin.IN, Pin.PULL_DOWN)
        pdv = self.temp_adc.read_u16()

        if puv < _shorted :
            self.status = 'NTC shorted'
        elif pdv < _shorted :
            self.status = 'missing pull-up'
        elif puv > _open :
            self.status = 'NTC open'
        else :
            self.status = 'OK'

        if self.status != 'OK' :
            log.warning(self.status)

            # remove pull-down
        p = Pin(26, Pin.IN)

        if self.status == 'OK' :
            self.adc_filter = self.temp_adc.read_u16() << 16
        else :
            self.adc_filter = 0x8000 << 16     # 25C value

        if hasattr(config, 'beta') :
            self.beta = int(config.beta)
        else :
            self.beta = _ntc_beta
            log.warning('using default value for temperature probe beta')

        # reads ADC and updates IIR filter if sensor functional
    def readADC(self) :
        if self.status == 'missing pull-up' :
            return

        value = self.temp_adc.read_u16()

            # check for bad sensor
        if value < _shorted :
            self.status = 'NTC shorted'
            log.warning(self.status)
        elif value > _open :
            self.status = 'NTC open'
            log.warning(self.status)
        else :
            self.status = 'OK'
        
            # add measurementy to filter
        self.adc_filter += ((value<<16)-self.adc_filter) >> _mu

    # routine to convert ADC reading to temperature
    # using simplified Steinhart-Hart equation
    def readTemperature(self) :
            # check for broken sensor
        if self.status != 'OK':
            return None

            # calculate the resistor ratio from the ADC reading
        adc_reading = (self.adc_filter+0x7fff)>>16
        R_overR0 = 1.0/(float(_maxReading) / float(adc_reading) - 1.0)

        temp_K = 1.0 / (1.0/_T0 + math.log(R_overR0)/_ntc_beta)
        temp_C = temp_K - _zeroC
        F = 1.8*temp_C + 32
        return temp_C
