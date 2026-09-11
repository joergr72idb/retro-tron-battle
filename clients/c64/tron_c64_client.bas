10 rem ===================================
11 rem retro tron - c64 client (http-polling)
12 rem server draws the board - this c64 just
13 rem steert. nutzt das bestaetigt funktion-
14 rem ierende meatloaf http-get-muster
15 rem (geraet 8, sekundaeradresse 3) statt
16 rem des unbestaetigten rohen sockets.
17 rem joystick in port 2.
18 rem ===================================
20 print chr$(147);chr$(14)
21 print chr$(18);
22 for i=1 to 40:print " ";:next i:print
23 print "   retro tron battle -"
24 print "   classic computing 2026"
25 print "     commodore 64 edition - build 11"
26 for i=1 to 40:print " ";:next i:print
27 print chr$(146)
28 print
30 ho$="192.168.17.11":rem <-- edit: server ip
40 po$="8098":rem <-- edit: http-bridge-port! (siehe server-startmeldung,
41 rem     NICHT der tcp-spielport 6502 - die http-bridge laeuft separat)
50 na$="COMMODORE64":rem <-- edit: dein spielername
100 tx$="mcp:> welcome to the grid...":gosub 4000
101 tx$="mcp:> user enter your pin (or enter":gosub 4000
102 tx$="      for moveon without):":gosub 4000
110 input pi$
120 if pi$="" then pi$="NONE"
121 if pi$="NONE" then 130
122 tx$="mcp:> master control program search photo...":gosub 4000
123 tx$="mcp:> download photo from fotofix-server -":gosub 4000
124 tx$="      upload to grid":gosub 4000
125 gosub 3000:rem ascii-kunst holen und anzeigen
126 for dl=1 to 5:for w=1 to 1500:next w:next dl :rem ca. 5 sek pause
130 tx$="mcp:> upload completed. connecting gridserver "+ho$+":"+po$:gosub 4000
140 u$="http://"+ho$+":"+po$+"/join/C64/"+na$+"/"+pi$
150 gosub 2000:rem http get -> r$
155 tx$="mcp:> you've granted access to the game grid":gosub 4000
160 rem erste zeile "session <id>" extrahieren
170 sp=1
180 if mid$(r$,sp,1)=" " then 200
190 sp=sp+1:if sp<=len(r$) then 180
200 ss=sp+1:se=ss
210 if se>len(r$) then 240
220 if mid$(r$,se,1)=chr$(10) or mid$(r$,se,1)=chr$(13) then 240
230 se=se+1:goto 210
240 sn$=mid$(r$,ss,se-ss)
250 gs=0
260 if left$(r$,5)="start" then 280
270 goto 400
280 tx$="mcp:> get ready for race. use joystick -":gosub 4000
281 tx$="      port 2. watch on grid screen":gosub 4000
290 gs=1
400 rem ===== main loop =====
405 dr$="N"
410 j=(255-peek(56320)) and 31
420 nd$="N"
430 if (j and 1)<>0 then nd$="U"
440 if (j and 2)<>0 then nd$="D"
450 if (j and 4)<>0 then nd$="L"
460 if (j and 8)<>0 then nd$="R"
470 if nd$<>"N" then dr$=nd$
480 u$="http://"+ho$+":"+po$+"/tick/"+sn$+"/"+dr$
490 gosub 2000:rem http get -> r$
491 if r$="" then 560
492 ec=0
493 if left$(r$,3)="err" then 800
494 if gs=1 then 510
495 if left$(r$,5)<>"start" then 510
496 tx$="mcp:> get ready for race. use joystick -":gosub 4000
497 tx$="      port 2. watch on grid screen":gosub 4000
498 gs=1
510 if left$(r$,3)<>"end" then 400
520 rem -- spiel zu ende: ergebnis zeigen, dann neustart --
521 tx$="mcp:> game ends here. "+r$:gosub 4000
523 rem kanal ist schon durch subroutine 2000 geschlossen worden
525 tx$="mcp:> game restarts - reseting all":gosub 4000
526 tx$="      connections. please wait.":gosub 4000
527 for dl=1 to 10:for w=1 to 1500:next w:next dl :rem ca. 10 sek, bei bedarf anpassen
528 goto 20
560 if gs=0 then 400 :rem noch kein gegner - das darf beliebig lange dauern
561 ec=ec+1
562 if ec>500 then tx$="mcp:> no response for a while - restarting...":gosub 4000:goto 20
563 goto 400
800 tx$="mcp:> session ended - restarting...":gosub 4000:goto 20
2000 rem -- http get u$ -> r$ (das bestaetigt funktionierende muster) --
2010 open 1,8,3,u$
2020 r$=""
2030 get#1,a$
2035 if a$<>"" then if len(r$)<250 then r$=r$+a$
2040 if st<>0 then 2070
2060 goto 2030
2070 close 1
2080 return
3000 rem -- ascii-kunst per http holen, zeichenweise auf 40 spalten reduziert
3001 rem    anzeigen (80x24 -> 40x24, jedes 2. zeichen, ^ ersetzt) --
3010 au$="http://fotofix.classic-computing.de/"+pi$+"/ascii-terminal.txt"
3020 open 1,8,3,au$
3030 sc=0:oc=0
3040 get#1,a$
3050 if a$<>"" then gosub 3200
3060 if st<>0 then 3090
3070 goto 3040
3090 close 1
3095 if oc>0 then print
3099 return
3200 rem -- ein empfangenes zeichen verarbeiten --
3210 if a$=chr$(13) or a$=chr$(10) then sc=0:if oc>0 then print:oc=0
3220 if a$=chr$(13) or a$=chr$(10) then return
3230 if (sc and 1)<>0 then goto 3260
3240 if a$="^" then a$=chr$(39):rem petscii-riskantes zeichen ersetzen
3250 print a$;:oc=oc+1:if oc=40 then print:oc=0
3260 sc=sc+1:if sc=80 then sc=0
3270 return
4000 rem -- tx$ mit terminal-tippeffekt ausgeben (wie das bild) --
4010 for ti=1 to len(tx$)
4020 print mid$(tx$,ti,1);
4030 for tw=1 to 80:next tw :rem tippgeschwindigkeit - kleiner=schneller
4040 next ti
4050 print
4060 return
