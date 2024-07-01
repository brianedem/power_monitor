from machine import ADC

_messages = []

# determine if the USB is connected or able to accept additional output data
# Method 1 - look for power on USB interface
    # ADC(3) monitors VBUS (USB power) scaled by 50%
    # For VBUS=5V, ADC should report ((5*0.50)/3.3)*0x10000=0xC1F0
    # disable the default pull-down on IO pad used for ADC3
#PADS_GPIO26 = const(0x4001c06c)
PADS_GPIO29 = const(0x4001c078)
mem32[PADS_GPIO29] &= 0xfffffff3
_usb_connected = ADC(3).read_u16() > 0x8000 # threshold about 2/3 of expected value

# Method 2 - use uselect.poll() on the output stream?

# Method 3 - look at hardware status bits?:
'''
SIE_STATUS=const(0x50110000+0x50)
CONNECTED=const(1<<16)
SUSPENDED=const(1<<4)
if (machine.mem32[SIE_STATUS] & (CONNECTED | SUSPENDED))==CONNECTED:
  print('....,')
'''

_console = _usb_connected

CRITICAL = 50
ERROR = 40
WARNING = 30
INFO = 20
DEBUG = 10
NOTSET = 0

_levelToName = {
    CRITICAL: 'CRITICAL',
    ERROR: 'ERROR',
    WARNING: 'WARNING',
    INFO: 'INFO',
    DEBUG: 'DEBUG',
    NOTSET: 'NOTSET',
}
_nameToLevel = {
    'CRITICAL': CRITICAL,
    'ERROR': ERROR,
    'WARN': WARNING,
    'WARNING': WARNING,
    'INFO': INFO,
    'DEBUG': DEBUG,
    'NOTSET': NOTSET,
}

def _checkLevel(level):
    if isinstance(level, int):
        rv = level
    else :
        rv = _nameToLevel[level]
    return rv

class getLogger(self, name, level=NOTSET) :
    def __init__ :
        self.name = name
        self.level = level

    def basicConfig(level=INFO):
        self.level = _checkLevel(level)

    def clear(self):
        messages.clear()

    def show(self):
        m = ''
        for l in messages:
            m += l
        return m

    def log(self, level, message):
        if level >= self.level :
        m = f'{_levelToName[self.level]}:{self.name}:{message}'
        if _console:
            print(m)
        messages.append(m)
        if count(messages) > 20:
            messages.pop(0)

    def critical(self,message):
        log(CRITICAL, message)

    def error(self,message):
        log(ERROR, message)

    def warning(self,message):
        log(WARNING, message)

    def info(self,message):
        log(INFO, message)

    def debug(self,message):
        log(DEBUG, message)
