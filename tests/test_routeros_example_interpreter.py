"""Integration tests: call the :global functions of `examples/modem_report.rsl`
(getTag, extractDigits) directly, without running the script's entry-point. This
stands in for the emulator's ability to load a real script as a library."""

import io
import os
import unittest

from routeros.device_model import DeviceModel
from routeros.launcher import load_file
from routeros.repl import Repl

_SCRIPT = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                       "examples", "modem_report.rsl")


def load(model, run_main=False):
    return load_file(_SCRIPT, model, run_main=run_main, main_name="makeReport")


class TestExampleFunctions(unittest.TestCase):
    """Single functions straight out of the example script."""

    def setUp(self):
        self.script = load(DeviceModel())

    def test_getTag(self):
        out = self.script.call("getTag", named={
            "tag": "Iccid",
            "src": "<r><Iccid>89883010000016182280</Iccid></r>",
        })
        self.assertEqual(out, "89883010000016182280")

    def test_getTag_missing(self):
        out = self.script.call("getTag", named={
            "tag": "Rssi",
            "src": "<r><Iccid>x</Iccid></r>",
        })
        self.assertEqual(out, "")

    def test_extractDigits(self):
        out = self.script.call(
            "extractDigits", args=["+ICCID: 89883010000016182280\r\nOK"])
        self.assertEqual(out, "89883010000016182280")

    def test_load_skips_entry_point(self):
        # run_main=False + main_name=makeReport -> [makeReport] never ran
        self.assertEqual(self.script.array("Report")["ping"], "")


class TestExampleREPL(unittest.TestCase):
    """:load of the example defines functions without running the entry-point."""

    def test_load_defines_functions_without_main(self):
        r = Repl(main_name="makeReport")
        out = io.StringIO()
        r.run(io.StringIO(f":load {_SCRIPT}\n"
                          f'[$getTag tag="Iccid" src="<r><Iccid>abc</Iccid></r>"]\n'),
              out)
        text = out.getvalue()
        self.assertTrue(text.startswith("loaded "), text)
        self.assertIn("abc", text)
        # The entry-point must NOT have run: collect() would have called ping/at-chat
        # and logged effects, so the model must be completely untouched.
        self.assertEqual(r.interp.model.effects, [])
        self.assertEqual(r.interp.model.qpro_payloads, [])


if __name__ == "__main__":
    unittest.main()