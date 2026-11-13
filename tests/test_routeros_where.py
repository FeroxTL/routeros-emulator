"""Unit tests: `where`-predicate support in the RouterOS emulator.

Verified against a real device via diff_tests/14_where.rsc and SSH probes:
find / print as-value filter records by their properties; `=`, `!=`, `~`,
`< > <= >=`, `in` (CIDR), `and`/`or`, parentheses and the bool `yes`/`no`
coercion are supported.
"""

import unittest

from routeros.device_model import DeviceModel
from routeros.interpreter import Interpreter
from routeros.parser import parse


class WhereCase(unittest.TestCase):
    """Base class: a model, an interpreter and helpers."""

    def setUp(self):
        self.model = DeviceModel()
        self.interp = Interpreter(self.model)

    def run_ros(self, src):
        self.interp.output.clear()
        self.interp.run(parse(src))
        return list(self.interp.output)


class TestWhereOvpn(WhereCase):
    """Predicates over /interface/ovpn-client."""

    def setUp(self):
        super().setUp()
        self.model.ovpn = [
            {"id": "*e", "name": "ovpn_msk_ixc_01", "running": True,
             "connect-to": "194.49.121.49"},
            {"id": "*f", "name": "ovpn_msk_ixc_02", "running": True,
             "connect-to": "194.49.121.50"},
            {"id": "*g", "name": "ovpn_old", "running": False},
        ]

    def test_find_where_name(self):
        """:find where name=... returns the id of the matching record."""
        self.assertEqual(self.run_ros(':put [/interface/ovpn-client/find where name="ovpn_msk_ixc_02"];'),
                         ["*f"])
        self.assertEqual(self.run_ros(':put [:len [/interface/ovpn-client/find where name="ovpn_msk_ixc_zzz"]];'),
                         ["0"])

    def test_guard_second_tunnel(self):
        """Core guard of migration 001.018: before tunnel-2 exists -> 0 (apply)."""
        self.model.ovpn = [{"id": "*e", "name": "ovpn_msk_ixc_01", "running": True}]
        self.assertEqual(self.run_ros(':put [:len [/interface/ovpn-client/find where name="ovpn_msk_ixc_02"]];'),
                         ["0"])

    def test_where_running_bool(self):
        """:where running / running=yes / running=no -- as on a device."""
        self.assertEqual(self.run_ros(':put [:len [/interface/ovpn-client/find where running]];'), ["2"])
        self.assertEqual(self.run_ros(':put [:len [/interface/ovpn-client/find where running=yes]];'), ["2"])
        self.assertEqual(self.run_ros(':put [:len [/interface/ovpn-client/find where running=no]];'), ["1"])

    def test_where_and_noteq(self):
        """:where with and / != ."""
        self.assertEqual(
            self.run_ros(':put [:len [/interface/ovpn-client/find where running and name!="ovpn_old"]];'), ["2"])

    def test_where_in_array(self):
        """:where property in { ... }."""
        self.assertEqual(
            self.run_ros(':put [:len [/interface/ovpn-client/find where connect-to in {"194.49.121.50"}]];'),
            ["1"])

    def test_where_value_from_var(self):
        """:where name=($var) -- value injected from a variable."""
        self.assertEqual(
            self.run_ros(':local want "ovpn_msk_ixc_01"; '
                         ':put [:len [/interface/ovpn-client/find where name=($want)]];'), ["1"])


