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

Observations
On 2024-12-31 during the 9AM defrost cycle I noticed the smell
at the start of the reheat after the defrost, so the problem may
not totally be related to the previous defrost cycles, although
there were three previous defrost cycles where the first two
ended reheat after 2m 29s and 3m 2s.

While observing the results of an earlier version of this code
the smell was detected after the second defrost cycle of continous
operation of the heat pump, and in that case the system continued
to run for at least 15 minutes after the second defrost cycle.

Additional Thougths
The system may already be taking actions to prevent the interruption
of a defrost cycle. The defrost circuitry in the compressor already
enables the W control during the time the compressor is operating
in the cool mode, so it may also be enabling the Y1 control to
ensure that the cycle is not interrupted.
I would need to add monitoring to determine if Y1 continues to be
enabled after the zone controller releases it.

Possible Fix
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

from enum import Enum
import logging
import picow_peacefair.pp_read as pp
import socket
import sys
import time

log = logging.getLogger(__name__)
logging.basicConfig(filename='defrost.log', encoding='utf-8', level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(message)s')

log.info("starting")

devices = (
    'condenser',
    'evaporator',
    )

addresses = {}
for device in devices:
    addresses[device] = socket.gethostbyname(device+'.lan')

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
    HEATING = 5

state = State.HS_WAIT

COND = 'condenser'
EVAP = 'evaporator'

fail_count = {
    COND: 0,
    EVAP: 0,
    }

MAX_FAIL = 100
class hvac_events:
    __slots__ = ()
    COMP_OFF = 1
    COMP_ON = 2
    EVAP_OFF = 3
    EVAP_FAN = 4
    EVAP_HS = 5
s = hvac_events()
test_events = iter((
    (10, s.COMP_ON),  # start cycle
    ( 5, s.EVAP_FAN),
    (10, s.COMP_OFF),
    ( 5, s.EVAP_OFF), # end cycle
    (10, s.COMP_ON),  # start cycle - with hs on after comp reverse
    ( 5, s.EVAP_FAN),
    (10, s.COMP_OFF), # defrost - comp off
    ( 5, s.COMP_ON),  # defrost - comp reverse
    ( 5, s.EVAP_HS),  # defrost hs on
    (10, s.COMP_OFF), # defrost - comp off
    ( 5, s.EVAP_FAN), # defrost hs off
    ( 5, s.COMP_ON),  # defrost - comp on
    (10, s.COMP_OFF), # defrost reheat complete
    ( 5, s.EVAP_OFF),
    (10, s.COMP_ON),  # start cycle - with hs on before comp reverse
    ( 5, s.EVAP_FAN),
    (10, s.COMP_OFF), # defrost - comp off
    ( 5, s.EVAP_HS),  # defrost hs on
    ( 5, s.COMP_ON),  # defrost - comp reverse
    ( 5, s.EVAP_FAN), # defrost hs off
    (10, s.COMP_OFF), # defrost - comp off
    ( 5, s.COMP_ON),  # defrost - comp on
    (10, s.COMP_OFF), # defrost reheat complete
    ( 5, s.EVAP_OFF),
    (0, 0),
))

test = False
comp_on = False
hs_on = False
evap_off = True
test_time = time.time()
resp = {COND: 0, EVAP:9}

while True:
    if test:
        print(state)
#       print(next(test_events))
#       continue
        delta, event = next(test_events)
        if delta == 0:
            print('End of test')
            sys.exit(0)
        match event:
            case s.COMP_OFF:
                comp_on = False
            case s.COMP_ON:
                comp_on = True
            case s.EVAP_OFF:
                hs_on = False
                evap_off = True
            case s.EVAP_FAN:
                hs_on = False
                evap_off = False
            case s.EVAP_HS:
                hs_on = True
                evap_off = False
            case _:
                raise ValueError("Invalid test event entry")
        test_time += delta
        ts = time.strftime('%H:%M:%S', time.localtime(test_time))
        print(f'{ts} {comp_on=}, {hs_on=}, {evap_off=}')
        
    else:
        time.sleep(10)
        resp = {}
        for device in devices :
            values = pp.read_dev(addresses[device])
            if values is None:
                fail_count[device] += 1
                continue
            elif 'power' in values:
                resp[device] = values['power']
                fail_count[device] = 0
            else:
                log.warning(f'Missing power value for {device}')
                fail_count[device] += 1

#   print(resp)

        if len(resp) != 2:
            if fail_count[COND] > MAX_FAIL:
                log.error(f'condensor is not responding')
                sys.exit(1)
            elif fail_count[EVAP] > MAX_FAIL:
                log.error(f'evaporator is not responding')
                sys.exit(1)
            continue
        comp_on = resp[COND] > 1000
        hs_on = resp[EVAP] > 2000
        evap_off = resp[EVAP] < 50
        ts = time.strftime('%H:%M:%S')

    if state != State.HS_WAIT and evap_off:
        print(f'{ts} evaporator shut off during defrost')
        state = State.HS_WAIT

    elif state == State.HS_WAIT:
        if comp_on and hs_on:
            state = State.DEFROST
            print(f'{ts} defrost start')

    elif state == State.DEFROST:      # hs and compressor are both on
        if not hs_on:
            state = State.HS_END
            print(f'{ts} heat strips off; compressor power = {resp[COND]}')
        if not comp_on:
            state = State.COMP_END
            print(f'{ts} compressor off; heat strip power = {resp[EVAP]}')

    elif state == State.HS_END:      # heat strips off, waiting for compressor to turn off
        if not comp_on:
            state = State.COMP_WAIT
            print(f'{ts} compressor and heat strip off')
        elif hs_on:         # unexpected transition
            state = State.DEFROST
            print(f'{ts} heat strips back on - unexpected transition')

    elif state == State.COMP_END:     # compressor off, waiting for heat strips to turn off
        if not hs_on:
            state = State.COMP_WAIT
            print(f'{ts} compressor and heat strip off')
        elif comp_on:
            state = State.DEFROST
            print(f'{ts} compressor back on - unexpected transition')

    elif state == State.COMP_WAIT:      # heat strips and compressor off
        if comp_on:
            state = State.HEATING
            reheat_start = time.time()
            print(f'{ts} compressor on - reheating indoor coil')
        elif hs_on:         # unexpected transition
            state = State.COMP_END
            print(f'{ts} heat strips back on - unexpected transition')

    elif state == State.HEATING:
        reheat_time = time.time() - reheat_start
        if not comp_on:
            state = State.HS_WAIT
            print(f'{ts} compressor off - indoor reheat ends')
        elif hs_on:
            state = State.DEFROST
            print(f'{ts} heat strips back on - unexpected transition')
        elif reheat_time > (5*60):
            state = State.HS_WAIT
            print(f'{ts} reheat 5 minute timeout - defrost ends')
