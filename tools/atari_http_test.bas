10 REM ===================================
11 REM FUJINET N:HTTP - ISOLATED TEST
12 REM this time straight against the real
13 REM target (plain http, no tls/https
14 REM complications) instead of gnu.org
15 REM ===================================
20 GRAPHICS 0:POKE 82,0
30 ? "testing fujinet n:http (fotofix)..."
40 TRAP 900
50 OPEN #1,12,0,"N:HTTP://fotofix.classic-computing.de/MUSTER/ascii-terminal.txt"
60 NB=0
70 GET #1,BY
80 NB=NB+1
90 IF BY=0 THEN 200
100 IF NB>500 THEN 200
110 ? CHR$(BY);
120 IF ST=0 THEN 70
200 ? "":? "done. characters read: ";NB
210 CLOSE #1
220 IF NB>1 THEN ? "http/fujinet works!"
230 IF NB<=1 THEN ? "no characters received - problem is with http/n:"
235 IF NB<=1 THEN ? "itself (dns/this mode/etc), not the basic code"
240 END
900 ? "":? "network error, code ";PEEK(195)
910 CLOSE #1
920 END
