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
import http

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
    except http.client.RemoteDisconnected :
        log.exception(f'{dev} disconnected before returning response')

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
state_start_time = time.time()
state_start_energy = None
day_start_time = time.localtime()
day_start_energy = None

while True:
    time.sleep(30)

    # read the power meter
    values = pollDevice(device)
    try:
        power = values['power']
        energy = values['energy']
    except KeyError:
        log.warning('Missing power or energy from returned values')
        continue

    # application startup values from first successful measurement
    if state_start_energy is None:        # incomplete day
        day_start_energy = energy
        state_start_energy = energy

    # capture time that measurement was made
    current_time_sec = time.time()                   # in seconds since epoc
    local_time = time.localtime(current_time_sec)    # and in struct_time

    # report summary of yesterday's energy use
    # *** add to database?
    if local_time.tm_yday != day_start_time.tm_yday:
        if day_start_energy:
            timestamp = time.strftime('%a %b %d', day_start_time)
            energy_used = energy - day_start_energy
            print(f'{timestamp}      {energy_used:.3f} Wh used yesterday')
        day_start_time = local_time
        day_start_energy = energy

    # determine what state the system currently is in
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

    # at this point we have confirmed that an event has occured
    # collect notifications and send in one message
    notification = []
    timestamp = time.strftime('%a %b %e %H:%M', local_time)

    # if something is turning off report event and results
    if prev_state is State.COMPRESSOR or prev_state is State.RESISTIVE:
        notification.append(f'{prev_element} is off')
        # placeholder for database update
        prev_state_duriation = int((current_time_sec - state_start_time)/60)
        energy_used = energy - state_start_energy
        print(f'{timestamp} ' +
            f'{prev_element} ran for {prev_state_duriation} minutes and used {energy_used:.3f} kWh')
            
    # if something is turning on report event
    if state is State.COMPRESSOR:
        notification.append('Compressor is on')
        prev_element = 'Compressor'
    elif state is State.RESISTIVE:
        notification.append('Resistive heater is on')
        prev_element = 'Resistive heater'

    for n in notification:
        log.info(n)
        print(f'{timestamp}: {n}')
        try:
            requests.post(f'http://ntfy.sh/{ntfy_key}', data=f'{timestamp} {n}')
        except:
            log.warning('post to ntfy failed')

    prev_state = state
    state_start_time = current_time_sec
    state_start_energy = energy
