#!/usr/bin/python3
import logging
logger = logging.getLogger(__name__)
logging.basicConfig(filename='power_poll.log', encoding='utf-8', level=logging.DEBUG)

import socket
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

timeout = 2
socket.setdefaulttimeout(timeout)

reqC = Request('http://192.168.1.77/data.json')
reqE = Request('http://192.168.1.133/data.json')

import json

def pollDevice(req) :
    values = None
    try:
        response = urlopen(req)
    except HTTPError as e:
        logger.exception(e.code)
    except URLError as e:
        logger.exception(e.reason)
    else :
        content_type = response.getheader('Content-type')
        if 'json' in content_type :
            body = response.read()
            logger.info(body)
            values = json.loads(body)
    return values

for i in range(2) :
    print('---')
    for device in (reqC, reqE) :
        values = pollDevice(device)
        print(values)
