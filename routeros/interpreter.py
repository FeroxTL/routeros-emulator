"""Interpreter for the RouterOS-script AST (evaluator + statements)."""

import ipaddress

from . import ast as A
from . import builtins as BI
from .commands import Commands
from .values import NOTHING, IPValue, ROArray, Time, to_str, truthy


class Env:
    __slots__ = ("store", "parent", "is_frame")

    def __init__(self, parent=None, store=None, is_frame=False):
        self.store = store if store is not None else {}
        self.parent = parent
        # A function-call frame is isolated from every enclosing scope. Only
        # parameters, the function's own `:local`s and globals explicitly
        # referenced with `:global name;` inside the body are visible in it.
        self.is_frame = is_frame


class _GlobalRef:
    """Bookkeeping binding used inside an isolated function frame.

    ``:global name;`` inside a function does *not* copy the value into the
    frame; instead it stores a ``_GlobalRef`` so that ``$name`` reads (and
    ``:set $name`` writes) the live global on the device.
    """
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name


class ReturnSignal(Exception):
    def __init__(self, value):
        super().__init__("return")
        self.value = value


class FunctionValue:
    __slots__ = ("body", "env")

    def __init__(self, body, env):
        self.body = body
        self.env = env


class _NotAFunction(Exception):
    pass


