# routeros-emulator

[English (README.md)](README.md) | **Русский**

Интерпретатор и эмулятор **скриптового языка MikroTik RouterOS** (RouterOS 7.x),
позволяющий исполнять реальные `RouterOS`-скрипты (`.rsl`) на обычном хосте —
без прошивки и без реального маршрутизатора.

Ключевая идея: вместо «приблизительного» python-порта интерпретатор выполняет
**сам исходный RouterOS-код** — те же `:global`/`:local`, `:if`/`:for`/`:foreach`,
`do={...}`, операторы, `$var`, функции и команды, — что написаны в вашем скрипте.
Семантика сверена с **живым устройством (RouterOS 7.9)**.

## Структура

```
routeros/          — пакет-интерпретатор (tokenizer → parser → AST → interpreter)
examples/          — пример скрипта modem_report.rsl + интеграционные тесты к нему
tests/             — юнит- и интеграционные тесты
diff_tests/        — дифференциальный стенд «эмулятор vs реальный MikroTik»
```

| Модуль | Назначение |
|--------|------------|
| `tokenizer.py` | Строка → токены (word/kw/str/num/dur/time/var/op) |
| `parser.py`    | Токены → AST (decl/if/for/foreach/do-catch/выражения/команды) |
| `ast.py`       | Узлы AST |
| `interpreter.py` | Исполнение AST (переменные, встроенные, функции, команды) |
| `commands.py`  | Командный слой: `[ /interface/... ]`, `/ping`, `/tool/fetch`, `/ip/...` → модель устройства |
| `device_model.py` | Модель «маршрутизатора» — что скрипт видит и на что влияет |
| `builtins.py`  | Встроенные `:find`, `:pick`, `:len`, `:tostr`, `:typeof`, ... |
| `values.py`    | Типы значений (`Time`, `ROArray`, `ip`), преобразования |
| `launcher.py`  | Высокоуровневый API: загрузить `.rsl`, вызвать функцию, прочитать глобалы |

## Установка

```bash
pip install .          # из корня репозитория
pip install -e .       # режим разработчика
```

Или просто добавьте папку `routeros/` в `sys.path` — внешних зависимостей нет,
достаточно чистой стандартной библиотеки (Python ≥ 3.11).

## Использование

Загрузите скрипт и выполните его против модели устройства:

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

Загрузить скрипт **как библиотеку**, не запуская его entry-point, и вызывать
функции по отдельности:

```python
script = load_source(src, DeviceModel(), run_main=False, main_name="makeReport")
script.call("getTag", named={"tag": "Iccid", "src": "<r><Iccid>x</Iccid></r>"})  # 'x'
script.call("extractDigits", args=["+ICCID: 1\r\nOK"])                           # '1'
```

## Загрузка без запуска (`main_name`)

RouterOS-скрипты часто оканчиваются авто-запуском entry-point, например
`[$makeReport]`. При `run_main=False` эмулятор пропускает верхнеуровневые вызовы
`[<main_name>]` и выполняет только определения (`:global ... do={...}`), поэтому
скрипт можно использовать как библиотеку функций. Имя entry-point передаётся
параметром `main_name=` (`load_source` / `load_file` / `Repl`).

## CLI / REPL

Интерактивная оболочка, где можно выполнять строки RouterOS-кода на лету
(`:put`, `:local`, `:if`, `do={...}`, вызовы функций). Переменные сохраняются
между строками, многострочные `do={...}` продолжаются до баланса скобок.

```bash
routeros-repl              # интерактивный ввод
python3 -m routeros.repl   # то же самое
echo ':put (10 / 4)' | python3 -m routeros.repl   # разовый / из pipe
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

Команды оболочки: `:load path` (загрузить скрипт как библиотеку), `:vars`,
`:model`, `:help`, `:exit`.

## Модель устройства (`DeviceModel`)

Скрипт не видит железа — только то, что вы положили в «модель»:

```python
m.lte             # список LTE-интерфейсов [{"id","name","model",...}]
m.monitor(id)     # результат /interface/lte/monitor (imei/imsi/rssi/model/...)
m.at_chat(id,cmd) # вывод /interface/lte/at-chat
m.e3372_responses # HTTP-ответы по суффиксу URL для Huawei E3372 (web-API)
m.files           # /file: имя -> содержимое
m.routes / m.addresses / m.ethernet / m.ovpn
m.clock / m.uptime
m.ping(ip)        # результат /ping
m.effects         # журнал побочных эффектов (удобно для проверок в тестах)
m.qpro_payloads   # payload /tool/fetch на http://qpro.local/...
```

`m.effects` — способ в тестах проверить, что скрипт *сделал* (перезапустил USB,
изменил OVPN, сохранил файл), не имея настоящего маршрутизатора.

`:delay` двигает `m.uptime`, поэтому ожидания по реальному времени (`:while` по
`/system/resource/get uptime`) в тестах завершаются, а их длительность в
секундах можно проверять ассертами.

## Тесты

```bash
python3 -m unittest discover -s tests -p 'test_*.py'
```

Два уровня:

- **Юнит-тесты интерпретатора** (`test_routeros_tokenizer/parser/interpreter/commands`)
  не зависят от конкретных скриптов и покрывают токенизацию, AST, приоритеты,
  обработку значений и командный слой.
- **Интеграционные** (`test_routeros_example_*`) исполняют `examples/modem_report.rsl`
  — и отдельные функции, и полный entry-point против разных моделей устройства
  (AT-модем SIMCOM/ME909, web-API модем Huawei E3372, недоступный WAN).

## Сверка с реальным устройством

Семантика выверялась против живого MikroTik (RouterOS 7.9) дифференциальным
стендом `diff_tests/`. Сверено и внесено:

- целочисленное деление с усечением (`10 / 4` → `2`), `%`, `<>`, битовые `^ & | << >>`;
- ip-тип вместо float-литералов (`2.5` → `2.0.0.5`), арифметика `+`/`-` над 32-битным целым;
- бинарный минус без пробелов (`10-4`, `10--4`, `10 -4`), унарный только «в начале»;
- `:for ... step=`, `do{}...while=()`, `:error` + `on-error`;
- логическое НЕ — `!`; слово `not` — **не оператор**, а пустой префикс;
- форматы массивов/времени, `:tobool` от строки → «nothing», `:tonum` только целые;
- аргументы функций: «голые» литералы приходят строками (`[$f 21]` → `"21"`,
  `A=true` → `"true"`, `A=2s` → `"2s"`), переменные/`()`/`[]`/массивы сохраняют
  тип; строки приводятся в арифметике (`"21" * 2` → `42`). Флаг-литерал нужно
  разбирать через `:tobool [:find {…} $Flag]`, а не `:typeof`/`:if`.

Запуск стенда и детали — в `diff_tests/README.md`.

## Лицензия

MIT — см. `LICENSE`.
