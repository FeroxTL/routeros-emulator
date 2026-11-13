"""Value model for the RouterOS-script interpreter.

RouterOS uses a small set of runtime types:

* `nothing` (the absence of a value, returned for missing lookups)
* num   (integer; division is truncating)
* bool  (true/false)
* str
* time  (both ``1s`` durations and ``00:30:00`` -- we model both as seconds)
* ip    (a dotted literal like ``2.5`` parses as ``ip`` and prints as ``2.0.0.5``;
  the device has no float literals)
* array (a single ordered ``{...}`` type that can hold KV pairs and/or plain
  values; used for both lists and dicts)

Strings keep RouterOS truthiness rules in mind (``""`` and ``0`` are false).
"""


class _Nothing:
    __slots__ = ()

    def __repr__(self):
        return "nothing"

    def __bool__(self):
        return False


NOTHING = _Nothing()


class Time:
    """A RouterOS ``time`` value (duration or clock-time), stored in seconds."""

    __slots__ = ("seconds",)

    def __init__(self, seconds):
        self.seconds = float(seconds)

    def __repr__(self):
        return f"time({self.seconds:g}s)"

    def __bool__(self):
        return self.seconds != 0  # 00:00:00 is falsy


class ROArray:
    """Ordered RouterOS ``array`` -- a sequence of (key, value) pairs.

    Used for both plain lists (keys are ints) and dicts (keys are strings).
    """

    __slots__ = ("items",)

    def __init__(self, items=None):
        self.items = list(items or [])

    def get(self, key):
        for k, v in self.items:
            if k == key:
                return v
        return NOTHING

    def set(self, key, value):
        for i, (k, _v) in enumerate(self.items):
            if k == key:
                self.items[i] = (key, value)
                return
        self.items.append((key, value))

    def keys(self):
        return [k for k, _v in self.items]

    def values(self):
        return [v for _k, v in self.items]

    def __len__(self):
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def __repr__(self):
        parts = []
        for k, v in self.items:
            if isinstance(k, int):
                parts.append(repr(v))
            else:
                parts.append(f"{k}={repr(v)}")
        return ";".join(parts)


class IPValue:
    """A RouterOS ``ip`` value.

    A real device parses dotted literals in its own special way (a "1::2"
    style): ``2.5`` → ``2.0.0.5``, ``1.2.3`` → ``1.2.0.3``, ``1.2.3.4`` stays
    as-is. The last component always lands in the 4th octet, the earlier ones
    are placed on the left and the middle bytes are filled with zeros. The
    value is stored as a 32-bit integer; ``+``/``-`` arithmetic works on that
    integer and the result remains ``ip``.
    """

    __slots__ = ("value",)

    def __init__(self, value):
        self.value = int(value) & 0xFFFFFFFF

    @property
    def octets(self):
        return [(self.value >> 24) & 0xFF, (self.value >> 16) & 0xFF,
                (self.value >> 8) & 0xFF, self.value & 0xFF]

    def __eq__(self, other):
        return isinstance(other, IPValue) and self.value == other.value

    def __hash__(self):
        return hash(self.value)

    def __repr__(self):
        return f"ip({self})"

    def __str__(self):
        return ".".join(str(o) for o in self.octets)


def parse_ip(text):
    """Parse a dotted literal into an IPValue, or return None."""
    parts = text.split(".")
    if not (2 <= len(parts) <= 4):
        return None
    if not all(p.isdigit() for p in parts):
        return None
    comps = [int(p) for p in parts]
    if any(c > 255 for c in comps):
        return None
    octets = [0, 0, 0, 0]
    n = len(comps)
    for i in range(n - 1):
        octets[i] = comps[i]
    octets[3] = comps[-1]
    value = (octets[0] << 24) | (octets[1] << 16) | (octets[2] << 8) | octets[3]
    return IPValue(value)


def truthy(value):
    """RouterOS truthiness."""
    if value is NOTHING:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value != ""
    if isinstance(value, ROArray):
        return len(value) > 0  # arrays are truthy when non-empty
    if isinstance(value, Time):
        return value.seconds != 0
    if isinstance(value, IPValue):
        return value.value != 0
    return True


def to_bool(value):
    """RouterOS ``:tobool`` semantics (approx)."""
    if value is NOTHING:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.lower() in ("true", "yes", "1", "on")
    if isinstance(value, Time):
        return value.seconds > 0
    if isinstance(value, ROArray):
        return len(value) > 0
    return False


def _time_to_str(seconds):
    """Render a RouterOS ``time`` value as ``HH:MM:SS``."""
    secs = int(round(float(seconds)))
    sign = "-" if secs < 0 else ""
    secs = abs(secs)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{sign}{h:02d}:{m:02d}:{s:02d}"


def to_str(value):
    """RouterOS ``:tostr`` semantics — how a real device prints values.

    Arrays print WITHOUT braces or spaces: ``{1;2;3}`` → ``1;2;3``, a dict
    ``{a=1;b=2}`` → ``a=1;b=2``, nested arrays are flattened. ``time`` prints
    as ``HH:MM:SS``.
    """
    if value is NOTHING:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Time):
        return _time_to_str(value.seconds)
    if isinstance(value, IPValue):
        return ".".join(str(o) for o in value.octets)
    if isinstance(value, ROArray):
        parts = []
        for k, v in value.items:
            if isinstance(k, int):
                parts.append(to_str(v))
            else:
                parts.append(f"{k}={to_str(v)}")
        return ";".join(parts)
    return str(value)


def type_of(value):
    """RouterOS ``:typeof`` results."""
    if value is NOTHING:
        return "nothing"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, Time):
        return "time"
    if isinstance(value, IPValue):
        return "ip"
    if isinstance(value, ROArray):
        return "array"
    if isinstance(value, (int, float)):
        return "num"
    if isinstance(value, str):
        return "str"
    return "str"


def as_num(value):
    """Best-effort numeric conversion."""
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (Time,)):
        return value.seconds
    return None