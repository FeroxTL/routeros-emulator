# Time: literals, durations, arithmetic, comparison
:put 1s
:put 90m
:put 1h30m
:put 00:30:00
:put [:typeof 1s]
:put [:typeof 00:30:00]
:put [:len 90m]
:put (1s + 2s)
:put (2s - 1s)
:put (1h - 30m)
:put (1m * 2)
:put (10s / 2)
:put (5 < 10s)
:local t 00:01:30; :put $t
:put (1s = 1s)
:put (1s < 2s)
:put (1h30m = 90m)
:put [:typeof (1h + 30m)]
:put (0.5s + 0.5s)
:put (00:00:05 + 5s)
:put [:tonum 5s]
:put [:tostr 300s]
:put (100s > 1m)