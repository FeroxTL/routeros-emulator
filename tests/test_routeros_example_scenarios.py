"""Integration tests: run the full entry-point of `examples/modem_report.rsl`
(makeReport) against different device setups and inspect the populated global
array `Report`. Mirrors the AT-chat / HTTP-API (E3372) limbs of real modems."""

import os
import unittest

from routeros.device_model import DeviceModel
from routeros.launcher import load_file

_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                       "examples", "modem_report.rsl")


class TestExampleScenarios(unittest.TestCase):
    def report_for(self, model):
        return load_file(_SCRIPT, model, run_main=True,
                         main_name="makeReport").array("Report")

    @staticmethod
    def _at_model(model_name):
        m = DeviceModel()
        m.lte = [{".id": "*1", "name": "lte1", "model": model_name}]
        m.monitor = lambda _id: {
            "imei": "864199030000000",
            "imsi": "250021234567890",
            "rssi": "-75",
            "model": model_name,
        }
        m.ping = lambda addr: True
        return m

    def test_simcom_at_modem(self):
        m = self._at_model("7600E V2")
        m.at_chat = lambda _id, cmd: (
            "+ICCID: 89883010000016182280\r\nOK" if "ICCID" in cmd else "OK")
        v = self.report_for(m)
        self.assertEqual(v["model"], "7600E V2")
        self.assertEqual(v["iccid"], "89883010000016182280")
        self.assertEqual(v["rssi"], "-75")
        self.assertEqual(v["ping"], "8.8.8.8")
        self.assertNotEqual(v["collected-at"], "")

    def test_me909_uses_at_chat_digits(self):
        # Any non-E3372 model takes the AT+ICCID path and the digit-only extractor.
        m = self._at_model("ME909s-120 V2")
        m.at_chat = lambda _id, cmd: "AT+ICCID\r\n+ICCID: 12345678901234567890\r\n"
        v = self.report_for(m)
        self.assertEqual(v["model"], "ME909s-120 V2")
        self.assertEqual(v["iccid"], "12345678901234567890")
        self.assertEqual(v["ping"], "8.8.8.8")

    def test_e3372_web_api(self):
        m = DeviceModel()
        m.lte = [{".id": "*1", "name": "lte1", "model": "E3372h-153"}]
        m.monitor = lambda _id: {"model": "E3372h-153", "rssi": "-51dBm"}
        m.e3372_responses = {
            "/api/webserver/SesTokInfo":
                "<response><SesInfo>token123</SesInfo></response>",
            "/api/device/information":
                "<response><DeviceName>E3372h-153</DeviceName>"
                "<Imei>864199030000000</Imei><Iccid>898830100000abcdef0</Iccid></response>",
        }
        m.ping = lambda addr: True
        v = self.report_for(m)
        self.assertEqual(v["model"], "E3372h-153")
        self.assertEqual(v["iccid"], "898830100000abcdef0")

    def test_report_empty_ping_when_unreachable(self):
        m = self._at_model("7600E V2")
        m.at_chat = lambda _id, cmd: (
            "+ICCID: 89883010000016182280\r\nOK" if "ICCID" in cmd else "OK")
        m.ping = lambda addr: False
        v = self.report_for(m)
        self.assertEqual(v["ping"], "")


if __name__ == "__main__":
    unittest.main()