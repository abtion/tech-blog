---
marp: true
theme: default
paginate: true
---

# CSP in 2026: Why 99% of Policies Are Still Broken (And How to Fix Yours)

**BornHack 2026**

<!-- TALKING NOTES (slide 1 — ~1 min)
Introduce yourself. One sentence on where you work and what you do.
Mention that the talk is rooted in a real implementation project you worked on recently —
not a theoretical walkthrough, but a post-mortem of what actually went wrong and how you fixed it.
Estimated talk length: ~35–40 minutes + Q&A.
-->

---

## Quick show of hands

- Who is sending a `Content-Security-Policy` header right now?
- Of those: who is doing it *without* `'unsafe-inline'` in `script-src`?
- Who has heard of `'strict-dynamic'`?
- Who is using it?

<!-- TALKING NOTES (slide 2 — ~2 min)
This is a quick audience calibration. Pause and wait for hands.
The gap between "has CSP" and "uses strict-dynamic" is usually large — that gap is what the
whole talk is about.
-->

---

## The numbers

A 2016 Google Research study found:

- **94.68%** of policies *trying* to restrict script execution are ineffective
- **99.34%** of all hosts with CSP get no XSS benefit at all

Fast-forward to June 2026 (Tranco Top 1 Million crawl):

- 170,057 sites have a `Content-Security-Policy` header
- **46.8%** still include `'unsafe-inline'`
- Only **1.6%** use `'strict-dynamic'`

Ten years. Barely moved.

<!-- TALKING NOTES (slide 3 — ~3 min)
The 2016 paper ("CSP Is Dead, Long Live CSP!") proposed strict-dynamic as the fix.
It has had broad browser support since March 2022 — Safari was the last holdout.
Despite that, adoption is essentially flat. The talk is about why, and what to do about it.
Keep this punchy. The numbers do the work.
-->

---

## What `'unsafe-inline'` actually means

```
Content-Security-Policy: script-src 'self' 'unsafe-inline'
```

This tells the browser:

> "Execute any script that appears inline on the page."

That includes the ones *an attacker injected*.

- Reflected XSS payload in a query parameter? Executes.
- Stored XSS in a comment field? Executes.
- Supply-chain compromise injecting a `<script>` tag? Executes.

**CSP with `'unsafe-inline'` does not stop XSS. It is theatre.**

<!-- TALKING NOTES (slide 4 — ~3 min)
Be concrete. The audience will know what XSS is — skip the primer.
The point is that 'unsafe-inline' specifically neutralises the one thing script-src is
there to do: prevent unauthorised script execution.
Domain allowlists (e.g. 'self', CDN domains) are marginally better — they stop some
injection vectors — but they still leave you exposed to any script hosted on those domains,
including ones an attacker could place there.
-->

---

## `'unsafe-eval'` is the same problem

```js
eval(userControlledString)   // classic
new Function(userInput)()    // same thing
setTimeout(attackerPayload)  // also counts
```

`'unsafe-eval'` permits all of these.

It is how injected *strings* become *executing code*.

If your policy includes `'unsafe-eval'`, you are not protected against the injection class
that CSP is specifically designed to mitigate.

<!-- TALKING NOTES (slide 5 — ~2 min)
Brief slide. Make the point and move on.
The reason this matters is GTM — which you'll come back to later.
-->

---

## The fix: nonces + `'strict-dynamic'`

A nonce is a random value generated fresh on every response:

```html
<script nonce="r4nd0m">/* your code */</script>
```

```
Content-Security-Policy: script-src 'nonce-r4nd0m' 'strict-dynamic'
```

`'strict-dynamic'` extends trust **transitively**:

- Any script loaded by a nonced script is also trusted
- No domain allowlist needed
- You do not touch third-party scripts

