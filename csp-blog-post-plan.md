# CSP blog post — remaining work

The main post is `csp-blog-post.md`. All changes should be committed as you go.
See `WRITING_STYLE.md` for tone and conventions.

---

## 🔴 High priority — content gaps

### 1. Nonces never explained
The word "nonce" appears 8 times but is never defined. Add a brief explanation:
- Per-request cryptographically random value, base64-encoded
- Must be injected into both the `script` tag *and* the CSP header on every response
- The `{random}` placeholder in the policy examples should be clarified as exactly this

Also add a short pseudocode/framework example showing how to generate and inject a nonce
(e.g. Rails `SecureRandom.base64(16)`, Node `crypto.randomBytes(16).toString('base64')`).

### 2. GTM nonce setup not shown
The post says "GTM's container snippet accepts a `nonce` attribute" but never shows how.
Find the official GTM docs for passing a nonce to the container snippet and add a concrete
example. This is typically the first thing a reader needs to do before worrying about
Custom Templates.
- Docs: https://developers.google.com/tag-platform/security/guides/csp

### 3. CookieInformation template export not offered ✅ Done
Added an inline reference to [working template export](./cookie_cat_functional_template.tpl)
in `csp-blog-post.md`, plus links to the live CookieInformation guide and a Web Archive snapshot.

---

## 🟡 Medium priority — accuracy / completeness

### 4. Extension API — verify Manifest V3 compatibility ✅ Done
Updated `csp-blog-post.md` to clarify MV3 behaviour: `webRequest.onHeadersReceived`
still works for passive response-header inspection in the extension-author guidance.

### 5. Connect `'report-sample'` to the `script-sample` field
The monitoring section tells readers to look at the `script-sample` field in violation reports,
but does not explain that `'report-sample'` in the policy is what populates it.
Add a one-sentence link between the two.

### 6. Explain *why* domain allowlists are weak
The post says allowlists "leave you exposed to any script hosted on those domains" without
explaining why that matters in practice. Add a concrete example:
- A CDN that hosts user-uploaded content
- An analytics provider with a JSONP endpoint (e.g. `?callback=alert(1)`)
This sharpens the argument for preferring `'strict-dynamic'` over allowlists.

---

## 🟢 Lower priority — polish

### 7. Sharpen the title
Current: "Implement Content-Security-Policy — and what to expect when you do"
This undersells the `unsafe-*` → `strict-dynamic` angle that now frames the post.
Consider something that signals the payoff more directly.

### 8. Weak transition at line 20
"A policy that gets you there:" — find a stronger lead-in.

### 9. GTM Custom Template Code tab screenshot
The GTM Permissions tab screenshot is in the post. A screenshot of the Code tab
(showing the `callInWindow` + `queryPermission` template code) would complete the picture.
Not critical but was mentioned as desirable earlier.

---

## Git log (most recent first, as of 30 June 2026)

```
7cb7b9c  Promote strict-dynamic origin and browser support timeline into intro
0652e42  Soften comparison between 2016 Google study and 2026 Helme crawl (different methodologies)
171e246  Replace 2016 stats with Scott Helme June 2026 top-1M crawl data
f68a6dc  Add 2026 Turkish domain study as corroborating evidence for CSP misconfig prevalence
eadc084  Acknowledge 2016 data age; no more recent study available
f6d1940  Update csp-stats footnote to link directly to full PDF
f4c946d  Cite original source: Weichselbaum et al. CCS 2016
f9b4a3f  Reframe post around unsafe-* prevalence and strict-dynamic payoff
a425e74  Encourage contributing to wp-admin CSP tickets, not just watching
712e3fe  Update wp-admin CSP status: development stalled late 2025
7e1a4e4  Add WordPress admin CSP caveat
b14b40f  Add diagnostic tip for spotting eval in GTM container
a04b14a  Add GTM Permissions tab screenshot and silent-undefined gotcha
89d6eb9  Use real CookieInformation GTM template as concrete example
73f711a  Add real-world WordPress implementation section
5e9a32c  Apply review feedback on precision and examples
9abd203  Add browser support footnotes for strict-dynamic and report-to
2037e97  Add writing style guide
```
