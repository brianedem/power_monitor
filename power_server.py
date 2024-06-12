# This file is to be writen to the Raspberry Pi Pico W as main.py
from machine import Pin
from machine import UART
from machine import ADC
import struct
import time

# set up the LED and define routine to toggle
led = Pin("LED", Pin.OUT)
def toggleLED() :
    led.value(not led.value())

# disable the default pull-down on IO pad used for ADC0
from micropython import const
PADS_GPIO26 = const(0x4001c06c)
from machine import mem32
mem32[PADS_GPIO26] = mem32[PADS_GPIO26] & 0xfffffff3

# set up ADC channel 0 to monitor temperature
# The NTC temperature sensor forms part of a resistive divider
# feeding ADC channel 0. NTC is lower resistor of the divider,
# while a fixed resistor matching the NTC Ro, connected to
# the ADC reference is used for the upper resistor
ntc_temp = ADC(0)
ntc_beta = 3984             # from the NTC datasheet

# routine to convert ADC reading to temperature
# using simplified Steinhart-Hart equation
from math import log
def readTemperature(channel) :
        # calculate the resistor ratio from the ADC reading
    reading = channel.read_u16()
    maxReading = 0xFFFF
    RoverR0 = 1.0/(float(maxReading) / float(reading) - 1.0)

    zeroC = 273.15          # 0 degrees C in Kelvin
    T0 = zeroC + 25.0       # reference point temperature

    temp_K = 1.0 / (1.0/T0 + log(RoverR0)/ntc_beta)
    temp_C = temp_K - zeroC
    F = 1.8*temp_C + 32
    return temp_C


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

           
import network
from time import sleep
import socket

import ujson as json
hostname = None
try:
    with open('passwords.json', 'r') as f:
        data = json.load(f)
        ssid = data['ssid']
        password = data['password']
        if 'hostname' in data :
            hostname = data['hostname']
        else :
            hostname = ''
        print('file read: ssid={}, password={}, hostname={}'.format(ssid, password, hostname))
except:
    print("Error - no password.json file found")
    while True :
        sleep(0.2)
        toggleLED()
def connectWifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    while wlan.isconnected() == False:
        print('Waiting for connection...')
        toggleLED()
        sleep(1)
    led.on()
    ip_addr = wlan.ifconfig()[0]
    print(f'WiFi connected')
    print(f'IP address {ip_addr}')
    print(f'Monitoring {hostname}')
    mac = wlan.config('mac')
    ma = f'{mac[0]:02x}:{mac[1]:02x}:{mac[2]:02x}:{mac[3]:02x}:{mac[4]:02x}:{mac[5]:02x}'
    return (ip_addr, ma)

def open_server(ip):
    address = (ip, 80)
    s = socket.socket()
    s.bind(address)
    s.listen(5)
    return s

try:
    network_ip, mac_address = connectWifi()
    server = open_server(network_ip)
except KeyboardInterrupt:
    machine.reset()

print(mac_address)

m_format = """
Energy  = {0:10.1f} {1}
Voltage = {2:10.1f} {3}
Power   = {4:10.1f} {5}
Current = {6:10.1f} {7}
Temp    = {10:10.1f} C
"""
html = """<!DOCTYPE html>
<html>
    <head> <title>Pico W Power Monitor</title> </head>
    <body> <h1>Pico W {9} Power Monitor</h1>
        <pre style="font-size:4vw;">
MAC Address: {8}
""" + m_format + """
        </pre>
    </body>
</html>
"""
html_error = """<!DOCTYPE html>
<html>
    <head> <title>Pico W Power Monitor</title> </head>
    <body> <h1>Pico W Power Monitor {1} {0}</h1>
        <p style="font-size:4vw;">
            Error - Power meter hardware not responding
        </p>
    </body>
</html>
"""

meter = powerMeter()
v=meter.read_all(units=True)
tempC = readTemperature(ntc_temp)

if v is None :
    print(html_error.format(mac_address, hostname))
else :
    print(v)
    print(m_format.format(
        v['energy'][0],v['energy'][1],
        v['voltage'][0],v['voltage'][1],
        v['power'][0],v['power'][1],
        v['current'][0],v['current'][1],
        mac_address, hostname, tempC))

errorMessages = {
    400:'Bad Request',
    404:'Not Found',
    405:'Method Not Allowed'
    }
def respondError(cl, code, explain=None):
    cl.send(f'HTTP/1.0 {code} {errorMessages[code]}\r\nContent-type: text/html\r\n\r\n')
    if explain :
        cl.send(f'<!DOCTYPE html><html><head><title>{errorMessages[code]}</title></head>'+
                f'<body><center><h1>{explain}</h1></center></body></html>\r\n')
    return
def processRequest(cl, request):
    print(request)
    try :
        header, body = request.split(b'\r\n\r\n', 1)
    except ValueError :
        respondError(cl,400, 'Unable to detect blank line separating header from body')
        return
    headerLines = header.splitlines()
    firstHeaderLine = headerLines[0].split()
    if len(firstHeaderLine) != 3 :
        respondError(cl,400, 'Missing request parameter')
        return
    (method, target, version) = firstHeaderLine
    if method != b'GET' :
        respondError(cl,405, 'Only GET method supported')		# Method not supported
        return
    if target == b'/' or target == b'/index.html' :
        v = meter.read_all(units=True)
        tempC = readTemperature(ntc_temp)

        cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
        if v is None :
            cl.send(html_error.format(mac_address, hostname))
        else :
            cl.send(html.format(
                v['energy'][0],v['energy'][1],
                v['voltage'][0],v['voltage'][1],
                v['power'][0],v['power'][1],
                v['current'][0],v['current'][1],
                mac_address, hostname, tempC))
        
    elif target == b'/data.json' :
        cl.send('HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n')
        v = meter.read_all()
        tempC = readTemperature(ntc_temp)
        if v is None :
            cl.send(json.dumps({}))
        else :
            if hostname :
                v['hostname'] = hostname
            v['temperature'] = tempC
            cl.send(json.dumps(v))
    else :
        request = request.decode()
        print(request, firstHeaderLine)
        respondError(cl,404, 'File not found')

while True:
    try :
        cl, addr = server.accept()
    except OSError as e:
        print(f'Connection accept() error: {e}')
        continue
    print('client connected from', addr)
    cl.settimeout(5)    # LG WebTV opens connection without sending request
    try :
        request = cl.recv(1024)
    except OSError as e:
        print(f'Connection timeout - closing; {e}')
    else :
        processRequest(cl, request)
    finally :
        cl.close()
