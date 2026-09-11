# CLAUDE.md — Kontext & Lektionen für dieses Projekt

Dieses Dokument richtet sich an jeden (KI-Assistent oder Mensch), der an
diesem Projekt weiterarbeitet. Es fasst zusammen, was in der ursprünglichen
Entwicklungssession (Claude, über mehrere Wochen) mühsam herausgefunden
wurde — vieles davon ist auf keiner offiziellen Doku-Seite zu finden.
**Bitte lesen, bevor du an den Clients herumschraubst — sonst wiederholst
du wahrscheinlich Fehler, die schon gemacht und behoben wurden.**

## Projektüberblick

Ein Tron/Lightcycle-Duell für eine Retro-Computing-Ausstellung
(Classic Computing 2026). Drei echte Retro-Rechner (Atari XL/XE, Commodore
64, Schneider/Amstrad CPC) treten gegeneinander an. Ein Python-Server auf
einem modernen PC übernimmt die komplette Spiellogik und zeichnet alles
selbst (pygame-Fenster, gut für einen Beamer) — die Retro-Rechner steuern
nur per Joystick.

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
  Beispielprogramm (`FOTOFIX.C000`, aus einem D64-Image extrahiert und per
  eigenem Mini-Disassembler analysiert) enthält bereits eine
  **wiederverwendbare** `SYS 49152,U$,Zieladresse`-Routine, die die WiC64-
  Low-Level-Details kapselt. Statt das nachzubauen: **einfach mit
  wiederladen und mit unseren eigenen URLs aufrufen** (`archive/` enthält
  den ursprünglichen, verworfenen Ansatz "eigenen Treiber von Grund auf
  schreiben" — nicht weiterverfolgen, der oben genannte Ansatz ist
  vielversprechender).
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
- **Noch unklar / ungetestet:** Ob `SYS 49152` für sehr häufiges,
  wiederholtes Abfragen (unser `/tick`-Polling, viele Aufrufe pro Sekunde)
  genauso zuverlässig ist wie für die vom Original-Programm vorgesehenen
  seltenen Einzelabrufe. Aktuell wird untersucht, warum der Server nach
  einem scheinbar erfolgreichen `/join` keine Verbindung registriert,
  während `/tick` konsequent "ERR UNKNOWN SESSION" zurückbekommt — das
  deutet auf einen Bug in der `/join`-Antwortbehandlung im Client hin,
  nicht zwingend auf ein WiC64-Problem selbst. **Stand: in Bearbeitung,
  siehe letzte Nachrichten im ursprünglichen Chat-Verlauf.**

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

```python
# Schnelle BASIC-Zeilennummern-Konsistenzpruefung
with open("datei.bas") as f:
    lines = f.read().splitlines()
nums = [int(l.split()[0]) for l in lines if l.strip() and l.split()[0].isdigit()]
assert len(set(nums)) == len(nums), "Duplikate!"
assert all(nums[i] < nums[i+1] for i in range(len(nums)-1)), "Nicht aufsteigend!"
```

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

## Aktueller Stand (siehe auch git log für Details)

- **Server**: stabil, produktiv im Einsatz getestet über viele Spiele.
- **Atari-Client**: stabil, inkl. ASCII-Kunst-Digitalisierungseffekt.
- **C64-Client (Meatloaf)**: stabil.
- **CPC-Client**: stabil, inkl. ASCII-Kunst.
- **C64-Client (WiC64)**: experimentell, erster Test zeigt Fortschritt
  (ASCII-Kunst funktioniert), aber Spielverbindung selbst noch fehlerhaft
  (siehe offener Punkt oben).
