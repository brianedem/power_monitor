#!/usr/bin/python3
"""HVAC Heatpump Monitor

This script monitors the power used by a heat pump system
and infers its current operating mode.

Cycle run time, power consumed per cycle, and
daily power consumption are logged
"""

import logging
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json
import time
from enum import Enum
import platform
import argparse
import sys

# handle command line arguments
parser = argparse.ArgumentParser()
parser.add_argument("--detail", help="print details of HVAC activity",
    action="store_true")
parser.add_argument("--daily", help="log daily total power to database",
    action="store_true")
parser.add_argument("--sql_test", help="test SQL power logging",
    action="store_true")
args = parser.parse_args()

# determine if running on macBook
MACOS = platform.system()=='Darwin'

#default behavior controls
MYSQL = False
SAMPLE_INTERVAL = 60    # interval to read the power meter
PERIODIC_INTERVAL = 30  # interval to poll when HVAC system is on and power is stable

if args.daily and not MACOS:
    # missing Mariadb connector for MACOS
    MYSQL = True
if args.detail:
    # increase sampling rate
    SAMPLE_INTERVAL = 5

if args.sql_test:
    if MACOS:
        print('unable to test sql on MACOS platform')
        sys.exit()
    MYSQL = True
    test_time = 8*60*60     # test timer that starts in 1970 and increments daily
    SAMPLE_INTERVAL = 5

log = logging.getLogger(__name__)
if args.sql_test:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(filename=f'{parser.prog}.log', encoding='utf-8', level=logging.WARN)

sql_database = 'elpowerdb'
if MYSQL:
    import mariadb
    try:
        mdb = mariadb.connect(user='power_update', database=sql_database)
        mc = mdb.cursor()
    except mariadb.OperationalError:
        MYSQL = False
        log.exception(f'Unable to connect to {sql_database} database')

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
#               log.debug(body)
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

class State():
    STARTUP = 0
    OFF = 1
    ON = 2

    def __init__(self, name):
        self.name = name
        self.url = name + '.lan'
        self.day_start_energy = None
        self.power = None
        self.state = State.STARTUP

condenser = State('condenser')
evaporator = State('evaporator')

devices = [condenser, evaporator]

class Mode(Enum):
    STARTUP = 0
    HEAT = 1
    COOL = 2

system_mode = Mode.STARTUP

day_start_time = time.localtime()
power_change_timer = 1
run_time = 0
previous_message = ''

while True:
    time.sleep(SAMPLE_INTERVAL)

    # capture time that measurement was made
    current_time_local = time.localtime()   # time structure

    # read the power meters
    errors = []
    power_change_detected = False
    for device in devices:
        values = pollDevice(device.url)
        try:
            power = values['power']
            energy = values['energy']
        except KeyError:
            log.warning(f'Missing power or energy from {device.name}')
            errors.append(device.name)
            continue
#       print(device.name, power)

        # application startup values from first successful measurement
        if device.state is State.STARTUP:
            device.day_start_energy = energy
            device.power = power
            if power > 50:
                device.state = State.ON
            else:
                device.state = State.OFF

        # power change detection - use fixed thresholds when powering on/off
        if device.state is State.OFF and power > 50:
            power_change_detected = True
            device.state = State.ON
        elif device.state is State.ON:
            if power < 20:
                power_change_detected = True
                device.state = State.OFF
            else:
                low_threshold = device.power*0.8
                high_threshold = device.power*1.2
                power_change_detected |= not low_threshold < power < high_threshold

        # record values
        device.power = power
        device.energy = energy

    if errors:
        # TODO
        # Need enhancements to deal with continued loss of connectivity so as to not
        # flood the log.
        # Sustained loss of connectivity to one device indicates a device failure
        # that requires intervention.
        # Sustained loss of connectivity to one device, then the other should also
        # be considered device failures that need intervention
        # Simultainous sustained loss of connectivty to both devices will usually
        # be an indication of a utility power is lost that should eventually recover
        # without intervention, but should include .
        continue


    # report summary of yesterday's energy use
    # TODO add to database?
    if MYSQL:
        if args.sql_test:
            new_day = True
            timestamp = time.strftime('%a %b %d', time.localtime(test_time))
            sql_timestamp = time.strftime('%Y-%m-%d', time.localtime(test_time))
            test_time += 24*60*60   # advance a day
        else:
            new_day = current_time_local.tm_yday != day_start_time.tm_yday 
            timestamp = time.strftime('%a %b %d', day_start_time)
            sql_timestamp = time.strftime('%Y-%m-%d', day_start_time)
            day_start_time = current_time_local
        if new_day:
            c_energy = condenser.energy - condenser.day_start_energy
            e_energy = evaporator.energy - evaporator.day_start_energy
            energy_used = c_energy + e_energy
            print(f'{timestamp}      {c_energy:.1f} + {e_energy:.1f} = {energy_used:.1f} kWh used yesterday')
            if MYSQL:
                try:
                    sql_command = 'INSERT INTO hvac_power (day, condensor_energy, evaporator_energy)' \
                        f' VALUES ("{sql_timestamp}", {c_energy}, {e_energy})'
                    print(sql_command)
                    mc.execute(sql_command)
                    mdb.commit()
                except mariadb.Error:
                    log.error("unable to update hvac_power table in elpowerdb")
                    sys.exit()

            condenser.day_start_energy = condenser.energy
            evaporator.day_start_energy = evaporator.energy

    # skip the following if not reporting power details
    if not args.detail:
        continue

    # start timers every time a change in load is detected
    if power_change_detected:
        # generate messages for this many seconds after the last detected change
        power_change_timer = PERIODIC_INTERVAL
        # periodically generate messages while the system is running
        run_time = 0

    # increment the periodic timer while the system is running
    if condenser.state is State.ON or evaporator.state is State.ON:
        run_time += SAMPLE_INTERVAL

    # create the message
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S', current_time_local)
    message = f'{timestamp},{condenser.power:.1f},{evaporator.power:.1f}'

    # generate message if required
    if power_change_timer > 0 or run_time>(5*60):
        power_change_timer -= SAMPLE_INTERVAL
        run_time = 0
        # a previous_message indicates that we didnt print on previous cycle
        if previous_message:
            # so print that now so we can see what we transitioned from
            print(previous_message)
            previous_message = ''
        print(message)

        # kill timer when system is fully off
        if condenser.state is State.OFF and evaporator.state is State.OFF:
            power_change_timer = 0
    else:
        # if not printing keep previous message
        previous_message = message
