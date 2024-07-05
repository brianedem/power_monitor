from machine import ADC
from machine import mem32
from machine import Pin

_messages = []

# determine if the USB is connected or able to accept additional output data
# Method 1 - look for power on USB interface
    # WL_GPIO2 monitors VBUS (USB power)
_VBUS = Pin('WL_GPIO2', Pin.IN)
_usb_connected = _VBUS.value()

# Method 2 - use uselect.poll() on the output stream?

# Method 3 - look at hardware status bits?:
'''
SIE_STATUS=const(0x50110000+0x50)
CONNECTED=const(1<<16)
SUSPENDED=const(1<<4)
if (machine.mem32[SIE_STATUS] & (CONNECTED | SUSPENDED))==CONNECTED:
  print('....,')
'''

# micropython does provide a logging library that probably could be used
# in place of this by writing a stream handler that provides the added
# functionaly and replacing the default handler by calling logging.basicConfig(stream=<new_handler>)
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

class getLogger() :
    def __init__(self, name, level=NOTSET) :
        self.name = name
        self.level = level

    def basicConfig(self, level=INFO):
        self.level = _checkLevel(level)

    def clear(self):
        _messages.clear()

    def show(self):
#       m = ''
#       for l in _messages:
#           m += l
#       return m
        return _messages

    def log(self, level, message):
        if level >= self.level :
            m = f'{_levelToName[level]}:{self.name}:{message}'
            if _console:
                print(m)
            _messages.append(m)
            if len(_messages) > 20:
                _messages.pop(0)

    def critical(self,message):
        self.log(CRITICAL, message)

    def error(self,message):
        self.log(ERROR, message)

    def warning(self,message):
        self.log(WARNING, message)

    def info(self,message):
        self.log(INFO, message)

    def debug(self,message):
        self.log(DEBUG, message)
