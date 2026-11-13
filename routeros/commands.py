"""Command layer: executes the ``[ /sub/command params ]`` expressions against a
DeviceModel -- the interface that makes the interpreter "see" a router.

``where`` support: the interpreter builds a ``match(record)`` callable from the
predicate and passes it into execute; each menu builds a list of record dicts,
filters them through ``match`` and returns ids (``find``) or records
(``print as-value``).
"""

from .values import NOTHING, ROArray


def dict_to_array(d):
    return ROArray([(k, v) for k, v in d.items()])


def list_of_dicts(items):
    return ROArray([(i, dict_to_array(v)) for i, v in enumerate(items)])


def _ids(rows):
    """``find``: return ``[(0, id) ...]`` -- internal refs of the found records."""
    return ROArray([(0, r.get(".id", r.get("id", ""))) for r in rows])


def _records(rows):
    """``print as-value``: array of record dicts (for `->"prop"`)."""
    return list_of_dicts(rows)


def _filter(rows, match):
    return rows if match is None else [r for r in rows if match(r)]


class Commands:
    def __init__(self, model):
        self.model = model

    def execute(self, name, named, positional, match=None):
        path = name.lstrip("/").split("/")
        head = path[0] if path else name
        return self._dispatch(head, path, named, positional, match)

    def _dispatch(self, head, path, named, positional, match):
        model = self.model
        if head == "ping":
            addr = named.get("address", "")
            return ROArray([]) if model.ping(addr) else ROArray([("status", "timeout")])
        if head == "find":
            if "interface" in named:
                return ROArray([("interface", named["interface"])])
            return ROArray([])
        if head == "tool":
            return self._tool_fetch(named)
        if head == "file":
            return self._file(path[1:], named, positional, match)
        if head == "system":
            return self._system(path[1:], named, positional, match)
        if head == "interface":
            return self._interface(path[1:], named, positional, match)
        if head == "ip":
            return self._ip(path[1:], named, positional, match)
        if head == "routing":
            return self._routing(path[1:], named, positional, match)
        if head == "ppp":
            return self._ppp(path[1:], named, positional, match)
        if head == "certificate":
            return self._certificate(path[1:], named, positional, match)
        return NOTHING

    # ------------------------------------------------------------------ tool
    def _tool_fetch(self, named):
        url = named.get("url", "")
        if url.startswith("http://qpro.local/"):
            self.model.qpro_payloads.append(named.get("http-data"))
            return ROArray([("data", "")])
        if "192.168.8.1" in url:
            suffix = url[url.index("/api"):]
            body = self.model.e3372_responses.get(suffix, "")
            return ROArray([("data", body)])
        return ROArray([("data", "")])

    # ------------------------------------------------------------------ file
    def _file(self, path, named, positional, match):
        model = self.model
        cmd = path[0]
        if cmd == "find":
            rows = [{"name": n, "contents": c, ".id": n,
                     "type": ".txt file"} for n, c in model.files.items()]
            if match is None and named.get("name") is not None:
                rows = [r for r in rows if r["name"] == named["name"]]
            return _ids(_filter(rows, match))
        if cmd == "get":
            fname = named.get("name") or (positional[0] if positional else None)
            return model.files.get(fname or "", "")
        if cmd in ("set", "add"):
            fname = named.get("name") or (positional[0] if positional else None)
            if fname is None:
                raise KeyError(f"file/{cmd}: no file name")
            model.files[fname] = named.get("contents", "")
            return NOTHING
        if cmd in ("remove",):
            num = named.get("numbers") or (positional[0] if positional else None)
            model.files.pop(num, None)
            return NOTHING
        return NOTHING

    # ----------------------------------------------------------------- system
    def _system(self, path, named, positional, match):
        model = self.model
        cmd = path[0]
        if cmd == "clock":
            prop = positional[0] if positional else path[1] if len(path) >= 2 else None
            return model.clock.get(prop, "")
        if cmd == "resource":
            if positional and positional[0] == "uptime":
                return model.uptime
        if cmd == "routerboard":
            # print / usb/power-reset -- no network side effects
            return NOTHING
        if cmd == "backup":
            model.log(f"system/backup {named.get('name')}")
            return NOTHING
        if cmd == "ntp" and "client" in path:
            model.log("system/ntp/print")
            return NOTHING
        if cmd == "script" and "job" in path:
            scripts = model.job_scripts
            if not scripts:
                scripts = ["modem_report" for _ in range(model.jobs)]
            rows = [{"script": s, ".id": "*%d" % (i + 1)}
                    for i, s in enumerate(scripts)]
            if len(path) >= 2 and path[1] == "print":
                return _records(_filter(rows, match))
            if len(path) >= 2 and path[1] == "find":
                return _ids(_filter(rows, match))
            return NOTHING
        return NOTHING

    # -------------------------------------------------------------- interface
    def _interface(self, path, named, positional, match):
        model = self.model
        kind = path[0]
        if kind == "get":
            it = model.lte_by_id(named.get("number"))
            prop = positional[0] if positional else None
            if it is not None and prop in it:
                return it[prop]
            return NOTHING
        if kind == "lte":
            return self._lte(path[1:], named, positional, match)
        if kind == "ethernet":
            name = named.get("name")
            return ROArray([(0, name)]) if model.ethernet.get(name) else ROArray([])
        if kind == "wireless":
            if "find" in path:
                return ROArray([(0, "wlan")]) if model.wireless["running"] else ROArray([])
            if "registration-table" in path:
                return model.wireless["signal"]
        if kind == "ovpn-client":
            return self._ovpn(path[1:], named, positional, match)
        if kind in ("enable", "disable", "set"):
            model.log(f"interface/{kind}")
            return NOTHING
        raise KeyError(f"interface/{kind}")

    def _lte(self, path, named, positional, match):
        model = self.model
        cmd = path[0] if path else "print"
        if cmd == "print":
            rows = [dict(it) for it in model.lte]
            for i, r in enumerate(rows):
                r.setdefault(".id", r.get(".id", "*%d" % (i + 1)))
            return _records(_filter(rows, match))
        if cmd == "monitor":
            return dict_to_array(model.monitor(_num_arg(named)))
        if cmd == "at-chat":
            out = model.at_chat(_num_arg(named), named.get("input", ""))
            return ROArray([("output", out)])
        if cmd in ("disable", "enable", "set"):
            model.log(f"lte/{cmd}")
            return NOTHING
        # unknown lte sub-command (e.g. apn/find) -> benign empty
        return ROArray([])

    def _ovpn(self, path, named, positional, match):
        model = self.model
        cmd = path[0]
        if cmd == "find":
            rows = []
            for it in model.ovpn:
                r = dict(it)
                r.setdefault(".id", it.get("id", ""))
                rows.append(r)
            return _ids(_filter(rows, match))
        if cmd == "get":
            it = model.ovpn_by_id(named.get("number"))
            prop = positional[0] if positional else None
            if it is not None and prop in it:
                return it[prop]
            return NOTHING
        if cmd == "print":
            rows = [dict(it) for it in model.ovpn]
            for i, r in enumerate(rows):
                r.setdefault(".id", r.get("id", "*%d" % (i + 1)))
            return _records(_filter(rows, match))
        if cmd in ("enable", "disable", "set", "add", "remove"):
            model.log(f"ovpn-client/{cmd} {named.get('number', '')}{named.get('name', '')}")
            return NOTHING
        return NOTHING

    # ---------------------------------------------------------------------- ip
    def _ip(self, path, named, positional, match):
        model = self.model
        sub = path[0]
        if sub == "address":
            rows = [{"address": addr, "interface": iface, ".id": "*%d" % (i + 1)}
                    for i, (iface, addr) in enumerate(model.addresses.items())]
            if len(path) >= 2 and path[1] == "print":
                return _records(_filter(rows, match))
            interface = named.get("interface")
            if interface is None and positional and isinstance(positional[0], ROArray):
                interface = positional[0].get("interface")
            elif interface is None and positional:
                interface = positional[0]
            if match is None and interface is not None:
                addr = model.addresses.get(interface, NOTHING)
                if addr is NOTHING:
                    return NOTHING
                return ROArray([("address", addr), ("interface", interface)])
            return _ids(_filter(rows, match))
        if sub == "route":
            rows = []
            for r in model.routes:
                rr = {
                    ".id": r.get("id", ""),
                    "dst-address": r.get("dst-address", ""),
                    "gateway": r.get("gateway", ""),
                    "distance": r.get("distance", ""),
                    "comment": r.get("comment", ""),
                }
                rows.append(rr)
            if len(path) >= 2 and path[1] == "print":
                return _records(_filter(rows, match))
            if match is not None:
                return _ids(_filter(rows, match))
            # without `where` -- as before: exact match on name/value params
            return ROArray([(0, r["id"]) for r in model.route_matches(
                named.get("gateway"), named.get("dst-address"), named.get("distance"))])
        if sub == "dhcp-client":
            if len(path) >= 2 and path[1] == "renew":
                model.log("dhcp/renew")
                return NOTHING
            return NOTHING
        if sub == "dns":
            return self._dns(path[1:], named, positional, match)
        if sub == "firewall":
            return self._firewall(path[1:], named, positional, match)
        if sub == "service":
            model.log(f"ip/service/{named.get('numbers','')}")
            return NOTHING
        if sub in ("pool", "dhcp-server", "route"):
            return NOTHING
        return NOTHING

    def _dns(self, path, named, positional, match):
        model = self.model
        if path and path[0] == "static":
            rest = path[1:]
            cmd = rest[0] if rest else "print"
            rows = []
            for i, d in enumerate(model.dns_static):
                rr = dict(d)
                rr.setdefault(".id", d.get("id", "*%d" % (i + 1)))
                rows.append(rr)
            if cmd == "find":
                return _ids(_filter(rows, match))
            if cmd == "print":
                return _records(_filter(rows, match))
            if cmd == "remove":
                model.log("dns/static/remove")
                return NOTHING
            if cmd == "add":
                model.dns_static.append({"name": named.get("name", ""),
                                         "address": named.get("address", ""),
                                         "ttl": named.get("ttl", "1d")})
                return NOTHING
            if cmd == "set":
                model.log("dns/static/set")
                return NOTHING
        return NOTHING

    # ----------------------------------------------------------------- routing
    def _routing(self, path, named, positional, match):
        model = self.model
        if len(path) >= 3 and path[0] == "bgp":
            kind = path[1]  # connection | session | template
            cmd = path[2]
            rows = [dict(it) for it in getattr(model, "bgp_" + kind, [])]
            for i, r in enumerate(rows):
                r.setdefault(".id", r.get("id", "*%d" % (i + 1)))
            if cmd == "find":
                return _ids(_filter(rows, match))
            if cmd == "add":
                model.log("routing/bgp/" + kind + "/add")
                return NOTHING
            return NOTHING
        if len(path) >= 2 and path[0] == "filter":
            cmd = path[1]  # rule
            rows = [dict(it) for it in model.filter_rules]
            for i, r in enumerate(rows):
                r.setdefault(".id", r.get("id", "*%d" % (i + 1)))
            if len(path) >= 3 and path[2] == "find":
                return _ids(_filter(rows, match))
            if cmd == "rule":
                model.log("routing/filter/rule/add")
                return NOTHING
            return NOTHING
        if len(path) >= 1 and path[0] == "table":
            model.log("routing/table/add")
            return NOTHING
        return NOTHING

    # --------------------------------------------------------------- firewall
    def _firewall(self, path, named, positional, match):
        model = self.model
        if not path:
            return NOTHING
        sub = path[0]
        kind = path[1] if len(path) >= 2 else "print"
        if sub == "nat":
            rows = [dict(it) for it in model.nat_rules]
            for i, r in enumerate(rows):
                r.setdefault(".id", r.get("id", "*%d" % (i + 1)))
            if kind == "find":
                return _ids(_filter(rows, match))
            if kind == "print":
                return _records(_filter(rows, match))
            if kind == "add":
                model.log("firewall/nat/add")
                return NOTHING
            if kind in ("remove", "set"):
                model.log("firewall/nat/" + kind)
                return NOTHING
            return NOTHING
        if sub == "address-list":
            rows = [dict(it) for it in model.address_lists]
            for i, r in enumerate(rows):
                r.setdefault(".id", r.get("id", "*%d" % (i + 1)))
            if kind == "find":
                return _ids(_filter(rows, match))
            if kind == "print":
                return _records(_filter(rows, match))
            if kind == "add":
                model.address_lists.append({"address": named.get("address", ""),
                                            "list": named.get("list", ""),
                                            "comment": named.get("comment", "")})
                return NOTHING
            if kind == "remove":
                model.log("firewall/address-list/remove")
                return NOTHING
            return NOTHING
        if sub == "mangle":
            if kind in ("add", "remove", "set"):
                model.log("firewall/mangle/" + kind)
            return NOTHING
        return NOTHING

    # -------------------------------------------------------------------- ppp
    def _ppp(self, path, named, positional, match):
        model = self.model
        if path and path[0] == "profile":
            cmd = path[1] if len(path) >= 2 else "print"
            rows = []
            for i, p in enumerate(model.ppp_profiles):
                rr = dict(p)
                rr.setdefault(".id", p.get("id", "*%d" % (i + 1)))
                rows.append(rr)
            if cmd == "find":
                return _ids(_filter(rows, match))
            if cmd == "print":
                return _records(_filter(rows, match))
            if cmd == "add":
                model.ppp_profiles.append({"name": named.get("name", "")})
                return NOTHING
            if cmd in ("remove", "set"):
                model.log("ppp/profile/" + cmd)
                return NOTHING
        return NOTHING

    # ------------------------------------------------------------ certificate
    def _certificate(self, path, named, positional, match):
        model = self.model
        cmd = path[0]
        rows = []
        for i, c in enumerate(model.certificates):
            rr = dict(c)
            rr.setdefault(".id", c.get("id", "*%d" % (i + 1)))
            rows.append(rr)
        if cmd == "find":
            return _ids(_filter(rows, match))
        if cmd == "print":
            return _records(_filter(rows, match))
        if cmd in ("add", "import", "remove", "issued-revoke", "set"):
            if cmd in ("add", "import"):
                model.certificates.append({"name": named.get("name", "")})
            model.log("certificate/" + cmd)
            return NOTHING
        return NOTHING


def _num_arg(named):
    """RouterOS uses both ``number=`` and ``numbers=`` for a single interface."""
    for k in ("numbers", "number"):
        if k in named:
            return named[k]
    return None
