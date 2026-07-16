---
marp: true
theme: default
paginate: true
---

# Stop Injected JavaScript with CSP: Defense in Depth That Works

**BornHack 2026**

<!-- TALKING NOTES (slide 1 — ~1 min)
Introduce yourself. One sentence on where you work and what you do.
Mention that the talk is rooted in a real implementation project you worked on recently —
not a theoretical walkthrough, but a post-mortem of what actually went wrong and how you fixed it.
Estimated talk length: ~35–40 minutes + Q&A.
-->

---

## Quick show of hands

- Who has made a webapp / website?
- Who has configured `Content-Security-Policy`?
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

June 2026 (Tranco Top 1 Million crawl):

- 170,057 sites have a `Content-Security-Policy` header
- **125469 (73.8%)** no script restriction at all, or `'unsafe-inline'` still allowed
- **2221 (1.3%)** Host/scheme allowlist or 'self' only (no nonce / hashes)
- **38882 + 727 (23%)** use a nonce / hash ()
- **2569 (1.5%)** use `'strict-dynamic'`
- **189 (0.1%)** use 'none' (blocks all scripts)

And **41.9%** still include `'unsafe-eval'`

<!-- TALKING NOTES (slide 3 — ~3 min)
73.8% of sites with a CSP header would not stop an injected `<script>` tag from running.
So roughly a quarter of "CSP" sites actually restrict what scripts can run.
Only 1.5% use strict-dynamic. These figures come from our own directive-level
re-parse of the same 13 June 2026 crawl data Helme's report is built on (script-src-elem takes
precedence over script-src per CSP3, though only 2.05% of sites set it).
The 2016 paper ("CSP Is Dead, Long Live CSP!") proposed strict-dynamic as the fix.
It has had broad browser support since March 2022 — Safari was the last holdout.
Use the 2016 figures only to frame adoption rate: a decade after the fix was proposed,
uptake is essentially flat.
The two bullets at the bottom are the spine of the whole talk: the secure path is hard
because frameworks/tools do not default to it, and the reports you rely on are noisy
because extensions inject without checking CSP. Everything that follows is about fixing
those two things — for site owners now, and for tool/extension authors going forward.
Keep this punchy. The numbers do the work.
-->

---

## CSP

Some things keeping it stuck:

- **Tools and frameworks** still default to no CSP
- * Webflow does not support it
- * Wordpress does not support it in the admin interface
- * Ruby On Rails supports it, but not enabled by default
- **Extension noise** buries the real violations in your reports
- Some **Libraries and plugins** still do not support nonces

<!-- TALKING NOTES (slide 4 — ~3 min)
This slide previews the three threads the rest of the talk picks up. Webflow has no CSP
support at all. WordPress does not support CSP in the wp-admin interface — covered in
depth later in the WordPress admin slide. Rails ships strict-dynamic + nonce support via
a few lines of config; it's the model other frameworks should follow, contrast with
WordPress later. Extension noise burying real violations gets its own deep dive near the
end of the talk. Keep this slide brief — it's a signpost, not the payload.
-->

---

## What `'unsafe-inline'` means

```
Content-Security-Policy: script-src 'self' 'unsafe-inline'
```

This tells the browser:

> "Execute any script that appears inline on the page."

That includes the ones *an attacker injected*.

- Reflected XSS payload in a query parameter? Executes.
- Stored XSS in a comment field? Executes.
- Supply-chain compromise injecting a `<script>` tag? Executes.

**CSP with `'unsafe-inline'` does not stop XSS.**

<!-- TALKING NOTES (slide 5 — ~3 min)
Be concrete. The audience will know what XSS is — skip the primer.
The point is that 'unsafe-inline' specifically neutralises the one thing script-src is
there to do: prevent unauthorised script execution.
Domain allowlists (e.g. 'self', CDN domains) are marginally better — they stop some
injection vectors — but they still leave you exposed to any script hosted on those domains,
including ones an attacker could place there.
-->

---

## `'unsafe-eval'` is a similar problem

```js
eval(userControlledString)   // classic
new Function(userInput)()    // same thing
setTimeout(attackerPayload)  // also counts
```

`'unsafe-eval'` permits all of these.

Removing `'unsafe-eval'`, makes it even harder to exploit injections.

<!-- TALKING NOTES (slide 6 — ~2 min)
This presentation is mostly about unsafe-inline, but I will touch on unsafe-eval with respect to Google Tag Manager later.
-->

---

## CSP without `'unsafe-inline'` can be hard

External libraries and services often load extra scripts, either from a cdn or
inject inline script tags and it can be hard to get them to change.

Extra scripts loaded from a URL can be handled with allowlists, nonces, and hashes but it is hard.

