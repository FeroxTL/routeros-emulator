# Loops: for / foreach / while / do-while (each probe accumulates into a string and :put once)
:local s ""; :for i from=1 to=3 do={:set s ($s . $i)}; :put $s
:local s ""; :for i from=3 to=1 step=-1 do={:set s ($s . $i)}; :put $s
:local s ""; :for i from=1 to=5 step=2 do={:set s ($s . $i)}; :put $s
:local s ""; :foreach x in={1;2;3} do={:set s ($s . $x)}; :put $s
:local s ""; :foreach k,v in={a=1;b=2;c=3} do={:set s ($s . $k . $v)}; :put $s
:local s ""; :local i 0; :while ($i < 3) do={:set s ($s . $i); :set i ($i+1)}; :put $s
:local s "0"; :local i 0; :do {:set s ($s . $i); :set i ($i+1)} while=($i < 3); :put $s
:local s ""; :for i from=1 to=3 do={:set s ($s . $i); :if ($i = 2) do={:break}}; :put $s
:local s ""; :for i from=1 to=3 do={:if ($i = 2) do={:continue}; :set s ($s . $i)}; :put $s
:local s ""; :foreach x in={5;6;7} do={:set s ($s . $x)}; :put $s
:local s ""; :for i from=0 to=4 do={:set s ($s . ($i * 2))}; :put $s
:local sum 0; :for i from=1 to=5 do={:set sum ($sum + $i)}; :put $sum
:local sum 0; :foreach x in={2;4;6} do={:set sum ($sum + $x)}; :put $sum
:local s ""; :local i 5; :while ($i > 0) do={:set s ($s . $i); :set i ($i - 1)}; :put $s
:local s ""; :foreach i,v in={10;20;30} do={:set s ($s . $i . ":" . $v . ";")}; :put $s