"""Built-in RouterOS functions (``[:find ...]``, ``[:len ...]``, ...)."""

from .values import (NOTHING, IPValue, ROArray, Time, to_bool, to_str, type_of)


def _index(value, needle, start=0):
    if start is NOTHING or needle is NOTHING:
        return NOTHING
    res = -1
    if isinstance(value, str):
        res = value.find(str(needle), int(start))
    elif isinstance(value, ROArray):
        for i, (_k, v) in enumerate(value.items):
            if i < int(start):
                continue
            if _equal(v, needle):
                res = i
                break
    # The device returns "nothing" on a missing match, not -1
    return NOTHING if res < 0 else res


def _equal(a, b):
    if isinstance(a, Time) or isinstance(b, Time):
        return float(getattr(a, "seconds", a)) == float(getattr(b, "seconds", b))
    if isinstance(a, bool) or isinstance(b, bool):
        return to_bool(a) == to_bool(b)
    return a == b


def _len(value):
    if value is NOTHING:
        return 0
    if isinstance(value, (str, ROArray, list, tuple, dict)):
        return len(value)
    if isinstance(value, Time):
        # Device: :len 90m => 8 (length of the string form "01:30:00")
        return len(to_str(value))
    if isinstance(value, IPValue):
        # Device: [:len 1.2.3.4] => 7 (length of the string form "1.2.3.4")
        return len(to_str(value))
    return 0


def _pick(value, start, stop=None):
    if start is NOTHING or stop is NOTHING:
        return ""
    if isinstance(value, str):
        s = int(start)
        if s < 0:
            return ""
        e = int(stop) if stop is not None else s + 1
        return value[s:e]
    if isinstance(value, ROArray):
        s = int(start)
        if s < 0:
            return ""
        e = int(stop) if stop is not None else s + 1
        return ROArray(value.items[s:e])
    return ""


BUILTINS = {}


def _reg(name, fn):
    BUILTINS[name] = fn


def _tobool(v):
    # Device: strings are NOT converted -> "nothing"; numbers/bools/arrays are.
    if isinstance(v, str):
        return NOTHING
    return to_bool(v)


def _tonum(v):
    # Device only accepts integers (no spaces/fractions): anything else is "nothing".
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v) if v.is_integer() else NOTHING
    if isinstance(v, str):
        if v and v.strip() == v and v.lstrip("+-").isdigit():
            return int(v)
        return NOTHING
    return NOTHING


_reg("find", lambda v, n, s=0: _index(v, n, s))
_reg("pick", _pick)
_reg("len", lambda v: _len(v))
_reg("tostr", lambda v: to_str(v))
_reg("tobool", _tobool)
_reg("typeof", lambda v: type_of(v))
_reg("tonum", _tonum)
_reg("string", lambda v: to_str(v))


def _as_number(v):
    if isinstance(v, bool):
        return 1 if v else 0
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, Time):
        return v.seconds
    if isinstance(v, str):
        try:
            return int(v)
        except ValueError:
            return int(float(v))
    return 0


def call_builtin(name, args):
    if name not in BUILTINS:
        raise KeyError(f"unhandled builtin: :{name}")
    return BUILTINS[name](*args)