<!-- TALKING NOTES (slide 6 — ~4 min)
The nonce must be:
  - cryptographically random (use your framework's secure RNG, not Math.random())
  - different on every response (not cached)
  - at least 128 bits of entropy

strict-dynamic was the core contribution of the 2016 Google paper. The idea is that if you
trust the entry-point script (the nonced one), you can transitively trust whatever it loads —
because a legitimate script only loads other legitimate scripts.

This eliminates the CDN/domain allowlist maintenance problem entirely.

Mention that you only need to nonce your *own* entry-point scripts. Third-party scripts
loaded by those scripts inherit trust automatically.
-->

---

## A model policy

```
Content-Security-Policy:
  default-src 'none';
  script-src  'nonce-{random}' 'strict-dynamic' 'report-sample';
  style-src   'self';
  img-src     'self' data:;
  font-src    'self';
  connect-src 'self';
  object-src  'none';
  base-uri    'none';
  frame-ancestors 'none'
```

<!-- TALKING NOTES (slide 7 — ~4 min)
Walk through each directive:

default-src 'none': everything blocked unless explicitly permitted. This is the right
starting point — you then open only what you actually need.

script-src 'nonce-{random}' 'strict-dynamic': the core. report-sample tells the browser
to include a snippet of the offending script in violation reports — invaluable for triage.

style-src 'self': inline styles are blocked by default. If a framework injects them,
you may need to add 'unsafe-inline' here — it is a known trade-off (style injection is
lower severity than script injection).

connect-src 'self': strict-dynamic only propagates trust for *script loading*. Fetch and
XHR calls from dynamically-loaded scripts still need explicit connect-src entries.
This catches people out.

frame-ancestors 'none': clickjacking protection. Note that this is NOT covered by
default-src and must always be set explicitly.

object-src 'none' and base-uri 'none' are redundant with default-src 'none' but
conventional to include explicitly for clarity.
-->

---

## Start in report-only mode

```
Content-Security-Policy-Report-Only: ...policy...; report-to csp-endpoint
```

```
Reporting-Endpoints: csp-endpoint="https://sentry.io/api/<project>/security/?sentry_key=<key>"
```

- Nothing is blocked — the policy is only observed
- Violations are sent to your reporting endpoint
- Promote to enforcement once reports are clean

Keep `report-uri` alongside `report-to` — Firefox only added `report-to` support in March 2026 (v149).

<!-- TALKING NOTES (slide 8 — ~3 min)
This is the deployment strategy. You never enforce a new CSP on day one.
Deploy report-only, watch the violations, fix them, then enforce.

Sentry works well here and most teams already have it.
The violation report includes: blocked-uri, source-file, script-sample (if you included
'report-sample' in script-src), violated-directive, and the referrer.

The report-uri / report-to compatibility note is worth mentioning — it catches people
who drop report-uri too early.
-->

---

## Violation reports: signal vs. noise

When you turn on reporting, you will see violations from:

1. **Your code** — inline event handlers, forgotten scripts, dynamic injection
2. **Third-party integrations** — consent banners, tag managers, analytics
3. **Browser extensions** — VPNs, anti-virus tools, ad blockers

Category 3 is the most common source of persistent noise.

<!-- TALKING NOTES (slide 9 — ~2 min)
Briefly introduce the three categories. The next slide goes deep on extensions.
Categories 1 and 2 are actionable and that is where you spend most of your time initially.
Category 3 is where most long-term noise comes from.
-->

---

## The extension noise problem

VPN clients, anti-virus products, and ad blockers routinely:

- Inject inline scripts for fingerprinting and tracker detection
- Load fonts and UI assets from external origins
- Make requests to their own backend services

When your CSP blocks these, **the browser sends a violation report.**

What you see in Sentry:
```
blocked-uri: inline
source-file: chrome-extension://...
script-sample: (function() { var _detect = ...
```

**These are not vulnerabilities in your application.**

<!-- TALKING NOTES (slide 10 — ~3 min)
Triage heuristics:
- Violations appearing across many unrelated users and pages = likely extension noise
- Check source-file: chrome-extension:// or moz-extension:// is a strong signal
- script-sample often shows detection/fingerprinting code

You cannot fix these from your side (short of removing your CSP).
The fix is on the extension side — which is the next slide.
-->

---

## What good extension authors do

Privacy Badger (EFF) recently shipped a fix:

1. Read the `Content-Security-Policy` response header in `webRequest.onHeadersReceived`
2. Parse the `script-src` (or `default-src`) directive
3. Handle `'unsafe-inline'`, nonces, hashes, and `'strict-dynamic'`
4. **Skip injection** when the policy would block it

> "If a detection feature can't run on a given page, it simply doesn't run —
> no console error, no violation report."

This is what respectful extension citizenship looks like.

<!-- TALKING NOTES (slide 11 — ~3 min)
Reference the specific commit if you have it:
https://github.com/EFForg/privacybadger/commit/4b42c2eafc2319d1aa2cfe1e4cf36cc0889b12b5

The approach is clean: the extension reads the CSP header (which is available to the
background page via the webRequest API), parses it, and decides per-frame whether
injection is permitted. If not permitted, the feature is silently skipped.

Note the limitation: this works for CSP delivered as a response header. CSP in <meta>
tags is not accessible via the webRequest API and is therefore out of scope.

This is a good example to point extension developers in the audience towards.
-->

---

## Real world: CookieInformation on WordPress

The consent popup ships with inline event handlers throughout its template:

```html
<!-- Before -->
<button id="declineButton" onclick="CookieInformation.declineAllCategories()">
  Decline
</button>
```

A policy without `'unsafe-inline'` **silently breaks all of them**.
Buttons render. Nothing happens when you click.

```html
<!-- After -->
<button id="declineButton">Decline</button>
```
```js
document.getElementById('declineButton')
  .addEventListener('click', () => CookieInformation.declineAllCategories());
```

Also need: `frame-src` and `connect-src` entries for their policy iframe and API.

<!-- TALKING NOTES (slide 12 — ~4 min)
CookieInformation does document this fix — it is in their CSP implementation guide.
But it requires you to edit their template and maintain the changes across updates.

The "silently breaks" part is important. There is no error in the console by default.
The buttons just stop working. You will not catch this in automated testing unless you
have a specific CSP test.

List the extra directives:
  frame-src   'self' https://policy.app.cookieinformation.com/;
  connect-src 'self' https://policy.app.cookieinformation.com/
                     https://consent.app.cookieinformation.com/;

Expect a handful of follow-up fixes as you find edge cases in the live template —
elements that do not exist on every page, dynamically-rendered checkboxes, etc.
-->

---

## Real world: Google Tag Manager and `eval`

GTM's container snippet supports nonces. The container itself is fine.

The problem: **Custom JavaScript Variables use `eval()`.**

```js
// In the compiled GTM container script:
w[g].e = function(s) { return eval(s); };
```

If this line is in your container, you need `'unsafe-eval'` — which defeats CSP for scripts.

**How to check:** open your GTM container URL directly and search for that line.

<!-- TALKING NOTES (slide 13 — ~3 min)
URL pattern: https://www.googletagmanager.com/gtm.js?id=GTM-XXXXXX

The eval wrapper is there because Custom JavaScript Variables are literally evaluated
strings — GTM calls eval() on the function body you typed into the UI.

If you see this line, you have at least one Custom JavaScript Variable and you need
to migrate it before you can remove 'unsafe-eval'.

This is the biggest blocker for GTM users moving to strict CSP.
-->

---

## The GTM fix: Custom Templates

GTM's sandboxed JavaScript environment does not use `eval`.

```js
// Custom JavaScript Variable — breaks under strict CSP
function() {
  return CookieInformation.getConsentGivenFor('cookie_cat_functional');
}
```

```js
// Custom Template — works under strict CSP
const queryPermission = require('queryPermission');
const callInWindow = require('callInWindow');

if (queryPermission('access_globals', 'execute', 'CookieInformation.getConsentGivenFor')) {
  return callInWindow('CookieInformation.getConsentGivenFor', 'cookie_cat_functional');
}
```

Declare `Accesses Global Variables → CookieInformation.getConsentGivenFor (execute)` in the **Permissions** tab.

<!-- TALKING NOTES (slide 14 — ~4 min)
The permissions tab gotcha: permissions are NOT auto-populated when you paste in template
code. You have to add the key manually. If you miss this step, the template silently
returns undefined — easy to miss in testing because the trigger may still fire.

Common replacements for other Custom JavaScript Variables:
  - copyFromWindow  → read a global variable
  - copyFromDataLayer → read from dataLayer
  - getUrl          → get parts of the current URL

Full API reference: https://developers.google.com/tag-platform/tag-manager/templates/sandboxed-javascript

We reported the CookieInformation guide gap to them in November 2025 with a working
template export. As of this talk it has not been updated — you will need to do this
migration yourself.
-->

---

## The unsolved problem: WordPress admin

A strict CSP breaks a large portion of `wp-admin`:

- Block editor relies on inline scripts
- Media library uses `eval`
- Many plugins add their own inline code

Active core tickets: [#59446](https://core.trac.wordpress.org/ticket/59446), [#39941](https://core.trac.wordpress.org/ticket/39941)

**Practical options:**

- Apply strict CSP to the public site only; use a loose policy (or none) for `/wp-admin`
- Allowlist admin scripts by hash — possible, but hashes change on every WordPress update

<!-- TALKING NOTES (slide 15 — ~3 min)
This is the honest "we did not solve everything" slide.

The pragmatic answer is option 1: scope the policy to the public site.
Most of the security value is on the public-facing side anyway — that is where
attacker-controlled input reaches the browser.

If full wp-admin coverage matters to your client, the best thing you can do is
contribute to the core tickets: test patches, review proposed solutions, comment on
stalled issues. Development appears to have stalled as of late 2025. Community involvement
is what moves WordPress core forward.
-->

---

## Recommendations

**If you run a website:**

- Deploy `Content-Security-Policy-Report-Only` today
- Connect it to Sentry (or any reporting endpoint)
- Triage for two weeks, then promote to enforcement
- Use `'strict-dynamic'` with nonces — not domain allowlists

**If you build browser extensions:**

- Read the CSP header in `webRequest.onHeadersReceived`
- Skip inline script injection when the policy disallows it
- Your users' sites will thank you

<!-- TALKING NOTES (slide 16 — ~2 min)
Closing slide — keep it brief and actionable.
The two audiences have very different actions to take.
For site owners: the report-only → enforce pipeline is low risk and immediately valuable.
For extension authors: Privacy Badger's commit is a concrete reference implementation.
-->

---

## Thank you — questions?

Resources:

- [Blog post: Implement Content-Security-Policy](./csp-blog-post/)
- *CSP Is Dead, Long Live CSP!* — Weichselbaum et al., ACM CCS 2016
- Scott Helme's Top 1 Million Analysis, June 2026
- [MDN: Content-Security-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy)
- [GTM Sandboxed JavaScript API reference](https://developers.google.com/tag-platform/tag-manager/templates/sandboxed-javascript)
- [Privacy Badger CSP fix commit](https://github.com/EFForg/privacybadger/commit/4b42c2eafc2319d1aa2cfe1e4cf36cc0889b12b5)
- [WordPress core ticket #39941](https://core.trac.wordpress.org/ticket/39941)

<!-- TALKING NOTES (slide 17 — Q&A)
Likely questions to prepare for:

Q: What about CSP in a <meta> tag instead of a response header?
A: Works for most directives, but frame-ancestors and report-to/report-uri are ignored
   in meta CSP. Always prefer the response header.

Q: Does strict-dynamic break anything?
A: Older browsers (pre-2022 Safari, very old Firefox/Chrome) ignore strict-dynamic and
   fall back to whatever else is in script-src. You can include explicit fallback domains
   in the same script-src for those cases — modern browsers ignore them.

Q: What about Content-Security-Policy-Report-Only vs enforcement — can you run both?
A: Yes. You can send both headers simultaneously — useful for testing a stricter policy
   while keeping a looser enforcement policy in place.

Q: Isn't CSP dead because of browser extensions / user-generated bypass?
A: It reduces the attack surface significantly even if it is not airtight.
   Defense in depth — not a silver bullet.
-->

---

## Time estimate

| Section | Slides | Time |
|---|---|---|
| Hook + data | 1–3 | ~6 min |
| What unsafe-* means | 4–5 | ~5 min |
| The fix (nonces + strict-dynamic) | 6–7 | ~8 min |
| Report-only deployment | 8 | ~3 min |
| Violation noise + extensions | 9–11 | ~8 min |
| Real-world cases (CookieInformation, GTM, WP admin) | 12–15 | ~14 min |
| Recommendations | 16 | ~2 min |
| **Total talk** | | **~46 min** |
| Q&A | | ~10 min |
| **Total with Q&A** | | **~56 min** |

Fits comfortably in a **60-minute slot**. If you need a 45-minute slot, trim the
real-world cases section to one example (GTM is the most novel) and cut the extension
noise slides to one — saves ~10 minutes.

<!-- NOTE: This page is for your planning reference only — remove it before presenting. -->
