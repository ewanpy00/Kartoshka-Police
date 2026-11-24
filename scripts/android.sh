#!/usr/bin/env bash
# Gatekeeper on the Android emulator, built natively (Android Studio's SDK in ~/Library/Android/sdk).
#
#   scripts/android.sh run          # build, start the emulator if needed, install, launch
#   scripts/android.sh open <url>   # tap a link: sends a VIEW intent, as an SMS link would
#   scripts/android.sh shot [file]  # screenshot of the emulator (default gatekeeper/dist/screen.png)
#   scripts/android.sh studio       # open the project in Android Studio
#   scripts/android.sh tour [en|ar] # record the product tour on the device (showcase-video/kartoshka-tour-phone-<lang>.mp4)
#
# The emulator reaches the Mac at 10.0.2.2, which is the build's default core address.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

SDK="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
ADB="$SDK/platform-tools/adb"
AVD="${AVD:-Kartoshka_Pixel}"
PKG=ae.kartoshka.gatekeeper
export JAVA_HOME="${JAVA_HOME:-$(/usr/libexec/java_home -v 17)}"

ensure_emulator() {
  if ! "$ADB" devices | grep -q 'emulator-'; then
    echo "Starting emulator $AVD"
    nohup "$SDK/emulator/emulator" -avd "$AVD" -no-snapshot-save -no-boot-anim >/tmp/kartoshka-emulator.log 2>&1 &
    "$ADB" wait-for-device
  fi
  until [ "$("$ADB" shell getprop sys.boot_completed 2>/dev/null | tr -d '\r')" = "1" ]; do sleep 2; done
}

case "${1:-run}" in
  run)
    # The offline product tour (TourActivity) goes into the APK when the resident app's packages are installed.
    if [ -d resident/node_modules ]; then (cd resident && npx vite build -c vite.tour.config.ts --logLevel error); fi
    # GRADLE_ARGS passes build options, e.g. -Pdemo=true for the sample-data build (make android-demo).
    (cd gatekeeper && ./gradlew assembleDebug -q ${GRADLE_ARGS:-})
    ensure_emulator
    "$ADB" install -r gatekeeper/app/build/outputs/apk/debug/app-debug.apk >/dev/null
    "$ADB" shell am force-stop "$PKG"
    "$ADB" shell am start -n "$PKG/.MainActivity" >/dev/null
    echo "Gatekeeper $(grep -o 'versionName = "[^"]*"' gatekeeper/app/build.gradle.kts | cut -d'"' -f2) is running on the emulator"
    ;;
  open)
    # Straight to Gatekeeper, so this works before it is the default browser.
    "$ADB" shell am start -a android.intent.action.VIEW -c android.intent.category.BROWSABLE -d "${2:?url}" -n "$PKG/.LinkActivity" >/dev/null
    ;;
  shot)
    out="${2:-gatekeeper/dist/screen.png}"
    mkdir -p "$(dirname "$out")"
    "$ADB" exec-out screencap -p > "$out"
    echo "$out"
    ;;
  studio)
    open -a "Android Studio" gatekeeper
    ;;
  tour)
    # Works with the emulator or a phone on USB. The tour opens paused on its first frame, the recording
    # starts, a tap starts the tour, and it plays once (24 s) and holds the end card.
    lang="${2:-en}"
    out="showcase-video/kartoshka-tour-phone-$lang.mp4"
    mkdir -p showcase-video
    # Skip Android's one-time "Viewing full screen" hint, which would cover the start of the video.
    "$ADB" shell settings put secure immersive_mode_confirmations confirmed
    "$ADB" shell am force-stop "$PKG"
    "$ADB" shell am start -n "$PKG/.TourActivity" --es lang "$lang" --ez record true >/dev/null
    sleep 2
    "$ADB" shell screenrecord --time-limit 26 --bit-rate 16000000 /sdcard/kp-tour.mp4 &
    rec=$!
    sleep 0.6
    size=$("$ADB" shell wm size | tr -dc '0-9x\n' | tail -1)
    "$ADB" shell input tap $(( ${size%x*} / 2 )) $(( ${size#*x} / 2 ))
    wait $rec
    "$ADB" pull -q /sdcard/kp-tour.mp4 "$out" && "$ADB" shell rm /sdcard/kp-tour.mp4
    echo "$out"
    ;;
  *)
    sed -n 2,9p "$0"
    exit 2
    ;;
esac
