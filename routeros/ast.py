"""AST node definitions for the RouterOS-script interpreter."""


class Node:
    __slots__ = ()


class Program(Node):
    __slots__ = ("statements",)

    def __init__(self, statements):
        self.statements = statements


class Var(Node):
    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name


class Prop(Node):
    """A reference to a record property inside a ``where`` predicate.

    In that context (``/x/find where name="a"``) a bare word like ``name``
    denotes a property of the current record rather than a string literal.
    Outside ``where`` bare words stay strings -- ``Prop`` is only produced by
    the command parser.
    """

    __slots__ = ("name",)

    def __init__(self, name):
        self.name = name


class Str(Node):
    __slots__ = ("parts",)  # list of ("lit", str) | ("var", name)

    def __init__(self, parts):
        self.parts = parts


class Lit(Node):
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


class ListLit(Node):
    __slots__ = ("items",)  # list of expr for ()-tuples

    def __init__(self, items):
        self.items = items


class ArrayLit(Node):
    __slots__ = ("entries",)  # list of (key:str|int|None, expr)

    def __init__(self, entries):
        self.entries = entries


class Member(Node):
    __slots__ = ("target", "key")

    def __init__(self, target, key):
        self.target = target
        self.key = key


class BinOp(Node):
    __slots__ = ("op", "left", "right")

    def __init__(self, op, left, right):
        self.op = op
        self.left = left
        self.right = right


class UnOp(Node):
    __slots__ = ("op", "operand")

    def __init__(self, op, operand):
        self.op = op
        self.operand = operand


class Arg(Node):
    __slots__ = ("name", "op", "value")

    def __init__(self, name, op, value):
        self.name = name  # str | None (named param)
        self.op = op      # comparison op for filter params | None
        self.value = value


class Bracket(Node):
    """A ``[...]`` expression: function / builtin / command call."""

    __slots__ = ("kind", "name", "args", "filters")

    def __init__(self, kind, name, args, filters=None):
        self.kind = kind  # 'func' | 'builtin' | 'command'
        self.name = name
        self.args = args
        self.filters = filters or []  # parsed `where` predicates (AST nodes)


class FuncLit(Node):
    __slots__ = ("body",)

    def __init__(self, body):
        self.body = body


class Decl(Node):
    __slots__ = ("kind", "name", "value")

    def __init__(self, kind, name, value):
        self.kind = kind  # 'global' | 'local'
        self.name = name
        self.value = value


class SetStmt(Node):
    __slots__ = ("target", "value")

    def __init__(self, target, value):
        self.target = target
        self.value = value


class If(Node):
    __slots__ = ("cond", "then", "else_")

    def __init__(self, cond, then, else_):
        self.cond = cond
        self.then = then
        self.else_ = else_


class For(Node):
    __slots__ = ("var", "from_", "to", "body", "step")

    def __init__(self, var, from_, to, body, step=None):
        self.var = var
        self.from_ = from_
        self.to = to
        self.body = body
        self.step = step


class Foreach(Node):
    __slots__ = ("key", "val", "iterable", "body")

    def __init__(self, key, val, iterable, body):
        self.key = key
        self.val = val
        self.iterable = iterable
        self.body = body


class While(Node):
    __slots__ = ("cond", "body")

    def __init__(self, cond, body):
        self.cond = cond
        self.body = body


class DoCatch(Node):
    __slots__ = ("body", "catch")

    def __init__(self, body, catch):
        self.body = body
        self.catch = catch


class DoWhile(Node):
    __slots__ = ("cond", "body")

    def __init__(self, cond, body):
        self.cond = cond
        self.body = body


class Error(Node):
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


class Return(Node):
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


class Put(Node):
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


class Delay(Node):
    __slots__ = ("value",)

    def __init__(self, value):
        self.value = value


class Log(Node):
    __slots__ = ("level", "message")

    def __init__(self, level, message):
        self.level = level
        self.message = message


class ExprStmt(Node):
    __slots__ = ("expr",)

    def __init__(self, expr):
        self.expr = expr