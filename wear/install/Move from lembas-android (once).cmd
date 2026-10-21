<# :
@echo off
title Lembas for your watch - move to the new repo
powershell -NoProfile -ExecutionPolicy Bypass -Command "iex ([IO.File]::ReadAllText('%~f0'))"
exit /b
#>
# One-off: removes the Lembas watch app and watch face that came from gbesh/lembas-android,
# then installs the current ones from gbesh/lembas-wear (which is where updates come from now).
$ErrorActionPreference = 'Stop'
$work = Join-Path $env:LOCALAPPDATA 'Lembas\Watch'
New-Item -ItemType Directory -Path $work -Force | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
function Say($t, $c = 'Gray') { Write-Host $t -ForegroundColor $c }
function Quit($t) { Say "  $t" 'Red'; Read-Host "  Press Enter to close" | Out-Null; exit 1 }

Say ""
Say "  LEMBAS FOR YOUR WATCH - MOVE TO THE NEW REPO" 'Yellow'
Say ""

# 1. Google's adb tool (reused if the installer already downloaded it)
$adb = Join-Path $work 'platform-tools\adb.exe'
if (-not (Test-Path $adb)) {
    Say "  * Downloading Google's adb tool" 'DarkYellow'
    $zip = Join-Path $work 'platform-tools.zip'
    Invoke-WebRequest 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip' -OutFile $zip -UseBasicParsing
    Expand-Archive $zip -DestinationPath $work -Force
    Remove-Item $zip -Force
}

# 2. The newest build from the new repo (fetched before touching the watch)
Say "  * Downloading Lembas for Wear OS from gbesh/lembas-wear" 'DarkYellow'
try {
    $rel = Invoke-RestMethod 'https://api.github.com/repos/gbesh/lembas-wear/releases/latest' -Headers @{ 'User-Agent' = 'Lembas' }
} catch { Quit "gbesh/lembas-wear has no release yet. Nothing on the watch was changed; try again once it has one." }
foreach ($n in 'lembas-wear.apk', 'lembas-watchface.apk') {
    $a = $rel.assets | Where-Object name -eq $n | Select-Object -First 1
    if (-not $a) { Quit "The release $($rel.tag_name) has no $n. Nothing on the watch was changed." }
    Invoke-WebRequest $a.browser_download_url -OutFile (Join-Path $work $n) -UseBasicParsing
}
Say "    Got $($rel.tag_name)."

# 3. Connect to the watch
Say ""
Say "  On your watch:" 'Yellow'
Say "   1. Settings > Developer options: turn on 'ADB debugging' and 'Wireless debugging'."
Say "      (No Developer options? Settings > System > About > Versions: tap 'Build number' 7 times.)"
Say "      Keep the watch and this PC on the same Wi-Fi."
Say "   2. Wireless debugging > 'Pair new device'. The watch shows an IP address:port and a code."
Say ""
$pairAt = Read-Host "  IP address:port shown under 'Pair new device' (e.g. 192.168.1.20:41234)"
$code = Read-Host "  Pairing code"
& $adb pair $pairAt $code | Out-Host
Say ""
Say "  Now the IP address:port shown on the main 'Wireless debugging' screen (a different port)." 'Yellow'
$connectAt = Read-Host "  IP address:port"
& $adb connect $connectAt | Out-Host
Start-Sleep -Seconds 2
$state = (& $adb -s $connectAt get-state 2>$null)
if ($state -ne 'device') { Quit "Couldn't connect to the watch. Nothing was changed. Check Wireless debugging is on and run this again." }

# 4. Remove the old ones, install the new ones
$ErrorActionPreference = 'Continue'
Say ""
Say "  * Removing the old Lembas watch face and app" 'DarkYellow'
foreach ($p in 'com.middleearth.launcher.watchface', 'com.middleearth.launcher') {
    $out = (& $adb -s $connectAt uninstall $p 2>&1) -join ' '
    if ($out -match 'Success') { Say "    Removed $p" } else { Say "    $p wasn't installed" 'DarkGray' }
}
Say "  * Installing Lembas $($rel.tag_name) from the new repo" 'DarkYellow'
$ok = $true
foreach ($n in 'lembas-watchface.apk', 'lembas-wear.apk') {
    $out = (& $adb -s $connectAt install (Join-Path $work $n) 2>&1) -join ' '
    if ($out -match 'Success') { Say "    Installed $n" } else { Say "    Couldn't install $n : $out" 'Red'; $ok = $false }
}
& $adb -s $connectAt shell appops set com.middleearth.launcher REQUEST_INSTALL_PACKAGES allow | Out-Null
& $adb disconnect $connectAt | Out-Null
if (-not $ok) { Quit "Something didn't install. Run this again; it's safe to repeat." }

Say ""
Say "  Done. Lembas on your watch now updates from gbesh/lembas-wear." 'Yellow'
Say "  Removing the old version also removed the face and tile from your watch, so add them back:"
Say "   - Watch face: touch and hold the watch face, swipe to the end, tap +, choose Lembas."
Say "   - Tile: swipe left from the watch face, add the Lembas tile."
Say "  You can turn Wireless debugging off again now. You can delete this file."
Say ""
Read-Host "  Press Enter to close" | Out-Null
