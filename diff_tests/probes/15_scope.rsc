# variable scope: first declaration fixes kind / function isolation (RouterOS 7.9)
:global y1 1; :local y1 5; :put $y1
:local y2 9; :global y2 2; :put $y2
:global y3 1; :global y3 2; :put $y3
:local y4 1; :local y4 2; :put $y4
:global b1 42; :global h1 do={:return $b1}; :put [$h1]
:global b2 42; :global h2 do={:global b2; :return $b2}; :put [$h2]
:global x1 10; :global f1 do={:global x1; :set $x1 99; :return $x1}; :put [$f1]
:local q1 5; :global g1 do={:return $q1}; :put [$g1]