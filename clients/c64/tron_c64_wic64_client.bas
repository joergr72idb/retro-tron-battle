10 if peek(49152)=32 then goto 40
20 poke631,82:poke632,85:poke633,78:poke634,13:poke198,4
30 load"FOTOFIX.C000",8,1
40 poke55,254:poke56,31:clr:sys50497
50 rem -- neustart-punkt nach jedem spiel (laden/init nur einmal) --
60 print chr$(147);chr$(14);chr$(18)
70 for i=1 to 40:print" ";:next i:print
80 print"   RETRO TRON BATTLE -"
90 print"   CLASSIC COMPUTING 2026"
100 print"     COMMODORE 64 / WIC64 EDITION - BUILD 1"
110 for i=1 to 40:print" ";:next i:print
120 print chr$(146):print
130 ho$="192.168.17.11":rem <-- edit: server ip
140 po$="8098":rem <-- edit: http-bridge-port! (siehe server-startmeldung)
150 na$="COMMODORE64":rem <-- edit: spielername
160 da=8190:rem zieladresse fuer wic64-abrufe (=$1ffe, wie im fotofix-beispiel)
170 tx$="MCP:> WELCOME TO THE GRID...":gosub4000
180 tx$="MCP:> USER ENTER YOUR PIN (OR ENTER":gosub4000
190 tx$="      FOR MOVEON WITHOUT):":gosub4000
200 input pi$
210 if pi$=""then pi$="NONE"
220 if pi$="NONE"then 260
230 tx$="MCP:> MASTER CONTROL PROGRAM SEARCH PHOTO...":gosub4000
240 tx$="MCP:> DOWNLOAD PHOTO FROM FOTOFIX-SERVER -":gosub4000
241 tx$="      UPLOAD TO GRID":gosub4000
250 gosub3000:rem ascii-kunst holen und anzeigen
260 tx$="MCP:> UPLOAD COMPLETED. CONNECTING GRIDSERVER "+ho$+":"+po$:gosub4000
270 u$="HTTP://"+ho$+":"+po$+"/JOIN/C64/"+na$+"/"+pi$
280 gosub2000:rem wic64-http-abruf -> r$
285 print"[debug join r$=<";r$;">]"
290 tx$="MCP:> YOU'VE GRANTED ACCESS TO THE GAME GRID":gosub4000
300 rem -- session-id aus r$ extrahieren --
310 sp=1
320 if mid$(r$,sp,1)=" "then340
330 sp=sp+1:ifsp<=len(r$)then320
340 ss=sp+1:se=ss
350 ifse>len(r$)then380
360 ifmid$(r$,se,1)=chr$(10)ormid$(r$,se,1)=chr$(13)then380
370 se=se+1:goto350
380 sn$=mid$(r$,ss,se-ss)
390 gs=0
400 ifleft$(r$,5)="START"then420
410 goto500
420 tx$="MCP:> GET READY FOR RACE. USE JOYSTICK -":gosub4000
430 tx$="      PORT 2. WATCH ON GRID SCREEN":gosub4000
440 gs=1
500 rem ===== hauptschleife =====
510 dr$="N"
520 j=(255-peek(56320))and31
530 nd$="N"
540 if(jand1)<>0thennd$="U"
550 if(jand2)<>0thennd$="D"
560 if(jand4)<>0thennd$="L"
570 if(jand8)<>0thennd$="R"
580 ifnd$<>"N"thendr$=nd$
590 u$="HTTP://"+ho$+":"+po$+"/TICK/"+sn$+"/"+dr$
600 gosub2000
610 ifr$=""then500
620 ifleft$(r$,3)="ERR"then900
630 ifgs=1then660
640 ifleft$(r$,5)<>"START"then660
650 tx$="MCP:> GET READY FOR RACE. USE JOYSTICK -":gosub4000:tx$="      PORT 2. WATCH ON GRID SCREEN":gosub4000:gs=1
660 ifleft$(r$,3)<>"END"then500
700 rem -- spiel zu ende: ergebnis zeigen, dann neustart --
710 tx$="MCP:> GAME ENDS HERE. "+r$:gosub4000
720 tx$="MCP:> GAME RESTARTS - RESETING ALL":gosub4000
730 tx$="      CONNECTIONS. PLEASE WAIT.":gosub4000
740 for dl=1 to10:forw=1to1500:nextw:nextdl
750 goto50
900 tx$="MCP:> SESSION ENDED - RESTARTING...":gosub4000:goto50
2000 rem -- wic64-http-abruf: url in u$ -> ergebnis in r$. nutzt die --
2001 rem    wiederverwendete fotofix.c000-treiberroutine (sys49152). --
2010 fori=0to199:pokeda+i,0:nexti
2020 sys49152,u$,da
2030 if 1 and peek(783) then r$="":return
2040 r$=""
2050 fori=0to199
2060 b=peek(da+i)
2070 ifb=0then2090
2080 r$=r$+chr$(b)
2085 nexti
2090 return
3000 rem -- ascii-kunst holen, zeichenweise auf 40 spalten reduziert --
3001 rem    anzeigen. nutzt dieselbe wic64-routine, aber ohne r$ zu --
3002 rem    fuellen (zu gross fuer eine c64-string-variable). --
3010 u$="HTTP://FOTOFIX.CLASSIC-COMPUTING.DE/"+pi$+"/ASCII-TERMINAL.TXT"
3020 fori=0to1999:pokeda+i,0:nexti
3030 sys49152,u$,da
3040 if 1 and peek(783) then return
3050 sc=0:oc=0
3060 fori=0to1999
3070 b=peek(da+i)
3080 ifb=0then3170
3090 ifb=13orb=10thensc=0:ifoc>0thenprint:oc=0
3095 ifb=13orb=10then3160
3100 if(scand1)<>0then3150
3110 ifb=94thenb=39
3120 printchr$(b);
3130 oc=oc+1:ifoc=40thenoc=0
3150 sc=sc+1:ifsc=80thensc=0
3160 nexti
3170 ifoc>0thenprint
3180 return
4000 rem -- tx$ mit terminal-tippeffekt ausgeben --
4010 fortc=1tolen(tx$)
4020 printmid$(tx$,tc,1);
4030 fortw=1to80:nexttw
4040 nexttc
4050 print
4060 return