And allowlisting a whole cdn domain is problematic.

Injected inline scripts won't work.

<!-- TALKING NOTES (slide 7 — ~2 min)
Transition slide: without 'unsafe-inline' you have to account for every script your page
loads, including ones injected by third-party libraries you do not control.
Allowlisting an entire CDN domain is weak — it trusts everything hosted there, including
anything an attacker could place on that same domain. That is the allowlist weakness the
2016 paper called out.
Injected inline scripts are the hard failure case: no allowlist entry saves you there —
only 'unsafe-inline' or a matching nonce/hash would, and you do not want to grant either
broadly. This pain is exactly why 'strict-dynamic' exists — next slide.
-->

---

## The fix `'strict-dynamic'`

The fix has been ready for years. A 2016 Google Research study proposed `'strict-dynamic'` —
and it has had broad browser support since March 2022

<!-- TALKING NOTES (slide 8 — ~1 min)
Emphasize the timeline: proposed in 2016, universally supported since Safari added it in
March 2022. That is four years of full browser support with adoption still stuck around
1.5%. Keep this slide short and punchy — let the timeline speak, then move to what
strict-dynamic actually does.
-->

---

## `'strict-dynamic'`

Makes it easier to remove `'unsafe-inline'`, because trust propagates,
so injected scripts are allowed, if they are injected by trusted scripts.

However, disables use of URI allowlists (and 'unsafe-inline').

<!-- TALKING NOTES (slide 9 — ~2 min)
Core mechanic: trust propagates transitively from your nonced entry-point scripts to
whatever they load. Flag the trade-off immediately: strict-dynamic disables host/scheme
allowlists in script-src (and unsafe-inline) — browsers that understand strict-dynamic
ignore those other source expressions entirely. That is intentional: it is what closes
the allowlist weakness from the earlier slide. The next slide shows the nonce mechanics
that make this work in practice.
-->

---

## hashes / nonces + `'strict-dynamic'`

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

<!-- TALKING NOTES (slide 10 — ~4 min)
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

<!-- TALKING NOTES (slide 11 — ~4 min)
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

## Real world: CookieInformation

The consent popup ships with inline event handlers throughout its template:

```html
 <button tabindex="1" aria-label="renew consent" title="renew consent" id="Coi-Renew" onclick="javascript:CookieConsent.renew();">
```

Without `'unsafe-inline'`: Buttons render. Nothing happens when you click.

### Fix (mentioned in their CSP guide)

```html
<button tabindex="1" aria-label="renew consent" title="renew consent" id="Coi-Renew">
```
```js
   document.getElementById("Coi-Renew").addEventListener('click', function() {
       CookieConsent.renew();
   });
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

## Real world: Google Tag Manager and nonces

GTM's nonce-aware container snippet supports passing on nonces (only necessary if you use nonces without 'strict-dynamic').

The default snippet from GTM UI does not.

<!-- TALKING NOTES (slide 13 — ~2 min)
URL pattern: https://www.googletagmanager.com/gtm.js?id=GTM-XXXXXX

Call out that you need the official nonce-aware snippet from the GTM CSP docs:
  - `nonce="..."` on the inline bootstrap script
  - nonce propagation to dynamically injected `gtm.js`

-->

---

## Reak world: Google Tag Manager and  `eval`

The problem: **Custom JavaScript Variables use `eval()`.**

```js
// In the compiled GTM container script:
w[g].e = function(s) { return eval(s); };
```

If this line is in your container, you need `'unsafe-eval'` — which is another open door to string-to-code injection (classic `eval`/`Function` payloads),
even though `script-src`'s `'strict-dynamic'`/nonce protection against injected `<script>` tags is untouched.

**How to check:** open your GTM container URL directly and search for that line (https://www.googletagmanager.com/gtm.js?id=GTM-XXXXXX).

<!-- TALKING NOTES (slide 14 — ~3 min)
The eval wrapper is there because Custom JavaScript Variables are literally evaluated
strings — GTM calls eval() on the function body you typed into the UI.

If you see this line, you have at least one Custom JavaScript Variable and you need
to migrate it before you can remove 'unsafe-eval'.

Important nuance: this is NOT a blocker for adopting 'strict-dynamic'. strict-dynamic and
'unsafe-eval' are orthogonal — strict-dynamic governs which <script> tags/dynamically
created scripts are trusted, while 'unsafe-eval' governs whether string-to-code execution
(eval, new Function, etc.) is allowed. You can ship
`script-src 'nonce-xxx' 'strict-dynamic' 'unsafe-eval'` today and still get the full
strict-dynamic benefit against injected <script> tags.
This is the biggest blocker for GTM users dropping 'unsafe-eval' — i.e. reaching the fully
hardened policy that also closes the eval-injection gap, not for adopting strict-dynamic
itself.
-->

---

## The GTM fix: Custom Templates

GTM's sandboxed JavaScript environment does not use `eval`.

```js
// Custom JavaScript Variable — breaks without 'unsafe-eval'
function() {
  return CookieInformation.getConsentGivenFor('cookie_cat_functional');
}
```

```js
// Custom Template — works
const queryPermission = require('queryPermission');
const callInWindow = require('callInWindow');

