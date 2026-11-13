# Arrays/dicts: literals, access, len, nesting, mutation
:put {1;2;3}
:put [:len {1;2;3}]
:local a {10;20;30}; :put [:len $a]
:put {a=1;b=2}
:put [:len {a=1;b=2}]
:put [:find {1;5;9} 5]
:put [:find {a=1;b=2} "b"]
:put [:find {1;5;9} 99]
:put [:pick {1;2;3;4} 1 3]
:put {1;{2;3};4}
:put {a={x=1};b=2}
:put ($x)
:local arr {1;2;3}; :set ($arr->1) 99; :put $arr
:local dict {k="v0"}; :set ($dict->"k") "novo"; :put $dict
:put [:tostr {1;{2;3}}]
:local m {1;2;3}; :put ($m->1)
:local d {n=7}; :put ($d->"n")
:put [:len {a=1;b=2;c=3}]
:local arr {5;6;7}; :put ($arr->2)
:local arr {1;2;3}; :put ($arr->0)