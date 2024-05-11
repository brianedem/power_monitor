from machine import Pin

led = Pin("LED", Pin.OUT)
led.on()
print(led.value())
def toggleLED() :
    led.value(not led.value())
    
from machine import UART
import struct
import time

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
        5: (2, 0.1,     'energy', 'Wh'),
        7: (1, 0.1,     'frequency', 'Hz'),
        8: (1, 0.1,     'powerFactor', ''),
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
                        value |= values[i+s] << s
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
try:
    with open('passwords.json', 'r') as f:
        data = json.load(f)
        ssid = data['ssid']
        password = data['password']
        print('file read: ssid={}, password={}'.format(ssid, password))
except:
    ssid = 'ArcadiaPalms'
    password = 'ranchomirage'
    print("no file found - using defaults")
def connectWifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    while wlan.isconnected() == False:
        print('Waiting for connection...')
        toggleLED()
        sleep(1)
    print('WiFi connected')
    led.on()
    mac = wlan.config('mac')
    mac = f'{mac[0]:02x}:{mac[1]:02x}:{mac[2]:02x}:{mac[3]:02x}:{mac[4]:02x}:{mac[5]:02x}'

    return (wlan.ifconfig()[0], mac)

def open_server(ip):
    address = (ip, 80)
    s = socket.socket()
    s.bind(address)
    s.listen(1)
    return s

try:
    network_ip, mac_address = connectWifi()
    server = open_server(network_ip)
except KeyboardInterrupt:
    machine.reset()

print(mac_address)

html = """<!DOCTYPE html>
<html>
    <head> <title>Pico W Power Monitor</title> </head>
    <body> <h1>Pico W Power Monitor {8}</h1>
        <pre>
Energy  = {0:10.1f} {1}
Voltage = {2:10.1f} {3}
Power   = {4:10.1f} {5}
Current = {6:10.1f} {7}
        </pre>
    </body>
</html>
"""
meter = powerMeter()
v=meter.read_all(units=True)
print(v)
print(html.format(
    v['energy'][0],v['energy'][1],
    v['voltage'][0],v['voltage'][1],
    v['power'][0],v['power'][1],
    v['current'][0],v['current'][1],
    mac_address))

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
        cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
        cl.send(html.format(
            v['energy'][0],v['energy'][1],
            v['voltage'][0],v['voltage'][1],
            v['power'][0],v['power'][1],
            v['current'][0],v['current'][1],
            mac_address))
        
    elif target == b'/data.json' :
        cl.send('HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n')
        cl.send(json.dumps(meter.read_all()))
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
    cl.settimeout(1)	# LG WebTV opens connection without sending request
    try :
        request = cl.recv(1024)
    except OSError as e:
        print(f'Connection timeout - closing; {e}')
    else :
        processRequest(cl, request)
    finally :
        cl.close()
