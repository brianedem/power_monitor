from machine import UART
from machine import Pin
import struct

def crc16(data) :
    crc = 0xFFFF
    for d in data :
        crc ^= d
        for i in range(8) :
            if crc&0x0001 : crc ^= 0xA001<<1
            crc >>= 1
    return struct.pack('H',crc)

    # modbus registers are 16-bit so 32-bit measurements require two registers
registers = {
# address: (width, scaling, name, units)
        0: (1, 0.1,     'voltage', 'V'),
        1: (2, 0.001,   'current', 'A'),
        3: (2, 0.1,     'power',   'W'),
        5: (2, 0.001,   'energy', 'kWh'),
        7: (1, 0.1,     'frequency', 'Hz'),
        8: (1, 0.01,    'powerFactor', ''),
        9: (1, 1,       'powerAlarm', ''),
        }

class powerMeter:
    def __init__(self):
        self.uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1),timeout=200)

    def read_all(self, units=False) :
        request = struct.pack('>2B2H', 0x01, 0x04, 0, 10)
        request += crc16(request)

#       print (request)
        self.uart.write(request)
        response = self.uart.read(25)
        if response and len(response) is 25 :
                # first three bytes of response - dev addr, request, length
            values = struct.unpack('>11H', response[3:])  # 11 16-bit shorts, big endian
            meter_values = {}
            for i in range(len(values)) :
                if i in registers :
                    reg = registers[i]
                    value = 0
                    for s in range(reg[0]) :
                        value |= values[i+s] << (s*16)
                    if units :
                        meter_values[reg[2]] = (value*reg[1], reg[3])
                    else :
                        meter_values[reg[2]] = value*reg[1]
        else :
            meter_values = None
        return meter_values


