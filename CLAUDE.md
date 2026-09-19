# CLAUDE.md — Kontext & Lektionen für dieses Projekt

Dieses Dokument richtet sich an jeden (KI-Assistent oder Mensch), der an
diesem Projekt weiterarbeitet. Es fasst zusammen, was in der ursprünglichen
Entwicklungssession (Claude, über mehrere Wochen) mühsam herausgefunden
wurde — vieles davon ist auf keiner offiziellen Doku-Seite zu finden.
**Bitte lesen, bevor du an den Clients herumschraubst — sonst wiederholst
du wahrscheinlich Fehler, die schon gemacht und behoben wurden.**

## Projektüberblick

Ein Tron/Lightcycle-Duell für eine Retro-Computing-Ausstellung, gebaut für
[Classic Computing 2026](https://www.classic-computing.de/cc2026/) in
Celle (10.–11. Oktober 2026, Halle 10 / CD-Kaserne). Drei echte
Retro-Rechner (Atari XL/XE, Commodore 64, Schneider/Amstrad CPC) treten
gegeneinander an. Ein Python-Server auf einem modernen PC übernimmt die
komplette Spiellogik und zeichnet alles selbst (pygame-Fenster, gut für
einen Beamer) — die Retro-Rechner steuern nur per Joystick.

Jeder Retro-Rechner braucht ein passendes WiFi-Interface, um den Server
zu erreichen:

- **Atari XL/XE:** [FujiNet](https://fujinet.online/)
- **Commodore 64 (Standard-Client):** [Meatloaf](https://github.com/idolpx/meatloaf)
- **Commodore 64 (experimenteller Client):** [WiC64](https://www.wic64.de/)
- **Schneider/Amstrad CPC:** [M4 Board](https://www.cpcwiki.eu/index.php/M4_Board)

## Architektur in Kürze

- **`server/tron_server.py`** — der einzige Server. Führt Spiellogik aus,
  zeichnet das Spielfeld, verwaltet Fotos/Logos/Scrolltext/Statistik.
  Der Haupt-Docstring im Code selbst ist die primäre Protokoll-Doku —
  bei Änderungen am Protokoll dort zuerst nachschauen/aktualisieren.
- **Zwei Teilnahme-Methoden**, je nach Hardware-Fähigkeit:
  - **Rohes TCP** (Port 6502) — für Atari/FujiNet, das einen dauerhaften
    Socket aus BASIC heraus offen halten kann.
  - **HTTP-Polling** (Port 8080, Routen `/join` und `/tick`) — für C64
    (Meatloaf) und Schneider CPC (M4), die das nicht zuverlässig können.
- Beide Wege laufen serverseitig durch **dieselbe** `run_game()`-Logik.

## Die wichtigsten Lektionen (chronologisch nach Plattform)

### Commodore 64 + Meatloaf

- **PETSCII-Fallstrick (der wichtigste Fund im ganzen Projekt):**
  Meatloaf wandelt beim Lesen über `GET#` empfangenen HTTP-Text-Inhalt
  **tatsächlich in Kleinbuchstaben um** — keine reine Anzeige-Eigenart,
  sondern eine echte Byte-Umwandlung. Server sendet z.B. `START`, C64
  empfängt `start`. **Konsequenz:** Jeder String-Vergleich auf Client- UND
  Server-Seite muss das tolerieren (siehe `session_id.upper()` im Server,
  und die doppelten `="start" OR ="START"`-Prüfungen im C64-Client).
- **Joystick-Port: zurück auf Port 2 (2026-09-14, endgültig) —
  C64-spezifische Ausnahme von der "erster Joystick-Port"-Konvention:**
  Beide C64-Clients lasen den Joystick eine Zeit lang aus Port 1
  (`PEEK(56321)`, CIA#1 Port B, `$DC01`), um plattformübergreifend
  konsistent "immer den ersten Joystick-Port" zu nutzen. Port 1 teilt sich
  aber `$DC01` mit dem KERNAL-Tastatur-Scan (läuft per IRQ 60x/Sek. im
  Hintergrund, unabhängig vom BASIC-Programm) — das theoretische
  "Ghosting"-Risiko wurde am 2026-09-14 auf echter Hardware real
  beobachtet (siehe PIN-Eingabe-Lektion weiter unten: ein
  Phantom-Tastendruck verfälschte die PIN-Abfrage nach einem Neustart).
  **Fix:** beide C64-Clients lesen den Joystick jetzt wieder aus **Port 2**
  (`PEEK(56320)`, CIA#1 Port A, `$DC00`) — Bit-Layout identisch zu Port 1
  (Bit 0-3 = Up/Down/Left/Right, aktiv-low), nur die Peek-Adresse ändert
  sich. Port 2 teilt sich keine Leitungen mit der Tastaturmatrix, ist
  deshalb ghosting-frei. **Konsequenz:** Die C64-Clients (Meatloaf UND
  WiC64) sind damit eine bewusste, dokumentierte Ausnahme von der
  "gleicher Joystick-Port auf jeder Plattform"-Konvention (siehe
  Muster 7 unten) — Zuverlässigkeit auf der Ausstellung hat Vorrang vor
  Konsistenz. Betrifft nur das Lesen des Joysticks in der Hauptschleife;
  die PIN-Eingabe-Validierung (Längen-/Leerzeichen-Check, siehe unten)
  bleibt zusätzlich als zweite Absicherung bestehen.
- **`TI` ist eine reservierte Systemvariable** (Jiffy-Uhr) in Commodore
  BASIC — genau wie `PI` beim CPC (siehe unten) darf sie nicht als eigener
  Variablenname verwendet werden. Symptom: `?SYNTAX ERROR` an einer Stelle,
  die beim genauen Hinsehen überhaupt nichts Verdächtiges enthält.
  **Ist zweimal aufgetreten:** einmal ursprünglich, dann erneut am
  2026-09-12 als `ti` Schleifenvariable in der Tippeffekt-Subroutine
  (Zeile 4010, `tron_c64_client.bas`) — der WiC64-Client hat dieselbe
  Subroutine, nennt die Variable dort aber bereits korrekt `tc`. Bei
  neuem Code für diese Subroutine (oder Kopien davon) **immer `tc`
  verwenden, nie `ti`**.
- **Ungeprüfte Join-Antwort → Session-Mismatch (2026-09-12, auf echter
  Hardware gefunden):** Der Meatloaf-Client extrahierte die Session-ID
  aus der `/join`-Antwort rein positionsbasiert (erstes Leerzeichen bis
  Zeilenende), ohne vorher zu prüfen, ob die Antwort überhaupt mit
  `SESSION`/`session` beginnt — genau derselbe Bug, der beim WiC64-Client
  schon einmal gefunden und dort bereits gefixt war (siehe WiC64-Abschnitt
  unten), hier aber im Meatloaf-Client übersehen. Symptom auf Hardware:
  Server-Log zeigt `/tick`-Aufrufe mit einer Session-ID, die serverseitig
  nie existiert hat (`aktuelle keys: []`) — wirkt wie ein Groß-/
  Kleinschreibungsproblem, ist aber eigentlich eine ungültige/leere
  extrahierte ID aus einer nicht als Erfolg erkannten Antwort. **Fix:**
  Join-Antwort wird jetzt auf `SESSION`/`session`-Prefix geprüft, bevor
  die ID weiterverwendet wird (kurze Pause + Retry sonst) — analog zum
  WiC64-Fix. Gleichzeitig im CPC-Client vorsorglich mitgefixt, da
  strukturell identischer Code (gleiches `/join`-Antwortformat).
- **Port-1-Joystick kann die PIN-Eingabe verfaelschen (2026-09-14, auf
  echter Hardware gefunden):** Joystick Port 1 haengt am selben CIA1-Register
  ($DC01/56321), das der KERNAL-Tastatur-Scan (laeuft per IRQ 60x/Sek. im
  Hintergrund, unabhaengig vom BASIC-Programm) zum Auslesen der
  Tastaturmatrix-Zeilen benutzt. Steht der Joystick in Port 1, kann das
  theoretisch (siehe Joystick-Port-Lektion oben) einen Phantom-Tastendruck
  erzeugen — beobachtet wurde ein Phantom-Cursor-Up+RETURN genau waehrend
  der `INPUT PI$`-PIN-Abfrage nach einem Neustart. Der C64-Bildschirmeditor
  behandelt beim `INPUT`-Befehl die aktuelle Bildschirmzeile als Eingabe:
  landet der Cursor per Phantom-Tastendruck auf der bereits ausgegebenen
  Prompt-Zeile ("enter your pin or press enter:") und feuert dort ein
  Phantom-RETURN, wird die Prompt-Zeile selbst als PIN eingelesen und an
  `/join` geschickt (Server-Log zeigt dann exakt den Prompt-Text als PIN;
  Symptom fuer den Spieler: der Foto-Abruf schlaegt mit 404 fehl). **Das
  eigentliche Steuern ist NICHT betroffen** — die Hauptschleife liest den
  Joystick per direktem `PEEK`, nie ueber den (von diesem Bug betroffenen)
  Tastatur-/Bildschirm-Eingabepfad. **Fix (zwei Ebenen):** (1) `pi$` nach
  dem `INPUT` auf Laenge (>10 Zeichen) und Leerzeichen pruefen, im
  Verdachtsfall auf `""` (→ `"NONE"`) zuruecksetzen — in
  `tron_c64_client.bas` UND `tron_c64_wic64_client.bas`. (2) Root Cause
  behoben: beide Clients lesen den Joystick seit 2026-09-14 aus **Port 2**
  statt Port 1 (siehe Joystick-Port-Lektion oben) — vermeidet den
  Leitungskonflikt komplett, statt nur dessen Symptom abzufangen. Der
  PIN-Laengen-/Leerzeichen-Check bleibt trotzdem als zweite, billige
  Absicherung im Code.
- **HTTP-Session-Race-Condition:** Ein `/tick`, das genau beim Spielende
  eintrifft, muss noch Zeit haben, das `END`+`STATS` abzuholen, bevor die
  Session serverseitig aufgeräumt wird. Lösung: 15 Sekunden Gnadenfrist
  nach `close()`, bevor die Session wirklich gelöscht wird
  (`HTTPPlayerConn._expire`).
- **`GET#` char-für-char:** Erst das Byte verwenden, DANN `ST` prüfen
  (nicht umgekehrt) — sonst geht das letzte Byte vor Verbindungsende
  verloren.

### Schneider/Amstrad CPC + M4-Board

- **`PI` ist ein reserviertes Schlüsselwort** (Kreiszahl π) in Locomotive
  BASIC. `PI$` als Variablenname erzeugt einen `Syntax error`, der beim
  Zurücklisten ein verräterisches Leerzeichen vor dem `$` zeigt
  (`INPUT PI $` statt `INPUT PI$`). Generelles Muster, falls das nochmal
  auftaucht: kurze, unscheinbare Variablennamen können mit reservierten
  Wörtern kollidieren (`TIME`, `MAX`, `MIN`, `FIX`, `TAG`, `MASK`, `TEST`
  sind weitere Kandidaten in Locomotive BASIC).
- **`|HTTPMEM` lädt in einen Speicherpuffer**, nicht in eine String-
  Variable — praktisch, da CPC-Strings (wie C64) auf 255 Zeichen begrenzt
  sind. Puffer vor jedem Abruf mit Nullen vorfüllen, danach bis zum ersten
  Nullbyte scannen.
- **"Line too long"-Fehler beim Laden** hatte NICHTS mit der tatsächlichen
  Zeilenlänge zu tun (alle Zeilen waren weit unter dem ~255-Zeichen-Limit).
  Ursache war ein fehlender/falscher AMSDOS-Header beim Hochladen über
  das M4-Webinterface. Lösung war letztlich **WinAPE mit "Auto Type"**
  (tippt eine Textdatei zeichenweise ein, genau wie beim Atari-Emulator-
  Paste) — das umgeht das Headerproblem komplett.

### Atari XL/XE + FujiNet

- **`N:TCP://`** (fürs eigentliche Spiel) und **`N:HTTP://`** (für den
  ASCII-Kunst-Abruf) verhalten sich **unterschiedlich**, obwohl beide über
  dasselbe `N:`-Device laufen:
  - TCP: `AUX2=2` (CR/LF-Übersetzung) ist korrekt — bestätigt über
    hunderte Testspiele.
  - HTTP: `AUX2` hat dort eine andere Bedeutung — `AUX2=0`, nicht `2`.
  - Beim HTTP-Modus **kein XIO 77 nötig** — das war eine falsche Annahme
    von mir (Claude) aus einer zu wörtlichen Doku-Interpretation, die zu
    Fehler 146 ("Funktion nicht unterstützt") führte.
  - `ST` nach einem `GET#` im HTTP-Modus ist **nicht zuverlässig** als
    "fertig"-Signal nutzbar (führte zu endlosem Nullbyte-Ausgeben,
    ATASCII `CHR$(0)` = Herzchen-Symbol). Ein Nullbyte selbst als Ende-
    Signal zu werten hat zuverlässig funktioniert.
  - **Firmware-Version ist entscheidend:** Mit FujiNet-Firmware 1.4
    (Oktober 2024) funktionierte der HTTP-Modus praktisch gar nicht
    (immer nur 1 Byte, dann Stille). Mit 1.51 lief es. Offizielle Doku-
    Beispiele stimmen nur mit halbwegs aktueller Firmware überein.
- **Zwei verschiedene Kanäle (`#1` fürs Spiel, `#2` fürs Bild) gleichzeitig
  "bekannt" zu haben** hat zu Fehler 144 geführt beim Wechsel vom Bild zum
  Spiel. Lösung: **strikt denselben Kanal** für beides nacheinander nutzen
  (öffnen, benutzen, schließen, dann neu öffnen).
- **`GOTO` zum Neustarten reicht nicht** — nach einem abgeschlossenen
  Spiel funktionierte der *zweite* ASCII-Kunst-Abruf nicht mehr
  zuverlässig, obwohl der *erste* tadellos lief. Der Sprung von `GOTO
  <neustart-zeile>` (bleibt im selben Programmlauf) auf ein echtes `RUN`
  (kompletter Neustart, alle Variablen weg, offenbar auch ein
  gründlicherer Reset auf OS-/FujiNet-Ebene) hat das behoben. Falls
  ähnliche "funktioniert beim ersten Mal, nicht beim zweiten Mal"-Symptome
  wieder auftauchen: **`RUN` statt `GOTO`** als Test in Erwägung ziehen.
- Bei Atari BASIC gibt es **keine Zeilen-Länge über ~120 Zeichen** — lange
  zusammengesetzte Anweisungen (mit `:` verkettet) ggf. auf mehrere
  Zeilen aufteilen. Symptom: "ERROR bei der Übertragung" beim Einspielen.

### Commodore 64 + WiC64 (neuester, experimenteller Client)

- WiC64 hängt am **User-Port** (nicht am seriellen/IEC-Bus wie Meatloaf) —
  komplett andere Hardware, eigenes Protokoll.
- Statt eigenen Assembler-Code zu schreiben: Ein vom Nutzer bereitgestelltes
  Beispielprogramm (`FOTOFIX.C000`, aus einem D64-Image extrahiert) enthält
  bereits eine **wiederverwendbare** `SYS 49152,U$,Zieladresse`-Routine,
  die die WiC64-Low-Level-Details kapselt. Statt das nachzubauen: **einfach
  mit wiederladen und mit unseren eigenen URLs aufrufen** (`archive/`
  enthält den ursprünglichen, verworfenen Ansatz "eigenen Treiber von
  Grund auf schreiben" — nicht weiterverfolgen, der oben genannte Ansatz
  ist vielversprechender). **Autor von `FOTOFIX.C000`: Andreas Beermann**
  ("andi6510", siehe Disk-Label der Original-`fotofix.d64`) — die Datei
  liegt jetzt unter `clients/c64/wic64-driver/` im Repo, siehe die
  README dort für Details/Credit.
- **Ursache des "`/join` scheinbar ok, `/tick` konsequent 'ERR UNKNOWN
  SESSION'"-Bugs gefunden (2026-09-11, noch nicht auf echter Hardware
  verifiziert):** Das im Repo mitgelieferte, definitiv funktionierende
  Referenzbeispiel `fotofix.prg` (auf derselben Diskette) ruft `SYS 49152`
  ausschließlich mit **kleingeschriebenen** URLs auf
  (`"http://fotofix.classic-computing.de/"+id$+...`). Unser WiC64-Client
  baute die Join-/Tick-URLs dagegen mit **Großschreibung**
  (`"HTTP://"+ho$+":"+po$+"/JOIN/..."` bzw. `"/TICK/..."`). Zusätzlich
  prüfte die Session-ID-Extraktion nicht, ob die Antwort überhaupt mit
  `SESSION` beginnt — bei einer Fehlerantwort (z.B. vom Server als
  `"ERR UNKNOWN REQUEST"` zurückgegeben, falls die Pfad-Großschreibung den
  Server verwirrt) wurde einfach der Text nach dem ersten Leerzeichen als
  vermeintliche Session-ID übernommen. Das erklärt den Eindruck "`/join`
  hat funktioniert" (`r$` war nicht leer, sah nach einer ID aus), obwohl
  in Wahrheit keine gültige Session existierte — jedes `/tick` scheiterte
  danach zwangsläufig.
  **Fix in `tron_c64_wic64_client.bas`:** alle URLs (Join, Tick,
  ASCII-Kunst-Abruf) auf Kleinschreibung umgestellt (matching
  `fotofix.prg`); Join-Antwort wird jetzt auf `SESSION`/`session`-Prefix
  geprüft, bevor die Session-ID weiterverwendet wird (sonst kurze Pause +
  Retry); Debug-Ausgabe bei `/tick`-Fehlern ergänzt (zeigt `r$` und `sn$`
  auf dem Bildschirm), analog zum bereits vorhandenen Join-Debug-Print.
  **Nächster Schritt:** auf echter Hardware testen — falls das
  `/tick`-Problem weiterhin auftritt, zeigt die neue Debug-Ausgabe jetzt
  wenigstens die rohe Serverantwort statt im Dunkeln zu tappen.
- Ladetrick: Nach `LOAD"fotofix.c000",8,1` stoppt das BASIC-Programm
  (Standardverhalten bei `LOAD` aus einem laufenden Programm heraus, auch
  wenn der Load fehlschlägt — ein `FILE NOT FOUND` ist ein normaler
  BASIC-Laufzeitfehler und stoppt genauso). Der klassische Trick, das zu
  umgehen: `POKE631,82:POKE632,85:POKE633,78:POKE634,13:POKE198,4`
  (schreibt "RUN"+Return in den Tastaturpuffer) direkt vor dem `LOAD`.
  Erkennung "ist der Treiber schon geladen" per `PEEK(49152)=32` (erstes
  Byte der Routine, eine normale BASIC-Variable würde ein `RUN` nicht
  überleben).
- **`petcat` tokenisiert Grossbuchstaben in String-Literalen als
  "shifted" PETSCII (128+), nicht als das erwartete unshiftete PETSCII —
  das bricht `LOAD`/`SAVE`-Dateinamen (2026-09-14, auf echter Hardware
  gefunden, per Byte-Vergleich gegen das echte Disk-Verzeichnis
  bestätigt):** Die alte Annahme "Textinhalte in Anführungszeichen bleiben
  unberührt, egal welche Schreibweise" (siehe darunter) ist **so nicht
  richtig** — sie stimmt nur für Text, der NACH einem Wechsel in den
  Kleinbuchstaben-Zeichensatz (`CHR$(14)`) angezeigt wird (dort rendern
  die "shifted"-Codes 193-218 tatsächlich als lesbare Grossbuchstaben).
  Für alles, was auf EXAKTE Byte-Werte ankommt — allen voran ein
  `LOAD`/`SAVE`-Dateiname, der 1:1 gegen den Diskettenverzeichnis-Eintrag
  verglichen wird — ist sie falsch: `tron_c64_wic64_client.bas` schrieb
  `LOAD"FOTOFIX.C000",8,1` (Grossbuchstaben im Quelltext), petcat
  tokenisierte das zu den Byte-Werten 198,207,212,207,198,201,216,...
  (= Buchstabe+128), waehrend das echte Disk-Verzeichnis (verifiziert per
  `c1541 -dir` und direktem Parsen der D64-Verzeichnis-Sektoren) den
  Dateinamen mit den PLAIN/unshifteten Werten 70,79,84,79,70,73,88,...
  speichert. Ergebnis: `LOAD` findet die Datei NIE — dieselben
  Bytewerte rendern zudem im Default-Zeichensatz (der beim `LOAD`, VOR
  dem `CHR$(14)`-Wechsel, noch aktiv ist) als Grafiksymbole statt Text,
  daher der Eindruck "Garbage in Zeile 30" beim `LIST`en. **Symptom beim
  Testen:** Auto-Load des Treibers schlägt fehl, Betroffene mussten den
  `LOAD`-Befehl manuell am READY-Prompt eintippen, bevor sie das
  Hauptprogramm starten konnten — und weil der Treiber dann NIE regulär
  automatisch lädt, bleiben nachfolgende `SYS49152`-Aufrufe im
  Kaltstart-Fall wirkungslos (Client "verbindet", tut danach aber nichts
  sichtbares mehr). **Fix:** Dateinamen fuer `LOAD`/`SAVE` IMMER in
  Kleinschreibung in den Quelltext schreiben (`"fotofix.c000"` statt
  `"FOTOFIX.C000"`) — das ergibt die unshifteten Byte-Werte, die zum
  Diskettenverzeichnis passen. Per petcat-Testlauf bestaetigt: die
  tokenisierten Bytes von `"fotofix.c000"` matchen exakt die echten
  Verzeichnis-Bytes aus `fotofix.d64`.
- **`petcat` will Befehle/Variablennamen in Kleinschreibung** — sonst
  Tokenisierungsfehler. Reiner Anzeige-Text in Anführungszeichen (der NACH
  dem `CHR$(14)`-Zeichensatzwechsel ausgegeben wird) darf in der
  gewünschten Anzeige-Schreibweise bleiben — **Ausnahme:
  Dateinamen für `LOAD`/`SAVE` müssen trotzdem klein geschrieben werden**,
  siehe Lektion direkt darüber.
- **WiC64-Hauptschleife prüfte `START`/`END`/`ERR` nur in Grossschreibung
  — Client blieb bei laufendem Spiel "stumm" (2026-09-14, auf echter
  Hardware gefunden):** Die Join-Antwort-Prüfung akzeptierte von Anfang an
  sowohl `SESSION` als auch `session` (siehe Fix-Eintrag oben), die
  Haupschleife (`tron_c64_wic64_client.bas`, Prüfungen auf `START`/`END`/
  `ERR`) aber nur die Grossschreibung. Da genau derselbe Treiber/dieselbe
  Verbindung nachweislich auch abgehende Texte in Kleinschreibung
  verwandelt (siehe Fix oben — Server-Log zeigt ankommende Requests
  durchgehend klein geschrieben, obwohl der Client-Code Grossschreibung
  verwendet), ist es sehr wahrscheinlich, dass auch ankommende
  Serverantworten kleingeschrieben ankommen — die reinen
  Grossschreibungs-Vergleiche haetten dann NIE gegriffen. Symptom auf
  Hardware: Client verbindet, zeigt "waiting for opponent...", aber selbst
  nachdem ein zweiter Spieler beigetreten ist und die Partie serverseitig
  läuft/endet, bleibt der Bildschirm unveraendert (kein "use joystick",
  kein "game over") — Server-Log zeigt derweil endloses `/tick`-Polling
  mit Richtung `n` weit über das Spielende hinaus. **Fix:** `START`/`END`/
  `ERR`-Pruefungen in der Hauptschleife akzeptieren jetzt beide
  Schreibweisen, analog zum bereits vorhandenen `SESSION`/`session`-Muster
  bei der Join-Antwort.
- **"`/join` ok, `/tick` = 'ERR UNKNOWN SESSION'"-Bug:** siehe Fix-Eintrag
  weiter oben (Großschreibung der URLs + fehlende Prefix-Prüfung der
  Join-Antwort) — auf Hardware noch zu verifizieren.
- **Weiterhin offen:** Ob `SYS 49152` für sehr häufiges, wiederholtes
  Abfragen (unser `/tick`-Polling, viele Aufrufe pro Sekunde) genauso
  zuverlässig ist wie für die vom Original-Programm vorgesehenen seltenen
  Einzelabrufe — falls der obige Fix das Problem nicht vollständig löst,
  hier als Nächstes ansetzen (z.B. Pacing/Delay zwischen `/tick`-Aufrufen
  testen).
  - **Erste Messung (2026-09-19):** Beantwortet die obige Frage zumindest
    teilweise — mit dem neuen `[tick-latency]`-Logging (siehe
    `HTTPPlayerConn.last_tick_at` in `server/tron_server.py`) lag die
    Zeit zwischen aufeinanderfolgenden `/tick`-Aufrufen des WiC64-Clients
    (VICE-Emulator, kein Bot als Gegner sondern ein echter TCP-Bot auf
    Atari-Seite) durchgehend bei **1272–1290 ms** — bei `TICK_RATE=8`
    (125 ms/Tick) also rund **10 Server-Ticks pro WiC64-Eingabe**. Die
    enge Spanne (nur ~18 ms Streuung) spricht eher für einen festen,
    deterministischen Overhead im WiC64-Protokoll/Treiber (User-Port-
    Handshake mit dem ESP-Modul) als für reines Netzwerk-Jitter.
    **Testumgebung:** Ubuntu Linux, Intel i5, 16 GB RAM, VICE aus dem
    Git-Quellcode selbst kompiliert (nicht auf echter WiC64-Hardware
    verifiziert — der Emulator könnte hier anders/langsamer als echte
    Hardware timen). **Einordnung:** `TICK_RATE` deswegen NICHT global
    absenken — das würde das Spiel für alle Plattformen verlangsamen,
    allen voran Atari mit praktisch keiner Eingabe-Latenz, ohne WiC64
    dadurch wirklich konkurrenzfähig zu machen. WiC64 bleibt der
    experimentelle Bonus-Client, Meatloaf bleibt der verlässliche
    Standard-C64-Client für CC2026.
  - **Vergleichsmessung Meatloaf (2026-09-19, echtes Spiel gegen
    `bots/tron_bot.sh`):** Im Steady State **294–306 ms** pro `/tick`
    — rund **4x schneller als WiC64** (~1280 ms), aber immer noch gut
    **2,4x langsamer als `TICK_RATE=8`** (125 ms/Tick) — auch der
    "verlässliche" HTTP-Polling-Client bekommt also nur etwa alle 2-3
    Server-Ticks eine neue Eingabe durch, nicht jeden. Einmalig ein
    Ausreißer von 1444 ms beobachtet (Ursache unklar - GC-Pause,
    OS-Scheduling-Jitter im Emulator, oder eine intern wiederholte
    Anfrage - bisher einmalig, kein wiederkehrendes Muster). Bestätigt:
    HTTP-Polling hat generell einen spürbaren Latenz-Sockel gegenüber
    Atars rohem TCP, aber der ist bei Meatloaf offenbar akzeptabel
    (Client gilt seit vielen echten Spielen als stabil) - WiC64s
    ~1280 ms sind nochmal eine andere Größenordnung.
  - **Vergleichsmessung CPC/M4 (2026-09-19, ECHTE HARDWARE - nicht
    Emulator):** Im Steady State **542–559 ms** pro `/tick` (Solo-Test)
    bzw. **543–551 ms** (im anschließenden echten Spiel gegen den
    Meatloaf-Client, s.u.) — liegt damit zwischen Meatloaf (~300 ms)
    und WiC64 (~1280 ms), rund **1,8x langsamer als Meatloaf**, aber
    **2,3x schneller als WiC64**. Bei `TICK_RATE=8` (125 ms/Tick) macht
    das rund **4,4 Server-Ticks pro CPC-Eingabe**. Erklärt sich
    plausibel durch die bereits in `CLAUDE.md` dokumentierte
    `|HTTPMEM`-Eigenschaft, während des Abrufs jede andere Verarbeitung
    zu blockieren. Auch hier einmalig ein Ausreißer (1095 ms statt
    ~550 ms) im späteren Spiel beobachtet, gleiches Bild wie beim
    Meatloaf-Ausreißer oben - einmalig, kein Muster.
  - **Rangfolge nach dieser ersten Messrunde (schnellste zuerst):**
    Atari (rohes TCP, praktisch verzögerungsfrei) < Meatloaf (~300 ms,
    ~2,4 Ticks) < CPC/M4 (~550 ms, ~4,4 Ticks) < WiC64 (~1280 ms,
    ~10 Ticks). Alle drei HTTP-Polling-Werte liegen deutlich über
    `TICK_RATE`s 125 ms, das Spiel funktioniert trotzdem seit vielen
    Spielen zuverlässig - spricht weiterhin dagegen, `TICK_RATE` als
    Reaktion darauf zu verändern (siehe Einordnung oben).
  - **Erster echter Hardware-Crossplay-Smoketest (2026-09-19):**
    CPC/M4 vs. C64/Meatloaf, beide auf echter Hardware, endete mit
    "draw (simultaneous crash)" nach ~7 Sekunden - Pairing/Countdown/
    Bewegung/Kollisionserkennung/Spielende liefen sauber durch. Erste
    von der Testcheckliste (`docs/hardware_test_checklist.pdf`,
    Abschnitt 5) tatsächlich auf echter Hardware durchgespielte
    Cross-Platform-Paarung.

## UI-Vereinfachung aller Clients (2026-09-12)

Nach dem Meatloaf-Hardwaretest vom 2026-09-12 (siehe Session-Mismatch-Fund
oben) — dort zeigte sich außerdem, dass die ASCII-Kunst-Anzeige auf dem
C64 nicht korrekt dargestellt wurde — wurden alle vier Clients
(`tron_atari_client.bas`, `tron_c64_client.bas`,
`tron_c64_wic64_client.bas`, `tron_cpc_client.bas`) bewusst radikal
vereinfacht:

- **Entfernt, in allen vier Clients:**
  - Die ASCII-Kunst-Digitalisierung des Besucherfotos (Subroutine `3000`
    je Client, inkl. des HTTP/`|HTTPMEM`/`SYS49152`-Abrufs von
    `ascii-terminal.txt`).
  - Der zeichenweise "Terminal-Tippeffekt" beim Ausgeben von Text
    (Subroutine `4000` je Client).
  - Die MCP-Storyline (`"MCP:> ..."`-Texte wie "WELCOME TO THE GRID",
    "MASTER CONTROL PROGRAM SEARCH PHOTO", "YOU'VE GRANTED ACCESS...").
- **Übrig bleibt eine knappe, rein funktionale Textausgabe** (direktes
  `PRINT`, kein Zwischenschritt mehr über `tx$`+`GOSUB`): PIN-Abfrage
  (`"ENTER YOUR PIN OR PRESS ENTER:"`), Verbindungsaufbau
  (`"CONNECTING..."`), Warten auf Gegner (`"WAITING FOR OPPONENT..."`),
  Joystick-Hinweis (`"USE JOYSTICK"`), Spielende + Ergebnis
  (`"GAME OVER"` + die rohe Server-Antwortzeile), und Neustart
  (`"RESTARTING..."`).
- **Nicht betroffen:** Das serverseitige Foto-Feature (Besucherfoto im
  pygame-Seitenpanel) bleibt unverändert — das ist komplett serverseitig
  (`fetch_photo_ftp_blocking`/`fetch_photo_http`) und unabhängig von der
  jetzt entfernten Client-seitigen ASCII-Vorschau. Die PIN wird weiterhin
  ganz normal an `/join` bzw. `HELLO` mitgegeben.
- **Warum:** Weniger Code pro Client bedeutet weniger Fläche für genau
  die Art von Bugs, die dieses Projekt bisher am meisten Zeit gekostet
  hat (siehe Lektionen oben) — und ein kaputter Digitalisierungs-Screen
  ist auf einer Ausstellung schlechter als gar keiner.

## Allgemeine, plattformübergreifende Muster

1. **Reservierte Variablennamen sind eine wiederkehrende Fallgrube.**
   Kurze Variablennamen (2-3 Buchstaben) IMMER gegen die jeweilige
   BASIC-Referenz prüfen, bevor sie verwendet werden — `PI` (CPC), `TI`
   (C64) waren beide genau diese Art Bug, mit demselben Symptom-Muster
   (Syntax error an einer unauffälligen Stelle).
2. **Groß-/Kleinschreibung bei Netzwerk-Text niemals voraussetzen.**
   Sowohl Meatloaf als auch WiC64 (über die Fotofix-Routine) wandeln
   Text beim Senden/Empfangen um. Server-seitige Vergleiche IMMER
   case-insensitive halten (`.upper()`).
3. **String-Längenbegrenzung auf 8-Bit-BASIC (255 Zeichen)** — nie eine
   komplette HTTP-Antwort in eine String-Variable akkumulieren, wenn sie
   potenziell groß werden kann (z.B. die ASCII-Kunst). Stattdessen
   zeichenweise aus dem Speicher verarbeiten.
4. **Bei "funktioniert einmal, dann nicht mehr"-Symptomen**: Verdacht auf
   nicht vollständig zurückgesetzten Verbindungs-/Geräte-Zustand nach
   Wiederverwendung eines Kanals/einer Verbindung. Bisher beste Lösungen:
   entweder denselben Kanal strikt sequenziell nutzen, oder (Atari-Fall)
   einen kompletten `RUN`-Neustart statt `GOTO`.
5. **Bei jedem neuen Fehlerbild: zuerst Sichtbarkeit schaffen, dann
   raten.** Diagnose-Ausgaben (Fehlercode, Rohantwort, Byteanzahl) haben
   in fast jedem Fall schneller zur Lösung geführt als eine zweite oder
   dritte Vermutung ohne neue Daten.
6. **BASIC-Zeilennummern-Konsistenz nach jeder Änderung prüfen** (keine
   Duplikate, aufsteigend, keine Zeile über der jeweiligen Plattform-
   Grenze — Atari ~120 Zeichen, C64/CPC deutlich lockerer). Ein kleines
   Python-Skript dafür lohnt sich, siehe Beispiel unten.
7. **Konvention: Alle Clients nutzen den ersten Joystick-Port ihres
   Rechners — mit einer bewussten, dokumentierten Ausnahme für den C64.**
   Atari (`STICK(JSPORT)` mit `JSPORT=0`) und CPC (`JOY(0)`) nutzen von
   Anfang an korrekt ihren jeweils ersten Port. Der C64 (Meatloaf UND
   WiC64) wurde testweise auf Port 1 (`PEEK(56321)`/`$DC01`) umgestellt,
   dann aber am 2026-09-14 wieder auf **Port 2** (`PEEK(56320)`/`$DC00`)
   zurückgestellt — Port 1 teilt sich Leitungen mit der Tastaturmatrix und
   erzeugte auf echter Hardware reale Phantom-Tastendrücke (siehe
   Joystick-Port-Lektion und PIN-Eingabe-Lektion oben). Für den C64 hat
   Zuverlässigkeit auf der Ausstellung Vorrang vor der reinen
   Port-Nummern-Konsistenz zwischen den Plattformen.

```python
# Schnelle BASIC-Zeilennummern-Konsistenzpruefung
with open("datei.bas") as f:
    lines = f.read().splitlines()
nums = [int(l.split()[0]) for l in lines if l.strip() and l.split()[0].isdigit()]
assert len(set(nums)) == len(nums), "Duplikate!"
assert all(nums[i] < nums[i+1] for i in range(len(nums)-1)), "Nicht aufsteigend!"
```

## Clients auf die Zielsysteme übertragen

Wie der `.bas`-Quelltext tatsächlich auf dem jeweiligen Retro-Rechner
landet (vom Nutzer erprobter Workflow, nicht offensichtlich aus dem Code
ersichtlich):

### Atari (FujiNet)

Auf einem PC FujiNet + Altirra installieren. Über FujiNet eine Diskette
mit dem N-Device auf die simulierte SD-Karte kopieren und davon booten.
Im BASIC-Interpreter lässt sich das Programm per Rechtsklick einfügen
("Paste"), dann abspeichern. Das fertige Disk-Image anschließend auf die
echte SD-Karte des FujiNet übertragen.

#### Alternative für Automatisierung: `.atr`-Images direkt bearbeiten (noch nicht getestet)

Der Weg oben (Altirra-Paste) ist für einzelne, manuelle Übertragungen
gedacht. Für ein automatisiertes Skript/Pipeline-Setup auf Ubuntu gibt es
mehrere Kommandozeilen-Tools, die `.atr`-Images direkt bearbeiten können
— normale Linux-Tools wie `mtools` funktionieren hier NICHT, weil Atari-
Dateisysteme (DOS 2.0, DOS 2.5, MyDOS, SpartaDOS) kein FAT sind:

- **[atrfs](https://github.com/pcrow/atari_8bit_utils)** — mountet ein
  `.atr`-Image per FUSE als normales Ubuntu-Verzeichnis (kein Root
  nötig), danach normales `cp`/Dateimanager möglich:
  ```
  mkdir ./atari_disk
  atrfs --name=game_disk.atr ./atari_disk
  cp myprog.bas ./atari_disk/
  fusermount -u ./atari_disk
  ```
  Unterstützt DOS 2.0/LiteDOS vollständig, MyDOS/SpartaDOS mit
  Einschränkungen.
- **franny** — Kommandozeilen-Tool zum Auflisten/Extrahieren/Einfügen
  ohne Mounten, u.a. für Skripte geeignet: `franny -l image.atr`
  (Inhalt auflisten), `franny -g image.atr ATARIFILE.BAS localfile.bas`
  (extrahieren), `franny -a image.atr localfile.bas ATARIFILE.BAS`
  (einfügen). Kann auch neue Leer-Images erzeugen.
- **[atari-tools](https://github.com/jhallen/atari-tools)** von Joseph
  Allen — kompiliert schnell per `make`, liefert ein `atr`-Binary:
  `atr image.atr ls` (auflisten), `atr image.atr put file.txt`
  (einfügen).
- **GUI-Alternative:** Altirra hat unter System → Disk Drives → Select
  Drive → Explore einen Disk-Explorer, in den sich Dateien direkt vom
  Ubuntu-Desktop hinein-draggen lassen (inkl. optionaler
  Zeilenenden-Konvertierung) — auch `atari800` (`sudo apt install
  atari800`) hat einen nativen Linux-Emulator als Alternative zu
  Altirra/Wine.

**Wichtig bei reinen ASCII-`.bas`-Textdateien:** Der Atari erwartet
ATASCII-Zeilenenden — ein einzelnes `CR` (`\r`, ASCII 155), NICHT Linux-
`LF` (`\n`) oder Windows-`CRLF` (`\r\n`). Falls eine skriptgenerierte
`.bas`-Datei beim Laden (`ENTER "D:MYPROG.BAS"`) nicht sauber läuft,
vorher die Zeilenenden mit `awk`/`sed` auf `\r` umwandeln.

**Status:** Aus einer KI-Recherche übernommen, **noch nicht ausprobiert**
— nützlich als Ausgangspunkt, falls das manuelle Altirra-Paste durch ein
Skript ersetzt werden soll (z.B. für automatisiertes Ausrollen neuer
Client-Stände auf mehrere FujiNet-SD-Karten).

### Commodore 64 (Meatloaf)

VICE installieren — enthält `petcat`, das eine Text-Datei als Tokens
speichert: `petcat -w2 -o OUT.PRG -- IN.TXT` (aus `xyz.bas` wird
`xyz.prg`). Danach über das Meatloaf-Webinterface auf den Flash-Speicher
hochladen.

**Achtung:** Ein HTTP-Aufruf aus BASIC heraus verstellt offenbar das
Destination-Verzeichnis für Device 8. Zurücksetzen mit `LOAD"CD^",8`
(Pfeil-nach-oben-Zeichen, PETSCII `$5E`), danach `LOAD"$",8` — dann ist
wieder alles normal.

### Schneider/Amstrad CPC (M4)

Sonderfall wegen des AMSDOS-Headers (siehe auch Lektion oben zum
"Line too long"-Fehler). Workflow: WinAPE starten, neue Diskette
erstellen und formatieren, das BASIC-Programm per Paste in die Emulation
kopieren, auf der virtuellen Diskette speichern. Anschließend über das
M4-Webinterface diese Diskette auf die SD-Karte des M4 kopieren, dort
auswählen und das Programm per Browser auf dem CPC starten.

Bekannte Einschränkung: Beim `|HTTPMEM`-Aufruf (CALL der HTTP-Seite) wird
jede andere Verarbeitung (insbesondere Joystick-Abfrage) blockiert — das
Spielgefühl ist auf dem CPC dadurch spürbar weniger flüssig als auf den
anderen Plattformen. Ein reduzierter Puffer hilft etwas, die Grenzen
bleiben aber deutlich spürbar.

#### Möglicher einfacherer Weg: `MERGE` statt WinAPE-Umweg (noch nicht getestet)

Der WinAPE-Umweg oben ist nötig, weil eine **tokenisierte** BASIC-Datei
(normales `SAVE"datei"`) einen korrekten 128-Byte-AMSDOS-Header braucht,
den das M4-Webinterface beim Hochladen einer rohen Textdatei nicht von
selbst erzeugt (siehe "Line too long"-Lektion oben). Es gibt aber einen
möglichen Weg, dieses Header-Problem komplett zu umgehen, indem man gar
keine tokenisierte Datei braucht:

- Der CPC kann eine **rohe ASCII-Textdatei** (entspricht `SAVE"datei",A`)
  direkt einlesen und ausführen — ganz ohne Tokenisierung/Header —, und
  zwar über den `MERGE`-Befehl:
  ```
  NEW
  MERGE "dateiname.txt"
  RUN
  ```
  `MERGE` liest die Textdatei Zeile für Zeile genauso ein, als würde man
  sie von Hand eintippen (ähnlich dem WinAPE-"Auto Type"/Atari-Paste, nur
  direkt vom CPC-Interpreter erledigt statt vom Emulator).
- Alternative dazu, als reines Zeilen-Einlesen ohne BASIC-Interpretation:
  ```
  OPENIN "dateiname.txt":LINE INPUT #9,a$:CLOSEIN
  ```
- **Warum das speziell beim M4 interessant ist:** Das M4-Board stellt die
  SD-Karte als normales FAT32-Dateisystem bereit — für `MERGE` wird kein
  `.DSK`-Image gebraucht. Die erzeugte `.bas`/`.txt`-Datei müsste sich
  also direkt auf die SD-Karte kopieren lassen; am CPC dann mit `|DIR`
  sichtbar machen und per `MERGE "dateiname.txt"` laden — potenziell ganz
  ohne WinAPE/Emulator-Umweg.
- Falls doch ein direktes `RUN"dateiname"` ohne vorheriges `MERGE`
  gewünscht ist: ein 128-Byte-AMSDOS-Header lässt sich der Textdatei auch
  nachträglich per Kommandozeilen-Tool (z.B. `2cpc`, `cpcfs` mit
  `-t 0`/`-t 1` beim Import in ein `.DSK`-Image) voranstellen — macht die
  Datei-für-Datei-Behandlung aber wieder komplizierter als der
  `MERGE`-Weg oben.

**Status:** Aus einer KI-Recherche übernommen, **noch nicht auf echter
M4-Hardware verifiziert** — falls es funktioniert, macht es den
WinAPE-Umweg beim Übertragen neuer Client-Stände überflüssig. Vor dem
nächsten Hardware-Test lohnt sich ein Ausprobieren mit einer kleinen
Testdatei, bevor der komplette Client-Code darüber läuft.

## Testing ohne echte Hardware

Für den Server gibt es einen minimalen `pygame`-Stub (im ursprünglichen
Sandbox-Environment unter `/home/claude/faketest/pygame_stub/`), der es
erlaubt, den Server headless laufen zu lassen und per rohem TCP-Socket
(Python `socket`-Modul) End-to-End-Tests zu fahren (HELLO senden, WAIT/
START abwarten, etc.), ohne ein echtes pygame-Fenster zu benötigen. Dieser
Stub ist NICHT Teil dieses Repos (war nur eine Sandbox-Hilfskonstruktion)
— bei Bedarf leicht selbst nachbaubar (siehe `pygame.font`, `pygame.init`,
`pygame.display` als minimal zu stubbende Oberfläche).

Für BASIC-Clients gibt es keine Möglichkeit, ohne echten Emulator
(Altirra/Fujisan für Atari, VICE für C64, WinAPE/CPCEmu für CPC) sinnvoll
zu testen — jede Änderung an einem `.bas`-Client sollte vor der Auslieferung
zumindest auf Zeilennummern-Konsistenz geprüft werden (siehe oben), echte
Funktionstests sind nur mit Emulator/Hardware durch den Nutzer möglich.

**Stand der Emulator-Tests pro Plattform (Nutzererfahrung):**

- **Atari:** Fujisan 2.0.5beta unter Linux funktioniert zuverlässig als
  Testumgebung für den FujiNet-Client. Unter Windows funktioniert dasselbe
  Setup **nicht** — Ursache bisher unbekannt, noch nicht untersucht.
- **C64 (WiC64):** VICE kann den WiC64-Client emulieren, d.h. der
  experimentelle WiC64-Client lässt sich damit **ohne echte Hardware**
  testen — nützlich gerade weil die WiC64-Hardware selten verfügbar ist.
- **CPC (M4):** CPCEmu simuliert ein M4-Interface, das ist aber **bisher
  nicht getestet** — Status unklar, könnte als nächster Schritt für
  hardwarefreies CPC-Testing dienen.
- **Basic-Programme in ein D64-Image packen** (für C64-Tests, z.B. mit
  VICE): [d64-inspector](https://github.com/pdbuchan/d64-inspector)
  (Autor: P. David Buchan, GPLv3) hat sich dafür als nützlich erwiesen —
  Quellcode liegt unter [`tools/d64-inspector/`](./tools/d64-inspector/)
  im Repo (aus dem Original-Git-Clone übernommen, ohne `.git`- und
  Build-Artefakte). Für die PETSCII-Ansicht nutzt d64-inspector selbst
  die [C64 TrueType](https://style64.org/c64-truetype)-Fontfamilie
  (Autor: "Style", style64.org), ebenfalls im Repo unter
  [`tools/C64_TrueType_v1.2.1-STYLE/`](./tools/C64_TrueType_v1.2.1-STYLE/)
  (unveränderte Distribution, siehe Lizenz dort). **Vor dem Bauen unter
  Ubuntu:** `sudo apt install build-essential pkg-config libgtk-4-dev`,
  dann die TrueType-Fonts aus `tools/C64_TrueType_v1.2.1-STYLE/fonts/`
  installieren (für die PETSCII-Anzeige gedacht), danach `make` in
  `tools/d64-inspector/src/`. Referenz-Disk-Images (u.a. für Atari/CPC)
  liegen unter [`disk-images/`](./disk-images/), siehe README dort.

### Foto-/FTP-Infrastruktur lokal simulieren

Ohne den echten Event-Fotoserver lässt sich `PHOTO_SOURCE = "FTP"` lokal
mit einem simplen FTP-Server testen (aus dem Bilderverzeichnis heraus
starten):

```bash
# Linux
sudo python -m pyftpdlib -p 21
# Windows
python -m pyftpdlib -p 21
```

Zum Testen bereits benutzte Besucher-PINs: `0001`, `0002`, `4711`,
`0815`.

**Fertiges Test-Fixture:** [`assets/test_ftproot/`](./assets/test_ftproot/)
enthält ein Demo-Foto (`photo.jpg`) und eine ASCII-Kunst-Datei
(`ascii-terminal.txt`) unter der PIN `MUSTER`, heruntergeladen vom echten
`fotofix.classic-computing.de`-Server. `ascii-terminal.txt` wird seit der
Client-Vereinfachung vom 2026-09-12 von keinem Client mehr abgerufen,
bleibt aber als Fixture liegen (harmlos, minimaler Pflegeaufwand). Einfach
den pyftpdlib-Befehl oben aus `assets/test_ftproot/` heraus starten und
mit PIN `MUSTER` testen,
statt eigene Testbilder anzulegen.

## Ideen für später

- **`pygame` → `pygame-ce`/`pygame-ng` erwägen:** Klassisches `pygame` ist
  unmaintained; ein Community-Fork würde aktuellere Wartung/Fixes bringen.
  Kein akuter Handlungsbedarf, aber bei größeren Server-Änderungen im
  Hinterkopf behalten.
- **Soundeffekte aus dem Tron-Film (1982):** Ein paar kurze Audioclips
  (Bit-artige "yes"/"no", MCP-artige Zeilen) liegen lokal bereit für
  eine mögliche spätere Integration (z.B. als Sound-Effekte im Server bei
  Spielstart/-ende). **Bewusst nicht ins Repo/Git aufgenommen** — es
  handelt sich um Ausschnitte aus urheberrechtlich geschütztem
  Filmmaterial (Disney), das sollte vor einer Verwendung/Veröffentlichung
  nochmal bewusst abgewogen werden, insbesondere falls das Repo je
  öffentlich gehostet wird.
- **Vierte Plattform: Apple II via FujiNet (nur falls am Ende Zeit übrig
  ist):** FujiNet unterstützt offiziell auch Apple II/III, mit demselben
  `N:`-Netzwerk-Device-Konzept wie beim Atari, inklusive rohem TCP —
  Methode 1 (Port 6502) sollte sich also direkt anwenden lassen, ganz
  ohne Server-Änderung (siehe Abschnitt "Erweiterung um weitere
  Retro-Computer" oben). Kein Apple II in der eigenen Hardware-Sammlung
  bisher, geplanter erster Test über den "FujiNet Go"-Emulator auf
  Handy/Tablet — reine Nice-to-have-Idee, keine Priorität vor CC2026.
  Quickstart: <https://github.com/FujiNetWIFI/fujinet-firmware/wiki/Apple-II-&-III-FujiNet-Quickstart-Guide>
  - **Erster Client-Entwurf existiert bereits:**
    [`clients/apple2/tron_apple2_client.bas`](./clients/apple2/tron_apple2_client.bas)
    — **komplett unverifiziert, noch nie gelaufen**, weder auf echter
    Hardware noch im Emulator. Anders als beim Atari-Client (CIO
    `OPEN`/`PRINT#`/`INPUT#`) läuft Netzwerk auf Apple II über
    FujiNet-spezifische Applesoft-"Ampersand"-Routinen
    (`&NOPEN`/`&NREAD`/`&NWRITE`/`&NCLOSE`/`&NSTATUS`), die erst per
    `BLOAD /FUJI.APPLE/FUJIAPPLE` + `CALL 16384` geladen werden müssen.
    Aus dem FujiNet-Wiki (Seiten "Applesoft Network extensions" und
    "N: SIO Command 'R' — Read") ließ sich kein vollständiges
    funktionierendes TCP-Beispielprogramm finden — der Client ist aus
    der reinen Parameter-Referenz gebaut, nicht aus einem bestätigten
    Beispiel. **Bekannte offene Punkte, vor dem ersten Testlauf im
    Hinterkopf behalten:**
    - Ob `&NREAD`/`&NWRITE` blockieren oder sofort zurückkehren, ist in
      der Doku nicht spezifiziert — der Client folgt dem empfohlenen
      Muster "immer erst `&NSTATUS` fürs Byte-Waiting prüfen, dann erst
      `&NREAD` mit genau dieser Byte-Anzahl" (die Doku warnt explizit
      vor einem Fehler, wenn mehr Bytes angefragt werden als anliegen).
    - Wie ein fehlgeschlagenes `&NOPEN` (z.B. Server nicht erreichbar)
      sich bemerkbar macht, ist unbekannt — noch kein Applesoft-`ONERR
      GOTO`-Fehlerhandling eingebaut (anders als das `TRAP`-basierte
      beim Atari-Client).
    - `PDL(0)`/`PDL(1)` fürs Joystick-Lesen: Center (`CX`/`CY`) und
      Deadzone (`DZ`) sind im Kopf des Clients als Platzhalter (128/40)
      hinterlegt — echte Paddle-/Joystick-Hardware braucht dafür
      erfahrungsgemäß eine Kalibrierung pro Gerät.
    - Applesoft unterscheidet Variablennamen historisch nur an den
      ersten zwei Zeichen — der PIN-Eingabe-Variable bewusst `PN$`
      genannt (nicht `PIN$`), da `PI` in Applesoft ein reserviertes
      Schlüsselwort ist (Kreiszahl, dieselbe Fallgrube wie beim CPC,
      siehe Muster 1 oben).
    - Serverseitig ist `"APPLE2"` bereits in `PLATFORM_COLORS`/
      `LOGO_NAME_CANDIDATES` in `server/tron_server.py` eingetragen
      (amber Trail-Farbe), noch kein `assets/logos/apple2.*`-Bild
      vorhanden.
- **Fünfte Plattform: TI-99/4A via PicoPEB (ebenfalls nur bei Zeitüberschuss):**
  PicoPEB ist eine DIY-Nachbildung der TI-Peripheral-Expansion-Box auf
  Basis eines Raspberry Pi Pico W und emuliert u.a. ein RS232-Gerät mit
  einem reinen Client-TCP-Socket (`PI.TCP=...` in der `autoload.cfg`) —
  von TI BASIC/Extended BASIC aus per `OPEN #1:"RS232/2..."` (bzw. der
  `PI.TCP`-Variante) und `PRINT #1:`/`INPUT #1:` angesprochen, vom Prinzip
  her wie das serielle `N:`-Device beim Atari. Würde also ebenfalls auf
  Methode 1 (rohes TCP, Port 6502) abgebildet, ohne Server-Änderung.
  Genaue `OPEN`-Syntax fürs TCP-Client-Socket war in der verfügbaren
  Doku nicht vollständig spezifiziert — reine Hands-on-Ermittlung auf
  echter Hardware wie bei jeder bisherigen Plattform. Zusätzliche Hürden:
  PicoPEB ist eine Lötbausatz-Platine (inkl. SMD-Bauteile), stock TI
  BASIC ist langsam/string-limitiert (vermutlich Extended-BASIC-Modul
  nötig), und es ist kein TI-99/4A in der eigenen Hardware-Sammlung
  vorhanden — reine Nice-to-have-Idee, keine Priorität vor CC2026.
  Doku: <https://github.com/hexbus/ppebcr-docs>

## Aktueller Stand (siehe auch git log für Details)

- **Server**: stabil, produktiv im Einsatz getestet über viele Spiele.
- **Alle vier Clients** (Atari, C64/Meatloaf, C64/WiC64, CPC): am
  2026-09-12 UI-seitig radikal vereinfacht — ASCII-Kunst-Anzeige,
  Terminal-Tippeffekt und MCP-Storyline entfernt, siehe Abschnitt
  "UI-Vereinfachung aller Clients" oben. C64/Meatloaf und CPC/M4 am
  2026-09-19 auf echter Hardware nach der Vereinfachung erneut
  verifiziert (siehe direkt unten); Atari und C64/WiC64 stehen das
  noch aus.
- **Atari-Client**: bisher stabil (vor der Vereinfachung).
- **C64-Client (Meatloaf)**: Session-Mismatch-Bug (ungeprüfte
  Join-Antwort) am 2026-09-12 auf echter Hardware gefunden und gefixt.
  Am 2026-09-19 auf echter Hardware erneut verifiziert (`/tick`-Latenz
  ~300 ms, siehe Vergleichsmessung im WiC64-Abschnitt oben) - Fix hält.
- **CPC-Client**: bisher stabil (vor der Vereinfachung); denselben
  Join-Antwort-Fix wie beim Meatloaf-Client vorsorglich mitbekommen.
  Am 2026-09-19 auf echter Hardware nach der Vereinfachung verifiziert
  (`/tick`-Latenz ~550 ms, siehe Vergleichsmessung oben) - inklusive
  eines erfolgreichen Cross-Platform-Matches gegen den Meatloaf-Client
  (draw, siehe "Erster echter Hardware-Crossplay-Smoketest" oben).
- **C64-Client (WiC64)**: experimentell, keine physische Hardware
  vorhanden (siehe "Ideen für später"/Testcheckliste). Spielverbindung
  (`/join`/`/tick`) hatte einen Bug (URL-Großschreibung + fehlende
  Antwort-Prüfung), Fix am 2026-09-11 eingebaut. Am 2026-09-19 im
  VICE-Emulator gegen einen TCP-Bot erfolgreich gespielt (funktioniert
  grundsätzlich) — dabei aber eine `/tick`-Latenz von 1272–1290 ms
  gemessen, siehe Detail-Eintrag oben im WiC64-Abschnitt. Weiterhin
  nicht auf echter WiC64-Hardware verifiziert.
