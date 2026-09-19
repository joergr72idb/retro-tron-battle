10 rem ===================================
11 rem standalone joystick test - c64
12 rem no networking. shows port 2 ($dc00)
13 rem and port 1 ($dc01) side by side so
14 rem keyboard-scan ghosting is visible live.
15 rem same convention as the real client:
16 rem j=(255-peek(addr)) and 31
17 rem 1=up 2=down 4=left 8=right 16=fire
18 rem ===================================
20 print chr$(147);chr$(14)
100 print chr$(147)
110 print "move joystick / press keys."
120 print "watch if port 1 changes on its own"
130 print "while typing - that's the ghosting"
140 print "bug this project moved to port 2 for."
150 print "idle = 0 (no bits set)."
160 print
170 j=(255-peek(56320)) and 31:gosub 500
180 print "port 2 ($dc00) = ";j;" ";d$
190 j=(255-peek(56321)) and 31:gosub 500
200 print "port 1 ($dc01) = ";j;" ";d$
210 goto 100
500 rem -- decode bits of j into direction text --
510 d$=""
520 if (j and 1)<>0 then d$=d$+"up "
530 if (j and 2)<>0 then d$=d$+"down "
540 if (j and 4)<>0 then d$=d$+"left "
550 if (j and 8)<>0 then d$=d$+"right "
560 if (j and 16)<>0 then d$=d$+"fire "
570 if d$="" then d$="-"
580 return
