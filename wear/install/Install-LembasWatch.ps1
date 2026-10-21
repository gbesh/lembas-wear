<#
  Lembas for Wear OS - install the watch app and the watch face on your watch, once.
  After this, Lembas on the watch keeps itself (and the watch face) up to date.

  It uses Google's own "adb" tool over Wi-Fi (downloaded from Google into
  %LOCALAPPDATA%\Lembas\Watch), pairs with your watch using the code the watch shows,
  installs the newest Lembas release from GitHub, and lets Lembas install its own updates.
#>
$ErrorActionPreference = 'Stop'
$work = Join-Path $env:LOCALAPPDATA 'Lembas\Watch'
New-Item -ItemType Directory -Path $work -Force | Out-Null
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Say($t, $c = 'Gray') { Write-Host $t -ForegroundColor $c }
Say ""
Say "  LEMBAS FOR YOUR WATCH" 'Yellow'
Say ""

# 1. Google's adb
$adb = Join-Path $work 'platform-tools\adb.exe'
if (-not (Test-Path $adb)) {
    Say "  * Downloading Google's adb tool" 'DarkYellow'
    $zip = Join-Path $work 'platform-tools.zip'
    Invoke-WebRequest 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip' -OutFile $zip -UseBasicParsing
    Expand-Archive $zip -DestinationPath $work -Force
    Remove-Item $zip -Force
}

# 2. The newest Lembas for the watch
Say "  * Downloading the newest Lembas for Wear OS" 'DarkYellow'
$rel = Invoke-RestMethod 'https://api.github.com/repos/gbesh/lembas-wear/releases/latest' -Headers @{ 'User-Agent' = 'Lembas' }
foreach ($n in 'lembas-wear.apk', 'lembas-watchface.apk') {
    $a = $rel.assets | Where-Object name -eq $n | Select-Object -First 1
    if (-not $a) { Say "  The release has no $n yet." 'Red'; Read-Host "  Press Enter to close"; exit 1 }
    Invoke-WebRequest $a.browser_download_url -OutFile (Join-Path $work $n) -UseBasicParsing
}

# 3. Pair with the watch
Say ""
Say "  On your watch:" 'Yellow'
Say "   1. Settings > System > About > Versions: tap 'Build number' 7 times (Developer options)."
Say "   2. Settings > Developer options: turn on 'ADB debugging' and 'Wireless debugging'."
Say "      Keep the watch and this PC on the same Wi-Fi."
Say "   3. Wireless debugging > 'Pair new device'. The watch shows an IP address:port and a code."
Say ""
$pairAt = Read-Host "  IP address:port shown under 'Pair new device' (e.g. 192.168.1.20:41234)"
$code = Read-Host "  Pairing code"
& $adb pair $pairAt $code
Say ""
Say "  Now the IP address:port shown on the main 'Wireless debugging' screen (a different port)." 'Yellow'
$connectAt = Read-Host "  IP address:port"
& $adb connect $connectAt | Out-Host
Start-Sleep -Seconds 2
$state = (& $adb -s $connectAt get-state 2>$null)
if ($state -ne 'device') { Say "  Couldn't connect to the watch. Check Wireless debugging is on and try again." 'Red'; Read-Host "  Press Enter to close"; exit 1 }

# 4. Install, and let Lembas update itself from now on
Say "  * Installing the Lembas watch face and app" 'DarkYellow'
& $adb -s $connectAt install -r (Join-Path $work 'lembas-watchface.apk') | Out-Host
& $adb -s $connectAt install -r (Join-Path $work 'lembas-wear.apk') | Out-Host
& $adb -s $connectAt shell appops set com.middleearth.launcher REQUEST_INSTALL_PACKAGES allow | Out-Null
& $adb disconnect $connectAt | Out-Null

Say ""
Say "  Done." 'Yellow'
Say "  Watch face: touch and hold the watch face, swipe to the end, tap +, and choose Lembas."
Say "  Its settings (touch and hold > Customise) choose the look and the complications."
Say "  App: Lembas is in your app list. Tile: swipe left on the watch face, add the Lembas tile."
Say "  Tip: Settings > Buttons can open Lembas with a double press of the side button."
Say "  You can turn Wireless debugging off again now."
Say ""
Read-Host "  Press Enter to close" | Out-Null
