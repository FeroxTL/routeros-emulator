# Conditionals: if/else, nesting, and/or/not, do/on-error
:if true do={:put "yes"} else={:put "no"}
:if false do={:put "yes"} else={:put "no"}
:local a 3; :if ($a = 3) do={:put "eq"} else={:put "ne"}
:local a 3; :if ($a > 5) do={:put "gt"} else={:put "notgt"}
:if (true and false) do={:put "and-t"} else={:put "and-f"}
:if (true and true) do={:put "and-t"} else={:put "and-f"}
:if (false or true) do={:put "or-t"} else={:put "or-f"}
:if (not false) do={:put "nottrue"} else={:put "notfalse"}
:if (false and true) do={:put "and-t"} else={:put "and-f"}
:if ($x) do={:put "x-t"} else={:put "x-f"}
:if (1 and 0) do={:put "n-t"} else={:put "n-f"}
:local a 1; :local b 2; :if (($a = 1) and ($b = 2)) do={:put "both"} else={:put "noboth"}
:if (3 > 2) do={:if (2 > 1) do={:put "nested=true"} else={:put "nested=m1"} } else={:put "nested=m2"}
:if ("a" = "a" or "b" = "c") do={:put "co"} else={:put "cn"}
:local flag (1 = 1); :if $flag do={:put "flagtrue"} else={:put "flagfalse"}
:do {:put "trybody"} on-error={:put "caught"}
:do {:error "boom"} on-error={:put "caught-boom"}
:do {:put "only"} 
:if (2 > 1 and 3 > 2 and 4 > 3) do={:put "chain"} else={:put "nochain"}
:if (2 > 5 or 3 > 2) do={:put "chainor"} else={:put "nochainor"}