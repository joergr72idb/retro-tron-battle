10 if peek(49152)=32 then goto 40
20 poke631,82:poke632,85:poke633,78:poke634,13:poke198,4
30 rem -- write filename lowercase! petcat tokenizes uppercase in
31 rem    strings as "shifted" petscii (128+), but the real disk directory
32 rem    uses unshifted petscii - load would never find the file otherwise.
33 load"fotofix.c000",8,1
40 poke55,254:poke56,31:clr:sys50497
41 rem -- tiny cli+rts stub in the cassette buffer (always free ram):
42 rem    forces interrupts back on if sys49152 leaves them disabled
43 rem    (that's why the joystick on port 2 always read 0 - port 2
44 rem    needs the kernal keyboard-scan irq to reset itself back to
45 rem    idle between reads).
46 poke828,88:poke829,96
50 rem -- restart point, reached via "run" (load/init only once, --
51 rem    line 10 checks whether the driver is already loaded) --
60 print chr$(147);chr$(14);chr$(18)
70 for i=1 to 40:print" ";:next i:print
80 print"   RETRO TRON BATTLE -"
90 print"   CLASSIC COMPUTING 2026"
100 print"     COMMODORE 64 / WIC64 EDITION - BUILD 8"
110 for i=1 to 40:print" ";:next i:print
120 print chr$(146):print
130 ho$="192.168.17.138":rem <-- edit: server ip
140 po$="8080":rem <-- edit: http bridge port! (see server startup message)
150 na$="COMMODORE64":rem <-- edit: player name
160 da=8190:rem target address for wic64 fetches (=$1ffe, as in the fotofix example)
170 print"enter your pin or press enter:"
180 input pi$
181 rem -- port-1 joystick shares the keyboard matrix; a phantom key can
182 rem    reset the cursor onto the prompt line, "input" then reads the
183 rem    prompt text itself as the pin. length/whitespace check catches that.
184 bad=0:iflen(pi$)>10thenbad=1:goto187
185 forpc=1tolen(pi$):ifmid$(pi$,pc,1)=" "thenbad=1
186 nextpc
187 ifbad=1thenpi$=""
190 if pi$=""then pi$="NONE"
200 print"connecting..."
210 u$="http://"+ho$+":"+po$+"/join/C64/"+na$+"/"+pi$
220 gosub2000:rem wic64 http fetch -> r$
230 ifleft$(r$,7)="SESSION"then270
240 ifleft$(r$,7)="session"then270
250 print"[debug join r$=<";r$;">]"
260 fordl=1to3:forw=1to1500:nextw:nextdl:goto200
270 rem -- extract session id from r$ --
280 sp=1
290 if mid$(r$,sp,1)=" "then310
300 sp=sp+1:ifsp<=len(r$)then290
310 ss=sp+1:se=ss
320 ifse>len(r$)then350
330 ifmid$(r$,se,1)=chr$(10)ormid$(r$,se,1)=chr$(13)then350
340 se=se+1:goto320
350 sn$=mid$(r$,ss,se-ss)
360 gs=0
370 ifleft$(r$,5)="START"orleft$(r$,5)="start"then400
380 print"waiting for opponent...":goto500
400 print"use joystick - port 2":gs=1
500 rem ===== main loop =====
510 dr$="N"
520 j=(255-peek(56320))and31
530 nd$="N"
540 if(jand1)<>0thennd$="U"
550 if(jand2)<>0thennd$="D"
560 if(jand4)<>0thennd$="L"
570 if(jand8)<>0thennd$="R"
580 ifnd$<>"N"thendr$=nd$
585 rem -- temporary diagnostic: shows the raw joystick value + the
586 rem    resulting direction, to check whether the problem is in reading
587 rem    it or only in transmission via the driver. remove later.
588 printchr$(19);"j=";j;" dir=";dr$;"      "
590 u$="http://"+ho$+":"+po$+"/tick/"+sn$+"/"+dr$
600 gosub2000
610 ifr$=""then500
615 if(left$(r$,3)="ERR"orleft$(r$,3)="err")thenprint"[debug tick r$=<";r$;"> sn$=<";sn$;">]"
620 ifleft$(r$,3)="ERR"orleft$(r$,3)="err"then900
630 ifgs=1then660
640 if(left$(r$,5)<>"START"andleft$(r$,5)<>"start")then660
650 print"use joystick - port 2":gs=1
660 if(left$(r$,3)<>"END"andleft$(r$,3)<>"end")then500
700 rem -- game over: show result, then restart --
710 print"game over":printr$
720 print"restarting..."
740 fordl=1to3:forw=1to1500:nextw:nextdl:rem ~3sec
750 run
900 print"restarting...":run
2000 rem -- wic64 http fetch: url in u$ -> result in r$. uses the --
2001 rem    reused fotofix.c000 driver routine (sys49152). --
2010 fori=0to199:pokeda+i,0:nexti
2020 sys49152,u$,da
2025 sys828:rem cli stub - see comment at line 41
2030 if 1 and peek(783) then r$="":return
2040 r$=""
2050 fori=0to199
2060 b=peek(da+i)
2070 ifb=0then2090
2080 r$=r$+chr$(b)
2085 nexti
2090 return
