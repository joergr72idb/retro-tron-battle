10 if peek(49152)=32 then goto 40
20 poke631,82:poke632,85:poke633,78:poke634,13:poke198,4
30 rem -- filename klein schreiben! petcat tokenisiert grossbuchstaben in
31 rem    strings als "shifted" petscii (128+), das echte diskettenverzeichnis
32 rem    nutzt aber unshiftetes petscii - load faende die datei sonst nie.
33 load"fotofix.c000",8,1
40 poke55,254:poke56,31:clr:sys50497
41 rem -- winziger cli+rts-stub im kassettenpuffer (immer freies ram):
42 rem    zwingt interrupts wieder an, falls sys49152 sie deaktiviert
43 rem    laesst (deshalb blieb der joystick auf port 2 immer 0 -
44 rem    port 2 braucht den kernal-tastatur-scan-irq, um sich zwischen
45 rem    abfragen in den ruhezustand zurueckzusetzen).
46 poke828,88:poke829,96
50 rem -- neustart-punkt, per "run" erreicht (laden/init nur einmal, --
51 rem    zeile10-checkt ob treiber schon geladen ist) --
60 print chr$(147);chr$(14);chr$(18)
70 for i=1 to 40:print" ";:next i:print
80 print"   RETRO TRON BATTLE -"
90 print"   CLASSIC COMPUTING 2026"
100 print"     COMMODORE 64 / WIC64 EDITION - BUILD 8"
110 for i=1 to 40:print" ";:next i:print
120 print chr$(146):print
130 ho$="192.168.17.158":rem <-- edit: server ip
140 po$="8080":rem <-- edit: http-bridge-port! (siehe server-startmeldung)
150 na$="COMMODORE64":rem <-- edit: spielername
160 da=8190:rem zieladresse fuer wic64-abrufe (=$1ffe, wie im fotofix-beispiel)
170 print"enter your pin or press enter:"
180 input pi$
181 rem -- port-1-joystick teilt sich die tastaturmatrix; phantom-taste kann
182 rem    cursor auf die prompt-zeile zuruecksetzen, "input" liest dann den
183 rem    prompt-text selbst als pin. laenge/leerzeichen-check faengt das ab.
184 bad=0:iflen(pi$)>10thenbad=1:goto187
185 forpc=1tolen(pi$):ifmid$(pi$,pc,1)=" "thenbad=1
186 nextpc
187 ifbad=1thenpi$=""
190 if pi$=""then pi$="NONE"
200 print"connecting..."
210 u$="http://"+ho$+":"+po$+"/join/C64/"+na$+"/"+pi$
220 gosub2000:rem wic64-http-abruf -> r$
230 ifleft$(r$,7)="SESSION"then270
240 ifleft$(r$,7)="session"then270
250 print"[debug join r$=<";r$;">]"
260 fordl=1to3:forw=1to1500:nextw:nextdl:goto200
270 rem -- session-id aus r$ extrahieren --
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
500 rem ===== hauptschleife =====
510 dr$="N"
520 j=(255-peek(56320))and31
530 nd$="N"
540 if(jand1)<>0thennd$="U"
550 if(jand2)<>0thennd$="D"
560 if(jand4)<>0thennd$="L"
570 if(jand8)<>0thennd$="R"
580 ifnd$<>"N"thendr$=nd$
585 rem -- temporaere diagnose: zeigt rohen joystickwert + ermittelte
586 rem    richtung, um zu pruefen ob das problem beim lesen oder erst
587 rem    bei der uebertragung durch den treiber liegt. spaeter entfernen.
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
700 rem -- spiel zu ende: ergebnis zeigen, dann neustart --
710 print"game over":printr$
720 print"restarting..."
740 fordl=1to3:forw=1to1500:nextw:nextdl:rem ca.3sek
750 run
900 print"restarting...":run
2000 rem -- wic64-http-abruf: url in u$ -> ergebnis in r$. nutzt die --
2001 rem    wiederverwendete fotofix.c000-treiberroutine (sys49152). --
2010 fori=0to199:pokeda+i,0:nexti
2020 sys49152,u$,da
2025 sys828:rem cli-stub - siehe kommentar bei zeile 41
2030 if 1 and peek(783) then r$="":return
2040 r$=""
2050 fori=0to199
2060 b=peek(da+i)
2070 ifb=0then2090
2080 r$=r$+chr$(b)
2085 nexti
2090 return
