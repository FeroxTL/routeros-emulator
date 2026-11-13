# Types, variables, casting, truthiness
:put [:typeof 5]
:put [:typeof "abc"]
:put [:typeof true]
:put [:typeof false]
:put [:typeof 1s]
:put [:typeof {1;2}]
:put [:typeof {a=1}]
:local x 42; :put $x
:local s "hello"; :put $s
:put [:typeof $x]
:put [:tonum "42"]
:put [:tonum "-7"]
:put [:tonum "3.5"]
:put [:tonum "abc"]
:put [:tostr 42]
:put [:tostr true]
:put [:tobool "yes"]
:put [:tobool "0"]
:put [:tobool 0]
:put [:tobool 1]
:put [:tobool ""]
:put [:tobool "false"]
:local b 0; :if $b do={:put "truthy"} else={:put "falsy"}
:local c 3; :if $c do={:put "truthy"} else={:put "falsy"}
:local d ""; :if $d do={:put "truthy"} else={:put "falsy"}
:local e "no"; :if $e do={:put "truthy"} else={:put "falsy"}
:local f 0.0; :if $f do={:put "truthy"} else={:put "falsy"}
:put (1 = 1)
:put (1 != 1)
:put (1 <> 2)
:put ("a" = "a")
:put (2 > 1)
:put (1 >= 1)
:put (2 < 1)
:put ("" != "x")