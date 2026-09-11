10 REM ===================================
11 REM FUJINET N:HTTP - ISOLIERTER TEST
12 REM diesmal direkt mit dem echten ziel
13 REM (einfaches http, keine tls/https-
14 REM komplikationen) statt gnu.org
15 REM ===================================
20 GRAPHICS 0:POKE 82,0
30 ? "teste fujinet n:http (fotofix)..."
40 TRAP 900
50 OPEN #1,12,0,"N:HTTP://fotofix.classic-computing.de/MUSTER/ascii-terminal.txt"
60 NB=0
70 GET #1,BY
80 NB=NB+1
90 IF BY=0 THEN 200
100 IF NB>500 THEN 200
110 ? CHR$(BY);
120 IF ST=0 THEN 70
200 ? "":? "fertig. gelesene zeichen: ";NB
210 CLOSE #1
220 IF NB>1 THEN ? "http/fujinet funktioniert!"
230 IF NB<=1 THEN ? "kein zeichen erhalten - problem liegt an http/n:"
235 IF NB<=1 THEN ? "selbst (dns/dieser modus/etc), nicht an basic-code"
240 END
900 ? "":? "netzwerkfehler, code ";PEEK(195)
910 CLOSE #1
920 END
