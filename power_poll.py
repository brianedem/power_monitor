#!/usr/bin/python3
import logging
import socket
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import json
import time

logger = logging.getLogger(__name__)
logging.basicConfig(filename='power_poll.log', encoding='utf-8', level=logging.INFO)

    # if 'DNS Assist' is enabled in the network privicy settings then
    # host names with the .local suffix are forwarded to their DNS server
    # The workaround is to use .attlocal.net instead, but which to use?
    # The 'search' item in /etc/resolve.conf will be set to attlocal.net
    # if DNS Assist is enabled
try :
    with open('/etc/resolve.conf') as fd:
        for line in fd :
            if line.startswith('search') :
                search = '.'+line.split()[1]
                break
except FileNotFoundError :
    search = ''     # maybe this should be '.local'?

timeout = 2
socket.setdefaulttimeout(timeout)

devices = ('condenser', 'evaporator', 'waterheater')
#devices = ('condenser', 'evaporator')

mapping = {}

def pollDevice(dev) :
    req = Request(f'http://{dev+search}/data.json')
    values = {}
    try:
        response = urlopen(req)
    except HTTPError as e:
        logger.exception(f'Request to {dev} {e.code}')
    except URLError as e:
        logger.exception(f'Request to {dev} {e.reason}')
    except TimeoutError :
        logger.exception(f'Request to {dev} timed out')
    else :
        content_type = response.getheader('Content-type')
        if 'json' in content_type :
            body = response.read()
            logger.debug(body)
            values = json.loads(body)
        else :
            print('{dev}: json content not found')
            print(response.read())
    return values

def extract(data, values) :
    result = {}
    for value in values :
        if value in data :
            result[value] = data[value]
    return result

fd = open('data.json', 'a', encoding='utf-8')

while True :
    responses = {'time': time.localtime()}
    for device in devices :
        values = extract(pollDevice(device), ('voltage', 'current', 'power', 'energy', 'temperature'))
        if 'temperature' in values and values['temperature'] > 55 :
            del values['temperature']
        responses[device] = values

#   print(json.dumps(responses))
    fd.write(json.dumps(responses)+'\n')
    fd.flush()
    time.sleep(5)