if (queryPermission('access_globals', 'execute', 'CookieInformation.getConsentGivenFor')) {
  return callInWindow('CookieInformation.getConsentGivenFor', 'cookie_cat_functional');
}
```

Declare `Accesses Global Variables → CookieInformation.getConsentGivenFor (execute)` in the **Permissions** tab.

<!-- TALKING NOTES (slide 15 — ~4 min)
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

- Many places does not use the helper function for adding inline scripts
- Media library uses `eval`
- Many plugins add their own inline code

Active core tickets: [#59446](https://core.trac.wordpress.org/ticket/59446), [#39941](https://core.trac.wordpress.org/ticket/39941)

**Practical options:**

- Apply strict CSP to the public site only; use a loose policy (or none) for `/wp-admin`
- Some scripts contain db data, so they cannot be allowlisted with hashes

<!-- TALKING NOTES (slide 16 — ~3 min)
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
- Grade the result with [Mozilla's HTTP Observatory](https://developer.mozilla.org/en-US/observatory)

Keep `report-uri` alongside `report-to` — Firefox only added `report-to` support in March 2026 (v149).

<!-- TALKING NOTES (slide 17 — ~3 min)
This is the deployment strategy. You never enforce a new CSP on day one.
Deploy report-only, watch the violations, fix them, then enforce.

Sentry works well here and most teams already have it.
The violation report includes: blocked-uri, source-file, script-sample (if you included
'report-sample' in script-src), violated-directive, and the referrer.

Mozilla's HTTP Observatory is also worth a mention here — it scans a live URL and grades
its security headers, flagging 'unsafe-inline' as a finding. Public grading tools like this
are a big part of what drives the compliance pressure that gets teams to bother with CSP at
all: a failing grade in a security questionnaire or pen-test report is often the trigger.

The report-uri / report-to compatibility note is worth mentioning — it catches people
who drop report-uri too early.
-->

---

## Violation reports: signal vs. noise

CSP is **defence-in-depth** — it does not stop injection, it stops injected
scripts from *executing*. So a `script-src` violation can be your best signal:
**an attacker's injection that got past sanitization and CSP caught on the way out.**

To be useful, your reports should surface exactly those — real sanitization
failures in the app you are protecting.

<!-- TALKING NOTES (slide 18 — ~1 min)
Lead with the security framing: the whole reason to watch the report stream is that a
blocked inline script might be a failed XSS attempt — evidence that something got past
your output encoding and CSP stopped it on the way out. That is the signal worth
protecting, and it is the frame for the categories on the next slide.
-->

---

## Voilation reports: Signal vs. Noise

When you turn on reporting, you will see violations from:

1. **Your code** — inline event handlers, forgotten scripts, dynamic injection
2. **Third-party integrations** — consent banners, tag managers, analytics

and noise from

3. **Browser extensions** — VPNs, anti-virus tools, ad blockers

Category 3 is the most common source of persistent noise — and it **hides the
attacker attempts** you actually want to see.

<!-- TALKING NOTES (slide 19 — ~2 min)
Introduce the three categories of violation source. Categories 1 and 2 (your own code,
third-party integrations) are actionable and that is where you spend most of your time
initially. Category 3 (browser extensions) is where most long-term noise comes from —
and it does real harm by burying genuine attack attempts, not just by being untidy.
The next slide goes deep on extensions.
-->

---

## The extension noise problem

VPN clients, anti-virus products, and ad blockers routinely:

- Inject inline scripts for fingerprinting and tracker detection
- Load fonts and UI assets from external origins
- Make requests to their own backend services

When your CSP blocks these, **the browser sends a violation report.**

Example of what you might see in Sentry:
```
Blocked 'frame-src' from 'pwm-image.trendmicro.com'
```

**These are not vulnerabilities in your application — but they bury the ones that are.**

<!-- TALKING NOTES (slide 20 — ~3 min)
Triage heuristics:
- Violations appearing across many unrelated users and pages = likely extension noise
- Check source-file: chrome-extension:// or moz-extension:// is a strong signal
- script-sample often shows detection/fingerprinting code

The cost is not just triage time: every extension report in the pile makes it more
likely you miss a real attacker attempt. That is the defence-in-depth value leaking away.

You cannot fix these from your side (short of removing your CSP).
The fix is on the extension side — which is the next slide.
-->

---

## Respecting the page's CSP

I opened a PR against Privacy Badger (EFF) to do exactly this:

1. Read the `Content-Security-Policy` response header in `onHeadersReceived`
2. Parse `script-src` etc. (falling back to `default-src`)
3. Handle `'unsafe-inline'`, nonces, hashes, `'strict-dynamic'`, and multiple headers
4. **Skip injection** when the policy would block it
5. Alternatively, alter the header to allow your addition

<!-- TALKING NOTES (slide 21 — ~3 min)
This is our own contribution — Privacy Badger PR #3200 ("Skip injectScript() on
CSP-restricted pages"): https://github.com/EFForg/privacybadger/pull/3200
It gates four feature detectors (fingerprinting, supercookies, script-clobbering check,
and DNT verification) that previously called injectScript() regardless of the page CSP.

The approach is clean: the extension reads the CSP header (which is available to the
background page via the webRequest API), parses it, and decides per-frame whether
injection is permitted. If not permitted, the feature is silently skipped.

Note the limitation: this works for CSP delivered as a response header. CSP in <meta>
tags is not accessible via the webRequest API and is therefore out of scope.

This is a good example to point extension developers in the audience towards.
-->

---

## Recommendations

**If you run a website:**

- Deploy `Content-Security-Policy-Report-Only` today
- Connect it to Sentry (or any reporting endpoint)
- Triage for two weeks, then promote to enforcement
- Use `'strict-dynamic'` with nonces — not domain allowlists

<!-- TALKING NOTES (slide 22 — ~1 min)
First of three closing recommendation slides — keep each brief and actionable. Three
audiences, three different actions, mapping straight back to the two levers from the
numbers slide. For site owners: the report-only → enforce pipeline is low risk and
immediately valuable.
-->

---

## Recommendations

**If you build frameworks or tools:**

- Make `'strict-dynamic'` + a per-request nonce the **default**, not an opt-in recipe
- Drop inline handlers and `eval` features — ship a CSP-compatible path instead
- Treat "works under a nonce-based policy" as a support requirement

<!-- TALKING NOTES (slide 23 — ~1 min)
Every default that assumes 'unsafe-inline' is a tax on every site that integrates it.
Adonis Shield and Rails are good examples of getting this right — a few lines of config
away from a fully nonce-based strict-dynamic policy.
-->

---

## Recommendations

**If you build browser extensions:**

- Read the CSP header in `webRequest.onHeadersReceived`
- Skip injections when the policy disallows it
- Or, controversially add to the CSP header

<!-- TALKING NOTES (slide 24 — ~1 min)
Closing recommendation slide. Privacy Badger's commit (PR #3200) is a concrete reference
implementation for extension authors: read the CSP header in
webRequest.onHeadersReceived, skip injections when the policy disallows it. The
alternative — controversially adding to the CSP header instead of skipping — is more
invasive but worth a one-line mention.
-->

---

## Thank you — questions?

Resources:

- [Blog post: Implement Content-Security-Policy](./csp-blog-post/)
- *CSP Is Dead, Long Live CSP!* — Weichselbaum et al., ACM CCS 2016
- Scott Helme's Top 1 Million Analysis, June 2026
- [MDN: Content-Security-Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Security-Policy)
- [GTM Sandboxed JavaScript API reference](https://developers.google.com/tag-platform/tag-manager/templates/sandboxed-javascript)
- [Privacy Badger CSP fix PR #3200](https://github.com/EFForg/privacybadger/pull/3200)
- [WordPress core ticket #39941](https://core.trac.wordpress.org/ticket/39941)

<!-- TALKING NOTES (slide 25 — Q&A)
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
| Why adoption is stuck + unsafe-* costs | 4–7 | ~10 min |
| The fix (strict-dynamic + nonces) | 8–11 | ~10 min |
| Real-world cases (CookieInformation, GTM, WP admin) | 12–16 | ~16 min |
| Report-only deployment | 17 | ~3 min |
| Violation noise + extensions | 18–21 | ~9 min |
| Recommendations | 22–24 | ~3 min |
| **Total talk** | | **~57 min** |
| Q&A | | ~10 min |
| **Total with Q&A** | | **~67 min** |

Fits comfortably in a **60–75 minute slot**. If you only have 60 minutes, trim the
real-world cases section to one example (GTM is the most novel) — saves ~10 minutes.
For a 45-minute slot, additionally cut the WordPress admin slide and merge the three
recommendation slides back into one — saves another ~5 minutes.

<!-- NOTE: This page is for your planning reference only — remove it before presenting. -->
