"""Tokenizer for the RouterOS scripting language (a practical subset).
Pragmatic: words, numbers, durations, times, strings (with ``$var``
interpolation), variables and operators are recognised without fully resolving
the notoriously ambiguous RouterOS grammar.
"""

from .values import NOTHING, parse_ip


class Token:
    __slots__ = ("kind", "value", "line")

    def __init__(self, kind, value, line):
        # kind: word | kw | str | num | dur | time | var | op | eol | eof
        self.kind = kind
        self.value = value
        self.line = line

    def __repr__(self):
        return f"Token({self.kind!r}, {self.value!r})"


def _is_word_char(c):
    return c is not None and c.isspace() is False and c not in "<>=!+*%;,(){}[]~&|\"'"
def _rhs_ended(tokens):
    """True if the last token ends a right-hand operand, so the next `-` is binary.

    On a device `10-4`, `10 -4`, `10--4` mean subtraction (left side is a
    number/ip/var), while a negative literal `-3` (e.g. the argument of
    `:pick "s" -3`) stays unary, so string/word operands give no "binaryness".
    Unary `-` appears only "at the start" (after `(`, an operator, a comma) or
    after a string/word."""
    if not tokens:
        return False
    t = tokens[-1]
    if t.kind in ("num", "ip", "var", "time", "dur"):
        return True
    return t.kind == "op" and t.value in (")", "]", "}")


def _classify_word(text, line):
    if text in ("-", ".", "/"):
        return Token("op", text, line)
    if text.startswith(":") and len(text) > 1:
        return Token("kw", text[1:], line)
    if text in ("true", "false", "nil"):
        return Token("word", text, line)
    time = _parse_time(text)
    if time is not None:
        return Token("time", time, line)
    ip = parse_ip(text)
    if ip is not None:
        return Token("ip", ip, line)
    num = _parse_num(text)
    if num is not None:
        return Token("num", num, line)
    dur = _parse_duration(text)
    if dur is not None:
        return Token("dur", dur, line)
    return Token("word", text, line)


def _parse_int(text):
    if text in ("", "+", "-"):
        return None
    s = text[1:] if text[:1] in "+-" else text
    if s.isdigit():
        return int(text)
    return None


def _parse_num(text):
    if _parse_int(text) is not None:
        return _parse_int(text)
    s = text[1:] if text[:1] in "+-" else text
    if s.count(".") != 1:
        return None
    a, b = s.split(".")
    if (a.isdigit() or a == "") and (b.isdigit() or b == ""):
        return float(text)
    return None


_UNITS = {"ms": 0.001, "s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800, "y": 31536000}


def _parse_duration(text):
    # Composite durations like `1h30m`, `2m30s`, `1h5s` (RouterOS adds them up).
    total = 0.0
    i = 0
    matched = False
    while i < len(text):
        j = i
        while j < len(text) and text[j].isdigit():
            j += 1
        if j == i:
            break
        num = int(text[i:j])
        unit = text[j] if j < len(text) and text[j] in _UNITS else None
        if unit is None:
            break
        total += num * _UNITS[unit]
        i = j + 1
        matched = True
    if matched and i == len(text):
        return float(total)
    # legacy behaviour: `2.5s` and other single units
    for unit, mult in _UNITS.items():
        if text.endswith(unit):
            num = _parse_num(text[: -len(unit)])
            if num is not None:
                return float(num) * mult
    return None


def _parse_time(text):
    if text.count(":") == 2:
        a, b, c = text.split(":")
        if a.isdigit() and b.isdigit() and c.isdigit():
            return float(int(a) * 3600 + int(b) * 60 + int(c))
    return None


_ESCAPES = {"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"', "'": "'", "$": "$", "/": "/"}


def _read_string(src, i, line):
    quote = src[i]
    i += 1
    parts = []
    buf = []
    interp = quote == '"'
    while i < len(src):
        c = src[i]
        if c == "\\" and i + 1 < len(src):
            buf.append(_ESCAPES.get(src[i + 1], src[i + 1]))
            i += 2
            continue
        if c == quote:
            i += 1
            if buf:
                parts.append(("lit", "".join(buf)))
            return parts, i
        if interp and c == "$" and i + 1 < len(src) and (src[i + 1].isalnum() or src[i + 1] == "_"):
            if buf:
                parts.append(("lit", "".join(buf)))
                buf = []
            j = i + 1
            while j < len(src) and (src[j].isalnum() or src[j] == "_"):
                j += 1
            parts.append(("var", src[i + 1:j]))
            i = j
            continue
        buf.append(c)
        i += 1
    raise SyntaxError(f"unterminated string at line {line}")


_SIMPLE_PUNCT = set("(){}[];,")
_TWO_OP = {"->", "<=", ">=", "!=", "==", "<>", "<<", ">>", "||", "&&"}


def tokenize(text):
    tokens = []
    i = 0
    line = 1
    n = len(text)
    prev_i = -1
    nest = 0  # depth of [ and ( -- a newline inside them does NOT end a statement
    while i < n:
        if i == prev_i:
            raise RuntimeError(f"tokenizer stuck at {i}: {text[max(0,i-8):i+8]!r}")
        prev_i = i
        c = text[i]
        if c == "\n":
            # at the top level (outside [ and () a newline terminates a statement
            if nest == 0:
                tokens.append(Token("eol", "eol", line))
            line += 1
            i += 1
            continue
        if c.isspace():
            i += 1
            continue
        if c == "#":
            while i < n and text[i] != "\n":
                i += 1
            continue
        if c in _SIMPLE_PUNCT:
            tokens.append(Token("op", c, line))
            if c in "[(":
                nest += 1
            elif c in "])":
                nest -= 1
            i += 1
            continue
        if c == "$":
            j = i + 1
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            if j == i + 1:
                raise SyntaxError(f"bad variable at line {line}")
            tokens.append(Token("var", text[i + 1:j], line))
            i = j
            continue
        if c in "\"'":
            parts, i = _read_string(text, i, line)
            tokens.append(Token("str", parts, line))
            continue
        if c == "~":
            tokens.append(Token("op", "~", line))
            i += 1
            continue
        if text[i:i + 2] in _TWO_OP:
            tokens.append(Token("op", text[i:i + 2], line))
            i += 2
            continue
        if c in "=<>!+*%&|,^":
            tokens.append(Token("op", c, line))
            i += 1
            continue
        if c == "-":
            if text[i:i + 2] == "->":
                tokens.append(Token("op", "->", line))
                i += 2
                continue
            if _rhs_ended(tokens):
                # 10-4 / 10 -4 / 10--4 on a device = subtraction
                tokens.append(Token("op", "-", line))
                i += 1
                continue
            nxt = text[i + 1] if i + 1 < n else None
            if nxt is not None and (_is_word_char(nxt) or nxt in "-."):
                start = i
                i += 1
                while i < n and (_is_word_char(text[i]) or text[i] in "-."):
                    i += 1
                tokens.append(_classify_word(text[start:i], line))
                continue
            tokens.append(Token("op", "-", line))
            i += 1
            continue
        # otherwise a word
        start = i
        if text[i].isdigit():
            # numeric tokens don't merge with `-`: `10-4` is not a single word
            while i < n and text[i] != "-" and _is_word_char(text[i]):
                i += 1
        else:
            while i < n and (_is_word_char(text[i]) or text[i] in "-."):
                i += 1
        tokens.append(_classify_word(text[start:i], line))

    tokens.append(Token("eof", NOTHING, line))
    return tokens