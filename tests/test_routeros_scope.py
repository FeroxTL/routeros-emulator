"""Unit tests: variable scope and function isolation in the RouterOS emulator.

Semantics are device-verified (via SSH probes against a real RouterOS box):

* A `:global`/`:local`'s first declaration fixes the kind for the execution —
  a later `:local name` cannot shadow an existing `:global`, a later
  `:global name` is likewise ignored when the name was `:local` first, while a
  same-kind redeclaration updates the value.
* A `:local` declared in the global scope is available for the rest of the same
  script, but it is NOT visible inside functions.
* Functions are fully isolated: only parameters, their own `:local`s and globals
  explicitly referenced with `:global name;` inside the body are visible there.
* Inside a function `:set $name` writes through to the persistent global.
"""

import unittest

from routeros.device_model import DeviceModel
from routeros.interpreter import Interpreter
from routeros.parser import parse


class ScopeCase(unittest.TestCase):
    """Base class: a fresh interpreter per test (so no cross-test state)."""

    def setUp(self):
        self.interp = Interpreter(DeviceModel())

    def run_ros(self, src):
        self.interp.output.clear()
        self.interp.run(parse(src))
        return list(self.interp.output)


class TestFirstDeclarationWins(ScopeCase):
    """The first :global/:local binding fixes the variable's kind."""

    def test_local_available_later_in_same_script(self):
        self.assertEqual(self.run_ros(":local x 7\n:put $x"), ["7"])

    def test_local_cannot_shadow_existing_global(self):
        # global declared first -> the :local is a no-op; reads resolve to 1.
        self.assertEqual(self.run_ros(":global y 1\n:local y 5\n:put $y"), ["1"])

    def test_global_cannot_rebind_a_local(self):
        # local declared first -> the :global is a no-op; reads resolve to 9.
        self.assertEqual(self.run_ros(":local yy 9\n:global yy 2\n:put $yy"), ["9"])

    def test_same_kind_local_redeclare_updates(self):
        self.assertEqual(self.run_ros(":local y 1\n:local y 2\n:put $y"), ["2"])

    def test_same_kind_global_redeclare_updates(self):
        self.assertEqual(self.run_ros(":global z 1\n:global z 2\n:put $z"), ["2"])

    def test_local_read_followed_by_local_shadow_is_ignored(self):
        # global read returns 1 both before and after the ineffective :local.
        out = self.run_ros(":global m 1\n:put $m\n:local m 9\n:put $m")
        self.assertEqual(out, ["1", "1"])


class TestFunctionIsolation(ScopeCase):
    """Functions see only params, their own :locals and declared globals."""

    def test_function_does_not_see_outer_local(self):
        # device: fn returns nothing, top-level :local still 123.
        out = self.run_ros(":local foo 123\n:local f do={:return $foo}\n"
                           ":put [$f]\n:put $foo")
        self.assertEqual(out, ["", "123"])

    def test_function_does_not_see_outer_global(self):
        # A global is NOT visible inside a function until `:global name;` is
        # issues in the function body itself.
        self.assertEqual(self.run_ros(":global bar 42\n"
                                      ":global h do={:return $bar}\n:put [$h]"), [""])

    def test_function_sees_global_after_local_declaration(self):
        out = self.run_ros(":global bar 42\n"
                           ":global h do={:global bar; :return $bar}\n"
                           ":put [$h]\n:put $bar")
        self.assertEqual(out, ["42", "42"])

    def test_set_writes_through_to_global(self):
        out = self.run_ros(":global x 10\n"
                           ":global f do={:global x; :set $x 99; :return $x}\n"
                           ":put [$f]\n:put $x")
        self.assertEqual(out, ["99", "99"])

    def test_function_local_does_not_leak_out(self):
        out = self.run_ros(":global f do={:local q 5; :return $q}\n"
                           ":put [$f]\n:put $q")
        self.assertEqual(out, ["5", ""])


if __name__ == "__main__":
    unittest.main()