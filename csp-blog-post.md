# Implement Content-Security-Policy — and what to expect when you do

At Abtion, we recommend that every web application we build for clients includes a `Content-Security-Policy` (CSP) header. CSP is one of the browser's strongest defences against cross-site scripting (XSS) — a bug class that remains among the most common and damaging on the web. A well-crafted policy tells the browser exactly which scripts, styles, and resources are permitted to load, and blocks everything else.

## Why CSP matters

XSS attacks work by injecting malicious scripts into a trusted page. Without CSP, the browser has no way to distinguish your code from an attacker's. CSP significantly reduces exploitability by restricting which scripts may run — but it is defense-in-depth, not a substitute for proper output encoding, sanitization, and safe DOM APIs.

A modern policy using `'strict-dynamic'` lets you whitelist scripts by nonce or hash, and those trusted scripts can load further scripts dynamically, without opening up entire domains:

```
Content-Security-Policy: script-src 'nonce-{random}' 'strict-dynamic'; object-src 'none'; base-uri 'none'
```

This is considerably stronger than `script-src 'self'`, which still permits any script hosted on your own origin — including ones an attacker could influence.

## Start in report-only mode

Before enforcing a policy, deploy it in observation mode so you can see what it *would* block without breaking anything:

```
Content-Security-Policy-Report-Only: script-src 'nonce-{random}' 'strict-dynamic'; object-src 'none'; base-uri 'none'; report-to csp-endpoint
```

The `report-to` directive names a reporting group you define via the `Reporting-Endpoints` response header:

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

These are not attacks and not your bugs. Filtering them out requires some manual triage: look at whether violations are appearing consistently across many different users and unrelated pages, correlate with the `script-sample`, `source-file`, and `blocked-uri` fields in the report, and be sceptical of anything that appears at high volume with no clear origin in your own codebase.

## What good extension authors do about it

This noise problem is solvable on the extension side. Extensions should check the `Content-Security-Policy` response header before attempting to inject inline scripts, and skip the injection when the policy would block it. If a detection feature can't run on a given page, it simply doesn't run — no console error, no violation report landing in your clients' dashboards.

Privacy Badger, the open-source tracker-blocking extension from the EFF, [recently shipped exactly this](https://github.com/EFForg/privacybadger/commit/4b42c2eafc2319d1aa2cfe1e4cf36cc0889b12b5). Four of its detection features were injecting inline scripts regardless of the page's CSP. The fix reads the `Content-Security-Policy` response header, parses the `script-src` (or `default-src`) directive — handling `'unsafe-inline'`, nonces, hashes, and `'strict-dynamic'` — and skips injection when the policy disallows it. A good example of an extension being a respectful citizen of the pages it runs on. (Note: it handles CSP delivered via response headers; CSP in `<meta>` tags is out of scope for the extension API approach.)

## Recommendations

**For our clients:**

- Deploy CSP. Start with `Content-Security-Policy-Report-Only` to build a baseline, then promote to enforcement.
- Use `'strict-dynamic'` with nonces rather than `'self'` — it is a materially stronger policy.
- Connect reporting to Sentry or similar, and triage regularly. Not every violation is a problem; learning to tell extension noise from genuine issues is part of operating CSP well.

**For extension authors:**

- Read the `Content-Security-Policy` response header in your `webRequest.onHeadersReceived` listener.
- Record whether inline scripts are permitted per frame.
- Gate any `injectScript()` calls behind that check. Your users' sites will thank you.
