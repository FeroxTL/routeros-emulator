"""Unit tests for the RouterOS tokenizer (string -> tokens)."""

import unittest

from routeros.tokenizer import tokenize
from routeros.values import IPValue, NOTHING


def kinds(src):
    return [(t.kind, t.value) for t in tokenize(src)]


class TestNumbersAndDurations(unittest.TestCase):
    """Numbers (incl. `-` tokenization), durations, time, ip literals."""
    def test_int(self):
        """Integer `42` => a num token."""
        self.assertEqual(kinds("42")[0], ("num", 42))

    def test_negative_and_float(self):
        """`-3` is a negative literal; a dotted literal is the ip type (not a float)."""
        self.assertEqual(kinds("-3")[0], ("num", -3))
        # a dotted literal is the ip type, not a float
        self.assertEqual(kinds("1.5")[0][0], "ip")
        self.assertEqual(kinds("1.5")[0][1].value, 0x01000005)
        self.assertEqual(str(kinds("1.2.3.4")[0][1]), "1.2.3.4")
        self.assertEqual(str(kinds("2.5")[0][1]), "2.0.0.5")
        self.assertEqual(str(kinds("1.2.3")[0][1]), "1.2.0.3")

    def test_binary_minus(self):
        """Device: 10-4/10 -4/10--4 is subtraction; unary `-` only "at the start"."""
        self.assertEqual(kinds("10-4"), [("num", 10), ("op", "-"), ("num", 4), ("eof", NOTHING)])
        self.assertEqual(kinds("10 -4")[1], ("op", "-"))
        self.assertEqual(kinds("10 --4"), [("num", 10), ("op", "-"), ("num", -4), ("eof", NOTHING)])
        # unary minus after a "("/an operator stays a negative literal
        self.assertEqual(kinds("-3")[0], ("num", -3))
        self.assertEqual(kinds("(5 + -3)")[3], ("num", -3))
        # a word with hyphens and letters is not split
        self.assertEqual(kinds("to-string")[0][0], "word")

    def test_duration(self):
        """Durations: 5s, 2.5s, 1m => seconds as float."""
        self.assertEqual(kinds("5s")[0], ("dur", 5.0))
        self.assertEqual(kinds("2.5s")[0], ("dur", 2.5))
        self.assertEqual(kinds("1m")[0], ("dur", 60.0))

    def test_clock_time(self):
        """HH:MM:SS => time in seconds."""
        self.assertEqual(kinds("00:05:00")[0], ("time", 300.0))


class TestStrings(unittest.TestCase):
    """String literals: double quotes with `$var` interpolation, single quotes without, escapes."""
    def test_double_quoted_interpolates(self):
        """Double quotes parse literals and $var for interpolation."""
        self.assertEqual(kinds('"a$b c"')[0], ("str", [("lit", "a"), ("var", "b"), ("lit", " c")]))

    def test_single_quoted_no_interpolation(self):
        """'...' — no interpolation; single quotes and `$` are literal."""
        self.assertEqual(kinds("'no$interp'")[0], ("str", [("lit", "no$interp")]))

    def test_escapes(self):
        """Escape sequences (\\n etc.) are resolved in the string."""
        self.assertEqual(kinds('"a\\nb"')[0], ("str", [("lit", "a\nb")]))


class TestKeywordsOperators(unittest.TestCase):
    """Keywords (`:local`), punctuation, operators, `$var`, command paths."""
    def test_keyword(self):
        """`:` + word => a keyword (kw)."""
        self.assertEqual(kinds(":local")[0], ("kw", "local"))

    def test_punctuation(self):
        """Separators (){}[]; are op tokens."""
        toks = [t.kind for t in tokenize("(){}[];") if t.kind != "eof"]
        self.assertEqual(toks, ["op"] * 7)

    def test_operators(self):
        """Binary operators (10 / 4) split into separate tokens."""
        vals = [t.value for t in tokenize("10 / 4") if t.kind != "eof"]
        self.assertEqual(vals, [10, "/", 4])

    def test_member_arrow(self):
        """Access `$x->"key"`: a var, the `->` arrow, a string key."""
        toks = tokenize("$x->\"a\"")
        self.assertEqual(toks[0].kind, "var")
        self.assertEqual(toks[1].value, "->")
        self.assertEqual(toks[2].kind, "str")

    def test_command_path_is_single_word(self):
        """The command path `/interface/lte/monitor` is one word."""
        toks = tokenize("/interface/lte/monitor")
        self.assertEqual(toks[0].kind, "word")
        self.assertEqual(toks[0].value, "/interface/lte/monitor")
        self.assertEqual(len(toks), 2)  # + eof

    def test_boolean_keywords_stay_words(self):
        """true/false are words (not nums) in the tokenizer."""
        self.assertEqual(kinds("true")[0], ("word", "true"))
        self.assertEqual(kinds("false")[0], ("word", "false"))


if __name__ == "__main__":
    unittest.main()