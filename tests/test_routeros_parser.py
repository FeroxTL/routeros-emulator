"""Unit tests for the RouterOS parser (tokens -> AST)."""

import unittest

from routeros import ast as A
from routeros.parser import parse


def stmts(src):
    return parse(src).statements


class TestDeclParams(unittest.TestCase):
    """:global/:local declarations and their values."""

    def test_global_with_equals(self):
        """:global x = {...} is a Decl with a name and an array value."""
        s = stmts(':global Config {imei="";};')
        self.assertEqual(len(s), 1)
        self.assertIsInstance(s[0], A.Decl)
        self.assertEqual(s[0].kind, "global")
        self.assertEqual(s[0].name, "Config")

    def test_global_without_equals_ok(self):
        """:global without `=` needs no value."""
        s = stmts(":global x {a=1};\n:global y 5;")
        self.assertEqual(len(s), 2)
        self.assertEqual(s[1].name, "y")

    def test_local_without_value_is_none(self):
        """:local a without a value => value = None."""
        s = stmts(":local a;")
        self.assertIsNone(s[0].value)


class TestIfAndBlocks(unittest.TestCase):
    """:if/:else and :do{:}on-error={:}."""
    def test_if_else_parses(self):
        """:if (cond) do={} else={} => an A.If node."""
        s = stmts(":if (true) do={:put 1;} else={:put 0;};")
        self.assertEqual(len(s), 1)
        self.assertIsInstance(s[0], A.If)

    def test_do_catch(self):
        """:do{:}on-error={:} => a DoCatch node with a catch branch."""
        s = stmts(":do {:local x 1;} on-error={:put 0;};")
        self.assertIsInstance(s[0], A.DoCatch)
        self.assertTrue(s[0].catch)


class TestLoopsAndFuncs(unittest.TestCase):
    """:for/:foreach and inline functions do={...}."""
    def test_for_with_ranges_and_times(self):
        """:for x from=1 to=15 => an A.For with a variable name."""
        s = stmts(":for x from=1 to=15 do={:delay 1s;};")
        f = s[0]
        self.assertIsInstance(f, A.For)
        self.assertEqual(f.var, "x")

    def test_foreach_in_equals(self):
        """:foreach k,v in=$arr => a Foreach with a key and a value."""
        s = stmts(":foreach k,v in=$arr do={:put ($k . $v);};")
        f = s[0]
        self.assertIsInstance(f, A.Foreach)
        self.assertEqual(f.key, "k")
        self.assertEqual(f.val, "v")

    def test_local_function_do_block(self):
        """:local f do={...} is initialized with an inline function (FuncLit)."""
        s = stmts(":local f do={:return ($1 * 2);};")
        self.assertIsInstance(s[0], A.Decl)
        self.assertIsInstance(s[0].value, A.FuncLit)


class TestExpressions(unittest.TestCase):
    """Expressions: precedence, literals, arrays, bracket commands."""
    def test_precedence_times_over_plus(self):
        """:* over +: 2 + 3*4 => the BinOp root is "+"."""
        s = stmts(":local v (2 + 3 * 4);")
        node = s[0].value
        self.assertIsInstance(node, A.BinOp)
        self.assertEqual(node.op, "+")

    def test_division(self):
        """:put (10 / 4) is a Put node with binary division."""
        s = stmts(":put (10 / 4);")
        self.assertIsInstance(s[0], A.Put)

    def test_list_literal_and_member(self):
        """:put ($x->"key") accesses an array through a Member node."""
        s = stmts(":put ($x->\"key\");")
        put = s[0]
        self.assertIsInstance(put, A.Put)
        self.assertIsInstance(put.value, A.Member)

    def test_array_literal_entries(self):
        """:local a {imei=;iccid=;} is an array with key/value entries."""
        s = stmts(':local a {imei="";iccid="";};')
        lit = s[0].value
        self.assertIsInstance(lit, A.ArrayLit)
        self.assertEqual(len(lit.entries), 2)

    def test_time_literal_value(self):
        """:put (1s) — a duration is parsed; a Put node."""
        s = stmts(":put (1s);")
        # 1s is a duration token -> Time value
        self.assertIsInstance(s[0], A.Put)

    def test_command_bracket(self):
        """:local x [/interface/lte/print] is a bracket command in an expression."""
        s = stmts(":local x [/interface/lte/print as-value];")
        self.assertIsInstance(s[0], A.Decl)
        expr = s[0].value
        self.assertIsInstance(expr, A.Bracket)
        self.assertEqual(expr.name, "/interface/lte/print")


if __name__ == "__main__":
    unittest.main()