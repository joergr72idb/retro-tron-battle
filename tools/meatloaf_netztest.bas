10 rem =====================================
11 rem meatloaf network diagnostic
12 rem independent of our tron protocol
13 rem uses the official http example from
14 rem the meatloaf docs (device 8, sec.addr. 3)
15 rem =====================================
20 print chr$(147)
30 print "testing meatloaf http fetch..."
40 open 1,8,3,"https://example.com/"
50 c=0
60 get#1,a$
65 if a$<>"" then c=c+1:if c<200 then print a$;
70 if st<>0 then 100
90 goto 60
100 print
110 print "done. characters read: ";c
120 close 1
130 if c>0 then print "network/wifi works!"
140 if c=0 then print "no characters received - check wifi/network (not our protocol!)"
