10 rem =====================================
11 rem meatloaf netzwerk-diagnose
12 rem unabhaengig von unserem tron-protokoll
13 rem nutzt das offizielle http-beispiel aus
14 rem der meatloaf-doku (geraet 8, sek.adr. 3)
15 rem =====================================
20 print chr$(147)
30 print "teste meatloaf http-abruf..."
40 open 1,8,3,"https://example.com/"
50 c=0
60 get#1,a$
65 if a$<>"" then c=c+1:if c<200 then print a$;
70 if st<>0 then 100
90 goto 60
100 print
110 print "fertig. gelesene zeichen: ";c
120 close 1
130 if c>0 then print "netzwerk/wlan funktioniert!"
140 if c=0 then print "kein zeichen empfangen - wlan/netzwerk pruefen (nicht unser protokoll!)"
