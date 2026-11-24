# Gatekeeper (Android)

The Android app: the default browser that checks every tapped link before it opens (ARCHITECTURE.md section 3). It is a separate Gradle build; `docker compose` does not build or start it.

**Status:** builds and passes its JVM unit tests. The debug APK is built in Docker (`make apk`), with no Android SDK needed on the machine. It has not yet been run on a phone.

## What it does

| Entry | Flow |
|---|---|
| Tapped link (default browser) | Local check, then `POST /v1/check` with a 400 ms budget, then one of: forward to the real browser, warn, block, or "Checking link…" for up to 3 s. |
| Share "Check with Kartoshka" | One link goes through the same flow. Text with none or several links opens the resident SMS check. |
| Home | A link box (with paste) whose result opens as its own screen; Recent checks (links checked on purpose, plus links Gatekeeper warned about or blocked, never plain safe taps); set as default browser (`RoleManager.ROLE_BROWSER`), Private DNS, the browser for safe links, language and theme. Tabs: Home, My reports, Scam radar. |

The local check:
- Official domains of a brand are forwarded with no network call.
- A **Bloom filter** holds the police-confirmed list (`GET /v1/blocklist?since=`, synced every 15 minutes and whenever a link arrives with a list older than that).
- A **tiny lexical scorer** uses core's features and weights.

The decision table is in `logic/Decision.kt`:

| Core's answer | Local result | Action |
|---|---|---|
| allow | any | forward |
| warn | any | warn |
| block | any | block |
| none in time (timeout or `pending`) | low score (<30) | forward |
| none in time (timeout or `pending`) | higher score | "Checking link…" for up to 3 s, then warn, or block when listed or over 70 |
| offline | over 70, or listed | block |
| offline | otherwise | warn |

The warn and block pages put Arabic first, show the defanged domain, the reasons, and **Go to the real service** (core's `safe_action`; offline, the same rule over the bundled `assets/brands.json`). Their buttons are Go back, Report to police, Details and, on warn only, Open anyway. Details opens the resident X-ray and safe preview in a WebView.

After a warn, a worker polls the deep analysis for up to 3 minutes and notifies if it turns to block. Reports keep their id and token on the phone only. They are copied into the resident screens' storage, so My reports lists them.

Privacy: no account and no device id with checks. The full URL goes to core only when the domain is not official.

## Build

**Without Android Studio (Docker):**

    make apk                      # phone over USB: core at 127.0.0.1, use adb reverse
    make apk host=192.168.1.20    # phone over Wi-Fi: core at that laptop address

The APK lands in `gatekeeper/dist/gatekeeper-debug-<host>.apk`.
- The build image (`gatekeeper/docker/Dockerfile`) holds JDK 17, Gradle 8.11.1 and the Android SDK, and accepts the SDK licences while it builds.
- On Apple Silicon it runs as linux/amd64 under emulation, because the Android build tools ship only for x86_64 on Linux. The first build takes about 15 minutes; later ones take a few.
- The debug signing key stays in the `kp-android-debug-key` Docker volume, so a new APK installs over the old one.

**With Android Studio:** open `gatekeeper/` and run `./gradlew installDebug`. The wrapper jar is not committed; without Android Studio, run `gradle wrapper --gradle-version 8.11.1` once.

**Install on the phone:** send the APK to the phone by any route (USB file transfer, a messenger, Drive), open it, and allow installs from that app. Play Protect may warn about an unknown developer; choose "Install anyway". With adb, run `adb install -r gatekeeper/dist/<file>.apk`.

After `data/brands.yaml` changes, refresh the bundled catalog:

    uv run --with pyyaml python gatekeeper/tools/brands_json.py

## Talking to core

`coreUrl` and `residentUrl` live in `gradle.properties` and default to `127.0.0.1`.

- **USB (recommended for recording).** Run `adb reverse tcp:8000 tcp:8000 && adb reverse tcp:5174 tcp:5174`. Nothing is exposed to the network.
- **Emulator.** Build with `make apk host=10.0.2.2`.
- **Wi-Fi.** Set `BIND_ADDR=0.0.0.0` in `.env`, restart the stack, then build with `make apk host=<laptop IP>`. Debug builds allow cleartext HTTP to any host (`src/debug/res/xml`); release builds allow it only to 127.0.0.1, localhost and 10.0.2.2. This exposes core to the whole network, so set `BIND_ADDR` back afterwards.

`POST /v1/check` can return `pending`. It means there is no verdict yet; it never means safe. Gatekeeper treats it as a timeout.

## Demo

    adb shell am start -a android.intent.action.VIEW -d "https://tamm-fines-pay.top/pay"     # with Gatekeeper as default browser
    adb emu sms send 0501234567 "RTA fine overdue, pay now: https://tamm-fines-pay.top/pay"  # emulator: a real incoming SMS

The block page shows **Check your real fines in TAMM** (`https://www.tamm.abudhabi/wb/adp/pay-traffic-fines`). Record the screen with `scrcpy --record demo.mp4`.

## Limits

- iOS cannot do this: the default-browser entitlement requires a real browser. iPhone users get the resident PWA and the share sheet.
- In-app browsers (Instagram, Telegram, TikTok) bypass the default browser; residents use the share button there.
- Android has no API to set Private DNS for the user. With `-PdnsHost=` the button copies the resolver hostname and opens the network settings. Without it (every build today: AdGuard in `dns/` serves plain DNS on 5335, not DNS-over-TLS on 853) the row is marked "coming soon" and explains why.
- `-Pdemo=true` (`make android-demo`) builds with sample data: the resident pages answer from `resident/src/demo.ts` and Home gets sample counters and recent checks.

## Product tour (screen recording)

`TourActivity` plays the 24 s product tour from the web `/showcase` (sample data, no network) full screen, with the system bars hidden and the screen kept on. It is drawn in the light theme; `--es theme dark` (or `make record-tour theme=dark`) plays the dark one. Tap pauses; back exits.

- Open it with a long press on the app icon (Product tour), a long press on the Home header, or `adb shell am start -n ae.kartoshka.gatekeeper/.TourActivity --es lang ar`.
- The tour is built into the APK by `make tour`; `make android` and `make android-demo` do this when `resident/node_modules` exists. Without it (for example `make apk` in Docker) the screen opens `/showcase?phone` on the resident server instead.
- `make record-tour lang=en` (add `theme=dark` for the dark tour) records it with `adb screenrecord`: the tour waits on its first frame, the recording starts, a tap starts the tour, and it plays once and holds the end card. On a phone you can also use the built-in screen recorder.

