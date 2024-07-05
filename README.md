# power_monitor
Wireless power monitor using PEZM-004 and Pico W

## Server
The server code that runs on the Pico W board is located in the picow directory. All files in this directory should be copied into the root directory of the pico board.
The Pico W also requires a password.json file for setting up the wifi SSID, password, and the advertised mDNS hostname. It has the following format:
```json
{
    "ssid":"<network_ssid>",
    "password":"<network_password>",
    "hostname":"<device name>"
}
```

## power_poll.py
This file contains demonstration code showing how a workstation application can pick
up data from one or more devices running the server code.
