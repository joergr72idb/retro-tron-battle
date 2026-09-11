<#
.SYNOPSIS
  Retro-Tron-Bot fuer Windows/PowerShell - simuliert einen zweiten Spieler,
  praktisch fuer Demos, wenn kein zweiter echter Rechner (oder Meatloaf/M4-
  Board) zur Hand ist.

.DESCRIPTION
  Verbindet sich per TCP mit dem Tron-Server, schickt HELLO, und dreht dann
  - sobald das Spiel gestartet ist - auf einem Timer zufaellig ab (nicht
  Tick-getriggert, da der Server keine Tick-Daten mehr sendet; das Spielfeld
  existiert nur noch serverseitig). Entspricht funktional tron_bot.sh, laeuft
  aber nativ unter Windows ohne WSL oder netcat.

.PARAMETER ServerHost
  IP oder Hostname des Spiel-Servers. Standard: 127.0.0.1

.PARAMETER Port
  TCP-Port des Spiel-Servers. Standard: 6502

.PARAMETER Platform
  Plattform-Code, der gemeldet wird, z.B. C64, CPC, ATARI. Standard: C64

.PARAMETER PlayerName
  Anzeigename. Standard: PSBot

.PARAMETER Pin
  Optionale Besucher-Foto-PIN, falls die Foto/Logo-Funktion mitgetestet werden soll.

.PARAMETER TurnChance
  Grob 1-zu-N Poll-Durchlaeufe loesen eine zufaellige Drehung aus. Standard: 12

.EXAMPLE
  .\tron_bot.ps1 -ServerHost 192.168.1.50 -Platform C64 -PlayerName "Commodore64"

.NOTES
  Falls das Ausfuehren mit "die Ausfuehrung von Skripts ist auf diesem System
  deaktiviert" verweigert wird, entweder so aufrufen:
    powershell -ExecutionPolicy Bypass -File .\tron_bot.ps1 ...
  oder einmalig fuer die aktuelle Sitzung:
    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#>

param(
    [string]$ServerHost = "127.0.0.1",
    [int]$Port = 6502,
    [string]$Platform = "C64",
    [string]$PlayerName = "PSBot",
    [string]$Pin = "",
    [int]$TurnChance = 12
)

$ErrorActionPreference = "Stop"
$PollIntervalMs = 200
$MaxIdlePolls = 150   # ~30s ganz ohne Serverantwort = aufgeben

Write-Host "[$Platform/$PlayerName] connecting to $ServerHost`:$Port ..."

try {
    $client = New-Object System.Net.Sockets.TcpClient
    $client.Connect($ServerHost, $Port)
} catch {
    Write-Error "Konnte nicht mit $ServerHost`:$Port verbinden - $_"
    exit 1
}

$stream = $client.GetStream()
$encoding = [System.Text.Encoding]::ASCII

function Send-Line {
    param([string]$Text)
    $bytes = $encoding.GetBytes($Text + "`r`n")
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Flush()
}

$helloLine = "HELLO $Platform $PlayerName"
if ($Pin -ne "") { $helloLine += " $Pin" }
Send-Line $helloLine

# --- Zeilenpuffer, tolerant gegenueber CR, LF oder CRLF als Trenner ---
$script:recvBuffer = New-Object System.Text.StringBuilder
$readBuf = New-Object byte[] 512

function Get-NextLine {
    $text = $script:recvBuffer.ToString()
    $crIdx = $text.IndexOf([char]13)
    $lfIdx = $text.IndexOf([char]10)
    if ($crIdx -lt 0 -and $lfIdx -lt 0) { return $null }
    if ($crIdx -lt 0) { $idx = $lfIdx }
    elseif ($lfIdx -lt 0) { $idx = $crIdx }
    else { $idx = [Math]::Min($crIdx, $lfIdx) }

    $line = $text.Substring(0, $idx)
    $rest = $text.Substring($idx + 1)
    $termChar = $text[$idx]
    if ($rest.Length -gt 0) {
        $nextChar = $rest[0]
        if ((($termChar -eq [char]13) -and ($nextChar -eq [char]10)) -or
            (($termChar -eq [char]10) -and ($nextChar -eq [char]13))) {
            $rest = $rest.Substring(1)
        }
    }

    $script:recvBuffer = New-Object System.Text.StringBuilder
    [void]$script:recvBuffer.Append($rest)
    return $line
}

function Read-Available {
    while ($stream.DataAvailable) {
        $n = $stream.Read($readBuf, 0, $readBuf.Length)
        if ($n -gt 0) {
            [void]$script:recvBuffer.Append($encoding.GetString($readBuf, 0, $n))
        }
    }
}

$directions = @("U", "D", "L", "R")
$currentDir = "R"
$started = $false
$rand = New-Object System.Random
$idleCount = 0
$running = $true

while ($running) {
    Read-Available
    $line = Get-NextLine

    if ($null -ne $line) {
        $idleCount = 0
        $line = $line.Trim()
        switch -Regex ($line) {
            '^WAIT$' {
                Write-Host "[$Platform/$PlayerName] waiting for an opponent..."
            }
            '^START' {
                $tokens = $line -split '\s+'
                # START <w> <h> <x1> <y1> <x2> <y2> <yourplayernum> <p1plat> <p2plat>
                $playerNum = $tokens[7]
                if ($playerNum -eq "1") { $currentDir = "R" } else { $currentDir = "L" }
                $started = $true
                Write-Host "[$Platform/$PlayerName] game start! I'm player $playerNum - watch the server's window"
            }
            '^END WIN' {
                Write-Host "[$Platform/$PlayerName] $line"
                $started = $false
            }
            '^END DRAW$' {
                Write-Host "[$Platform/$PlayerName] draw game."
                $started = $false
            }
            '^STATS' {
                Write-Host "[$Platform/$PlayerName] $line"
                $running = $false
            }
            default {
                Write-Host "[$Platform/$PlayerName] < $line"
            }
        }
    } else {
        $idleCount++
        if ($idleCount -ge $MaxIdlePolls) {
            Write-Host "[$Platform/$PlayerName] no response from server for a while, giving up."
            break
        }
        if ($started -and ($rand.Next($TurnChance) -eq 0)) {
            $options = @($directions | Where-Object { $_ -ne $currentDir })
            $newDir = $options[$rand.Next($options.Count)]
            $currentDir = $newDir
            Send-Line "MOVE $newDir"
        }
    }

    Start-Sleep -Milliseconds $PollIntervalMs
}

try { $stream.Close() } catch {}
try { $client.Close() } catch {}
Write-Host "[$Platform/$PlayerName] disconnected."
