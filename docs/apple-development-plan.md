# Apple development plan

Status: plan, not built. Written 2026-11-24.

Kartoshka-Police can run on iPhone as a real web browser that the user sets as their default. iOS then sends every tapped link in Messages, Mail and most apps through Kartoshka first. Four iOS extensions cover the links the browser can't reach. The iPhone app uses the same backend (core) as the Android app and the console. Only the code on the phone is new.

## Contents

1. Why iPhone is different from Android
2. Apple's rules for a default browser
3. Tech
4. Main features
5. What each part covers
6. How a tapped link is handled
7. Limits
8. What we need
9. Build order

---

## 1. Why iPhone is different from Android

On Android, Gatekeeper becomes the default browser, checks each link, and then **hands safe links to the user's real browser** (Chrome, for example).

iPhone doesn't allow that. A default browser app must **load the page itself**. So the iPhone version of Kartoshka has to be a browser people can use every day, not only a checker that passes links on.

| | Android (Gatekeeper) | iPhone (planned) |
|---|---|---|
| How it sees tapped links | Default browser | Default browser |
| What happens to a safe link | Handed to Chrome or another browser | Loaded inside Kartoshka |
| Apple or Google approval needed | No | Yes, Apple must grant an entitlement |
| Scam SMS filter | No | Yes (Message Filter Extension) |
| Turning on DNS Shield | The app copies a hostname and opens settings | The app turns it on with one tap |

---

## 2. Apple's rules for a default browser

