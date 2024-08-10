# This file is to be writen to the Raspberry Pi Pico W as main.py
from machine import Pin
import mlogging as logging
import ntc_temp
from ble_uart_peripheral import BLEUART
import time

import lan
import ujson as json
import socket
import select
import peacefair
import line_edit
import config
import _version

    # rough sense of time for uptime reporting
pollTimeoutMs = 100   # 100ms polling
loops = 0

# set up the LED and define routine to toggle
led = Pin('LED', Pin.OUT)
def toggleLED() :
    led.value(not led.value())

# set up logging
logging.basicConfig(logging.DEBUG)
log = logging.getLogger()

# read configuration data from configuration file
config_file = 'config.json'
#config_file = 'passwords.json'
configuration = config.config(config_file)

    # temperature monitoring
# to reduce sampling noise make continous measurements over time
# if all async events can not be polled consider running
# this in _thread.start_new_thread()
thermometer = ntc_temp.thermometer(configuration)

'''
config_file = 'passwords.json'
hostname = None
ssid = None
password = None
try:
    with open(config_file, 'r') as f:
        config_data = json.load(f)
        ssid = config_data['ssid']
        password = config_data['password']
        if 'hostname' in config_data :
            hostname = config_data['hostname']
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
'''

    # activate bluetooth interface
buart = BLEUART(name=configuration.hostname)
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
wifi = lan.lan(configuration.hostname)
wifi.wifi_connect(configuration.ssid, configuration.password)
while wifi.wlan.isconnected() == False:
    log.debug('Waiting for connection...')
    toggleLED()
    time.sleep(1)
led.on()
log.debug(f"wifi rssi: {wifi.wlan.status('rssi')}")
network_ip = wifi.wlan.ifconfig()[0]
log.debug(f'WiFi connected')
log.debug(f'IP address {network_ip}')
log.debug(f'Monitoring {configuration.hostname}')
mac = wifi.wlan.config('mac')
mac_address = mac.hex(':')

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
        mac_address, configuration.hostname, tempC))

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
                mac_address, configuration.hostname, tempC))
        else :
            cl.send(html.format(
                v['energy'][0],v['energy'][1],
                v['voltage'][0],v['voltage'][1],
                v['power'][0],v['power'][1],
                v['current'][0],v['current'][1],
                mac_address, configuration.hostname, tempC))
        
    elif target == b'/data.json' :
        cl.send('HTTP/1.0 200 OK\r\nContent-type: application/json\r\n\r\n')
        v = power_meter.read_all()
        tempC = thermometer.readTemperature()
        if v is None :
            v = {}
        if configuration.hostname :
            v['hostname'] = configuration.hostname
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

x = (
    (('show', 'temp'), (f'Temperature = {thermometer.readTemperature()}, loops = {loops}')),
    (('scan', 'wifi'), wifi),
#   (('set', 'beta', '<integer'>), beta.set),
#   (('set', 'wifi', '<string>', '<string>'), wifi.set),
)

# The console IO is not buffered so polling is triggered on the first charactor
def process_command(command):
    result = []
    tokens = command.split()
    num_tokens = len(tokens)
    if tokens[0].startswith('sh') :     #show
        if num_tokens==1:
            result.append(f'show options:')
            result.append(f' configuration')
            result.append(f' log')
            result.append(f' status')
            result.append(f' temperature')
        elif tokens[1].startswith('conf'):      #config
            result = configuration.show()
        elif tokens[1].startswith('log') :      #log
            result.append(f'Log:')
            for m in log.show() :
                result.append( f' {m}')
        elif tokens[1].startswith('stat') :     #stat
            result.append(f'web requests serviced = {request_count}')
            uptime = int(loops*pollTimeoutMs/1000)
            days = uptime//(24*60*60)
            uptime -= days*24*60*60
            hours = uptime//(60*60)
            uptime -= hours*60*60
            minutes = uptime//60
            uptime -= minutes*60
            seconds = uptime

            if days!=0 :
                result.append(f'uptime: {days} days, {hours} hours, {minutes} minutes')
            elif hours!=0 :
                result.append(f'uptime: {hours} hours, {minutes} minutes')
            else :
                result.append(f'uptime: {minutes} minutes, {seconds} seconds')
        elif tokens[1].startswith('temp') :     #temperature
            result.append(f'Temperature = {thermometer.readTemperature()}, loops = {loops}')
        elif tokens[1].startswith('ver') :      #version
            result.append(f'Version {_version.version}')
            result.append(f'Date {_version.releaseDate}')
            result.append(f'HEAD {_version.gitRevision}')
        elif tokens[1].startswith('peace') :    # peacefair response
            if power_meter.response is None :
                result.append(f'no peacefair response available')
            else :
                result.append(f'last peacefair response: {power_meter.response.hex()}')
        else :
            result.append(f'Error - unknown show object {tokens[1]}')

    elif tokens[0] == 'set':
        if num_tokens==1:
            result.append(f'set options:')
            result.append(f' beta <value>')
            result.append(f' wifi <ssid> <password>')
        elif num_tokens==2:
            result.append(f'set {tokens[1]} requires a parameter')
        elif num_tokens==3:
            if tokens[1]=='beta' :
                configuration.set('beta', tokens[2])
            elif tokens[1]=='hostname' :
                configuration.set('hostname', tokens[2])
        elif num_tokens==4:
            if tokens[1]=='wifi' :
                configuration.set('ssid', tokens[2])
                configuration.set('password', tokens[3])
                wifi.wifi_connect(tokens[2], tokens[3])
            
    elif tokens[0] == 'scan':
        if num_tokens==1:
            result.append(f'scan options:')
            result.append(f' wifi')
        elif 'wifi' in tokens[1]:
            result = wifi.wifi_scan()

    elif tokens[0] == 'save':
        if num_tokens==1:
            result.append(f'save options:')
            result.append(f' config')
        elif tokens[1]=='config' :
            configuration.save()

    else :
        result.append(f'unimplemented command {command}')

    return result
    
    # this loop operates on a 100ms tick
while True:
        # update temperature measurement filter
    thermometer.readADC()

        # check and service console and/or web server
    events = poller.poll(pollTimeoutMs)   # timeout generates empty list
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
