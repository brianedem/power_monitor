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
    if 'status' in command :
        buart.write(f'request_count = {request_count}\n')
    elif 'log' in command :
        buart.write(f'Log:\n')
        for m in log.show() :
            buart.write(f' {m}\n')
    else :
        buart.write(f'unimplemented command {command}\n')

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
    <body> <h1>Pico W Power Monitor {1} {0}</h1>
        <p style="font-size:4vw;">
            Error - Power meter hardware not responding
        </p>
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
# Implement a line buffer to collect keystrokes and handle backspace/delete
console_command = ''
csi_state = None
vt_key_code = ''
ESC = '\033'
ESC_MESSAGE = '<ESC>'

def process_console(key_value) :
    global csi_state
    global console_command
    if csi_state is not None :
        if csi_state == '': # == ESC      # have seen ESC, process second charactor
            if key_value == '[':            # expected value; consume for now
                csi_state = '['
                return
            else :                          # unexpected value, process normally
                pass

        elif csi_state[0] == '[':           # collecting CSI printable charactors
            if key_value.isdigit() :        #  all decimal digits after bracket
                csi_state += key_value
                return
            elif key_value == '~':          #  terminator of the digits (and CSI sequence)
                if csi_state == '[3':       #     VT-100 delete key
                    key_value = '\b'        #         remap to backspace code
                    csi_state = None
                else :
                    pass
            else :                          # unexpected value
                pass

        # if csi_state has a value at this point CSI processing was aborted
        if csi_state is not None:
            text = ESC_MESSAGE + csi_state
            console_command += text
            sys.stdout.write(text)
            csi_state = None

    if key_value == ESC:
        csi_state = ''  # indicates that ESC has been received
        return

        # process the command here? Maybe return the command?
    if key_value == '\n':
        print(f'\nCommand: {console_command}')
        console_command = ''
        return

    if key_value==chr(127) or key_value=='\b':
        if len(console_command) > 0 :
            console_command = console_command[:-1]
            sys.stdout.write('\b \b')
        return

        # no special processing - just collect and echo
    console_command += key_value
    sys.stdout.write(key_value)

while True:
# make a temperature measurement

        # check and service console and/or web server
    events = poller.poll(100)   # 100ms polling; timeout generates empty list
    loops += 1
    for fd, flag in events:
        if fd == sys.stdin :
#           print(f'{loops} loops')
            value = sys.stdin.read(1)
#           print(f'Got: {ord(value)}')
            process_console(value)

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

while True:
    try :
        cl, addr = server.accept()
    except OSError as e:
        if e.errno != errno.ETIMEDOUT:
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
