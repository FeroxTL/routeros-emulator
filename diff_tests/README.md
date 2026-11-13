# diff_tests — differential harness: emulator vs a real MikroTik

Runs the same RouterOS-script constructs on the **emulator** (the `routeros`
package) and on a **real device** (over SSH) and prints a per-line diff. Its
purpose is to verify that the interpreter's behaviour really matches the
hardware — at the language level (types, operators, loops, arrays, strings,
time), with no modems or network commands involved.

## Usage

```bash
# all probes
python3 diff_tests/run_compare.py

# a specific file (the .rsc extension is optional)
python3 diff_tests/run_compare.py 08_time
```

The device is taken from environment variables (default `admin@192.168.88.1`,
empty password — suitable for a fully reset MikroTik):

```bash
export MIKROTIK_HOST=192.168.88.1
export MIKROTIK_USER=admin
export MIKROTIK_PASS=''
```

You need `ssh` and `sshpass`. Verified on a **MikroTik hAP / RouterOS 7.9 (MIPS)**.
Ideally run it against a freshly reset device.

## How it works

Every non-empty, non-`#`-comment line in `probes/*.rsc` counts as one probe
(a single `:put` line producing a result). The device runs a whole chunk
(≈10 lines), each wrapped in `:do { ... } on-error={...}` — a failing line does
not break the rest. The emulator runs each line separately in memory. The
outputs are compared line by line.

## Probe groups covered

| File | What it checks |
|------|----------------|
| `01_arith.rsc`  | arithmetic, precedence, whitespace tokenization (`10-4`, `10 / 4`), `+ - * / %`, bitwise `^ & \| << >>`, `-`/`/` right up against a number |
| `02_types.rsc`  | `:typeof`, `:tonum`, `:tostr`, `:tobool`, truthiness, comparisons |
| `03_string.rsc` | concatenation `.`, `:len`, `:pick`, `:find`, string comparison |
| `04_array.rsc`  | arrays/dicts: literals, `->` access, nesting, `:set ($a->k)`, print format |
| `05_loop.rsc`   | `:for` (and `step=`), `:foreach` (k,v), `:while`, `do{}while=`, `:break`/`:continue` |
| `06_cond.rsc`   | `:if/else`, `and/or`, nesting, `do/on-error`, `not`, `:error` |
| `07_func.rsc`   | inline functions `do={...}`, `$1..$n`, `:return`, nesting, closures |
| `08_time.rsc`   | durations (`1h30m`, `90m`), `HH:MM:SS`, time arithmetic/comparison |
| `09_ip.rsc`     | ip type (`2.5` → `2.0.0.5`), `:typeof`, `+`/`-` arithmetic, only ip↔ip comparisons, `* / %` → error; non-canonical comparisons, `:tonum`/`:tostr` of ip, `"$a"` interpolation |
| `11_minus.rsc`  | binary/unary minus: `10-4`, `10--4`, `10 -4`, `5--3`, `(-3)` |
| `13_not.rsc`    | the `not` prefix (identity) and logical NOT `!` |

## What the comparison with hardware has confirmed and baked in

Real findings (RouterOS 7.9) already implemented in `routeros/*`:

- **Integer division truncating toward zero**: `10 / 4` → `2` (not `2.5`);
  `7 / 0` → "division by zero" error.
- **No float literals**: `2.5` is an **ip type** (prints as `2.0.0.5`;
  `1.2.3` → `1.2.0.3`, the lowest octet "fills" the 4th byte). `+`/`-` act on
  a 32-bit integer (`0.1 + 0.2` → `0.0.0.3`, `2.5 + 1` → `2.0.0.6`), while
  `*`/`/`/`%` → error. Comparisons only ip↔ip (`0.1 < 0.2` → `true`,
  `1.5 < 2` → error), `ip = num` → `false`. `:typeof` → `ip`;
  `[:len 1.2.3.4]` → `7` (length of the string form).
- **`^` is XOR** (`2 ^ 3` → `1`), plus bitwise `& | << >>`.
- **`<>` means "not equal"** (same as `!=`).
- **`%`** is the modulo operator.
- **Binary minus without spaces**: `10-4` → `6`, `10--4` → `14`, `5--3` → `8`,
  `10 -4` → `6`; unary minus only "at the start" (`(-3)` → `-3`).
- **`:for ... step=`** (`from=3 to=1 step=-1` → `321`), **`do{...}while=(...)`**;
- **`:error "text"`** is caught by `:do{...} on-error={...}`.
- **Logical NOT is `!`** (`!false` → `true`). The keyword **`not` is NOT an
  operator on 7.9** — it is an empty prefix: `(not X)` returns `X`
  (`not false` → `false`, `not 5` → `5`).
- **Arrays print without braces/spaces**: `{1;2;3}` → `1;2;3`,
  `{a={x=1};b=2}` → `a=x=1;b=2`, nested arrays are flattened.
- **Time prints as `HH:MM:SS`**: `90m` → `01:30:00`; composite durations like
  `1h30m` parse; `:len 90m` → `8`.
- **`:find` returns "nothing" on no match** (not `-1`); comparisons against
  "nothing" yield `false`.
- **`:pick` with 2 arguments** — one character from a position.
- **`:tobool` of a string → "nothing"**; **`:tonum`** accepts integers only
  (no spaces/fractions), otherwise "nothing".

## Known limitations (not implemented — they don't affect real scripts)

- **Slash right up against a number** (`6/3`, `6 /3`, `6/ 3`) behaves chaotically
  on hardware: `6/3` → empty, `6 /3` → `2`, but `6/ 3` → `3`, `8/-2` → `-2`
  (≠ -4). This is device UB that cannot be reproduced exactly; `/N` only
  appears in CIDR in real scripts.
- `num + ip` (`1 + 2.5`) on a device returns a "garbage" internal address
  (`0.0.12.242`, depends only on the `num`), while `num - ip` → error;
  the emulator gives `2.0.0.6`. This is hardware UB, not emulated.
- ip as an **array key** (`$a->1.2`, `{1.2=...}`) is a syntax error on the device
  (`expected end of command`); the emulator cleanly returns "nothing".
- `:break`/`:continue` do **not exist** in RouterOS (on 7.9 both the device and
  the emulator raise an error) — deliberately not implemented.
- `:if <literal>` (without parentheses, `:if true ...`) and `(1 and 0)` — the
  emulator works (treats them truthy), the device fails with a syntax error;
  the emulator is "smarter" here, but real scripts never use this form.
- Device inline functions do **not capture** outer `:local`s (the emulator does).
- `* / %` and `ip < num` raise `TypeError` in the emulator but a generic line
  error on the device; semantically it's the same "line fails", only the text
  differs.
- `1 not 2` / bare `(not)` — the emulator does not parse a non-unary `not` form
  (this never appears in real scripts; the unary `(not X)` → `X` is supported).