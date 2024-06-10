# power_monitor
Wireless power monitor using PEZM-004 and Pico W

## power_server.py
This file is to be copied as main.py to the Pico W that has microPython installed.
The Pico W also requires a password.json file containing the following:
```json
{
    "ssid":"<network_ssid>",
    "password":"<network_password>",
    "hostname":"<device name>"
}
```
Note that the hostname is only used to identify the device on its web page.

## power_poll.py
This file contains demonstration code showing how a workstation application can pick
up data from one or more devices runing power_server.py
