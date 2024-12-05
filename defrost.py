#
'''
The Problem
Some times when the heat pump is running it will emit
a moldy smell for a few minutes. This seems to occur when the
system runs a defrost cycle (cold outside, long run cycles), but
it doesn't occur on every defrost cycle.  The theory is
that the thermostat interrupts the defrost cycle, leaving the
evaporator wet from condensation, which then allows mold to grow
until the next call for heat. At the next heat cycle a smell is
generated as the mold dries out.

The Fix
A time delay relay will be added that will override the
thermostat during defrost to ensure that the system completes the
defrost cycle and the evaporator has had sufficient time to dry
before shutting the system off.

The relay will monitor the heat/backup heat control (W-C circuit)
the defrost controller (in the condensor) enables
while the defrost cycle is running. The relay contacts will connect
Y-R signals to extend the cycle. The relay will remain energized
for a configurable delay, which is to be determined by this
monitoring program.

This fix relies on the thermostat/zone controller maintaining the
state of the reversing valve control wire while not calling for
heat.  As the reversing valve is only energized for cooling it should
remain de-energized.

Relay Wiring
 A1 - R  24VAC
 A2 - C  Common/Return
 S  - W  Heat/Supplemental/Backup Heat
 15 - R  24VAC
 18 - Y1 Compressor stage 1
'''

import sys
import logging
import requests
import time
from enum import Enum

log = logging.getLogger(__name__)
logging.basicConfig(filename='defrost.log', encoding='utf-8', level=logging.DEBUG)

devices = (
    'condenser',
    'evaporator',
    )

def pollDevice(dev) :
    try:
        r = requests.get(f'http://{dev}/data.json')
    except requests.exceptions.ConnectionError:
        log.error(f'Unable to connect to {dev}')
        return None
    try:
        return r.json()
    except requests.exceptions.JSONDecodeError:
        log.exception(f'Unable to decode JSON data from {dev}')
        return None

def extract(data, values) :
    result = {}
    for value in values :
        if value in data :
            result[value] = data[value]
    return result

'''
During defrost the compressor will cycle off when before the
reversing valve is changed.
Around the first off cycle the system will turn on the heat strip.
Around the second off cycle the system will turn off the heat strip.
It is not clear what the exact timing of the heat strip relative to
compressor cycling.

1) Wait for both the compressor and heat strip are on. This indicates that defrost has started
2) When either the compressor or heat strip shut off, 
Record when heat strip goes off along with the compressor state.
If the compressor is off when the heat strip is turned off record when the compressor is enabled.
'''

class State(Enum):
    HS_WAIT = 0
    DEFROST = 1
    HS_END = 2
    COMP_END = 3
    COMP_WAIT = 4

state = State.HS_WAIT

COND = 'condenser'
EVAP = 'evaporator'

fail_count = {
    COND: 0,
    EVAP: 0,
    }

while True:
    resp = {}
    for device in devices :
        values = pollDevice(device)
        try:
            power = values['power']
            resp[device] = power
        except KeyError:
            log.warning(f'Missing value for {device}')
            resp[device] = None
            fail_count[device] += 1
        else:
            fail_count[device] = 0

#   print(resp)

    if len(resp) != 2:
        if fail_count[COND] > 10:
            log.error(f'condensor is not responding')
            sys.exit(1)
        elif fail_count[EVAP] > 10:
            log.error(f'evaporator is not responding')
            sys.exit(1)
    else:
        comp_on = resp[COND] > 1000
        hs_on = resp[EVAP] > 2000
        ts = time.strftime('%H:%M:%S')

        if state == State.HS_WAIT:
            if comp_on and hs_on:
                state = State.DEFROST
                print(f'{ds} defrost start')

        elif state == State.DEFROST:      # hs and compressor are both on
            if not hs_on:
                state = State.HS_END
                print(f'{ds} heat strips off; compressor power = {resp[COND]}')
            if not comp_on:
                state = State.COMP_END
                print(f'{ds} compressor off; heat strip power = {resp[EVAP]}')

        elif state == State.HS_END:      # heat strips off, waiting for compressor to turn off
            if not comp_on:
                state = State.COMP_WAIT
                print(f'{ds} compressor and heat strip off')
            elif hs_on:         # unexpected transition
                state = State.DEFROST
                print(f'{ds} heat strips back on - unexpected transition')

        elif state == State.COMP_END:     # compressor off, waiting for heat strips to turn off
            if not hs_on:
                state = State.COMP_WAIT
                print(f'{ds} compressor and heat strip off')
            elif comp_on:
                state = State.DEFROST
                print(f'{ds} compressor back on - unexpected transition')

        elif state == State.COMP_WAIT:      # heat strips and compressor off
            if comp_on:
                state = State.HS_WAIT
                print(f'{ds} compressor back on')
            elif hs_on:         # unexpected transition
                state = State.COMP_END
                print(f'{ds} heat strips back on - unexpected transition')

    time.sleep(10)
