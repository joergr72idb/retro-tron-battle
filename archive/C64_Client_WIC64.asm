; ============================================================
; RETRO TRON - C64_Client_WIC64 - BUILD 1 (ERSTE DEMO)
; ============================================================
;
; !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
; !! ERSTE DEMO-VERSION - UNGETESTET.                        !!
; !! Ich habe hier keinen Assembler und keine echte WiC64-   !!
; !! Hardware zur Verfuegung, um das selbst zu pruefen.      !!
; !! Anders als beim CPC-Assembler-Entwurf basiert das hier  !!
; !! aber auf der offiziell dokumentierten, gepflegten       !!
; !! "wic64-library" (nicht auf selbst zusammengesuchten     !!
; !! Low-Level-Kommandos) - das Verbindungsaufbau/Timeout-   !!
; !! Handling stammt komplett von dort. Trotzdem: bitte wie  !!
; !! bei den anderen Clients gemeinsam auf echter Hardware   !!
; !! testen und debuggen, nicht blind vertrauen.             !!
; ============================================================
;
; Basiert auf: https://github.com/WiC64-Team/wic64-library
; (ACME cross assembler, BSD-2-Clause Lizenz)
;
; Erwartete Verzeichnisstruktur (siehe README der library):
;   workspace/
;     wic64-library/              <- library hier reinklonen:
;                                     git clone \
;                                     https://github.com/WiC64-Team/wic64-library.git
;     retro-tron/
;       C64_Client_WIC64.asm      <- diese datei
;
; Assemblieren mit:
;   acme -I ../wic64-library C64_Client_WIC64.asm
;
; VEREINFACHUNG IN DIESER ERSTEN VERSION: die Foto-PIN wird noch
; NICHT interaktiv abgefragt (Tastatur-Eingabe in Assembler ist
; nochmal ein eigenes Stueck Code) - PIN ist unten als Konstante
; fest hinterlegt. Interaktive Abfrage waere ein guter naechster
; Ausbauschritt, sobald die Grundfunktion steht.
;
; Wie bei den anderen Clients gilt: Server rendert das Spielfeld,
; dieser Client liest nur den Joystick und sendet MOVE-aequivalente
; HTTP-GET-Anfragen (wie beim C64/Meatloaf und CPC/M4), ueber
; WIC64_HTTP_GET statt Meatloafs GET# oder M4s |HTTPMEM.
; ============================================================

BUILD_VERSION = 1  ; bei aenderungen erhoehen

!source "wic64.h"

; ---- Konfiguration - vor dem Assemblieren an BEIDEN stellen unten
;      (join_url und tick_url) anpassen: server-ip:port, name, pin ----

CIA1_PORT_A = $dc00   ; joystick port 2 (gleiche adresse wie im basic-client)
CHROUT      = $ffd2   ; kernal zeichen-ausgabe

* = $1000

main:
    +wic64_detect
    bcs device_not_present
    bne legacy_firmware

    +print banner_msg

restart:
    lda #0
    sta game_started

    +wic64_execute join_request, join_response
    bcs net_hiccup
    bne net_hiccup

    jsr extract_session_id

    ; frisch gejointe antwort direkt auf "START" pruefen (falls
    ; sofort gepaart wurde, wie bei den anderen clients auch) -
    ; body_ptr zeigt (dank extract_session_id) hinter die
    ; "SESSION xxx"-zeile, nicht auf deren anfang!
    ldx body_ptr
    ldy body_ptr+1
    jsr check_prefix_start
    bcc not_paired_yet

    jsr show_game_on
    jmp main_loop

not_paired_yet:
    +print waiting_msg

main_loop:
    jsr read_joystick_direction   ; -> .dir_char
    jsr poke_tick_direction

    +wic64_execute tick_request, tick_response
    bcs net_hiccup
    bne net_hiccup

    lda wic64_response_size
    beq main_loop                 ; leere antwort - einfach weiter pollen

    ldx #<tick_response
    ldy #>tick_response
    jsr check_prefix_err
    bcs restart                   ; "ERR..." -> session vorbei, neu starten

    ldx #<tick_response
    ldy #>tick_response
    jsr check_prefix_start
    bcc check_end
    lda game_started
    bne check_end
    jsr show_game_on

check_end:
    ldx #<tick_response
    ldy #>tick_response
    jsr check_prefix_end
    bcc main_loop

    ; --- spiel zu ende: ergebnis zeigen, dann neustart ---
    jsr print_newline
    ldx #<tick_response
    lda wic64_response_size
    tay
    jsr print_response_bytes
    jsr print_newline
    +print restarting_msg
    jsr delay_a_while
    jmp restart

net_hiccup:
    +print hiccup_msg
    jsr delay_a_while
    jmp restart

device_not_present:
    +print no_device_msg
    rts

legacy_firmware:
    +print legacy_msg
    rts

; ------------------------------------------------------------
; show_game_on: einmalige "spiel laeuft"-meldung
; ------------------------------------------------------------
show_game_on:
    lda #1
    sta game_started
    +print gameon_msg
    rts

