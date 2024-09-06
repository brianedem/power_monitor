# power_monitor
Wireless power monitor using PEZM-004 and Pico W

## Server
The server code that runs on the Pico W board is located in the picow directory. All files in this directory should be copied into the root directory of the pico board. Either rshell (CLI) or thonny (GUI) can be used to copy the files to the pico.

The wifi is configured via the config.json file, which is not included in the distribution. This file can be created using the server CLI, or it can be created externally and copied to the system.

The server provides CLI interfaces at both the USB and bluetooth interfaces. Rshell, thonny, or a serial terminal application can be used to access the USB CLI, while a general purpose bluetooth UART application, such as bluefruit, can be used to access the bluetooth CLI.
### Configuration Parameters
> ssid - wifi network ssid
> password - wifi network password
> hostname - hostname advertised via LAN nDNS and bluetooth (default PyPower)
> beta - thermister beta parameter

The Pico W also requires a config.json file for setting up the wifi SSID, password, and the advertised mDNS hostname. It has the following format:
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
