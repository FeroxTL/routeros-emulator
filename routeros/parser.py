"""Recursive-descent parser for the RouterOS-script interpreter."""

from . import ast as A
from .tokenizer import tokenize
from .values import NOTHING, Time


class ParseError(SyntaxError):
    pass


class Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.pos = 0

    # ---------- token helpers ----------
    def current(self):
        return self.toks[self.pos]

    def advance(self):
        t = self.toks[self.pos]
        if t.kind != "eof":
            self.pos += 1
        return t

    def peek(self, offset=1):
        i = min(self.pos + offset, len(self.toks) - 1)
        return self.toks[i]

    def is_op(self, value):
        t = self.current()
        return t.kind == "op" and t.value == value

    def is_word(self, value):
        t = self.current()
        return t.kind in ("kw", "word") and t.value == value

    def expect_op(self, value):
        t = self.current()
        if t.kind == "op" and t.value == value:
            self.advance()
            return
        raise ParseError(f"expected {value!r} at line {t.line}")

    def expect_word(self, value):
        t = self.current()
        if t.kind in ("kw", "word") and t.value == value:
            self.advance()
            return
        raise ParseError(f"expected {value!r} at line {t.line}")

    def expect_ident(self):
        t = self.current()
        if t.kind == "word":
            self.advance()
            return t.value
        raise ParseError(f"expected identifier at line {t.line}")

    # ---------- program / statements ----------
    def parse_program(self):
        stmts = []
        while self.current().kind != "eof":
            stmts.append(self.parse_statement())
        return A.Program(stmts)

    def parse_statement(self):
        t = self.current()
        if t.kind == "op" and t.value == "[":
            node = A.ExprStmt(self.parse_bracket_expr())
            self.skip_semi()
            return node

        val = t.value if t.kind in ("kw", "word") else None
        if val in ("local", "global"):
            node = self.parse_decl()
        elif val == "set":
            node = self.parse_set()
        elif val == "if":
            node = self.parse_if()
        elif val == "for":
            node = self.parse_for()
        elif val == "foreach":
            node = self.parse_foreach()
        elif val == "while":
            node = self.parse_while()
        elif val == "do":
            node = self.parse_docatch()
        elif val == "return":
            node = self.parse_return()
        elif val == "error":
            self.advance()
            t = self.current()
            value = None
            if not (t.kind == "op" and t.value in (";", "}")):
                value = self.parse_expr()
            node = A.Error(value)
        elif val == "put":
            self.advance()
            node = A.Put(self.parse_expr())
        elif val == "delay":
            self.advance()
            node = A.Delay(self.parse_expr())
        elif val == "log":
            node = self.parse_log()
        elif t.kind == "word":
            name = self.expect_ident()
            node = A.ExprStmt(A.Bracket("command", name, self.parse_command_args(";")))
        else:
            raise ParseError(f"unexpected token {t!r} at line {t.line}")

        self.skip_semi()
        return node

    def skip_semi(self):
        while self.is_op(";"):
            self.advance()

    def parse_block_body(self):
        self.expect_op("{")
        stmts = []
        while True:
            t = self.current()
            if t.kind == "eof":
                raise ParseError(f"unterminated block at line {t.line}")
            if self.is_op("}"):
                self.advance()
                break
            stmts.append(self.parse_statement())
        return stmts

    def do_block_or_brace(self):
        if self.is_word("do"):
            self.advance()
        if self.is_op("="):
            self.advance()
        return self.parse_block_body()

    # ---------- declarations / assignment ----------
    def parse_decl(self):
        t = self.current()
        kind = "global" if t.value == "global" else "local"
        self.advance()
        name = self.expect_ident()
        if self.is_op("="):
            self.advance()
        value = None
        if not self.is_op(";"):
            value = self.parse_expr()
        return A.Decl(kind, name, value)

    def parse_lvalue(self):
        t = self.current()
        if t.kind in ("var", "word"):
            self.advance()
            return A.Var(t.value)
        if self.is_op("("):
            self.advance()
            v = self.current()
            if v.kind != "var":
                raise ParseError(f"bad assignment target at line {v.line}")
            self.advance()
            target = A.Var(v.value)
            while self.is_op("->"):
                self.advance()
                key = self.parse_member_key()
                target = A.Member(target, key)
            self.expect_op(")")
            return target
        raise ParseError(f"bad assignment target at line {t.line}")

    def parse_set(self):
        self.advance()  # ':set'
        target = self.parse_lvalue()
        value = None
        if self.is_op("="):
            self.advance()
            value = self.parse_expr()
        elif not self.is_op(";"):
            value = self.parse_expr()
        return A.SetStmt(target, value)

    # ---------- control flow ----------
    def parse_if(self):
        self.advance()
        cond = self.parse_expr()
        then = self.do_block_or_brace()
        else_ = []
        if self.is_word("else"):
            self.advance()
            else_ = self.do_block_or_brace()
        return A.If(cond, then, else_)

    def parse_for(self):
        self.advance()
        var = self.expect_ident()
        self.expect_word("from")
        self.expect_op("=")
        from_expr = self.parse_expr()
        self.expect_word("to")
        self.expect_op("=")
        to_expr = self.parse_expr()
        step = None
        if self.is_word("step"):
            self.advance()
            self.expect_op("=")
            step = self.parse_expr()
        body = self.do_block_or_brace()
        return A.For(var, from_expr, to_expr, body, step)

    def parse_foreach(self):
        self.advance()
        key = self.expect_ident()
        val = None
        if self.is_op(","):
            self.advance()
            val = self.expect_ident()
        self.expect_word("in")
        if self.is_op("="):
            self.advance()
        iterable = self.parse_expr()
        body = self.do_block_or_brace()
        return A.Foreach(key, val, iterable, body)

    def parse_while(self):
        self.advance()
        cond = self.parse_expr()
        body = self.do_block_or_brace()
        return A.While(cond, body)

    def parse_docatch(self):
        self.advance()
        body = self.do_block_or_brace()
        if self.is_word("while"):
            # :do {...} while=(cond) — do-while
            self.advance()
            self.expect_op("=")
            cond = self.parse_expr()
            return A.DoWhile(cond, body)
        catch = []
        if self.is_word("on-error"):
            self.advance()
            catch = self.do_block_or_brace()
        return A.DoCatch(body, catch)

    def parse_return(self):
        self.advance()
        t = self.current()
        if t.kind == "eof" or (t.kind == "op" and t.value in (";", "}")):
            return A.Return(None)
        return A.Return(self.parse_expr())

    def parse_log(self):
        self.advance()
        level = self.expect_ident()
        self.expect_word("message")
        self.expect_op("=")
        message = self.parse_expr()
        return A.Log(level, message)

    # ---------- expressions ----------
    def parse_expr(self):
        return self.parse_or()

    def parse_or(self):
        node = self.parse_and()
        while self.is_word("or"):
            self.advance()
            node = A.BinOp("or", node, self.parse_and())
        return node

    def parse_and(self):
        node = self.parse_in()
        while self.is_word("and"):
            self.advance()
            node = A.BinOp("and", node, self.parse_in())
        return node

    def parse_in(self):
        node = self.parse_eq()
        while self.is_word("in"):
            self.advance()
            node = A.BinOp("in", node, self.parse_eq())
        return node

    def parse_eq(self):
        node = self.parse_rel()
        while self.is_op("=") or self.is_op("!=") or self.is_op("==") or self.is_op("<>"):
            op = self.current().value
            self.advance()
            if op == "<>":
                op = "!="  # RouterOS: `<>` and `!=` are the same thing
            node = A.BinOp(op, node, self.parse_rel())
        return node

    def parse_rel(self):
        node = self.parse_add()
        while self.current().kind == "op" and self.current().value in ("<", ">", "<=", ">=", "~"):
            op = self.current().value
            self.advance()
            node = A.BinOp(op, node, self.parse_add())
        return node

    def parse_add(self):
        node = self.parse_mul()
        bitwise = {"+", "-", ".", "^", "&", "|", "<<", ">>"}
        while self.current().kind == "op" and self.current().value in bitwise:
            op = self.current().value
            self.advance()
            node = A.BinOp(op, node, self.parse_mul())
        return node

    def parse_mul(self):
        node = self.parse_unary()
        while self.current().kind == "op" and self.current().value in ("*", "/", "%"):
            op = self.current().value
            self.advance()
            node = A.BinOp(op, node, self.parse_unary())
        return node

    def parse_unary(self):
        if self.is_op("!"):
            self.advance()
            return A.UnOp("!", self.parse_unary())
        if self.is_op("-"):
            self.advance()
            return A.UnOp("-", self.parse_unary())
        if self.is_word("not"):
            # on a device `not` is NOT an operator but an empty prefix: (not X) => X.
            # Logical NOT in RouterOS is `!`. Skip the `not` word.
            self.advance()
            return self.parse_unary()
        return self.parse_member()

    def parse_member(self):
        node = self.parse_primary()
        while self.is_op("->"):
            self.advance()
            key = self.parse_member_key()
            node = A.Member(node, key)
        return node

    def parse_member_key(self):
        t = self.current()
        if t.kind == "str":
            self.advance()
            return A.Str(t.value)
        if t.kind == "var":
            self.advance()
            return A.Var(t.value)
        if t.kind in ("num", "ip"):
            self.advance()
            return A.Lit(t.value)
        if t.kind == "word":
            self.advance()
            return A.Str([("lit", t.value)])
        raise ParseError(f"bad member key at line {t.line}")

    def parse_primary(self):
        t = self.current()
        if self.is_op("("):
            self.advance()
            if self.is_op(")"):
                self.advance()
                return A.ListLit([])
            first = self.parse_expr()
            if self.is_op(","):
                self.advance()
                items = [first]
                while not self.is_op(")"):
                    if self.current().kind == "eof":
                        raise ParseError("unterminated tuple")
                    items.append(self.parse_expr())
                    if self.is_op(","):
                        self.advance()
                self.expect_op(")")
                return A.ListLit(items)
            self.expect_op(")")
            return first
        if self.is_op("{"):
            return self.parse_array_lit()
        if self.is_op("["):
            return self.parse_bracket_expr()
        if t.kind == "str":
            self.advance()
            return A.Str(t.value)
        if t.kind in ("num", "dur", "time", "ip"):
            self.advance()
            if t.kind in ("dur", "time"):
                return A.Lit(Time(t.value))
            return A.Lit(t.value)
        if t.kind == "var":
            self.advance()
            return A.Var(t.value)
        if t.kind == "word":
            v = t.value
            if v == "true":
                self.advance()
                return A.Lit(True)
            if v == "false":
                self.advance()
                return A.Lit(False)
            if v == "nil":
                self.advance()
                return A.Lit(NOTHING)
            if v == "do":
                self.advance()
                if self.is_op("="):
                    self.advance()
                body = self.parse_block_body()
                return A.FuncLit(body)
            self.advance()
            return A.Str([("lit", v)])
        raise ParseError(f"unexpected token {t!r} at line {t.line}")

    def parse_array_lit(self):
        self.expect_op("{")
        entries = []
        while not self.is_op("}"):
            if self.current().kind == "eof":
                raise ParseError("unterminated array literal")
            t = self.current()
            if t.kind == "str":
                self.advance()
                if self.is_op("="):
                    self.advance()
                    entries.append((t.value, self.parse_expr()))
                else:
                    entries.append((None, A.Str(t.value)))
            elif t.kind == "word":
                self.advance()
                if self.is_op("="):
                    self.advance()
                    entries.append((t.value, self.parse_expr()))
                else:
                    entries.append((None, A.Str([("lit", t.value)])))
            elif t.kind == "num":
                self.advance()
                if self.is_op("="):
                    self.advance()
                    entries.append((t.value, self.parse_expr()))
                else:
                    entries.append((None, A.Lit(t.value)))
            else:
                entries.append((None, self.parse_expr()))
            if self.is_op(";"):
                self.advance()
        self.expect_op("}")
        return A.ArrayLit(entries)

    # ---------- bracket calls / commands ----------
    def parse_bracket_expr(self):
        self.expect_op("[")
        t = self.current()
        if t.kind == "var":
            self.advance()
            args = self.parse_call_args("]")
            self.expect_op("]")
            return A.Bracket("func", t.value, args)
        if t.kind == "kw":
            self.advance()
            args = self.parse_call_args("]")
            self.expect_op("]")
            return A.Bracket("builtin", t.value, args)
        if t.kind == "word":
            self.advance()
            args = self.parse_command_args("]")
            self.expect_op("]")
            return A.Bracket("command", t.value, args)
        raise ParseError(f"unexpected token {t!r} at line {t.line}")

    def parse_call_args(self, stop):
        args = []
        while True:
            t = self.current()
            if t.kind == "eof":
                raise ParseError("unterminated call")
            if t.kind == "op" and t.value == stop:
                break
            if t.kind in ("word", "kw") and self.peek().kind == "op" and self.peek().value == "=":
                name = t.value
                self.advance()
                self.advance()  # '='
                args.append(A.Arg(name, None, self.parse_expr()))
            else:
                args.append(A.Arg(None, None, self.parse_expr()))
        return args

    def parse_command_args(self, stop):
        args = []
        while True:
            t = self.current()
            if t.kind == "eof":
                raise ParseError("unterminated command")
            if t.kind == "op" and t.value in (stop, ";"):
                break
            if t.kind in ("word", "kw"):
                if t.value == "where":
                    self.advance()
                    self.parse_expr()  # filter, intentionally ignored by mocks
                    continue
                nxt = self.peek()
                if nxt.kind == "op" and nxt.value == "=":
                    name = t.value
                    self.advance()
                    self.advance()
                    args.append(A.Arg(name, None, self.parse_expr()))
                elif nxt.kind == "op" and nxt.value in ("<", ">", "<=", ">=", "in"):
                    name = t.value
                    op = nxt.value
                    self.advance()
                    self.advance()
                    args.append(A.Arg(name, op, self.parse_expr()))
                else:
                    self.advance()
                    args.append(A.Arg(None, None, A.Str([("lit", t.value)])))
            else:
                args.append(A.Arg(None, None, self.parse_expr()))
        return args


def parse(text):
    """Parse RouterOS source text into a Program AST."""
    return Parser(tokenize(text)).parse_program()