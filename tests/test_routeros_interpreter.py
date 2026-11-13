"""Unit tests for the interpreter core: execution of AST nodes."""

import unittest

from routeros.device_model import DeviceModel
from routeros.interpreter import Interpreter, ReturnSignal
from routeros.parser import parse
from routeros.values import NOTHING, Time


class InterpCase(unittest.TestCase):
    def setUp(self):
        self.interp = Interpreter(DeviceModel())

    def run_ros(self, src):
        prog = parse(src)
        try:
            self.interp.run(prog)
        except ReturnSignal as r:
            return r.value
        return list(self.interp.output)

    def var(self, name):
        return self.interp.resolve(name, self.interp.root)


class TestVariables(InterpCase):
    """:local/:global declarations and `:set` assignment."""

    def test_local_persist_in_shared_root(self):
        """:local outlives a call — the variable persists between lines."""
        self.run_ros(":local a 5;")
        self.assertEqual(self.var("a"), 5)

    def test_global_assignment(self):
        """:global puts a value into the root environment."""
        self.run_ros(":global x \"hello\";")
        self.assertEqual(self.var("x"), "hello")

    def test_set_member(self):
        """:set via `->"key"` changes a field of a nested dict."""
        self.run_ros(":local x {a=\"\";};")
        self.run_ros(':set ($x->"a") "1";')
        self.assertEqual(self.run_ros(':put ($x->"a");'), ["1"])

    def test_set_without_equals(self):
        """:set works on an existing variable without the `=` part too."""
        self.run_ros(":local y;")
        self.run_ros(":set y 3;")
        self.assertEqual(self.var("y"), 3)


class TestOperators(InterpCase):
    """Arithmetic, comparisons, concatenation, `in` — verified against 7.9 hardware."""
    def test_concat_and_arith(self):
        """.` is concatenation; `/` is integer division (10/4 => 2); `%` is modulo."""
        self.run_ros(':put ("a" . "b");')
        self.assertEqual(self.interp.output[-1], "ab")
        # RouterOS divides as integers with truncation (verified on a real 7.9 device):
        # :put (10 / 4) prints 2, not 2.5
        self.run_ros(":put (10 / 4);")
        self.assertEqual(self.interp.output[-1], "2")
        self.run_ros(":put (7 / 2);")
        self.assertEqual(self.interp.output[-1], "3")
        self.run_ros(":put (5 % 2);")
        self.assertEqual(self.interp.output[-1], "1")

    def test_binary_minus(self):
        """Minus as on a device: 10-4 => 6, 10--4 => 14, 5--3 => 8 (binary),
        while (-3 + 2) is a unary negative literal."""
        self.run_ros(":put (10-4);")
        self.assertEqual(self.interp.output[-1], "6")
        self.run_ros(":put (10 -4);")
        self.assertEqual(self.interp.output[-1], "6")
        self.run_ros(":put (10--4);")
        self.assertEqual(self.interp.output[-1], "14")
        self.run_ros(":put (5--3);")
        self.assertEqual(self.interp.output[-1], "8")
        # unary minus stays a negative literal
        self.run_ros(":put (-3 + 2);")
        self.assertEqual(self.interp.output[-1], "-1")

    def test_comparison_and_logic(self):
        """Relational operators and `and`/`or` return true/false."""
        self.run_ros(":put (2 < 3);")
        self.assertEqual(self.interp.output[-1], "true")
        self.run_ros(":put (true and false);")
        self.assertEqual(self.interp.output[-1], "false")

    def test_time_arithmetic(self):
        """Adding durations: 1s + 2s => a Time of 3.0 seconds."""
        self.run_ros(":local t (1s + 2s);")
        self.assertIsInstance(self.var("t"), Time)
        self.assertEqual(self.var("t").seconds, 3.0)

    def test_in_roarray(self):
        """`in` checks that an element belongs to an array."""
        self.run_ros(':put (2 in {1;2;3});')
        self.assertEqual(self.interp.output[-1], "true")


class TestBuiltins(InterpCase):
    """:find, :pick, :len, :tostr, :tobool, :typeof."""
    def test_find_start_position(self):
        """:find from a start position finds a substring after the given index."""
        self.run_ros(':put [:find "hello world" "o" 5];')
        self.assertEqual(self.interp.output[-1], "7")

    def test_find_substr(self):
        """:find returns an index (>= 0) when the substring matches."""
        self.run_ros(':put ([:find "abc" "b"] >= 0);')
        self.assertEqual(self.interp.output[-1], "true")

    def test_pick_and_len(self):
        """:pick (a slice) and :len — the length of a string."""
        self.run_ros(':put [:pick "abcdef" 1 4];')
        self.assertEqual(self.interp.output[-1], "bcd")
        self.run_ros(':put [:len "abc"];')
        self.assertEqual(self.interp.output[-1], "3")

    def test_tostr_bool_typeof(self):
        """:tostr of a number; :tobool of a string gives "nothing" on a device; :typeof => num."""
        self.run_ros(":put [:tostr 5];")
        self.assertEqual(self.interp.output[-1], "5")
        # :tobool of a string gives "nothing" on a real device, not true
        self.run_ros(":put [:tobool \"yes\"];")
        self.assertEqual(self.interp.output[-1], "")
        self.run_ros(":put [:typeof 5];")
        self.assertEqual(self.interp.output[-1], "num")


