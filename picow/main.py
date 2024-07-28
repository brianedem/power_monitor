# This file is to be writen to the Raspberry Pi Pico W as main.py
from machine import Pin
import mlogging as logging
import ntc_temp
from ble_uart_peripheral import BLEUART
import ujson as json
from time import sleep

import network
import socket
import select
import peacefair
import line_edit

# set up the LED and define routine to toggle
led = Pin('LED', Pin.OUT)
def toggleLED() :
    led.value(not led.value())

# set up logging
log = logging.getLogger('main')
log.basicConfig(logging.DEBUG)

    # temperature monitoring
# to reduce sampling noise make continous measurements over time
# if all async events can not be polled consider running
# this in _thread.start_new_thread()
thermometer = ntc_temp.thermometer()

# read configuration data from configuration file
config_file = 'passwords.json'
hostname = None
ssid = None
password = None
try:
    with open(config_file, 'r') as f:
        data = json.load(f)
        ssid = data['ssid']
        password = data['password']
        if 'hostname' in data :
            hostname = data['hostname']
        else :
            hostname = ''
        log.debug(f'file read: ssid={ssid}, password={password}, hostname={hostname}')
except OSError:
    log.error(f'No {config_file} file found')
    while True :
        sleep(0.2)
        toggleLED()
except ValueError:
    log.error('{config_file} does not have a valid json format')
except KeyError as key:
    log.error('No {key} found in file')


    # activate bluetooth interface
buart = BLEUART(name=hostname)
# possible commands:
#  show ap                      - shows available wifi access points
#  set ap <ssid> <password>     - stores ssid and password in file; connects to ap
#  show hostname
#  set hostname <name>
#  show log                     - dumps last 20 log entries
#  set loglevel <level>         - sets the logging level
#  
def on_rx():
    command = buart.read().decode().strip()
    log.debug(f'bluetooth rx: {command}')
    result = process_command(command)
    for line in result:
        buart.write(line+'\n')

buart.irq(handler=on_rx)

    # connect to the wifi
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
network_ip = wlan.ifconfig()[0]
log.debug(f'WiFi connected')
log.debug(f'IP address {network_ip}')
log.debug(f'Monitoring {hostname}')
mac = wlan.config('mac')
mac_address = f'{mac[0]:02x}:{mac[1]:02x}:{mac[2]:02x}:{mac[3]:02x}:{mac[4]:02x}:{mac[5]:02x}'

def open_server(ip):
    address = (ip, 80)
    s = socket.socket()
    s.bind(address)
    s.listen(5)
    return s

try:
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
    <body> <h1>Pico W {1} Power Monitor</h1>
        <pre style="font-size:3vw;">
MAC Address: {0}
Error - Power meter hardware not responding
Temp    = {2:10.1f} C
        </pre>
    </body>
</html>
"""

power_meter = peacefair.powerMeter()
v=power_meter.read_all(units=True)
tempC = thermometer.readTemperature()

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
        tempC = thermometer.readTemperature()

        cl.send('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
        if v is None :
            cl.send(html_error.format(
                mac_address, hostname, tempC))
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
        tempC = thermometer.readTemperature()
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

# set up socket polling to service both USB console and web server
import select
import sys
poller = select.poll()
#server.settimeout(1)
server.setblocking(False)
poller.register(server, select.POLLIN)
poller.register(sys.stdin, select.POLLIN)

import errno

request_count = 0
loops = 0

# The console IO is not buffered so polling is triggered on the first charactor
def process_command(command):
    result = []
    if   'status' in command :
        result.append(f'request_count = {request_count}')
    elif 'log' in command :
        result.append(f'Log:')
        for m in log.show() :
            result.append( f' {m}')
    elif 'temp' in command:
        result.append(f'Temperature = {thermometer.readTemperature()}, loops = {loops}')
    else :
        result.append(f'unimplemented command {command}')

    return result
    
    # this loop operates on a 100ms tick
while True:
        # update temperature measurement filter
    thermometer.readADC()

        # check and service console and/or web server
    events = poller.poll(100)   # 100ms polling; timeout generates empty list
    loops += 1
    for fd, flag in events:
        if fd == sys.stdin :
#           print(f'{loops} loops')
            value = sys.stdin.read(1)
#           print(f'Got: {ord(value)}')
            command = line_edit.process_key(value)
            if command is not None:
                result = process_command(command)
                for line in result:
                    print(line)

        elif fd == server :
            request_count += 1
            try :
                cl, addr = server.accept()
            except OSError as e:
                if e.errno != errno.ETIMEDOUT:
                    log.error(f'Connection accept() error: {e}')
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
