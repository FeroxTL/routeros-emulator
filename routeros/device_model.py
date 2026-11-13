"""Device model: the "world" the script sees. Tests populate this object to
simulate different LTE / wired / wifi setups and record side effects.
"""

from .values import Time


class DeviceModel:
    def __init__(self):
        # LTE interfaces: list of dicts with keys like
        # {".id", "name", "model", "apn-profiles", "disabled", "running"}
        self.lte = []
        # monitor(id) -> dict-like result of /interface/lte/monitor
        self.monitor = lambda _id: {}
        # at_chat(id, input) -> output string of /interface/lte/at-chat
        self.at_chat = lambda _id, _cmd: ""
        # Ethernet/wireless state. wireless is {"running": bool, "signal": str}
        self.ethernet = {}
        self.wireless = {"running": False, "signal": ""}
        # OVPN interfaces: list of {"id", "name", "disabled"}
        self.ovpn = []
        # Files: name -> content
        self.files = {}
        # Routes: list of {"id", "gateway", "dst-address", "distance"}
        self.routes = []
        # IP addresses: interface name -> ip string
        self.addresses = {}
        # Clock and uptime
        self.clock = {"date": "oct/27/2026", "time": "15:04:05"}
        self.uptime = Time(7200)
        # Number of currently running jobs (reentrancy guard)
        self.jobs = 0
        # Running script-jobs: list of {"script": name} for /system/script/job
        self.job_scripts = []
        # DNS static records: list of {"id", "name", "address", "ttl"}
        self.dns_static = []
        # Firewall nat rules: list of {"id", "comment", "out-interface"}
        self.nat_rules = []
        # Firewall address-list: list of {"id", "address", "list", "comment"}
        self.address_lists = []
        # PPP profiles: list of {"id", "name"}
        self.ppp_profiles = []
        # Certificates: list of {"id", "name", "common-name", "skid", "trusted", "private-key"}
        self.certificates = []
        # Routing filter rules: list of {"id", "chain", "rule"}
        self.filter_rules = []
        # Routing BGP: list of {"id", "name", "remote-address"}
        self.bgp_connection = []
        self.bgp_session = []
        # ping(ip) -> bool
        self.ping = lambda addr: True
        # E3372 web API responder: path suffix -> xml/dict body
        self.e3372_responses = {}
        # Side-effect log / captured qpro payloads
        self.effects = []
        self.qpro_payloads = []

    def log(self, msg):
        self.effects.append(msg)

    # ---- convenience accessors used by /interface/... overlay ----
    def lte_by_id(self, num):
        for it in self.lte:
            if str(it.get(".id")) == str(num) or str(it.get("id")) == str(num):
                return it
        return None

    def ovpn_by_id(self, num):
        for it in self.ovpn:
            if str(it.get("id")) == str(num):
                return it
        return None

    def route_matches(self, gateway=None, dst=None, distance=None):
        out = []
        for r in self.routes:
            if gateway is not None and str(r.get("gateway")) != str(gateway):
                continue
            if dst is not None and str(r.get("dst-address")) != str(dst):
                continue
            if distance is not None and r.get("distance") != distance:
                continue
            out.append(r)
        return out