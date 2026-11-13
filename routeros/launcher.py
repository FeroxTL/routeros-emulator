"""High-level helpers to load a RouterOS script, run it (optionally without its
auto-started entry-point), and call the global functions it declares."""

from . import ast as A
from .interpreter import Interpreter
from .parser import parse
from .values import NOTHING, ROArray


class Script:
    def __init__(self, interpreter, program, model):
        self.interp = interpreter
        self.program = program
        self.model = model

    def call(self, name, named=None, args=None):
        """Call a loaded global function, e.g. call('parseTag', args=['<r>x</r>'])."""
        interp = self.interp
        frame = type(interp.root)(interp.root)
        bracket_args = []
        if named:
            for k, v in named.items():
                bracket_args.append(_PseudoArg(k, A.Lit(v)))
        for i, v in enumerate((args or []), start=1):
            bracket_args.append(_PseudoArg(None, A.Lit(v)))
        value = interp.call_user(name, bracket_args, frame)
        return value

    def globals(self):
        """Snapshot of the global variables defined by the script."""
        return self.interp.globals_snapshot()

    def array(self, name):
        """Return a global RouterOS array as a plain dict ({} if missing/not array)."""
        v = self.globals().get(name, NOTHING)
        if not isinstance(v, ROArray):
            return {}
        return {k: v.get(k) for k in v.keys()}


class _PseudoArg:
    __slots__ = ("name", "value")

    def __init__(self, name, value):
        self.name = name
        self.value = value


def load_source(source, model, run_main=False, main_name=None):
    """Parse and run ``source`` in a fresh interpreter against ``model``.

    Pass ``main_name=<entry>`` (the name of the script's entry-point function)
    plus ``run_main=False`` to load the script as a library: every top-level
    ``[<entry>]`` call is skipped, only the definitions are evaluated.
    """
    interp = Interpreter(model, main_name=main_name)
    interp.run_main = run_main
    program = parse(source)
    interp.run(program)
    return Script(interp, program, model)


def load_file(path, model, run_main=False, main_name=None):
    with open(path, encoding="utf-8") as fh:
        return load_source(fh.read(), model, run_main=run_main, main_name=main_name)