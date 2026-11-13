"""Unit tests for the command layer (router "mocks"): /interface/lte/...,
/ip/..., /tool/fetch, /system/clock, /ping -- executed through the interpreter.
"""

import unittest

from routeros.device_model import DeviceModel
from routeros.interpreter import Interpreter
from routeros.parser import parse
from routeros.values import NOTHING, Time


class CommandCase(unittest.TestCase):
    """Base class: a device model + interpreter, plus the run_ros/var helpers."""

    def setUp(self):
        self.model = DeviceModel()
        self.interp = Interpreter(self.model)

    def run_ros(self, src):
        self.interp.run(parse(src))
        return list(self.interp.output)

    def var(self, name):
        return self.interp.resolve(name, self.interp.root)


class TestLteAtChat(CommandCase):
    """The /interface/lte/at-chat command returns the modem's AT reply."""

    def test_at_chat_returns_iccid(self):
        """:at-chat with AT+ICCID => the reply string "+ICCID: ..." from m.at_chat."""
        self.model.lte = [{".id": "*1", "name": "lte1"}]
        self.model.at_chat = lambda _id, cmd: (
            "+ICCID: 89883010000016182280\r\nOK" if "ICCID" in cmd else "OK")
        self.run_ros(':local out ([/interface/lte/at-chat number=1 input="AT+ICCID" as-value]->"output");')
        self.assertEqual(self.var("out"), "+ICCID: 89883010000016182280\r\nOK")


class TestLteMonitorAndPrint(CommandCase):
    """/interface/lte/monitor and /print: mapping to dicts/rows."""

    def test_monitor_maps_to_dict(self):
        """:monitor numbers=1 once as-value => a dict of fields (incl. rssi)."""
        self.model.lte = [{".id": "*1", "name": "lte1"}]
        self.model.monitor = lambda _id: {"functionality": "full", "rssi": "-75"}
        self.run_ros(":local m [/interface/lte/monitor numbers=1 once as-value];")
        self.assertEqual(self.run_ros(':put ($m->"rssi");'), ["-75"])

    def test_print_as_value_rows(self):
        """:print as-value => an array of interface rows (:len == the row count)."""
        self.model.lte = [{".id": "*1", "name": "lte1", "model": "7600E"}]
        self.run_ros(":local count [:len [/interface/lte/print as-value]];")
        self.assertEqual(self.var("count"), 1)


class TestIpCommands(CommandCase):
    """/ip/route/find and /ip/address/get: filtering by params and records."""

    def test_route_find_matches_params(self):
        """:find passes filter params and returns the ".id" match."""
        self.model.routes = [{"id": "*1", "gateway": "lte1",
                              "dst-address": "192.168.8.0/24", "distance": 0}]
        self.run_ros(":local r [/ip/route/find gateway=lte1 distance=0 dst-address=192.168.8.0/24];")
        self.assertEqual(self.var("r").items, [(0, "*1")])

    def test_address_get_returns_record_with_address(self):
        """waitIpAddress: [get [find interface=..]]->"address" => the interface address."""
        self.model.addresses = {"ISP_1": "192.168.1.5"}
        # waitIpAddress pattern: [find interface=..] -> "address"
        self.run_ros(':local a ([/ip/address/get [find interface=ISP_1]]->"address");')
        self.assertEqual(self.var("a"), "192.168.1.5")


class TestToolFetch(CommandCase):
    """/tool/fetch: capturing qpro.local payloads and E3372 responses."""

    def test_qpro_payload_captured(self):
        """:fetch http-data on qpro.local saves the payload into model.qpro_payloads."""
        self.run_ros(':local x [/tool/fetch url="http://qpro.local/api" output=user http-data=payload as-value];')
        self.assertEqual(len(self.model.qpro_payloads), 1)
        self.assertEqual(self.model.qpro_payloads[0], "payload")

    def test_e3372_api_from_responses(self):
        """:fetch on 192.168.8.1 ..api.. => data from model.e3372_responses."""
        self.model.e3372_responses = {
            "/api/device/information":
                "<r><Iccid>898830100000abcdef0</Iccid></r>",
        }
        self.run_ros(':local d ([/tool/fetch url="http://192.168.8.1/api/device/information" '
                 'output=user as-value]->"data");')
        data = self.var("d")
        self.assertIn("<Iccid>898830100000abcdef0</Iccid>", data)


class TestSystemClock(CommandCase):
    """/system/clock/get: date and time."""

    def test_clock_date_and_time(self):
        """:get date and :get time concatenate into "oct/27/2026 15:04:05"."""
        self.model.clock = {"date": "oct/27/2026", "time": "15:04:05"}
        self.run_ros(':local s ([/system/clock/get date] . " " . [/system/clock/get time]);')
        self.assertEqual(self.var("s"), "oct/27/2026 15:04:05")


class TestPingAndMisc(CommandCase):
    """/ping: depends on m.ping (OK = empty array, otherwise timeout)."""

    def test_ping_true_returns_empty(self):
        """:ping on success returns an empty array."""
        self.model.ping = lambda addr: True
        self.run_ros(":local r [/ping address=8.8.8.8];")
        self.assertEqual(self.var("r").items, [])

    def test_ping_false_returns_timeout(self):
        """:ping on failure returns an array with a "timeout" status."""
        self.model.ping = lambda addr: False
        self.run_ros(":local r [/ping address=8.8.8.8 count=1];")
        self.assertEqual(self.var("r").get("status"), "timeout")


if __name__ == "__main__":
    unittest.main()