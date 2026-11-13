# the `not` keyword: its real device semantics
:put (not false)
:put (not true)
:put (not 0)
:put (not 1)
:put (not 5)
:put (not "abc")
:put (not "")
:if (not false) do={:put "T"} else={:put "F"}
:if (not 0) do={:put "T"} else={:put "F"}
:local x false; :put (not $x)