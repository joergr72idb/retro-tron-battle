<#
.SYNOPSIS
  Retro Tron bot for Windows/PowerShell - simulates a second player,
  handy for demos when a second real computer (or Meatloaf/M4 board) isn't
  on hand.

.DESCRIPTION
  Connects to the Tron server via TCP, sends HELLO, and then - once the
  game has started - turns randomly on a timer (not tick-triggered, since
  the server no longer sends tick data; the playfield only exists
  server-side now). Functionally equivalent to tron_bot.sh, but runs
  natively on Windows without WSL or netcat.

.PARAMETER ServerHost
  IP or hostname of the game server. Default: 127.0.0.1

.PARAMETER Port
  TCP port of the game server. Default: 6502

.PARAMETER Platform
  Platform code reported to the server, e.g. C64, CPC, ATARI. Default: C64

.PARAMETER PlayerName
  Display name. Default: PSBot

.PARAMETER Pin
  Optional visitor photo PIN, if you want to test the photo/logo feature too.

.PARAMETER TurnChance
  Roughly 1-in-N poll cycles trigger a random turn. Default: 12

.EXAMPLE
  .\tron_bot.ps1 -ServerHost 192.168.1.50 -Platform C64 -PlayerName "Commodore64"

.NOTES
  If running it is refused with "running scripts is disabled on this
  system", either call it like this:
    powershell -ExecutionPolicy Bypass -File .\tron_bot.ps1 ...
  or once for the current session:
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
$MaxIdlePolls = 150   # ~30s with no server response at all = give up

Write-Host "[$Platform/$PlayerName] connecting to $ServerHost`:$Port ..."

try {
    $client = New-Object System.Net.Sockets.TcpClient
    $client.Connect($ServerHost, $Port)
} catch {
    Write-Error "Couldn't connect to $ServerHost`:$Port - $_"
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

# --- Line buffer, tolerant of CR, LF, or CRLF as a separator ---
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
