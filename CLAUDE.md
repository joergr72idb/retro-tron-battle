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
- **Joystick-Port:** Beide C64-Clients (Meatloaf und WiC64) lesen den
  Joystick jetzt aus **Port 1** (`PEEK(56321)`, CIA#1 Port B, `$DC01`) —
  vorher wurde Port 2 (`PEEK(56320)`, `$DC00`) verwendet, was auf dem C64
  zwar der übliche Default ist (Port 2 teilt sich keine Leitungen mit der
  Tastaturmatrix, Port 1 schon), aber nicht der gewünschten Konvention
  "alle Clients nutzen den ersten Joystick-Port ihres jeweiligen Rechners"
  entspricht. **Achtung:** Da Port 1 (`$DC01`) dieselben Leitungen wie die
  Tastaturmatrix-Zeilen nutzt, kann gleichzeitiges Tastendrücken theoretisch
  Phantom-Joystick-Signale erzeugen ("Ghosting") — im aktuellen Client wird
  während des Spiels aber nicht per Tastatur gelesen, daher in der Praxis
  bisher kein beobachtetes Problem. Falls doch: erster Verdacht hier.
- **`TI` ist eine reservierte Systemvariable** (Jiffy-Uhr) in Commodore
  BASIC — genau wie `PI` beim CPC (siehe unten) darf sie nicht als eigener
  Variablenname verwendet werden. Symptom: `?SYNTAX ERROR` an einer Stelle,
  die beim genauen Hinsehen überhaupt nichts Verdächtiges enthält.
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
- Ladetrick: Nach `LOAD"FOTOFIX.C000",8,1` stoppt das BASIC-Programm
  (Standardverhalten bei `LOAD` aus einem laufenden Programm heraus).
  Der klassische Trick, das zu umgehen: `POKE631,82:POKE632,85:
  POKE633,78:POKE634,13:POKE198,4` (schreibt "RUN"+Return in den
  Tastaturpuffer) direkt vor dem `LOAD`. Erkennung "ist der Treiber schon
  geladen" per `PEEK(49152)=32` (erstes Byte der Routine, eine normale
  BASIC-Variable würde ein `RUN` nicht überleben).
- **`petcat` will Befehle/Variablennamen in Kleinschreibung** — sonst
  Tokenisierungsfehler. Textinhalte in Anführungszeichen bleiben davon
  unberührt (bleiben in der Schreibweise, mit der sie angezeigt werden
  sollen).
- **"`/join` ok, `/tick` = 'ERR UNKNOWN SESSION'"-Bug:** siehe Fix-Eintrag
  weiter oben (Großschreibung der URLs + fehlende Prefix-Prüfung der
  Join-Antwort) — auf Hardware noch zu verifizieren.
- **Weiterhin offen:** Ob `SYS 49152` für sehr häufiges, wiederholtes
  Abfragen (unser `/tick`-Polling, viele Aufrufe pro Sekunde) genauso
  zuverlässig ist wie für die vom Original-Programm vorgesehenen seltenen
  Einzelabrufe — falls der obige Fix das Problem nicht vollständig löst,
  hier als Nächstes ansetzen (z.B. Pacing/Delay zwischen `/tick`-Aufrufen
  testen).

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
   Rechners.** Atari (`STICK(JSPORT)` mit `JSPORT=0`) und CPC (`JOY(0)`)
   waren von Anfang an korrekt. Beim C64 (Meatloaf UND WiC64) musste das
   umgestellt werden — vorher wurde `PEEK(56320)`/`$DC00` (Port 2, der
   auf dem C64 sonst übliche Default) gelesen, jetzt `PEEK(56321)`/`$DC01`
   (Port 1).

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
`fotofix.classic-computing.de`-Server. Einfach den pyftpdlib-Befehl oben
aus `assets/test_ftproot/` heraus starten und mit PIN `MUSTER` testen,
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

## Aktueller Stand (siehe auch git log für Details)

- **Server**: stabil, produktiv im Einsatz getestet über viele Spiele.
- **Atari-Client**: stabil, inkl. ASCII-Kunst-Digitalisierungseffekt.
- **C64-Client (Meatloaf)**: stabil.
- **CPC-Client**: stabil, inkl. ASCII-Kunst.
- **C64-Client (WiC64)**: experimentell, erster Test zeigt Fortschritt
  (ASCII-Kunst funktioniert). Spielverbindung (`/join`/`/tick`) hatte einen
  Bug (URL-Großschreibung + fehlende Antwort-Prüfung), Fix am 2026-09-11
  eingebaut, aber noch nicht auf echter Hardware verifiziert — siehe
  Fix-Eintrag oben.
