#!./venv/bin/python
""" Home Power Logger

This script will read the cumulative energy readings of the specified
power meters and log the values in a database.

This script should be run daily via cron
"""

import os
import logging
import socket
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json
import time
import platform
import sys
import mariadb

program_name = os.path.basename(sys.argv[0])
log_file = os.path.splitext(program_name)[0] + '.log'

log = logging.getLogger(__name__)
logging.basicConfig(filename=log_file, encoding='utf-8', level=logging.DEBUG)

# determine if running on macBook
MACOS = platform.system()=='Darwin'

if MACOS:
    log.exception('power_poll does not run on a MacBook')
    sys.exit()

# database
sql_database = 'elpowerdb'
try:
    mdb = mariadb.connect(user='power_update', database=sql_database)
    mc = mdb.cursor()
except mariadb.OperationalError:
    log.exception(f'Unable to connect to {sql_database} database')
    sys.exit()

timeout = 2
socket.setdefaulttimeout(timeout)

devices = (
    'condenser',
    'evaporator',
    'waterheater',
    )

def pollDevice(dev) :
    req = Request(f'http://{dev}.lan/data.json')
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

def extract(data, values) :
    result = {}
    for value in values :
        if value in data :
            result[value] = data[value]
    return result

resp = {}
for device in devices :
    values = pollDevice(device)
    try:
        energy = values['energy']
    except:
        energy = None
        log.warning(f'Missing value for {device}')
    resp[device] = energy

print(resp)
sql_timestamp = time.strftime('%Y-%m-%d')
sql_command = 'INSERT INTO hvac_power (day, condensor_energy, evaporator_energy, wh_energy)' \
                        f' VALUES ("{sql_timestamp}",' \
                        f' {resp["condensor"]}, {resp["evaporator"]})' 
