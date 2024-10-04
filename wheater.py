#!/usr/bin/python3
"""Heatpump Water Heater Monitor

This script monitors the power used by a water heater and infers its
current operating mode.

Notifications of on/off events are sent to ntfy.sh, and power consumption
for each cycle logged.

Daily readings of cumulative power consumption are also logged
"""
import logging
import requests
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json
import time
from enum import Enum
import random
import string

log = logging.getLogger(__name__)
logging.basicConfig(filename='wheater.log', encoding='utf-8', level=logging.WARN)

# the ntfy key is stored in a separate file for security
config_file = 'wheater.cfg'
try:
    fd = open(config_file)
    config_data = json.load(fd)
    ntfy_key = config_data['ntfy_key']
except FileNotFoundError:
    # generate a mostly random lower-case string (easy to enter on iphone)
    ntfy_key = 'wh' + ''.join(random.choices(string.ascii_lowercase, k=14))
    config_data = {'ntfy_key': ntfy_key}
    with open(config_file, mode='w', encoding='utf-8') as fd:
        print('creating config file')
        json.dump(config_data, fd)

print(f'using {ntfy_key} as nfty key')

device = 'waterheater.lan'

def pollDevice(dev) :
    """ Reads power information from picow + peacefair power meter
    """
    req = Request(f'http://{dev}/data.json')
    values = {}
    try:
        with urlopen(req) as response :
            content_type = response.getheader('Content-type')
            if 'json' in content_type :
                body = response.read()
                log.debug(body)
                values = json.loads(body)
            else :
                print('{dev}: json content not found')
                print(response.read())

    except HTTPError as e:
        log.exception(f'Request to {dev} {e.code}')
    except URLError as e:
        log.exception(f'Request to {dev} {e.reason}')
    except TimeoutError :
        log.exception(f'Request to {dev} timed out')

    return values

class State(Enum):
    STARTUP = 0
    IDLE = 2
    COMPRESSOR = 3
    RESISTIVE = 4

# send notifications when state changes

# at end of element interval, log to database:
#  element ID
#  start time
#  run-time in minutes
#  power used


prev_state = State.STARTUP
prev_element = None
start_time_sec = time.time()
start_energy = 0

while True:
    time.sleep(10)
    values = pollDevice(device)
    try:
        power = values['power']
        energy = values['energy']
    except KeyError:
        print('missing power or energy from returned values')
        continue

    # determine what the system is doing
    if power < 100:         # compressor power is ~440W
        state = State.IDLE
    elif power < 2000:      # resistive elements should be 5kW
        state = State.COMPRESSOR
    else:
        state = State.RESISTIVE

    if state == prev_state:
        continue            # state has not changed

    if prev_state is State.STARTUP and state is State.IDLE:
        prev_state = state  # startup to idle is not interesting
        continue

    current_time_sec = time.time()                  # float seconds
    local_time_struct = time.localtime(current_time_sec)   # struct_time
    time_duration_min = int((current_time_sec - start_time_sec)/60)
    energy_used = energy - start_energy
    notification = []
    # if something is turning off report event and results
    if prev_state is State.COMPRESSOR or prev_state is State.RESISTIVE:
        notification.append(f'{prev_element} is off')
        # placeholder for database update
        print(f'{time.asctime(local_time_struct)}: ' +
            f'{prev_element} ran for {time_duration_min} minutes and used {energy_used} kWh')
            
    # if something is turning on report event
    if state is State.COMPRESSOR:
        notification.append('Compressor is on')
        prev_element = 'Compressor'
    elif state is State.RESISTIVE:
        notification.append('Resistive heater is on')
        prev_element = 'Resistive heater'

    timestamp = time.strftime('%a %b %d %H:%M', local_time_struct)
    for n in notification:
        log.info(n)
        print(f'{timestamp}: {n}')
        try:
            requests.post(f'http://ntfy.sh/{ntfy_key}', data=f'{timestamp}: {n}')
        except:
            log.error('post to ntfy failed')

    prev_state = state
    start_time_sec = current_time_sec
    start_energy = energy
