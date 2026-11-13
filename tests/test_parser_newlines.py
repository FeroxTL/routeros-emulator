"""Unit tests: a newline as a statement separator and the logical operators || / &&.

RouterOS separates statements with newlines (no mandatory `;`); inside
`[...]`/`(...)`/strings a newline does not break an expression, while inside
`{...}` blocks it separates statements. This lets full migrations run.
"""

import unittest

from routeros.device_model import DeviceModel
from routeros.interpreter import Interpreter
from routeros.parser import parse


class NewlineCase(unittest.TestCase):
    def setUp(self):
        self.interp = Interpreter(DeviceModel())

    def run_ros(self, src):
        self.interp.output.clear()
        self.interp.run(parse(src))
        return list(self.interp.output)


class TestNewlineSeparation(NewlineCase):
    def test_statements_by_newline(self):
        """:local/:put separated by newlines without `;` (as on a device)."""
        self.assertEqual(self.run_ros(':local a 1\n:local b 2\n:put ($a . $b)\n:put "done"'),
                         ["12", "done"])

    def test_multiline_if_else(self):
        """if/else block over several lines without `;`: `else` separated by a newline."""
        src = (':if (1 = 1) do={\n'
               '  :local x 10\n'
               '  :put $x\n'
               '}\n'
               'else={\n'
               '  :put "no"\n'
               '}\n')
        self.assertEqual(self.run_ros(src), ["10"])

    def test_oneline_do_block_command_before_brace(self):
        """:do { /command } on-error={...} -- a command ends at `}` without `;`."""
        self.assertEqual(self.run_ros(':do { :put "inner" } on-error={ :put "err" };'), ["inner"])

    def test_migration_step0_like(self):
        """Like 001.018 step 0: if+command+log+put over lines without semicolons."""
        src = (':if ([:len [/file/find name~"nope"]] = 0) do={\n'
               '  :log info "no backup\"\n'
               '  :put "creating"\n'
               '} else={\n'
               '  :put "exists"\n'
               '}\n')
        self.assertEqual(self.run_ros(src), ["creating"])

    def test_newline_inside_brackets_does_not_split(self):
        """: A newline inside `[...]` does NOT break the command."""
        src = (':local n [\n'
               '  :len "abcd"\n'
               ']\n'
               ':put $n\n')
        self.assertEqual(self.run_ros(src), ["4"])


class TestLogicalPipeOps(NewlineCase):
    """|| and && are valid RouterOS logical operators (verified on 7.9)."""

    def test_pipe_pipe(self):
        self.assertEqual(self.run_ros(':put (true || false);'), ["true"])
        self.assertEqual(self.run_ros(':put (false || true);'), ["true"])
        self.assertEqual(self.run_ros(':put (false || false);'), ["false"])

    def test_amp_amp(self):
        self.assertEqual(self.run_ros(':put (true && true);'), ["true"])
        self.assertEqual(self.run_ros(':put (true && false);'), ["false"])

    def test_mixed_with_keywords(self):
        self.assertEqual(
            self.run_ros(':put (((1 = 1) || (2 = 3)) && (4 > 0));'), ["true"])


if __name__ == "__main__":
    unittest.main()
