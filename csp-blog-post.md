# Implement Content-Security-Policy — and what to expect when you do

At Abtion, we recommend that web application we build for clients includes a `Content-Security-Policy` (CSP) header. CSP is one of the browser's strongest defences against cross-site scripting (XSS) — a bug class that remains common and damaging on the web. A well-crafted policy tells the browser exactly which scripts, styles, and resources are permitted to load, and blocks everything else.

## Why CSP matters

XSS attacks work by injecting malicious scripts into a trusted page. Without CSP, the browser has no way to distinguish your code from an attacker's. CSP significantly reduces exploitability by restricting which scripts may run — but it is defense-in-depth, not a substitute for proper output encoding, sanitization, and safe DOM APIs.

A modern policy using `'strict-dynamic'`[^strict-dynamic] lets you whitelist scripts by nonce or hash, and those trusted scripts can load further scripts dynamically, without opening up entire domains:

```
Content-Security-Policy: default-src 'none'; script-src 'nonce-{random}' 'strict-dynamic' 'report-sample'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'
```

`default-src 'none'` is the foundation: every resource type is blocked unless explicitly permitted. The remaining directives carve out only what a typical app needs. A few things worth noting:

- `'strict-dynamic'` only propagates trust for *script loading* — it has no effect on `connect-src`. Scripts (including dynamically-loaded ones) can only make `fetch()` and XHR calls to your own origin unless you extend `connect-src` with specific third-party API origins.
- `style-src 'unsafe-inline'` is a common addition when frameworks inject inline styles; accept it as a known trade-off if needed.
- `frame-ancestors 'none'` is not covered by `default-src` and must always be set explicitly — it provides clickjacking protection.
- `object-src 'none'` and `base-uri 'none'` are technically redundant with `default-src 'none'`, but keeping them explicit is a common convention for clarity.

This is considerably stronger than `script-src 'self'`, which still permits any script hosted on your own origin — including ones an attacker could influence.

## Start in report-only mode

Before enforcing a policy, deploy it in observation mode so you can see what it *would* block without breaking anything:

```
Content-Security-Policy-Report-Only: default-src 'none'; script-src 'nonce-{random}' 'strict-dynamic' 'report-sample'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; report-to csp-endpoint
```

The `report-to`[^report-to] directive names a reporting group you define via the `Reporting-Endpoints` response header:

```
Reporting-Endpoints: csp-endpoint="https://sentry.io/api/<project>/security/?sentry_key=<key>"
```

The older `report-uri` directive still works and has wider browser support — worth keeping both while `report-to` adoption matures.

Once your violation reports reflect only intentional usage, you can promote the header to enforcement.

## Monitor your violations — but expect noise

Connecting CSP reporting to Sentry (or a similar platform) gives you visibility into violations as they happen. Many violations will be actionable: misconfigured third-party integrations, forgotten inline event handlers, legacy scripts that need nonces.

**But a significant share will be noise from your users' browser extensions.**

VPN clients, anti-virus products, and ad blockers routinely inject inline scripts into pages as part of their normal operation — fingerprinting detection, tracker blocking, ad replacement. When your CSP blocks those injections, the browser sends a violation report.

In practice you'll see things like:

- `blocked 'script' from 'inline'` — an extension tried to inject an inline script
- `blocked 'connect' from 'various domains'` — an extension is making requests to its own backend
- `blocked 'font' from 'various domains'` — an extension injected UI that loads fonts from external origins

These are often not vulnerabilities in your app and are frequently not actionable for the site owner. Filtering them out requires some manual triage: look at whether violations are appearing consistently across many different users and unrelated pages, correlate with the `script-sample`, `source-file`, and `blocked-uri` fields in the report, and be sceptical of anything that appears at high volume with no clear origin in your own codebase.

## What good extension authors do about it

This noise problem is solvable on the extension side. Extensions that inject inline scripts or page-context DOM resources should check the `Content-Security-Policy` response header before attempting those injections, and skip them when the policy would block it. If a detection feature can't run on a given page, it simply doesn't run — no console error, no violation report landing in your clients' dashboards.

