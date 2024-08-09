import network
import mlogging as logging

log = logging.getLogger(__name__)

status_decode = {
    network.STAT_IDLE:          'idle',
    network.STAT_CONNECTING:    'connecting',
    network.STAT_WRONG_PASSWORD:'wrong password',
    network.STAT_NO_AP_FOUND:   'no AP found',
    network.STAT_CONNECT_FAIL:  'connect fail',
    network.STAT_GOT_IP:        'connected',
    }
class lan():

    def __init__(self, hostname):
        self.hostname = hostname
        self.network_ip = '0.0.0.0'
        network.hostname(hostname)
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)
        self.mac_address = self.wlan.config('mac').hex(':')
        self.open_sockets = []

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

            # sort the stations into a list
        ap_list = []
        for ap in sorted(ap_strength, key=ap_strength.get, reverse=True):
            ap_list.append(f'{ap_strength[ap]:4} {ap}')
        return ap_list

    def wifi_connect(self, ssid, password):
        self.wlan.connect(ssid, password)

    def wifi_disconnect(self):
        for s in self.open_sockets:
            s.close()
        self.wlan.disconnect()

    def open_server(self):
        if self.wlan.isconnected() :
            ip_address = self.wlan.ifconfig()[0]
            address = (ip_address, 80)
            self.socket = socket.socket()
            self.socket.bind(address)
            self.socket.listen(5)
            self.open_sockets.append(self.socket)
            return self.socket
        else :
            return None

    def diagnose(self):
        status = self.wlan.status()
        return status_decode[status]
