# This file is to be writen to the Raspberry Pi Pico W as main.py
import machine
import select
import time
import socket
import errno
import select
import sys

from ble_uart_peripheral import BLEUART
import ujson as json

import mlogging as logging
import ntc_temp

import lan
import peacefair
import line_edit
import config
import _version

    # rough sense of time for uptime reporting
pollTimeoutMs = 100   # 100ms polling
loops = 0

# set up the LED and define routine to toggle
led = machine.Pin('LED', machine.Pin.OUT)
def toggleLED() :
    led.value(not led.value())

# set up logging
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger()

# read configuration data from configuration file
config_file = 'config.json'
configuration = config.config(config_file)

    # set up temperature monitoring
thermometer = ntc_temp.thermometer(configuration)

    # set up access to the power meter
power_meter = peacefair.powerMeter()

    # activate bluetooth interface
buart = BLEUART(name=configuration.hostname)

def on_rx():
    command = buart.read().decode().strip()
    log.debug(f'bluetooth rx: {command}')
    result = process_command(command)
    for line in result:
        buart.write(line+'\n')

buart.irq(handler=on_rx)

# The console IO is not buffered so polling is triggered on the first charactor
def process_command(command):
    result = []
    tokens = command.split()
    num_tokens = len(tokens)
    if num_tokens == 0:
        return []
    if tokens[0].startswith('sh') :     #show
        if num_tokens==1:
            result.append(f'show options:')
            result.append(f' configuration')
            result.append(f' log')
            result.append(f' peacefair')
            result.append(f' status')
            result.append(f' temperature')
            result.append(f' version')
        elif tokens[1].startswith('conf'):      #config
            result = configuration.show()
        elif tokens[1].startswith('log') :      #log
            result.append(f'Log:')
            for m in log.show() :
                result.append( f' {m}')
        elif tokens[1].startswith('peace') :    # peacefair response
            if power_meter.response is None :
                result.append(f'no peacefair response available')
            else :
                result.append(f'last peacefair response: {power_meter.response.hex()}')
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
        else :
            result.append(f'Error - unknown show object {tokens[1]}')

    elif tokens[0] == 'set':
        if num_tokens==1:
            result.append(f'set options:')
            result.append(f' beta <value>')
        elif num_tokens==2:
            result.append(f'set {tokens[1]} requires a parameter')
        elif num_tokens==3:
            if tokens[1]=='beta' :
                value = tokens[2]
                if not value.isdigit() :
                    result.append(f'Error - beta values must be numeric')
                else :
                    configuration.set('beta', int(value))
            elif tokens[1]=='hostname' :
                hostname = tokens[2]
                if hostname.startswith('-') or hostname.endswith('-') :
                    result.append(f'Error - hostname must not start or end with hyphen')
                elif hostname.count('-') > 1 :
                    result.append(f'Error - hostname may have at most one hyphen')
                elif not hostname[0].isalpha() :
                    result.append(f'Error - hostname must start with a letter')
                else :      # no isalnum() - have to check each charactor
                    for c in ''.join(hostname.split('-')) :
                        if not c.isalpha() and not c.isdigit() :
                            result.append(f"Error - the charactor '{c}' is not allowed in hostname")
                            break;
                if result==[] :     # no result implies no errors, so safe to set hostname
                    configuration.set('hostname', hostname)
            else :
                result.append(f'Error - unknown set object {tokens[1]}')
        else :
            result.append(f'Error - excessive number of parameters for set command')
            
    elif tokens[0] == 'save':
        if num_tokens==1:
            result.append(f'save options:')
            result.append(f' config')
        elif tokens[1]=='config' :
            configuration.save()

    elif tokens[0] == 'wifi':
        if num_tokens==1 :
            result.append(f'wifi options:')
            result.append(f' connect <net_number> <password>')
            result.append(f' networks')
            result.append(f' passwords')
            result.append(f' status')
        elif num_tokens==2 :
            if tokens[1].startswith('net'):     #networks
                result = wifi.wifi_list()
            elif tokens[1].startswith('pas'):   #passwords
                result.append(f'Known networks')
                password_list = configuration.wifi
                networks = list(password_list)
                for i in range(len(networks)) :
                    network = networks[i]
                    password = password_list[network]
                    result.append(f' {i} {network} {password}')
            elif tokens[1].startswith('stat'):  #status
                result = wifi.status()
        elif num_tokens==4:
            if tokens[1].startswith('con') :    #connect
                index, password = tokens[2:4]
                network = wifi.ap_list[int(index)]
                ssid = network[0]

                configuration.wifi[ssid] = password
#               wifi.wifi_connect(tokens[2], tokens[3])

    else :
        result.append(f'Unimplemented command {command}')
        result.append(f'Available commands are:')
        result.append(f' show')
        result.append(f' save')
        result.append(f' set')
        result.append(f' wifi')

    return result

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
                wifi.mac_address, configuration.hostname, tempC))
        else :
            cl.send(html.format(
                v['energy'][0],v['energy'][1],
                v['voltage'][0],v['voltage'][1],
                v['power'][0],v['power'][1],
                v['current'][0],v['current'][1],
                wifi.mac_address, configuration.hostname, tempC))
        
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

    # set up polling for USB console
poller = select.poll()
poller.register(sys.stdin, select.POLLIN)

    # initialize the wifi interface
wifi = lan.lan(configuration.hostname)

    # connect to the wifi
wifi.wifi_connect(configuration.wifi)

server = None
request_count = 0

    # this loop operates on a 100ms tick managed by the poller timeout
while True:
        # update temperature measurement filter
    thermometer.readADC()

        # set up the server socket when the network comes up
    if server is None :
        if wifi.wlan.isconnected() :
            ip_address = wifi.wlan.ifconfig()[0]
            address = (ip_address, 80)
            server = socket.socket()
            server.bind(address)
            server.listen(5)
            server.setblocking(False)
            poller.register(server, select.POLLIN)
            log.info(f'Server is listening on {ip_address}:80')
            led.on()
        else :
            toggleLED()

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
        else :
            print(f'unknown fd {fd}')
