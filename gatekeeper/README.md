# Gatekeeper (Android)

The Android app: the default browser that checks every tapped link before it opens (ARCHITECTURE.md section 3). It is a separate Gradle build; `docker compose` does not build or start it.

**Status:** builds and runs from Android Studio (see Build below). `make test` covers only the pure-Kotlin decision logic (`app/src/main/java/ae/kartoshka/gatekeeper/logic/`), compiled and unit-tested on a plain JVM; it was also checked against the running core.

## What it does

| Entry | Flow |
|---|---|
| Tapped link (default browser) | Local check, then `POST /v1/check` with a 400 ms budget, then one of: forward to the real browser, warn, block, or "Checking link…" for up to 3 s. |
| Share "Check with Kartoshka" | One link goes through the same flow. Text with none or several links opens the resident SMS check. |
| Home | Set as default browser (`RoleManager.ROLE_BROWSER`), Private DNS, choose the browser for safe links; then Check a link, Paste an SMS, My reports, Scam radar. |

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

Needs Android Studio (or the Android SDK with JDK 17).

1. Open `gatekeeper/` in Android Studio; it downloads Gradle 8.11.1 from `gradle/wrapper/gradle-wrapper.properties`. The wrapper jar is not committed. Without Android Studio, run `gradle wrapper --gradle-version 8.11.1` once, then use `./gradlew`.
2. Run `./gradlew installDebug` with a phone attached over USB.

After `data/brands.yaml` changes, refresh the bundled catalog:

    uv run --with pyyaml python gatekeeper/tools/brands_json.py

## Talking to core

`coreUrl` and `residentUrl` live in `gradle.properties` and default to `127.0.0.1`.

- **USB (recommended for recording).** Run `adb reverse tcp:8000 tcp:8000 && adb reverse tcp:5174 tcp:5174`. Nothing is exposed to the network.
- **Emulator.** Build with `./gradlew installDebug -PcoreUrl=http://10.0.2.2:8000 -PresidentUrl=http://10.0.2.2:5174`.
- **Wi-Fi.** Set `BIND_ADDR=0.0.0.0` in `.env`, restart the stack, then build with `-PcoreUrl=http://<laptop IP>:8000 -PresidentUrl=http://<laptop IP>:5174`. Debug builds allow cleartext HTTP to any host (`src/debug/res/xml`); release builds allow it only to 127.0.0.1, localhost and 10.0.2.2. This exposes core to the whole network, so set `BIND_ADDR` back afterwards.

`POST /v1/check` can return `pending`. It means there is no verdict yet; it never means safe. Gatekeeper treats it as a timeout.

## Demo

    adb shell am start -a android.intent.action.VIEW -d "https://tamm-fines-pay.top/pay"     # with Gatekeeper as default browser
    adb emu sms send 0501234567 "RTA fine overdue, pay now: https://tamm-fines-pay.top/pay"  # emulator: a real incoming SMS

The block page shows **Check your real fines in TAMM** (`https://www.tamm.abudhabi/wb/adp/pay-traffic-fines`). Record the screen with `scrcpy --record demo.mp4`.

## Limits

- iOS cannot do this with a check-and-redirect app: the default-browser entitlement requires a real browser. iPhone users get the resident web app for now; the iPhone plan is in `docs/apple-development-plan.md`.
- In-app browsers (Instagram, Telegram, TikTok) bypass the default browser; residents use the share button there.
- Android has no API to set Private DNS for the user. The button copies the resolver hostname (`-PdnsHost=`) and opens the network settings.
