"""Interactive REPL for the RouterOS-script interpreter.

Usage:
    python -m routeros.repl                 # interactive prompt
    echo ':put (1 + 2)' | python -m routeros.repl   # one-shot / piped
    python -m routeros.repl --model=test    # connect an empty test DeviceModel

Variables declared with :local/:global persist across lines. Clauses that span
multiple lines (e.g. `do={ ... }`) are auto-continued until braces balance.
"""

import sys

from . import ast as A
from .device_model import DeviceModel
from .interpreter import Env, Interpreter, ReturnSignal
from .parser import parse
from .values import NOTHING, to_str


class Repl:
    def __init__(self, model=None, main_name=None):
        self.interp = Interpreter(model or DeviceModel(), main_name=main_name)
        # one shared top-frame: :local + :global survive between inputs
        self.env = Env(self.interp.root)

    # -- commands --------------------------------------------------------
    def handle_bang(self, line):
        cmd = line.strip()
        low = cmd.lower()
        if low in (":exit", ":quit", ":q"):
            raise EOFError
        if low in (":help", ":h", "?"):
            return ("RouterOS REPL. Try:\n"
                    "  :local a 5; :put $a\n"
                    "  :put (\"a\" . \"b\")\n"
                    "  :local x {imei=\"\";iccid=\"\"}; :set ($x->\"iccid\") \"1\"; :put ($x->\"iccid\")\n"
                    "  :load examples/modem_report.rsl\n"
                    "  :vars, :model, :help, :exit", True)
        if low == ":vars":
            names = sorted(self.interp.root.store)
            return ("\n".join(names) if names else "(no globals)", True)
        if low == ":model":
            m = self.interp.model
            return (f"lte interfaces: {len(m.lte)}\n"
                    f"ethernet: {dict(m.ethernet)}\n"
                    f"qpro payloads: {len(m.qpro_payloads)}\n"
                    f"effects: {m.effects}", True)
        if cmd.startswith(":load ") or cmd.startswith(":load\t"):
            path = cmd.split(maxsplit=1)[1].strip()
            with open(path, encoding="utf-8") as fh:
                src = fh.read()
            self.evaluate(src, skip_main=True)
            return f"loaded {path}", True
        return None

    # -- evaluation ------------------------------------------------------
    def _is_main_call(self, stmt):
        if self.interp.main_name is None:
            return False
        return (isinstance(stmt, A.ExprStmt)
                and isinstance(stmt.expr, A.Bracket)
                and stmt.expr.kind == "func"
                and stmt.expr.name == self.interp.main_name)

    def evaluate(self, text, skip_main=False):
        """Parse and run one chunk; returns (printed_lines, last_value)."""
        interp = self.interp
        out_printed = []
        try:
            stmts = parse(text).statements
        except Exception as e:  # ParseError / SyntaxError
            return out_printed, f"<parse error: {e}>"

        if skip_main:
            stmts = [s for s in stmts if not self._is_main_call(s)]

        interp.output.clear()
        last = None
        try:
            for s in stmts:
                if isinstance(s, A.ExprStmt):
                    last = interp.eval_expr(s.expr, self.env)
                else:
                    interp.exec_stmt(s, self.env)
                    last = None
        except ReturnSignal as r:
            last = r.value
        except Exception as e:  # runtime error
            out_printed.extend(interp.output)
            interp.output.clear()
            return out_printed, f"<error: {e.__class__.__name__}: {e}>"

        out_printed.extend(interp.output)
        interp.output.clear()
        return out_printed, last

    # -- main loop -------------------------------------------------------
    def run(self, stdin, stdout):
        interactive = hasattr(stdin, "isatty") and stdin.isatty()
        buffer = []
        if interactive:
            stdout.write("RouterOS REPL. Type :help for help, :exit to quit.\n")
        while True:
            prompt = "..." if buffer else ">>> " if interactive else ""
            if interactive:
                try:
                    line = input(prompt) if not buffer else input("... ")
                except EOFError:
                    break
            else:
                line = stdin.readline()
                if line == "":
                    break
                line = line.rstrip("\n")
            stripped = line.strip()
            if not stripped:
                continue

            # :commands (bang) handled as soon as they're typed
            if not buffer and stripped.startswith(":"):
                bang = self.handle_bang(stripped)
                if bang is not None:
                    text = bang[0]
                    stdout.write(text + "\n")
                    if bang[1] is False:
                        pass
                    continue

            buffer.append(line)
            source = "\n".join(buffer)

            # keep reading until braces balance (multi-line do={...} blocks)
            if self._depth(source) > 0:
                continue

            printed, last = self.evaluate(source)
            buffer = []
            for p in printed:
                stdout.write(p + "\n")
            if last is not None and last is not NOTHING:
                stdout.write(to_str(last) + "\n")

    @staticmethod
    def _depth(text):
        openers = text.count("{") + text.count("(") + text.count("[")
        closers = text.count("}") + text.count(")") + text.count("]")
        return openers - closers


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    model = DeviceModel()
    if "--model" in argv:
        pass  # only "test"-like default for now; custom models come via API
    Repl(model).run(sys.stdin, sys.stdout)


if __name__ == "__main__":
    main()