Source: [Preparing your app to be the default web browser](https://developer.apple.com/documentation/xcode/preparing-your-app-to-be-the-default-browser) (Apple Developer Documentation).

1. **Apple's permission.** Request the managed entitlement `com.apple.developer.web-browser` through Apple's request form. This needs the paid Apple Developer account.
2. **Web links.** The app registers the `http` and `https` schemes in its `Info.plist`.
3. **Looks like a browser on launch.** It shows at least one of these: a URL field, a search, or a list of bookmarks.
4. **Opens the page the user asked for.** It goes straight to the link and shows the real content. It must not redirect elsewhere or change the page.
5. **Warnings are allowed.** Apple's text says the app may show a "Safe Browsing" or other warning for content suspected of phishing. Kartoshka's warn and block pages fit this rule.
6. **Apple's web engine.** Use WebKit through `WKWebView`. The old `UIWebView` isn't allowed.
7. **Limited personal data.** Apple rejects a browser app that asks for:
   - the full photo library (saving photos only is fine);
   - location "always" (in-use only is fine);
   - Health data;
   - HomeKit;
   - Bluetooth in the background.
8. **Universal Links.** A browser app can't claim Universal Links for its own domains. It can still open other apps' Universal Links.

---

## 3. Tech

| Part | Tech | Why |
|---|---|---|
| Language and screens | Swift, SwiftUI, built in Xcode | Apple's standard tools. Arabic right-to-left layout works with little extra effort. |
| Web pages | `WKWebView` | Required by Apple for a browser |
| Talking to core | `URLSession` calling `POST /v1/check`, `GET /v1/check/{id}` and `GET /v1/blocklist?since=` | The same API the Android app uses |
| Phone-side check | Bloom filter, lexical scorer and decision table, rewritten in Swift from `gatekeeper/app/src/main/java/ae/kartoshka/gatekeeper/logic/` | Gives the same quick answer as Android before the server replies |
| Scam SMS filter | Message Filter Extension (`IdentityLookup` framework) | Moves texts from unknown senders to Junk |
| Phone-wide protection | Network Extension, `NEDNSSettingsManager` | Turns on DNS Shield for the whole phone |
| Safari protection | Safari Content Blocker | Blocks confirmed scam sites when Safari is used anyway |
| Share menu | Share Extension | "Check with Kartoshka" from any app |
| Resident pages | `WKWebView` showing the existing resident PWA | Reuses Link X-ray, My reports, Scam radar and SMS paste |
| Keeping the list fresh | BackgroundTasks and App Groups | Updates the blocklist in the background and shares it with every extension |
| Alerts | UserNotifications | "A link you checked is now a confirmed scam" |

---

## 4. Main features

1. **Kartoshka browser.** It has an address bar, search, back and forward, tabs, bookmarks, history, share, downloads and password autofill. Every page is checked before it loads.
2. **Warn and block pages.** These show Arabic first, the domain with its dots broken (defanged), the reasons, and **Go to the real service**. Buttons: Go back, Report to police, Details and, on the warn page only, Open anyway.
3. **Scam texts go to Junk.** A text from an unknown number is checked, and scam texts never reach the inbox.
4. **One-tap DNS Shield.** Scam sites won't open in any app, including apps with their own built-in browser.
5. **Safari blocker.** Confirmed scam sites won't load in Safari either.
6. **Check with Kartoshka.** In any app, tap Share and then Kartoshka on a link or a message.
7. **Paste an SMS.** Every link in the pasted text is checked.
8. **Report to police.** One tap sends the case to the Officer Console. **My reports** shows what happened to it.
9. **Scam radar.** Shows which scams are active in the UAE now.
10. **Later alerts.** If a warned link is confirmed as a scam later, the user gets a notification.

---

## 5. What each part covers

| Where the link is | Browser | DNS Shield | Safari blocker | SMS filter | Share |
|---|---|---|---|---|---|
| Tapped in Messages, Mail, Notes, Calendar | Yes | Yes, confirmed sites only | — | — | Yes |
| Tapped in a chat app that opens your browser | Yes | Yes, confirmed sites only | — | — | Yes |
| Inside an app's own built-in browser (Instagram, TikTok, Facebook and others) | No | Yes, confirmed sites only | — | — | Yes |
| In an app's Safari pop-up | No | Yes, confirmed sites only | Yes | — | Yes |
| Typed into Safari | No | Yes, confirmed sites only | Yes | — | — |
| A text from an unknown number | — | — | — | Yes | Yes |

"Confirmed sites only" means sites an officer has confirmed. DNS Shield and the Safari blocker can't judge a brand-new site. The browser and the share button can.

---

## 6. How a tapped link is handled

1. The user taps a link in a text. iOS opens it in Kartoshka.
2. Kartoshka checks the link on the phone: is it an official brand domain, is it in the Bloom filter, and what's its lexical score?
3. Kartoshka asks core with `POST /v1/check`, waiting up to 400 ms.
4. It follows the same decision table as Android (`logic/Decision.kt`):
   - **Allow:** the page loads in Kartoshka.
   - **Warn:** the warn page appears.
   - **Block:** the block page appears.
   - **No answer in time, low score:** the page loads.
   - **No answer in time, higher score:** a "Checking link…" screen shows for up to 3 seconds, then a warning, or a block if the site is listed or the score is over 70.
5. After a warning, the app keeps checking the deep analysis for up to 3 minutes and sends a notification if the verdict turns to block.

---

## 7. Limits

- **Built-in browsers inside apps** (Instagram, TikTok, Facebook and others) don't use the default browser. DNS Shield and the share button cover them.
- **The SMS filter only checks unknown senders**, not contacts. It can only move a text to Junk. It can't show reasons.
- **The Safari blocker can't explain** why a site is blocked.
- **DNS Shield needs a public, secure resolver** (DNS over HTTPS or DNS over TLS). None is deployed yet: `dnsHost` is empty in `gatekeeper/gradle.properties`.
- **Apple must approve** the browser entitlement. We don't know how long this takes, and it could be refused.
- **People must want to browse in it.** If the browser feels worse than Safari, users will switch back and lose the protection.

---

## 8. What we need

| Need | Status | Note |
|---|---|---|
| Mac | Have | — |
| Xcode | Missing | Free from the Mac App Store, 10+ GB |
| iPhone and cable | — | For testing on a real device |
| Apple Developer account | Missing | Free accounts install on your own phone for 7 days only. The browser entitlement needs the paid account ($99/year). |
| Default browser entitlement | Not requested | Request it through Apple's form once a first version works |
| Public DNS Shield resolver | Not deployed | Needed for the DNS feature only |
| Core reachable from the iPhone | Works on the local network | The phone needs the Mac's IP over Wi-Fi, or core deployed online |

---

## 9. Build order

1. **Shared logic.** Port the Bloom filter, lexical scorer, decision table and core client to Swift. Test them against the same cases as the Android `LogicTest.kt`.
2. **Simple browser.** URL bar, search, back and forward, tabs, with the check before every page loads. This meets Apple's minimum rules.
3. **Warn and block pages.** Arabic first, with the same buttons as Android.
4. **Home screen and resident pages.** Check a link, Paste an SMS, My reports, Scam radar.
5. **Share Extension.** "Check with Kartoshka".
6. **Request the entitlement** from Apple with this working version.
7. **Message Filter Extension.** Scam texts go to Junk.
8. **Safari Content Blocker** using the confirmed blocklist.
9. **DNS Shield** with `NEDNSSettingsManager`, once a public resolver is deployed.
10. **Browser comfort features.** Bookmarks, history, downloads and password autofill.

Steps 1–5 can be built and shown with a free account. The browser works, but it can't be set as the default until Apple grants the entitlement in step 6. Steps 6–9 need the paid account. Check which extension capabilities a free account allows before planning a demo around them.
