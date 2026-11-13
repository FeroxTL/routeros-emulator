# Strings: concatenation, len, pick, find, interpolation
:put ("a" . "b")
:put (1 . 2)
:put ("a" . 1)
:put ("len=" . [:len "hello"])
:put [:len "hello"]
:put [:len ""]
:put [:pick "hello" 0 3]
:put [:pick "hello" 1]
:put [:pick "hello" -3]
:put [:find "hello" "l"]
:put [:find "hello" "z"]
:put [:find "hello" "lo"]
:put [:find "aaa" "aa"]
:local v "world"; :put ($v . "!")
:local n 5; :put ("n=" . $n)
:put ("x" = "x")
:put ("abc" > "abd")
:put ("abc" < "abd")
:put [:tostr {1;2;3}]
:put "esc\ttab"
:put "quote\"here"
:put ("" . "")
:put [:pick "0123456789" 0 10]