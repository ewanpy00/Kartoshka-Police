#!/usr/bin/env bash
# Builds the Gatekeeper debug APK in Docker (no Android SDK needed on this machine).
#
#   scripts/apk.sh              # phone over USB: core and resident at 127.0.0.1 (use adb reverse)
#   scripts/apk.sh 192.168.1.20 # phone over Wi-Fi: core and resident at that laptop address
#
# Under emulation (Apple Silicon) Gradle runs lean: no file watching, Kotlin compiled in-process, two
# workers, a 1.5 GB heap, so it fits next to the running stack in Docker's memory.
# The APK lands in gatekeeper/dist/. The debug signing key is kept in a Docker volume, so a new build
# installs over the previous one.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

host="${1:-127.0.0.1}"
core_port=$(grep -E '^CORE_PORT=' .env 2>/dev/null | cut -d= -f2 || true); core_port=${core_port:-8000}
resident_port=$(grep -E '^RESIDENT_PORT=' .env 2>/dev/null | cut -d= -f2 || true); resident_port=${resident_port:-5174}

docker build -q -t kartoshka-android-build gatekeeper/docker >/dev/null
docker run --rm --platform linux/amd64 \
  -v "$PWD/gatekeeper":/gk -w /gk \
  -v kp-gradle-android:/home/gradle/.gradle \
  -v kp-android-debug-key:/root/.android \
  kartoshka-android-build \
  gradle assembleDebug --no-daemon -q --no-watch-fs --max-workers=2 \
    -Dorg.gradle.jvmargs="-Xmx1536m -XX:MaxMetaspaceSize=512m -Dfile.encoding=UTF-8" \
    -Pkotlin.compiler.execution.strategy=in-process \
    -PcoreUrl="http://${host}:${core_port}" -PresidentUrl="http://${host}:${resident_port}"

mkdir -p gatekeeper/dist
name="gatekeeper-debug-${host//./-}.apk"
cp gatekeeper/app/build/outputs/apk/debug/app-debug.apk "gatekeeper/dist/${name}"
echo "Built gatekeeper/dist/${name} (core http://${host}:${core_port}, resident http://${host}:${resident_port})"
