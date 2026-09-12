10 rem ===================================
11 rem retro tron - c64 client (http-polling)
12 rem server draws the board - this c64 just
13 rem steert. nutzt das bestaetigt funktion-
14 rem ierende meatloaf http-get-muster
15 rem (geraet 8, sekundaeradresse 3) statt
16 rem des unbestaetigten rohen sockets.
17 rem joystick in port 1.
18 rem ===================================
20 print chr$(147);chr$(14)
21 print chr$(18);
22 for i=1 to 40:print " ";:next i:print
23 print "   retro tron battle -"
24 print "   classic computing 2026"
25 print "     commodore 64 edition - build 13"
26 for i=1 to 40:print " ";:next i:print
27 print chr$(146)
28 print
30 ho$="192.168.17.158":rem <-- edit: server ip
40 po$="8080":rem <-- edit: http-bridge-port! (siehe server-startmeldung,
41 rem     NICHT der tcp-spielport 6502 - die http-bridge laeuft separat)
50 na$="COMMODORE64":rem <-- edit: dein spielername
100 print "enter your pin or press enter:"
110 input pi$
120 if pi$="" then pi$="NONE"
130 print "connecting..."
140 u$="http://"+ho$+":"+po$+"/join/C64/"+na$+"/"+pi$
150 gosub 2000:rem http get -> r$
160 if left$(r$,7)="session" or left$(r$,7)="SESSION" then 220
170 for dl=1 to 3:for w=1 to 1500:next w:next dl:goto 140
220 rem erste zeile "session <id>" extrahieren
230 sp=1
240 if mid$(r$,sp,1)=" " then 260
250 sp=sp+1:if sp<=len(r$) then 240
260 ss=sp+1:se=ss
270 if se>len(r$) then 300
280 if mid$(r$,se,1)=chr$(10) or mid$(r$,se,1)=chr$(13) then 300
290 se=se+1:goto 270
300 sn$=mid$(r$,ss,se-ss)
310 gs=0
320 if left$(r$,5)="start" then 340
330 print "waiting for opponent...":goto 400
340 print "use joystick - port 1":gs=1
400 rem ===== main loop =====
405 dr$="N"
410 j=(255-peek(56321)) and 31
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
496 print "use joystick - port 1":gs=1
510 if left$(r$,3)<>"end" then 400
520 rem -- spiel zu ende: ergebnis zeigen, dann neustart --
521 print "game over":print r$
525 print "restarting..."
527 for dl=1 to 10:for w=1 to 1500:next w:next dl :rem ca. 10 sek, bei bedarf anpassen
528 goto 20
560 if gs=0 then 400 :rem noch kein gegner - das darf beliebig lange dauern
561 ec=ec+1
562 if ec>500 then print "no response - restarting...":goto 20
563 goto 400
800 print "restarting...":goto 20
2000 rem -- http get u$ -> r$ (das bestaetigt funktionierende muster) --
2010 open 1,8,3,u$
2020 r$=""
2030 get#1,a$
2035 if a$<>"" then if len(r$)<250 then r$=r$+a$
2040 if st<>0 then 2070
2060 goto 2030
2070 close 1
2080 return
