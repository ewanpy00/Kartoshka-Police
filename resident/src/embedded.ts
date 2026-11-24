// True inside the Gatekeeper Android app, whose WebView adds "KartoshkaGatekeeper" to the user agent.
// The app has its own header and tabs, so the page hides them; the language follows the phone.
export const embedded = typeof navigator !== 'undefined' && navigator.userAgent.includes('KartoshkaGatekeeper')
if (embedded) document.documentElement.classList.add('embedded')
