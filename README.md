# routeros-emulator

**English** | [Русский (README_RU.md)](README_RU.md)

An interpreter and emulator for the **MikroTik RouterOS scripting language**
(RouterOS 7.x) that lets you run real `RouterOS` scripts (`.rsl`) on a plain
host — no firmware and no actual router needed.

The key idea: instead of a "rough" Python port, the interpreter executes the
**original RouterOS code itself** — the same `:global`/`:local`,
`:if`/`:for`/`:foreach`, `do={...}`, operators, `$var`, functions and commands
you write in your script. Its semantics were verified against a **live device
(RouterOS 7.9)**.

## Layout

```
routeros/          — the interpreter package (tokenizer → parser → AST → interpreter)
examples/          — example script modem_report.rsl + integration tests for it
tests/             — unit and integration tests
diff_tests/        — differential harness: emulator vs a real MikroTik
```

| Module | Purpose |
|--------|---------|
| `tokenizer.py` | string → tokens (word/kw/str/num/dur/time/var/op) |
| `parser.py`    | tokens → AST (decl/if/for/foreach/do-catch/expressions/commands) |
| `ast.py`       | AST nodes |
| `interpreter.py` | executes the AST (variables, builtins, functions, commands) |
| `commands.py`  | command layer: `[ /interface/... ]`, `/ping`, `/tool/fetch`, `/ip/...` → device model |
| `device_model.py` | the "router" model — what a script sees and what it affects |
| `builtins.py`  | `:find`, `:pick`, `:len`, `:tostr`, `:typeof`, ... |
| `values.py`    | value types (`Time`, `ROArray`, `ip`), conversions |
| `launcher.py`  | high-level API: load a `.rsl`, call a function, read globals |

## Installation

```bash
pip install .          # from the repo root
pip install -e .       # editable/development mode
```

Or simply put the `routeros/` folder on your `sys.path` — there are no external
dependencies, only the standard library (Python ≥ 3.11).

## Usage

Load a script and run it against a device model:

```python
from routeros.device_model import DeviceModel
from routeros.launcher import load_source

m = DeviceModel()
m.lte = [{".id": "*1", "name": "lte1", "model": "7600E V2"}]
m.monitor = lambda _id: {
    "imei": "864199030000000", "imsi": "250021234567890",
    "rssi": "-75", "model": "7600E V2",
}
m.at_chat = lambda _id, cmd: "+ICCID: 89883010000016182280\r\nOK" if "ICCID" in cmd else "OK"
m.ping = lambda addr: True

script = load_source(
    open("examples/modem_report.rsl", encoding="utf-8").read(),
    m, run_main=True, main_name="makeReport")
print(script.array("Report"))
# {'imei': '864199030000000', ..., 'iccid': '89883010000016182280',
#  'ping': '8.8.8.8', 'collected-at': 'oct/27/2026 15:04:05'}
```

To load a script **as a library** without running its entry-point, then call
individual functions:

```python
script = load_source(src, DeviceModel(), run_main=False, main_name="makeReport")
script.call("getTag", named={"tag": "Iccid", "src": "<r><Iccid>x</Iccid></r>"})  # 'x'
script.call("extractDigits", args=["+ICCID: 1\r\nOK"])                           # '1'
```

## Loading without running (`main_name`)

RouterOS scripts often end with an auto-run entry-point, e.g. `[$makeReport]`.
With `run_main=False` the emulator skips the top-level `[<main_name>]` call and
only evaluates the definitions (`:global ... do={...}`), so the script can be
used as a library of functions. Pass the entry-point name via `main_name=`
(`load_source` / `load_file` / `Repl`).

## CLI / REPL

An interactive shell where you can execute RouterOS code on the fly
(`:put`, `:local`, `:if`, `do={...}`, function calls). Variables persist
between lines and multi-line `do={...}` blocks auto-continue until the braces
balance.

```bash
routeros-repl              # interactive input
python3 -m routeros.repl   # the same
echo ':put (10 / 4)' | python3 -m routeros.repl   # one-shot / piped
```

```text
>>> :local double do={
...   :return ($1 * 2);
... };
>>> :put [$double 21]
42
>>> :load examples/modem_report.rsl
loaded examples/modem_report.rsl
>>> [$getTag tag="Iccid" src="<r><Iccid>abc</Iccid></r>"]
abc
```

Shell commands: `:load path` (load a script as a library), `:vars`, `:model`,
`:help`, `:exit`.

## Device model (`DeviceModel`)

A script sees no hardware — only what you put into the "model":

```python
m.lte             # list of LTE interfaces [{"id","name","model",...}]
m.monitor(id)     # result of /interface/lte/monitor (imei/imsi/rssi/model/...)
m.at_chat(id,cmd) # output of /interface/lte/at-chat
m.e3372_responses # HTTP answers by URL suffix for Huawei E3372 (web API)
m.files           # /file: name -> contents
m.routes / m.addresses / m.ethernet / m.ovpn
m.clock / m.uptime
m.ping(ip)        # result of /ping
m.effects         # side-effect log (handy for assertions in tests)
m.qpro_payloads   # payloads of /tool/fetch to http://qpro.local/...
```

`m.effects` is a way for tests to assert what the script *did* (rebooted USB,
changed OVPN, saved a file) without a real router.

`:delay` advances `m.uptime`, so waits based on real time (a `:while` loop on
`/system/resource/get uptime`) terminate in tests and their duration in seconds
can be asserted.

## Tests

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Two levels:

- **Interpreter unit tests** (`test_routeros_tokenizer/parser/interpreter/commands`)
  do not depend on any particular script and cover tokenization, AST,
  precedence, value handling and the command layer.
- **Integration tests** (`test_routeros_example_*`) run `examples/modem_report.rsl`
  — both individual functions and the full entry-point against different device
  models (an AT modem SIMCOM/ME909, a web-API Huawei E3372 modem, an
  unreachable WAN).

## Verified against a real device

The semantics were verified against a live MikroTik (RouterOS 7.9) with the
`diff_tests/` differential harness. Confirmed and baked in:

- integer division with truncation (`10 / 4` → `2`), `%`, `<>`, bitwise `^ & | << >>`;
- the ip type instead of float literals (`2.5` → `2.0.0.5`), `+`/`-` over a 32-bit integer;
- binary minus without spaces (`10-4`, `10--4`, `10 -4`), unary only "at the start";
- `:for ... step=`, `do{}...while=()`, `:error` + `on-error`;
- logical NOT is `!`; the keyword `not` — **not an operator**, but an empty prefix;
- array/time formats, `:tobool` of a string → "nothing", `:tonum` accepts integers only;
- function arguments: bare literals arrive as strings (`[$f 21]` → `"21"`,
  `A=true` → `"true"`, `A=2s` → `"2s"`), while variables/`()`/`[]`/arrays keep
  their type; strings are coerced in arithmetic (`"21" * 2` → `42`). A literal
  flag must be parsed with `:tobool [:find {…} $Flag]`, not `:typeof`/`:if`.

How to run the harness and the details — see `diff_tests/README.md`.

## License

MIT — see `LICENSE`.