; ------------------------------------------------------------
; extract_session_id: sucht das erste leerzeichen in join_response
; und kopiert die 8 darauffolgenden zeichen (unsere session-ids
; sind immer genau 8 hex-zeichen lang) in tick_session_slot, das
; teil des vorgefertigten tick_request-blocks ist.
; ------------------------------------------------------------
extract_session_id:
    lda #<join_response          ; sicherer default-fallback fuer body_ptr,
    sta body_ptr                  ; falls die suche unten fehlschlaegt
    lda #>join_response
    sta body_ptr+1
    ldy #0
find_space:
    lda join_response,y
    beq extract_done          ; sicherheitsnetz: kein leerzeichen gefunden
    cmp #' '
    beq found_space
    iny
    cpy #40                   ; sicherheitsnetz: nicht endlos suchen
    bne find_space
    jmp extract_done
found_space:
    iny                       ; y zeigt jetzt auf das erste zeichen der id
    ldx #0
copy_id:
    lda join_response,y
    sta tick_session_slot,x
    iny
    inx
    cpx #8
    bne copy_id
    ; y zeigt jetzt direkt hinter die kopierte session-id - ueberspringe
    ; noch \r und/oder \n, damit body_ptr auf "WAIT"/"START..." zeigt,
    ; nicht auf den rest der "SESSION xxx"-zeile
skip_eol:
    lda join_response,y
    cmp #13
    beq eol_char
    cmp #10
    beq eol_char
    jmp compute_body_ptr
eol_char:
    iny
    jmp skip_eol
compute_body_ptr:
    tya
    clc
    adc #<join_response
    sta body_ptr
    lda #>join_response
    adc #0
    sta body_ptr+1
extract_done:
    rts

; ------------------------------------------------------------
; read_joystick_direction: liest port 2 ($dc00, aktiv-low, gleiche
; adresse/bitbelegung wie im basic-client), setzt .dir_char auf
; 'U'/'D'/'L'/'R'/'N'. Haelt die zuletzt gesendete richtung, wenn
; gerade nichts gedrueckt ist (gleiches verhalten wie die anderen
; http-polling-clients: bei gehaltener richtung jedes mal erneut
; senden, das ist fuer die polling-architektur robuster).
; ------------------------------------------------------------
read_joystick_direction:
    lda CIA1_PORT_A
    and #$01
    bne not_up
    lda #'U'
    sta dir_char
    rts
not_up:
    lda CIA1_PORT_A
    and #$02
    bne not_down
    lda #'D'
    sta dir_char
    rts
not_down:
    lda CIA1_PORT_A
    and #$04
    bne not_left
    lda #'L'
    sta dir_char
    rts
not_left:
    lda CIA1_PORT_A
    and #$08
    bne no_direction
    lda #'R'
    sta dir_char
no_direction:
    rts

poke_tick_direction:
    lda dir_char
    sta tick_dir_slot
    rts

; ------------------------------------------------------------
; check_prefix_start / _end / _err: vergleicht die ersten paar
; bytes des puffers (x=lo, y=hi der adresse) gegen "START"/"END"/
; "ERR", in beiden Schreibweisen (gross/klein) - bei Meatloaf haben
; wir gelernt, dass manche wifi-interfaces empfangenen text
; umwandeln; fuer WiC64 ist das nicht bestaetigt noetig, schadet
; aber nichts.
; Ergebnis: carry gesetzt = treffer, carry geloescht = kein treffer
; Diese drei sind bewusst als einfache, ausgeschriebene byte-fuer-
; byte-vergleiche implementiert (kein generisches string-makro),
; um das risiko eines subtilen makro-fehlers zu vermeiden.
; ------------------------------------------------------------
check_prefix_start:
    stx scan_ptr
    sty scan_ptr+1
    ldy #0
    lda (scan_ptr),y
    cmp #'S'
    beq cps_1u
    cmp #'s'
    bne cps_no
cps_1u:
    iny
    lda (scan_ptr),y
    cmp #'T'
    beq cps_2u
    cmp #'t'
    bne cps_no
cps_2u:
    iny
    lda (scan_ptr),y
    cmp #'A'
    beq cps_3u
    cmp #'a'
    bne cps_no
cps_3u:
    iny
    lda (scan_ptr),y
    cmp #'R'
    beq cps_4u
    cmp #'r'
    bne cps_no
cps_4u:
    iny
    lda (scan_ptr),y
    cmp #'T'
    beq cps_yes
    cmp #'t'
    bne cps_no
cps_yes:
    sec
    rts
cps_no:
    clc
    rts

check_prefix_end:
    stx scan_ptr
    sty scan_ptr+1
    ldy #0
    lda (scan_ptr),y
    cmp #'E'
    beq cpe_1u
    cmp #'e'
    bne cpe_no
cpe_1u:
    iny
    lda (scan_ptr),y
    cmp #'N'
    beq cpe_2u
    cmp #'n'
    bne cpe_no
