# power_monitor
Wireless power monitor using PEZM-004 and Pico W

## Server
The server code that runs on the Pico W board is located in the picow directory. All files in this directory should be copied into the root directory of the pico board. Either rshell (CLI) or thonny (GUI) can be used to copy the files to the pico.

The server provides CLI interfaces at both the USB and bluetooth interfaces. Rshell, thonny, or a serial terminal application can be used to access the USB CLI, while a general purpose bluetooth UART application, such as bluefruit, can be used to access the bluetooth CLI.

The default system name used by the HTTP server and BLE interface is "PyPower", but can be changed by using the CLI to set the hostname.

The WIFI is also configured vie the CLI using the "wifi" commands. The WIFI configuration is able to hold the information for several WIFI networks.

The system supports an external 10K NTC temperature sensor. The beta of the sensor can also be set vi the CLI to override the default value of 3984

## power_poll.py
This file contains demonstration code showing how a workstation application can pick
up data from one or more devices running the server code.

## analyze.py

## wheater.py
This application monitors the heat-pump water heater power usage, tracking its mode from the power readings. Changes in mode are reported via ntfy, and energy used in each cycle is tracked. Daily energy use is logged to a TBD database
