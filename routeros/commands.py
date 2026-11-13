"""Command layer: executes the ``[ /sub/command params ]`` expressions against a
DeviceModel -- the interface that makes the interpreter "see" a router.
"""

from .values import NOTHING, ROArray


def dict_to_array(d):
    return ROArray([(k, v) for k, v in d.items()])


def list_of_dicts(items):
    return ROArray([(i, v) for i, v in enumerate(items)])


class Commands:
    def __init__(self, model):
        self.model = model

    def execute(self, name, named, positional):
        path = name.lstrip("/").split("/")
        head = path[0] if path else name
        return self._dispatch(head, path, named, positional)

    def _dispatch(self, head, path, named, positional):
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
            return self._file(path[1:], named, positional)
        if head == "system":
            return self._system(path[1:], named, positional)
        if head == "interface":
            return self._interface(path[1:], named, positional)
        if head == "ip":
            return self._ip(path[1:], named, positional)
        return NOTHING

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

    def _file(self, path, named, positional):
        cmd = path[0]
        if cmd == "find":
            name = named.get("name")
            if name in self.model.files:
                return ROArray([(0, name)])
            return ROArray([])
        if cmd == "get":
            fname = named.get("name") or (positional[0] if positional else None)
            return TO_STR(self.model.files.get(fname or "", ""))
        if cmd in ("set", "add"):
            fname = named["name"]
            self.model.files[fname] = TO_STR(named.get("contents", ""))
            return NOTHING
        raise KeyError(f"file/{cmd}")

    def _system(self, path, named, positional):
        cmd = path[0]
        if cmd == "clock":
            prop = positional[0] if positional else path[1] if len(path) >= 2 else None
            return self.model.clock.get(prop, "")
        if cmd == "resource":
            if positional and positional[0] == "uptime":
                return self.model.uptime
        if cmd == "routerboard" and "usb" in path:
            self.model.log("power-reset")
            return NOTHING
        if cmd == "script" and "job" in path:
            return ROArray([(i, ROArray([])) for i in range(self.model.jobs)])
        raise KeyError(f"system/{cmd}")

    def _interface(self, path, named, positional):
        model = self.model
        kind = path[0]
        if kind == "get":
            it = model.lte_by_id(named.get("number"))
            prop = positional[0] if positional else None
            if it is not None and prop in it:
                return it[prop]
            return NOTHING
        if kind == "lte":
            return self._lte(path[1:], named, positional)
        if kind == "ethernet":
            name = named.get("name")
            return ROArray([(0, name)]) if model.ethernet.get(name) else ROArray([])
        if kind == "wireless":
            if "find" in path:
                return ROArray([(0, "wlan")]) if model.wireless["running"] else ROArray([])
            if "registration-table" in path:
                return model.wireless["signal"]
        if kind == "ovpn-client":
            return self._ovpn(path[1:], named, positional)
        if kind in ("enable", "disable", "set"):
            model.log(f"interface/{kind}")
            return NOTHING
        raise KeyError(f"interface/{kind}")

    def _lte(self, path, named, positional):
        model = self.model
        cmd = path[0] if path else "print"
        if cmd == "print":
            return list_of_dicts([dict_to_array(it) for it in model.lte])
        if cmd == "monitor":
            return dict_to_array(model.monitor(_num_arg(named)))
        if cmd == "at-chat":
            out = model.at_chat(_num_arg(named), named.get("input", ""))
            return ROArray([("output", out)])
        if cmd in ("disable", "enable", "set"):
            model.log(f"lte/{cmd}")
            return NOTHING
        # unknown lte sub-command (e.g. monitor/apn/find) -> benign empty
        return ROArray([])

    def _ovpn(self, path, named, positional):
        model = self.model
        cmd = path[0]
        if cmd == "find":
            return ROArray([(0, it["id"]) for it in model.ovpn])
        if cmd == "get":
            it = model.ovpn_by_id(named.get("number"))
            prop = positional[0] if positional else None
            if it is not None and prop in it:
                return it[prop]
            return NOTHING
        if cmd in ("enable", "disable"):
            model.log(f"ovpn/{cmd} {named.get('number')}")
            return NOTHING
        raise KeyError(f"ovpn-client/{cmd}")

    def _ip(self, path, named, positional):
        model = self.model
        sub = path[0]
        if sub == "address":
            if len(path) >= 2 and path[1] == "print":
                rows = []
                for iface, addr in model.addresses.items():
                    if iface.startswith("ovpn_"):
                        rows.append(ROArray([("address", addr)]))
                return list_of_dicts(rows)
            interface = named.get("interface")
            if interface is None and positional and isinstance(positional[0], ROArray):
                interface = positional[0].get("interface")
            elif interface is None and positional:
                interface = positional[0]
            addr = model.addresses.get(interface or "", NOTHING)
            if addr is NOTHING:
                return NOTHING
            # return a record so `->"address"` works like real RouterOS
            return ROArray([("address", addr), ("interface", interface or "")])
        if sub == "route":
            return ROArray([(0, r["id"]) for r in model.route_matches(
                named.get("gateway"), named.get("dst-address"), named.get("distance"))])
        if sub == "dhcp-client":
            if len(path) >= 2 and path[1] == "renew":
                model.log("dhcp/renew")
                return NOTHING
            if len(path) >= 2 and path[1] == "find":
                return ROArray([])
        raise KeyError(f"ip/{sub}")


def TO_STR(value):
    """Return a property lookup value unchanged (RouterOS-agnostic)."""
    return value


def _num_arg(named):
    """RouterOS uses both ``number=`` and ``numbers=`` for single interfaces."""
    for k in ("numbers", "number"):
        if k in named:
            return named[k]
    return None