Privacy Badger, the open-source tracker-blocking extension from the EFF, [recently shipped exactly this](https://github.com/EFForg/privacybadger/commit/4b42c2eafc2319d1aa2cfe1e4cf36cc0889b12b5). Four of its detection features were injecting inline scripts regardless of the page's CSP. The fix reads the `Content-Security-Policy` response header, parses the `script-src` (or `default-src`) directive — handling `'unsafe-inline'`, nonces, hashes, and `'strict-dynamic'` — and skips injection when the policy disallows it. A good example of an extension being a respectful citizen of the pages it runs on. (Note: it handles CSP delivered via response headers; CSP in `<meta>` tags is out of scope for the extension API approach.)

## A real-world example: WordPress with CookieInformation and GTM

Here is what we ran into implementing CSP on a WordPress project.

### CookieInformation

The CookieInformation consent popup ships with inline event handlers throughout its template HTML — `onclick="CookieInformation.declineAllCategories()"`, `href="javascript:CookieConsent.renew();"`, and so on. A policy without `'unsafe-inline'` blocks all of these silently, leaving a banner with buttons that do nothing.

[CookieInformation documents the fix](https://support.cookieinformation.com/articles/customization/consent-popup/csp-implementation/): strip the inline handlers from the template and wire the same behaviour up using `addEventListener` in your own external script. In practice it looked like this — before:

```html
<button id="declineButton" onclick="CookieInformation.declineAllCategories()">
  Decline
</button>
```

After:

```html
<button id="declineButton">Decline</button>
```

```js
document.getElementById('declineButton')
  .addEventListener('click', () => CookieInformation.declineAllCategories());
```

Every button and anchor with an inline handler needed the same treatment. Expect a handful of follow-up fixes as you discover edge cases in the live template — elements that don't exist on every page, category checkboxes that render dynamically, and so on.

You also need to add two extra directives to allow the popup to load its policy iframe and contact its API:

```
frame-src   'self' https://policy.app.cookieinformation.com/;
connect-src 'self' https://policy.app.cookieinformation.com/
                   https://consent.app.cookieinformation.com/;
```

### Google Tag Manager

GTM's container snippet accepts a `nonce` attribute and propagates it to any scripts it injects, so the container itself plays nicely with a nonce-based policy. The problem is **Custom JavaScript Variables**.

GTM evaluates Custom JavaScript Variables using `eval()`. CSP blocks `eval()` unless `'unsafe-eval'` is present in `script-src` — and adding `'unsafe-eval'` largely defeats the point of having CSP in the first place.

The [GTM documentation](https://developers.google.com/tag-platform/security/guides/csp#custom_javascript_variables) mentions the problem but is sparse on how to fix it. The answer is to replace Custom JavaScript Variables with **Custom Templates**, which run in GTM's sandboxed JavaScript environment and do not require `eval`.

A Custom JavaScript Variable that reads a value from `window` might look like this:

```js
// Custom JavaScript Variable — breaks under CSP
function() {
  return window.pageData && window.pageData.userId;
}
```

The Custom Template equivalent:

```js
// Custom Template — works under CSP
const copyFromWindow = require('copyFromWindow');
const pageData = copyFromWindow('pageData');
return pageData ? pageData.userId : undefined;
```

In the template's **Permissions** tab, add an `Accesses Global Variables` permission for `pageData` with read access. GTM will not execute the template without a matching permission declaration.

The migration is mechanical but requires going through each Custom JavaScript Variable in the container and rewriting it using the [sandboxed JavaScript APIs](https://developers.google.com/tag-platform/tag-manager/templates/sandboxed-javascript). Common replacements: `copyFromWindow` for globals, `copyFromDataLayer` for dataLayer reads, `getUrl` for URL parts, and `require('dom')` (with a declared permission) for DOM access.

## Recommendations

**For our clients:**

- Deploy CSP. Start with `Content-Security-Policy-Report-Only` to build a baseline, then promote to enforcement.
- Use `'strict-dynamic'` with nonces rather than `'self'` — it is a materially stronger policy.
- Connect reporting to Sentry or similar, and triage regularly. Not every violation is a problem; learning to tell extension noise from genuine issues is part of operating CSP well.

**For extension authors:**

- Read the `Content-Security-Policy` response header in your `webRequest.onHeadersReceived` listener.
- Record whether inline scripts and page-context DOM injections are permitted per frame.
- Gate any `injectScript()` calls behind that check. Your users' sites will thank you.

---

[^strict-dynamic]: `'strict-dynamic'` is [well-supported across modern browsers](https://caniuse.com/?search=strict-dynamic). If you need to support older browsers, you can still include explicit fallback source expressions in the same `script-src` directive — modern browsers that understand `'strict-dynamic'` will ignore those fallbacks, while older browsers will use them.

[^report-to]: `report-to` reached broad browser support around 2022, with Firefox adding support in version 149 (March 2026). See [caniuse](https://caniuse.com/mdn-http_headers_content-security-policy_report-to). This is why keeping `report-uri` alongside `report-to` remains worthwhile in the interim.