class TestWhereRoutes(WhereCase):
    """:where over /ip/route: comment, numeric comparisons, print as-value."""

    def setUp(self):
        super().setUp()
        self.model.routes = [
            {"id": "*1", "dst-address": "10.4.0.0/14", "gateway": "10.4.240.1",
             "distance": 221, "comment": "===adding_ovpn_msk_ixc_01==="},
            {"id": "*2", "dst-address": "10.4.0.0/14", "gateway": "10.4.248.1",
             "distance": 222, "comment": "===adding_ovpn_msk_ixc_02==="},
            {"id": "*3", "dst-address": "0.0.0.0/0", "gateway": "lte1",
             "distance": 1, "comment": ""},
        ]

    def test_route_where_comment(self):
        self.assertEqual(
            self.run_ros(':put [:len [/ip/route/find where comment="===adding_ovpn_msk_ixc_02==="]];'), ["1"])
        self.assertEqual(
            self.run_ros(':put [:len [/ip/route/find where comment]];'), ["2"])  # non-empty comment

    def test_route_where_numeric(self):
        self.assertEqual(self.run_ros(':put [:len [/ip/route/find where distance>5]];'), ["2"])

    def test_route_where_in_array(self):
        self.assertEqual(
            self.run_ros(':put [:len [/ip/route/find where gateway in {"10.4.240.1"; "10.4.248.1"}]];'), ["2"])

    def test_route_print_as_value_where(self):
        out = self.run_ros(':foreach x in=[/ip/route/print as-value where comment] '
                           'do={:put ($x->"comment")};')
        self.assertEqual(out, ["===adding_ovpn_msk_ixc_01===", "===adding_ovpn_msk_ixc_02==="])


class TestWhereDataMenus(WhereCase):
    """:where over other menus: addresses/files/address-list."""

    def test_address_print_as_value_where_tilde(self):
        self.model.addresses = {"Local_Network": "192.168.1.1/24",
                                "lte1": "192.168.8.100/24",
                                "ovpn_msk_ixc_01": "10.4.240.4/21"}
        out = self.run_ros(':foreach x in=[/ip/address/print as-value where interface~"ovpn"] '
                           'do={:put ($x->"address")};')
        self.assertEqual(out, ["10.4.240.4/21"])

    def test_file_find_where_or(self):
        self.model.files = {"a.crt": "x", "b.key": "y", "config": "z"}
        self.assertEqual(
            self.run_ros(':put [:len [/file/find where (name~".crt") or (name~".key")]];'), ["2"])

    def test_address_list_find_where_address(self):
        self.model.address_lists = [
            {"id": "*1", "address": "91.197.67.140", "list": "blocked"},
            {"id": "*2", "address": "10.4.248.0/21", "list": "ixc_ovpn_02_tunnel"},
        ]
        self.assertEqual(
            self.run_ros(':put [:len [/ip/firewall/address-list/find where address="91.197.67.140"]];'), ["1"])
        self.assertEqual(
            self.run_ros(':put [:len [/ip/firewall/address-list/find where address="90.189.155.185"]];'), ["0"])


class TestWhereOperatorSemantics(WhereCase):
    """Coercions and operators inside/outside `where` (verified with 14_where.rsc)."""

    def test_numeric_string_eq(self):
        self.assertEqual(self.run_ros(':put (1 = "1");'), ["true"])

    def test_bool_string_eq(self):
        # plain `=` does NOT coerce bool<->string (unlike `where running=yes`)
        self.assertEqual(self.run_ros(':put (true = "yes");'), ["false"])

    def test_tilde_and_in(self):
        self.assertEqual(self.run_ros(':put ("abc" ~ "b");'), ["true"])
        self.assertEqual(self.run_ros(':put (192.168.8.1 in "192.168.0.0/16");'), ["true"])


class TestParamOpAndLog(WhereCase):
    """The filter-via-parameter form (`find name~"x"`) rather than `where`, and :log."""

    def test_find_name_tilde_param(self):
        """:file/find name~"pattern" -- a filter param (as in 001.018 step 0)."""
        self.model.files = {"untill_ixc_adding_phase2.backup": "x", "config": "z"}
        self.assertEqual(
            self.run_ros(':put [:len [/file/find name~"untill_ixc_adding_phase2"]];'), ["1"])

    def test_log_bare_message(self):
        """:log info "text" (the canonical device form) parses and runs."""
        self.run_ros(':log info "hello world";')


if __name__ == "__main__":
    unittest.main()
