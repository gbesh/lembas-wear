#!/usr/bin/env bash
# Test builds only: installs Lembas on a Wear OS emulator and captures each look of the face and the app.
set -u
mkdir -p shots
S="$PWD/shots"
snap() {
  adb exec-out screencap -p > "$S/$1.png"
  adb emu screenrecord screenshot "$S/$1-display.png" > /dev/null 2>&1 || true
}
until [ "$(adb shell getprop sys.boot_completed | tr -d '\r')" = "1" ]; do sleep 2; done
sleep 45
adb install -r out/lembas-watchface.apk 2>&1 | tee "$S/install.txt"
adb install -r out/lembas-wear.apk 2>&1 | tee -a "$S/install.txt"
adb root || true
sleep 5
adb shell settings put global auto_time 0 || true
# Sydney's time zone, so the face works out the sun for a zone in its table
adb shell settings put global auto_time_zone 0 || true
adb shell cmd alarm set-timezone Australia/Sydney > "$S/timezone.txt" 2>&1 || true
adb shell service call alarm 3 s16 Australia/Sydney >> "$S/timezone.txt" 2>&1 || true
adb shell setprop persist.sys.timezone Australia/Sydney >> "$S/timezone.txt" 2>&1 || true
sleep 2
adb shell getprop persist.sys.timezone >> "$S/timezone.txt" 2>&1
# Off the charger, or Wear OS covers the face with its charging screen
adb emu power ac off > /dev/null 2>&1 || true
adb emu power status discharging > /dev/null 2>&1 || true
adb shell dumpsys battery unplug || true
adb shell dumpsys battery set level 80 || true
adb logcat -c || true
adb shell am broadcast -a com.google.android.wearable.app.DEBUG_SURFACE --es operation set-watchface --es watchFaceId com.middleearth.launcher.watchface 2>&1 | tee "$S/setface.txt"
sleep 20
adb shell input keyevent KEYCODE_WAKEUP; sleep 3
snap face-now
for t in 0603:dawn 0921:shire 1530:afternoon 1815:redbook 2005:starlit 0130:elven; do
  hm=${t%%:*}; n=${t##*:}
  adb shell "date $(date +%m%d)${hm}$(date +%Y).00" || true
  adb shell input keyevent KEYCODE_WAKEUP; sleep 8
  snap "face-$n"
  adb shell date >> "$S/timezone.txt" 2>&1
done
# three frames 0.3 s apart on the last look: the glint should have moved a little between each
for k in a b c; do adb emu screenrecord screenshot "$S/motion-$k.png" > /dev/null 2>&1; sleep 0.3; done
adb logcat -d > "$S/full.txt" || true
grep -E "DWF|middleearth|AndroidRuntime|DEBUG_SURFACE|WatchFaceRuntime" "$S/full.txt" | grep -v -E "RestrictionManager|Finsky|CanvasComplication" | tail -500 > "$S/logcat.txt" || true
grep -E " [EW] " "$S/full.txt" | grep -v -E "RestrictionManager|Finsky" | tail -300 > "$S/logcat-errors.txt" || true
rm -f "$S/full.txt"
# the look chosen in the app reaches the face (through the hidden Lembas look complication)
adb shell "date $(date +%m%d)0921$(date +%Y).00" || true
adb shell am start -n com.middleearth.launcher/com.middleearth.lembas.wear.MainActivity --es look redbook
sleep 4
adb shell input keyevent KEYCODE_HOME
sleep 8
snap face-picked-redbook
adb shell am start -n com.middleearth.launcher/com.middleearth.lembas.wear.MainActivity --es look auto
sleep 4
adb shell input keyevent KEYCODE_HOME
sleep 8
snap face-picked-auto
adb shell am start -n com.middleearth.launcher/com.middleearth.lembas.wear.MainActivity
sleep 6
snap app-top
adb shell input swipe 200 350 200 120 300
sleep 2
snap app-list
adb shell input keyevent KEYCODE_HOME
sleep 3
adb shell input keyevent KEYCODE_SLEEP
sleep 6
snap face-ambient
exit 0
