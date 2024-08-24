import network
import mlogging as logging
import time

log = logging.getLogger(__name__)

status_decode = {
    network.STAT_IDLE:          'idle',                     # 0
    network.STAT_CONNECTING:    'connecting',               # 1
    2:                          'waiting for IP address',
    network.STAT_GOT_IP:        'connected',                # 3
    network.STAT_CONNECT_FAIL:  'connect fail',             #-1
    network.STAT_NO_AP_FOUND:   'no AP found',              #-2
    network.STAT_WRONG_PASSWORD:'wrong password',           #-3
    }
class lan():

    def wifi_scan(self):
            # request list of available AP
        scan_list = self.wlan.scan()
            # extract names and rssi, eliminate duplicates and hidden values
        ap_strength = {}
        for ap in scan_list:
            ap_name = ap[0].decode()
            ap_rssi = ap[3]
            if ap_name in ap_strength:
                if ap_rssi > ap_strength[ap_name]:
                    ap_strength[ap_name] = ap_rssi
            elif ap_name != '':
                ap_strength[ap_name] = ap_rssi
            # sort available APs by signal strength
        self.ap_list = []
        for ap in sorted(ap_strength, key=ap_strength.get, reverse=True):
            self.ap_list.append([ap, ap_strength[ap]])

    def __init__(self, hostname):
        self.hostname = hostname
        self.network_ip = '0.0.0.0'
        network.hostname(hostname)
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.ap = ''
        self.wifi_scan()
        self.mac_address = self.wlan.config('mac').hex(':')

    def wifi_list(self):
        self.wifi_scan()
        response = []
        for index in range(len(self.ap_list)):
            name, rssi = self.ap_list[index]
            response.append(f' {index:2} {rssi:4} {name}')
        return response

    def wifi_connect(self, networks):
        if self.wlan.isconnected():
            self.wifi_disconnect()
            time.sleep(1)
        for ap in self.wlan.scan() :
            ssid = ap[0].decode() 
            if ssid in networks:
                self.wlan.connect(ssid, networks[ssid])
                self.ap = ssid
                log.info(f'WIFI connected to {ssid}')
                break

    def wifi_disconnect(self):
        self.wlan.disconnect()
        log.info(f'Disconnecting from WIFI {self.ap}')

    def status(self):
        response = []
        response.append(f'hostname: {self.hostname}')
        status = self.wlan.status()
        if status == network.STAT_GOT_IP :
            response.append(f'network is up')
            response.append(f'MAC address: {self.mac_address}')
            response.append(f'AP: {self.ap}')
            self.network_ip = self.wlan.ifconfig()[0]
            response.append(f'IP address: {self.network_ip}')
        elif status in status_decode :
            response.append( status_decode[status])
        else :
            response.append( f'Unknown status {status}')
        return response

    def test(self):
        prev_status = 100
        while True:
            wifi_status = self.wlan.status()
            if wifi_status != prev_status :
                if wifi_status not in status_decode :
                    print(f'{time.localtime} {wifi_status}')
                else :
                    print(f'{time.localtime()} {status_decode[wifi_status]}')
            prev_status = wifi_status
        