cpe_2u:
    iny
    lda (scan_ptr),y
    cmp #'D'
    beq cpe_yes
    cmp #'d'
    bne cpe_no
cpe_yes:
    sec
    rts
cpe_no:
    clc
    rts

check_prefix_err:
    stx scan_ptr
    sty scan_ptr+1
    ldy #0
    lda (scan_ptr),y
    cmp #'E'
    beq cpr_1u
    cmp #'e'
    bne cpr_no
cpr_1u:
    iny
    lda (scan_ptr),y
    cmp #'R'
    beq cpr_2u
    cmp #'r'
    bne cpr_no
cpr_2u:
    iny
    lda (scan_ptr),y
    cmp #'R'
    beq cpr_yes
    cmp #'r'
    bne cpr_no
cpr_yes:
    sec
    rts
cpr_no:
    clc
    rts

scan_ptr = $fb   ; zeropage, 2 bytes ($fb/$fc) - laut library-doku
                  ; von wic64.asm nicht benutzt
body_ptr = $fd   ; zeropage, 2 bytes ($fd/$fe) - zeigt nach extract_session_id
                  ; auf den beginn von "WAIT"/"START..." in der join-antwort

; ------------------------------------------------------------
; print_response_bytes: gibt y bytes ab (tick_response + x) aus,
; ueber die kernal-ausgabe-routine.
; ------------------------------------------------------------
print_response_bytes:
    stx print_idx
print_loop:
    cpy #0
    beq print_done
    ldx print_idx
    lda tick_response,x
    jsr CHROUT
    inc print_idx
    dey
    jmp print_loop
print_done:
    rts

print_newline:
    lda #13
    jsr CHROUT
    rts

; ------------------------------------------------------------
; delay_a_while: grobe verzoegerung (~10 sekunden), unkalibriert -
; auf echter hardware ggf. anpassen (innere schleifengrenze).
; ------------------------------------------------------------
delay_a_while:
    ldx #0
outer_delay:
    ldy #0
inner_delay:
    dey
    bne inner_delay
    dex
    bne outer_delay
    ldx #0
outer_delay2:
    ldy #0
inner_delay2:
    dey
    bne inner_delay2
    dex
    bne outer_delay2
    rts

; ------------------------------------------------------------
; Texte (petscii, null-terminiert fuer das print-makro)
; ------------------------------------------------------------
!macro print .string {
    lda #<.string
    ldy #>.string
    jsr $ab1e
}

banner_msg:     !pet 13, "*** retro tron - c64/wic64 ***", 13, "build 1", 13, 13, $00
waiting_msg:    !pet "warte auf gegner...", 13, $00
gameon_msg:     !pet 13, "spiel laeuft! steuere mit dem joystick.", 13, $00
restarting_msg: !pet 13, "naechstes spiel startet gleich...", 13, $00
hiccup_msg:     !pet "netzwerk-hicks - neuer versuch...", 13, $00
no_device_msg:  !pet "?wic64 nicht gefunden", 13, $00
legacy_msg:     !pet "?wic64 mit veralteter firmware", 13, $00

; ------------------------------------------------------------
; Variablen
; ------------------------------------------------------------
game_started:   !byte 0
dir_char:       !byte $4e   ; 'N'
print_idx:      !byte 0

; ------------------------------------------------------------
; JOIN-Anfrage - komplett statisch, da name/pin erst beim
; assemblieren feststehen (siehe hinweis zu interaktiver
; pin-eingabe ganz oben)
; ------------------------------------------------------------
join_request:
    !byte "R", WIC64_HTTP_GET
    !word join_url_len
join_url:
    !text "http://192.168.17.11:8098"     ; <-- EDIT: server-ip:http-bridge-port
    !text "/join/C64/"
    !text "COMMODORE64"                   ; <-- EDIT: spielername
    !text "/"
    !text "NONE"                          ; <-- EDIT: pin, oder "NONE"
join_url_end:
join_url_len = join_url_end - join_url

join_response: !fill 200, 0

; ------------------------------------------------------------
; TICK-Anfrage - der praefix ist statisch, session-id und
; richtung werden zur laufzeit ueberschrieben (siehe
; extract_session_id / poke_tick_direction). Die groesse ist
; deshalb bei uns immer konstant (unsere session-ids sind
; garantiert 8 hex-zeichen lang).
; ------------------------------------------------------------
tick_request:
    !byte "R", WIC64_HTTP_GET
    !word tick_url_len
tick_url:
    !text "http://192.168.17.11:8098"     ; <-- EDIT: gleiche server-ip:port wie oben!
    !text "/tick/"
tick_session_slot:
    !fill 8, $30
    !text "/"
tick_dir_slot:
    !byte $4e   ; 'N', wird von poke_tick_direction ueberschrieben
tick_url_end:
tick_url_len = tick_url_end - tick_url

tick_response: !fill 200, 0

!source "wic64.asm"