class Interpreter:
    def __init__(self, model, main_name=None):
        self.root = Env()
        self.model = model
        self.commands = Commands(model)
        self.output = []
        self.log_events = []
        self.run_main = True
        # Name of the entry-point function whose top-level `[call]` is filtered
        # out when `run_main` is False (so a script can be "loaded" as a library).
        self.main_name = main_name
        # First-declaration kind of each variable ('global' | 'local'). On RouterOS
        # the first `:global`/`:local` for a name fixes its kind: a later
        # declaration of the other kind is ignored (a `:local` cannot shadow an
        # existing `:global`), while a same-kind redeclaration updates the value.
        self.var_kind = {}

    # ---------- variable resolution ----------
    def find(self, name, env):
        e = env
        while e is not None:
            if name in e.store:
                return e
            e = e.parent
        return None

    def resolve(self, name, env):
        e = self.find(name, env)
        if e is None:
            return NOTHING
        v = e.store.get(name, NOTHING)
        # Inside an isolated function a `:global name;` binding is a reference
        # to the persistent global store.
        if isinstance(v, _GlobalRef):
            return self.root.store.get(v.name, NOTHING)
        return v

    # ---------- evaluation ----------
    def make_value(self, node, env):
        if node is None:
            return NOTHING
        if isinstance(node, A.FuncLit):
            return FunctionValue(node.body, env)
        return self.eval_expr(node, env)

    def eval_expr(self, node, env):
        if isinstance(node, A.Lit):
            return node.value
        if isinstance(node, A.Var):
            return self.resolve(node.name, env)
        if isinstance(node, A.Prop):
            # a record-property reference inside `where` reads the local env
            return env.store.get(node.name, NOTHING)
        if isinstance(node, A.Str):
            return self._interp_str(node, env)
        if isinstance(node, A.ListLit):
            return ROArray([(i, self.eval_expr(it, env)) for i, it in enumerate(node.items)])
        if isinstance(node, A.ArrayLit):
            return self._eval_array(node, env)
        if isinstance(node, A.Member):
            return self._eval_member(node, env)
        if isinstance(node, A.UnOp):
            return self._eval_unop(node, env)
        if isinstance(node, A.BinOp):
            return self._eval_binop(node, env)
        if isinstance(node, A.Bracket):
            return self._eval_bracket(node, env)
        if isinstance(node, A.FuncLit):
            return FunctionValue(node.body, env)
        raise TypeError(f"cannot evaluate {node!r}")

    def _interp_str(self, node, env):
        parts = []
        for kind, val in node.parts:
            if kind == "lit":
                parts.append(val)
            else:
                parts.append(to_str(self.resolve(val, env)))
        return "".join(parts)

    def _eval_array(self, node, env):
        arr = ROArray()
        idx = 0
        for key, expr in node.entries:
            value = self.eval_expr(expr, env)
            if key is None:
                arr.items.append((idx, value))
                idx += 1
            else:
                arr.items.append((key, value))
        return arr

    def _eval_member(self, node, env):
        obj = self.eval_expr(node.target, env)
        key = self.to_key(self.eval_expr(node.key, env))
        if isinstance(obj, ROArray):
            return obj.get(key)
        return NOTHING

    @staticmethod
    def to_key(k):
        if isinstance(k, bool):
            return int(k)
        if isinstance(k, Time):
            return k.seconds
        return k

    def _eval_unop(self, node, env):
        v = self.eval_expr(node.operand, env)
        if node.op == "!":
            return not truthy(v)
        if node.op == "-":
            if isinstance(v, Time):
                return Time(-v.seconds)
            return -(self._num(v))
        raise KeyError(f"unhandled unary {node.op}")

    def _num(self, v):
        if isinstance(v, bool):
            return 1 if v else 0
        if isinstance(v, Time):
            return v.seconds
        if isinstance(v, (int, float)):
            return v
        return 0

    @staticmethod
    def _eq(a, b):
        if isinstance(a, bool) or isinstance(b, bool):
            return a == b
        if isinstance(a, IPValue) or isinstance(b, IPValue):
            # ip compares only with ip; ip = num -> false (as on a device)
            return (isinstance(a, IPValue) and isinstance(b, IPValue)
                    and a.value == b.value)
        if isinstance(a, Time) or isinstance(b, Time):
            try:
                return float(getattr(a, "seconds", a)) == float(getattr(b, "seconds", b))
            except (TypeError, ValueError):
                return False
        if a is NOTHING or b is NOTHING:
            return a is b
        if isinstance(a, ROArray) or isinstance(b, ROArray):
            return to_str(a) == to_str(b)
        # RouterOS: 1 = "1" -> true (numeric coercion of strings, checked on 7.9)
        if ((isinstance(a, str) and isinstance(b, (int, float))) or
                (isinstance(b, str) and isinstance(a, (int, float)))):
            try:
                return float(a) == float(b)
            except (TypeError, ValueError):
                return False
        return a == b

    @staticmethod
    def _in(left, right):
        if isinstance(right, ROArray):
            return any(_val_eq(left, v) for _k, v in right.items)
        if isinstance(right, str) and isinstance(left, str) and "/" in right:
            try:
                return ipaddress.ip_address(left) in ipaddress.ip_network(right, strict=False)
            except ValueError:
                return False
        return True

    def _eval_bracket(self, node, env):
        if node.kind == "func":
            return self.call_user(node.name, node.args, env)
        if node.kind == "builtin":
            vals = [self.eval_expr(a.value, env) for a in node.args]
            return BI.call_builtin(node.name, vals)
        named = {}
        positional = []
        for a in node.args:
            if a.name is not None:
                if a.op is not None:
                    continue  # filter param, intentionally ignored
                named[a.name] = self.eval_expr(a.value, env)
            else:
                positional.append(self.eval_expr(a.value, env))
        match = self._mk_where_matcher(node.filters, env) if node.filters else None
        return self.commands.execute(node.name, named, positional, match)

    def _mk_where_matcher(self, filters, env):
        """Build a ``match(record)`` callable for the ``where`` predicates.

        For each record a child env is created carrying its properties; bare
        words (A.Prop) resolve from those properties, ``$var`` from the outer env.
        """
        def match(record):
            rec_env = Env(env)
            rec_env.store.update(record)
            for f in filters:
                if not truthy(self._eval_where(f, rec_env)):
                    return False
            return True
        return match

    _WHERE_CMP = {"=", "==", "!=", "<", ">", "<=", ">=", "~", "in"}

    @staticmethod
    def _coerce_yes_no(left, right):
        """Inside ``where`` a bool property is compared with ``yes``/``no`` rather
        than ``true``/``false`` (checked on 7.9); plain ``true = "yes"`` stays false."""
        if isinstance(left, bool) and isinstance(right, str):
            low = right.lower()
            if low in ("yes", "no"):
                return low == "yes"
        return right

    def _where_val(self, node, env):
        if isinstance(node, A.Prop):
            return env.store.get(node.name, NOTHING)
        return self.eval_expr(node, env)

    def _eval_where(self, node, env):
        """Evaluate a ``where`` predicate with the ``yes``/``no`` bool semantics."""
        if isinstance(node, A.BinOp):
            if node.op in self._WHERE_CMP:
                left = self._where_val(node.left, env)
                right = self._coerce_yes_no(left, self._where_val(node.right, env))
                op = "=" if node.op == "==" else node.op
                return self._eval_binop(A.BinOp(op, A.Lit(left), A.Lit(right)), env)
            if node.op in ("and", "or"):
                le = self._eval_where(node.left, env)
                if node.op == "and":
                    return le if not truthy(le) else self._eval_where(node.right, env)
                return le if truthy(le) else self._eval_where(node.right, env)
        if isinstance(node, A.UnOp) and node.op == "!":
            return not truthy(self._eval_where(node.operand, env))
        if isinstance(node, A.Prop):
            return env.store.get(node.name, NOTHING)
        return self.eval_expr(node, env)

    def call_user(self, name, args, env):
        fn = self.resolve(name, env)
        if not isinstance(fn, FunctionValue):
            raise _NotAFunction(f"{name} is not a function")
        frame = Env(None, is_frame=True)
        pos = 0
        for a in args:
            if a.name is not None:
                frame.store[a.name] = self.eval_expr(a.value, env)
            else:
                pos += 1
                frame.store[str(pos)] = self.eval_expr(a.value, env)
        try:
            self.exec_body(fn.body, frame)
        except ReturnSignal as r:
            return r.value
        return NOTHING

    _CMP = {"=": lambda a, b: a == b, "!=": lambda a, b: a != b,
            "<": lambda a, b: a < b, ">": lambda a, b: a > b,
            "<=": lambda a, b: a <= b, ">=": lambda a, b: a >= b}

    def _eval_binop(self, node, env):
        op = node.op
        if op == "and":
            left = self.eval_expr(node.left, env)
            if not truthy(left):
                return left
            return self.eval_expr(node.right, env)
        if op == "or":
            left = self.eval_expr(node.left, env)
            if truthy(left):
                return left
            return self.eval_expr(node.right, env)

        left = self.eval_expr(node.left, env)
        right = self.eval_expr(node.right, env)
        if op == ".":
            return to_str(left) + to_str(right)
        if op == "=":
            return self._eq(left, right)
        if op == "!=":
            return not self._eq(left, right)
        if op == "in":
            return self._in(left, right)
        if op == "~":
            return str(left).__contains__(str(right))
        if op in self._CMP:
            # Device: any relational comparison with "nothing" -> false
            if left is NOTHING or right is NOTHING:
                return False
            # ip compares only with ip; ip < num on a device is an error
            if isinstance(left, IPValue) or isinstance(right, IPValue):
                if isinstance(left, IPValue) and isinstance(right, IPValue):
                    return self._CMP[op](left.value, right.value)
                raise TypeError(f"cannot compare ip prefix with non-ip ({op})")
            lv = self._cmp_value(left)
            rv = self._cmp_value(right)
            return self._CMP[op](lv, rv)
        # ip: only `+`/`-` work on the 32-bit value; `*`/`/`/`%` are forbidden
        if isinstance(left, IPValue) or isinstance(right, IPValue):
            if op in ("+", "-"):
                lv = left.value if isinstance(left, IPValue) else int(self._num(left))
                rv = right.value if isinstance(right, IPValue) else int(self._num(right))
                return IPValue(lv + rv) if op == "+" else IPValue(lv - rv)
            raise TypeError(f"cannot {op} ip prefix")
        # arithmetic + - * /
        if isinstance(left, Time) or isinstance(right, Time):
            ls = self._num(left)
            rs = self._num(right)
            if op == "-":
                return Time(ls - rs)
            if op == "+":
                return Time(ls + rs)
            if op == "*":
                return Time(ls * rs)
            if op == "/":
                return Time(ls / rs)
        if op == "-":
            return self._num(left) - self._num(right)
        if op == "+":
            return self._num(left) + self._num(right)
        if op == "*":
            return self._num(left) * self._num(right)
        if op == "/":
            lv, rv = self._num(left), self._num(right)
            if rv == 0:
                raise ZeroDivisionError("division by zero")
            # RouterOS divides as integers, truncating toward zero (10/4 => 2, -7/2 => -3)
            return int(lv / rv)
        if op == "%":
            lv, rv = self._num(left), self._num(right)
            if rv == 0:
                raise ZeroDivisionError("division by zero")
            return int(lv) % int(rv)
        # Bitwise operations (RouterOS: `^` is XOR, `2 ^ 3` => 1)
        if op in ("^", "&", "|", "<<", ">>"):
            lv, rv = self._num(left), self._num(right)
            li, ri = int(lv), int(rv)
            if op == "^":
                return li ^ ri
            if op == "&":
                return li & ri
            if op == "|":
                return li | ri
            if op == "<<":
                return li << ri
            return li >> ri
        raise KeyError(f"unhandled binop {op}")

    def _cmp_value(self, v):
        if isinstance(v, Time):
            return v.seconds
        if isinstance(v, bool):
            return int(v)
        return v

    # ---------- statements ----------
    def exec_body(self, stmts, env):
        for s in stmts:
            self.exec_stmt(s, env)

    def assign_var(self, name, value, env):
        e = self.find(name, env)
        if e is not None:
            # Writing to a `:global name;` reference inside a function updates
            # the persistent global (`:set $x` writes through to the global).
            if isinstance(e.store.get(name), _GlobalRef):
                self.root.store[name] = value
            else:
                e.store[name] = value
        else:
            env.store[name] = value

    def exec_stmt(self, node, env):
        if isinstance(node, A.Decl):
            self.exec_decl(node, env)
            return
        if isinstance(node, A.SetStmt):
            self.exec_set(node, env)
            return
        if isinstance(node, A.If):
            if truthy(self.eval_expr(node.cond, env)):
                self.exec_body(node.then, Env(env))
            else:
                self.exec_body(node.else_, Env(env))
            return
        if isinstance(node, A.While):
            while truthy(self.eval_expr(node.cond, env)):
                self.exec_body(node.body, Env(env))
            return
        if isinstance(node, A.For):
            start = int(self.eval_expr(node.from_, env))
            end = int(self.eval_expr(node.to, env))
            step = int(self.eval_expr(node.step, env)) if node.step is not None else 1
            if step > 0:
                rng = range(start, end + 1, step)
            else:
                rng = range(start, end - 1, step)
            for i in rng:
                f = Env(env)
                f.store[node.var] = i
                self.exec_body(node.body, f)
            return
        if isinstance(node, A.Foreach):
            it = self.eval_expr(node.iterable, env)
            if isinstance(it, ROArray):
                for k, v in it.items:
                    f = Env(env)
                    if node.val:
                        f.store[node.key] = k
                        f.store[node.val] = v
                    else:
                        f.store[node.key] = v
                    self.exec_body(node.body, f)
            return
        if isinstance(node, A.DoCatch):
            self.exec_docatch(node, env)
            return
        if isinstance(node, A.DoWhile):
            while True:
                self.exec_body(node.body, Env(env))
                if not truthy(self.eval_expr(node.cond, env)):
                    break
            return
        if isinstance(node, A.Error):
            msg = to_str(self.eval_expr(node.value, env)) if node.value is not None else ""
            raise RuntimeError(msg)
        if isinstance(node, A.Return):
            value = self.eval_expr(node.value, env) if node.value is not None else NOTHING
            raise ReturnSignal(value)
        if isinstance(node, A.Put):
            self.output.append(to_str(self.eval_expr(node.value, env)))
            return
        if isinstance(node, A.Log):
            self.log_events.append((node.level, to_str(self.eval_expr(node.message, env))))
            return
        if isinstance(node, A.Delay):
            return
        if isinstance(node, A.ExprStmt):
            self.eval_expr(node.expr, env)
            return
        raise TypeError(f"cannot execute {node!r}")

    def exec_decl(self, node, env):
        name = node.name
        is_global = node.kind == "global"
        first = self.var_kind.get(name)
        if first is None:
            first = "global" if is_global else "local"
            self.var_kind[name] = first
        # The first declaration fixes the kind; a later declaration of the other
        # kind is a no-op (a `:local` cannot shadow an existing `:global`).
        if is_global:
            if first == "local":
                return
            if node.value is None:
                # `:global name;` -- a reference/re-declaration; don't clobber an
                # already-bound value (keeps a previously defined global intact).
                if name not in self.root.store:
                    self.root.store[name] = NOTHING
            else:
                self.root.store[name] = self.make_value(node.value, env)
            # Inside an isolated function a `:global name;` must also bind a
            # local reference so the global is writable/readable within the body.
            anc = env
            while anc is not None and not anc.is_frame:
                anc = anc.parent
            if anc is not None and name not in anc.store:
                anc.store[name] = _GlobalRef(name)
        else:
            if first == "global":
                return
            env.store[name] = self.make_value(node.value, env) if node.value is not None else NOTHING

    def exec_set(self, node, env):
        value = self.eval_expr(node.value, env)
        target = node.target
        if isinstance(target, A.Var):
            self.assign_var(target.name, value, env)
        elif isinstance(target, A.Member):
            obj = self.eval_expr(target.target, env)
            key = self.to_key(self.eval_expr(target.key, env))
            if isinstance(obj, ROArray):
                obj.set(key, value)
        else:
            raise TypeError("bad assignment target")

    def exec_docatch(self, node, env):
        try:
            self.exec_body(node.body, Env(env))
        except ReturnSignal:
            raise
        except Exception:
            if node.catch:
                self.exec_body(node.catch, Env(env))
            else:
                raise

    # ---------- program top-level ----------
    def run(self, program):
        stmts = program.statements
        if not self.run_main and self.main_name:
            stmts = [s for s in stmts if not self._is_main_call(s)]
        try:
            self.exec_body(stmts, self.root)
        except ReturnSignal:
            return NOTHING
        return NOTHING

    def _is_main_call(self, stmt):
        if not isinstance(stmt, A.ExprStmt):
            return False
        node = stmt.expr
        return (isinstance(node, A.Bracket)
                and node.kind == "func"
                and node.name == self.main_name)

    def globals_snapshot(self):
        return dict(self.root.store)


def _val_eq(a, b):
    if isinstance(a, IPValue) or isinstance(b, IPValue):
        return isinstance(a, IPValue) and isinstance(b, IPValue) and a.value == b.value
    if isinstance(a, Time) or isinstance(b, Time):
        return float(getattr(a, "seconds", a)) == float(getattr(b, "seconds", b))
    return a == b