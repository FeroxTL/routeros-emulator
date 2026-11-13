# ip type: dotted literals, rendering, typeof, arithmetic, comparison
:put (1.2)
:put (1.2.3)
:put (1.2.3.4)
:put (10.0)
:put (192.168.0.1)
:put [:typeof (1.2)]
:put [:typeof (1.2.3.4)]
:put (0.1 + 0.2)
:put (2.5 + 1)
:put (1.2 + 1.3)
:put (2.5 - 1)
:put (0.1 < 0.2)
:put (1.2 > 1.1)
:put (2.5 = 2.5)
:put (2.5 != 2.4)
:put (0.0.0.1 = 1)
:put [:typeof (0.1 + 0.2)]
:put (2.5 * 2)
:put (1.5 < 2)
:put (2.5 / 2)
:local ip 1.2.3.4; :put $ip
:local s "10.0.0.0/16"; :put $s
:put {192.168.1.1; 10.0.0.1}
:put [:len (1.2.3.4)]
# --- confirmed edge cases: non-canonical comparisons, tonum/tostr, interpolation ---
:put (1.2 = 1.2.0.0)
:put (2.5 = 2.0.0.5)
:put (1.2 = 1.2.0.1)
:put (1.2 < 1.2.0.1)
:put (1.2 < 1.3)
:put (1.2.0.1 < 1.2)
:put (255.0 < 255.0.0.0)
:put (1.2 <= 1.2.0.0)
:put (1.2 > 1.2.0.0)
:put (1.2 + 1.2.0.1)
:put [:tonum "1.5"]
:put [:tonum "1.2.3.4"]
:put [:tonum "10"]
:put [:tostr 1.2.3.4]
:put [:typeof [:tostr 1.2.3.4]]
:local a 1.2.3.4; :put "$a"
:local a 2.5; :put "$a-x"
:put (1.2.3.4 . "!")
:put [:len [:tostr 2.5]]