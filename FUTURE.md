# Kartoshka / ScamShield — Future

Things we want after the hackathon. They are not in the 24h build because they need development time on the other side (TAMM, UAE PASS, registrars), not because the Core API is missing. Each one is safe to show in the presentation as a next step: same check API, another client.

---

## 1. "Check a link" inside TAMM

Add ScamShield's link check as a service inside the TAMM app. The resident pastes a suspicious link, or shares one into TAMM, and gets the same verdict the Android app gets: allow / warn / block, score, and reasons in Arabic and English.

TAMM becomes another entry point. It calls the same Core API as Gatekeeper (`POST /v1/check`). No second scoring engine.

Why it matters:
- It covers the biggest limit of the current app. iPhone cannot use Kartoshka as the default browser. TAMM is already on iPhone and Android, so both platforms get the check.
- Millions of residents already have TAMM. They can check a link without installing a new app and without changing their default browser.
- A fake fine link checked here can still offer **Check your real fines in TAMM**, because the user is already inside the real service.

Why it waits:
- The service has to be built inside TAMM, on their side. We do not have that development time or access in this hackathon.
- Our side is already done for it: the check API, the verdict format, and AR/EN reasons. TAMM only needs a screen that sends the URL and shows the response.

What we show in the presentation:
- TAMM drawn as one more client next to Gatekeeper, DNS Shield, and the judges' CLI, all calling Core.
- A static screen: paste or share a link → "⚠️ Suspected scam" → reasons in Arabic and English → button to the real TAMM service.
- One line on the limits slide: not live in TAMM yet; blocked on their development resources, not on our API.
