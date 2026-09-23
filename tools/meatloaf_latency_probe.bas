10 rem ===================================
11 rem meatloaf latency probe - throwaway
12 rem NOT part of the real client - just
13 rem measures: fresh open/close per
14 rem request (addr 3, today's method) vs
15 rem one open + reused channel (addr 2,
16 rem full http client, per meatloaf docs)
17 rem safe to run against the real server -
18 rem hits /tick with a bogus session, gets
19 rem a harmless "err unknown session" back
20 print chr$(147)
30 ho$="192.168.17.138":rem <-- edit: server ip
40 po$="8080":rem <-- edit: http bridge port
50 n=10:rem requests per test
60 u$="http://"+ho$+":"+po$+"/tick/probe/n"
70 sa=0:sb=0
100 print "test a: fresh open/close per request"
110 print "        (device 8, addr 3 - today's method)"
120 for i=1 to n
130 t0=ti:e=0
140 open 1,8,3,u$
150 get#1,a$:e=e+1
155 if e>3000 then close 1:print "  timeout on req";i:goto 900
160 if st=0 then 150
170 close 1
180 d=ti-t0
190 print "  req";i;": ";d;" jiffies"
200 sa=sa+d
210 next i
220 print "  avg: ";sa/n;" jiffies/req"
230 print
300 print "test b: one open, reused channel"
310 print "        (device 8, addr 2 - full http client)"
320 open 2,8,2,u$
330 for i=1 to n
340 t0=ti:e=0
350 print#2,"m get"
360 print#2,"s"
370 print#2,"r-b"
380 get#2,a$:e=e+1
385 if e>3000 then close 2:print "  timeout on req";i:goto 900
390 if (st and 64)=0 then 380
400 print#2,"c"
410 d=ti-t0
420 print "  req";i;": ";d;" jiffies"
430 sb=sb+d
440 next i
450 close 2
460 print "  avg: ";sb/n;" jiffies/req"
470 print
500 print "ratio a/b: ";sa/sb;" (>1 means"
510 print "reuse is faster)"
520 print
530 print "jiffies: /50=sec pal, /60=sec ntsc"
540 print "done."
550 end
900 print "aborted - a request hung. if this"
910 print "was test b, addr 2 reuse may not"
920 print "work as documented on this"
930 print "firmware version."
