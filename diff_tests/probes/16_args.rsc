# Function arguments: bare literals arrive as strings, variables/expressions
# keep their type (only when the literal is passed directly, without brackets).
# Positional literal type
:local f do={:return [:typeof $1]}; :put [$f 21]
# Positional string stays a string
:local f do={:return [:typeof $1]}; :put [$f "21"]
# A num variable keeps its type
:local n 21; :local f do={:return [:typeof $1]}; :put [$f $n]
# A bool variable keeps its type
:local b true; :local f do={:return [:typeof $1]}; :put [$f $b]
# An array keeps its type
:local arr {"a";"b"}; :local f do={:return [:typeof $1]}; :put [$f $arr]
# Named literal true -> str
:local f do={:return [:typeof $A]}; :put [$f A=true]
# Named numeric literal -> str
:local f do={:return [:typeof $A]}; :put [$f A=21]
# Named variable keeps its type
:local b true; :local f do={:return [:typeof $A]}; :put [$f A=$b]
# A parenthesized expression keeps its type
:local f do={:return [:typeof $A]}; :put [$f A=(1+2)]
# A bracket command keeps its type
:local f do={:return [:typeof $A]}; :put [$f A=[:len "abc"]]
# A string argument is coerced in arithmetic
:local f do={:return ($1 * 2)}; :put [$f 21]
# Flag parsing (:find + :tobool): string literal true
:local f do={:return [:tostr [:tobool [:find {"";"true";"1";"yes";yes;1} $Flag]]]}; :put [$f Flag=true]
# Flag parsing: string literal false
:local f do={:return [:tostr [:tobool [:find {"";"true";"1";"yes";yes;1} $Flag]]]}; :put [$f Flag=false]
# Flag parsing: bool variable
:local b true; :local f do={:return [:tostr [:tobool [:find {"";"true";"1";"yes";yes;1} $Flag]]]}; :put [$f Flag=$b]
# Flag parsing: argument not passed
:local f do={:return [:tostr [:tobool [:find {"";"true";"1";"yes";yes;1} $Flag]]]}; :put [$f]
