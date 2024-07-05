# This file is to be writen to the Raspberry Pi Pico W as main.py
from machine import Pin
from machine import ADC
import mlogging as logging
import ntc_temp
import peacefair
import time

# set up the LED and define routine to toggle
led = Pin('LED', Pin.OUT)
def toggleLED() :
    led.value(not led.value())

log = logging.getLogger('main')
log.basicConfig(logging.DEBUG)

outside_thermometer = ntc_temp.thermometer()

           
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
        log.debug('file read: ssid={}, password={}, hostname={}'.format(ssid, password, hostname))
except:
    log.error('Error - no password.json file found')
    while True :
        sleep(0.2)
        toggleLED()

def connectWifi():
    network.hostname(hostname)
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(ssid, password)
    while wlan.isconnected() == False:
        log.debug('Waiting for connection...')
        toggleLED()
        sleep(1)
    led.on()
    log.debug(f"wifi rssi: {wlan.status('rssi')}")
    ip_addr = wlan.ifconfig()[0]
    log.debug(f'WiFi connected')
    log.debug(f'IP address {ip_addr}')
    log.debug(f'Monitoring {hostname}')
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

log.info(f'{mac_address}')

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

power_meter = peacefair.powerMeter()
v=power_meter.read_all(units=True)
tempC = outside_thermometer.readTemperature()

if v is None :
    log.error('Power meter hardware not responding')
else :
    log.debug(m_format.format(
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
    log.debug(request)
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
        v = power_meter.read_all(units=True)
        tempC = outside_thermometer.readTemperature()

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
        v = power_meter.read_all()
        tempC = outside_thermometer.readTemperature()
        if v is None :
            cl.send(json.dumps({}))
        else :
            if hostname :
                v['hostname'] = hostname
            v['temperature'] = tempC
            cl.send(json.dumps(v))
    else :
        request = request.decode()
        log.error(f'{request} {firstHeaderLine}')
        respondError(cl,404, 'File not found')

    # activate bluetooth interface
from ble_uart_peripheral import BLEUART

uart = BLEUART(name=hostname)
# possible commands:
#  show ap                      - shows available wifi access points
#  set ap <ssid> <password>     - stores ssid and password in file; connects to ap
#  show hostname
#  set hostname <name>
#  show log                     - dumps last 20 log entries
#  set loglevel <level>         - sets the logging level
#  
def on_rx():
    command = uart.read().decode().strip()
    log.debug(f'bluetooth rx: {command}')
    if 'status' in command :
        uart.write(f'request_count = {request_count}\n')
    elif 'log' in command :
        uart.write(f'Log:\n')
        for m in log.show() :
            uart.write(f' {m}\n')
    else :
        uart.write(f'unimplemented command {command}\n')

uart.irq(handler=on_rx)

request_count = 0
while True:
    try :
        cl, addr = server.accept()
    except OSError as e:
        log.error(f'Connection accept() error: {e}')
        request_count += 1
        continue
    log.debug(f'client connected from {addr}')
    cl.settimeout(5)    # LG WebTV opens connection without sending request
    try :
        request = cl.recv(1024)
    except OSError as e:
        log.error(f'Connection timeout - closing; {e}')
    else :
        processRequest(cl, request)
    finally :
        cl.close()
    request_count += 1