class TestControlFlow(InterpCase):
    """if/else, foreach, for, do{}on-error, functions do={...}; no break/continue in RouterOS."""
    def test_if_else(self):
        """:if (condition) picks a branch by a boolean condition."""
        self.run_ros(":if (true) do={:put 1;} else={:put 0;};")
        self.assertEqual(self.interp.output[-1], "1")

    def test_foreach_kv_and_single(self):
        """:foreach over a dict: `k,v in={...}` enumerates key/value pairs."""
        self.run_ros(":local s \"\";")
        self.run_ros(':foreach k,v in={a=1;b=2;} do={:set s ($s . $k . $v . \",\");};')
        self.assertEqual(self.var("s"), "a1,b2,")

    def test_for_loop(self):
        """:for x from=1 to=3 steps by 1 (the default)."""
        self.run_ros(":local s \"\";")
        self.run_ros(":for x from=1 to=3 do={:set s ($s . $x);};")
        self.assertEqual(self.var("s"), "123")

    def test_do_catch_on_error(self):
        """:do{}on-error={} catches an exception from the body and runs the catch branch."""
        self.run_ros(":local caught false;")
        # division by literal on strings would raise -> caught branch runs
        self.run_ros(":do {:[$nonexistentfn];} on-error={:set caught true;};")
        self.assertEqual(self.var("caught"), True)

    def test_func_literal_and_call(self):
        """:local d do={...} is an inline function; call [$d 21] with $1..$n args."""
        self.run_ros(":local d do={:return ($1 * 2);};")
        self.run_ros(":put [$d 21];")
        self.assertEqual(self.interp.output[-1], "42")


class TestIP(InterpCase):
    """The `ip` type (dotted literals) vs hardware: rendering, typeof, arithmetic, comparison."""
    def test_literal_render(self):
        """Canonical ip rendering: 2.5 => 2.0.0.5, 1.2.3 => 1.2.0.3 (as on a device)."""
        self.run_ros(":put (1.2.3.4);")
        self.assertEqual(self.interp.output[-1], "1.2.3.4")
        self.run_ros(":put (2.5);")
        self.assertEqual(self.interp.output[-1], "2.0.0.5")
        self.run_ros(":put (1.2.3);")
        self.assertEqual(self.interp.output[-1], "1.2.0.3")
        self.run_ros(":put (10.0);")
        self.assertEqual(self.interp.output[-1], "10.0.0.0")

    def test_typeof_and_arith(self):
        """:typeof(1.2)=ip; `+`/`-` act as a 32-bit integer over ip (0.1+0.2 => 0.0.0.3)."""
        self.run_ros(':put [:typeof (1.2)];')
        self.assertEqual(self.interp.output[-1], "ip")
        self.run_ros(":put (0.1 + 0.2);")
        self.assertEqual(self.interp.output[-1], "0.0.0.3")
        self.run_ros(":put (2.5 + 1);")
        self.assertEqual(self.interp.output[-1], "2.0.0.6")
        self.run_ros(":put (1.2 + 1.3);")
        self.assertEqual(self.interp.output[-1], "2.0.0.5")
        self.run_ros(":put (2.5 - 1);")
        self.assertEqual(self.interp.output[-1], "2.0.0.4")

    def test_cmp(self):
        """ip comparisons: only ip↔ip; `ip = num` => false."""
        self.run_ros(":put (0.1 < 0.2);")
        self.assertEqual(self.interp.output[-1], "true")
        self.run_ros(":put (1.2 > 1.1);")
        self.assertEqual(self.interp.output[-1], "true")
        self.run_ros(":put (2.5 = 2.5);")
        self.assertEqual(self.interp.output[-1], "true")
        self.run_ros(":put (0.0.0.1 = 1);")
        self.assertEqual(self.interp.output[-1], "false")


class TestControl(InterpCase):
    """:for step=, do{}while=(), :error+on-error, and `not` as an empty prefix / NOT=`!`."""
    def test_for_step(self):
        """:for step= — a custom step: 3..1 step=-1 => 321, 1..5 step=2 => 135."""
        self.run_ros(':local s ""; :for i from=3 to=1 step=-1 do={:set s ($s . $i)}; :put $s;')
        self.assertEqual(self.interp.output[-1], "321")
        self.run_ros(':local s ""; :for i from=1 to=5 step=2 do={:set s ($s . $i)}; :put $s;')
        self.assertEqual(self.interp.output[-1], "135")

    def test_dowhile(self):
        """:do{...}while=(cond) runs the body before checking the condition."""
        self.run_ros(':local s "0"; :local i 0; :do {:set s ($s . $i); :set i ($i+1)} while=($i < 3); :put $s;')
        self.assertEqual(self.interp.output[-1], "0012")

    def test_error_onerror(self):
        """:error inside :do{}on-error={} is caught by the catch branch."""
        self.run_ros(':do {:error "boom"} on-error={:put "caught"};')
        self.assertEqual(self.interp.output[-1], "caught")

    def test_not_identity_and_bang(self):
        """On a device `not` is an empty prefix ((not X)=>X); logical NOT is `!`."""
        self.run_ros(':put (not false);')
        self.assertEqual(self.interp.output[-1], "false")
        self.run_ros(':put (not 7);')
        self.assertEqual(self.interp.output[-1], "7")
        self.run_ros(":put (!false);")
        self.assertEqual(self.interp.output[-1], "true")
        self.run_ros(":put (!true);")
        self.assertEqual(self.interp.output[-1], "false")


if __name__ == "__main__":
    unittest.main()