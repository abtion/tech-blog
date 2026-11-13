---
layout: default
title: "npm overrides: when to reach for them — and when to leave them alone"
permalink: /npm-overrides/
---

# The green-alert temptation

Dependabot flags a vulnerable transitive dependency.
You run `npm update`, and nothing changes: the package that pulls it in still asks for the old major, and no release of that parent accepts the fix yet.

npm has a field for exactly this.
A few lines of `overrides` in `package.json`, a fresh lockfile, and the alert turns green:

```json
"overrides": {
  "glob@>=9": "^14.0.3",
  "minimatch@>=7": "^11.0.1"
}
```

It works, and it is often the wrong tool.
**An override closes the alert by changing what the lockfile says. Whether it fixes the vulnerability, and what it breaks along the way, are separate questions** — and the answers are frequently "no" and "more than you think".

This post covers what an override really does, the problems we have run into with them, and the narrower set of cases where they are the right call.

## What `overrides` actually does

`overrides`[^npm-overrides] tells npm to replace the version of a package anywhere in the dependency tree, regardless of the range the depending package asked for.
It comes in three shapes:

```json
"overrides": {
  "pkg": "^2.0.0",
  "pkg@>=1 <1.4.2": "^1.4.2",
  "some-parent": { "pkg": "^2.0.0" }
}
```

- **A bare name** replaces every copy of `pkg`.
- **A name with a range** replaces only the copies whose requested range matches the key.
- **A nested object** replaces `pkg` only below `some-parent`.

Only the root `package.json` counts — overrides in dependencies' manifests are ignored.
Yarn calls the same idea `resolutions` and pnpm uses `pnpm.overrides`; the problems below apply to all of them.

## Problem 1: the alert closes, the vulnerability may not

Dependabot reads the lockfile.
If the lockfile no longer contains a vulnerable version, the alert closes — whether or not vulnerable code still runs.

We hit this with a queue dashboard package that declared an old, vulnerable major of a validation library as a dependency.
On closer inspection the package **never imported it**: it shipped its own bundled copy of the library inside its build.
Overriding the dependency to the patched major removed an unused package from `node_modules` and closed a _high_ alert — while the bundled, vulnerable copy kept running exactly as before.

Before you override, find out **how** the vulnerable package is used.
`npm explain <pkg>` shows who pulls it in; a quick look at the parent's published files shows whether it imports the package or bundles its own.

## Problem 2: open-ended keys catch future majors

This one is subtle.
npm decides whether an override applies by checking whether the key's range **intersects** the range the depending package asks for[^arborist] — not whether it matches the version that would otherwise be installed.

So a key like `glob@>=9` does not mean "the vulnerable versions of glob".
It means "every dependent whose range overlaps `>=9`" — **which includes a future `^15`**.
The day your test runner or linter moves on to glob 15, npm quietly forces it back to 14.

We reproduced this one major lower, with npm 11.19.1, so the versions already exist.
One package depends on `minimatch ^10`:

```json
"overrides": { "minimatch@>=7": "^9.0.5" }
```

| Override key | minimatch installed for the `^10` dependent |
| --- | --- |
| `minimatch@>=7` | **9.0.9** — forced down a major |
| `minimatch@>=7 <9.0.5` | 10.2.6 — left alone |

`npm ls minimatch` reports the forced 9.0.9 without any warning, and exits 0.
Nothing in CI tells you a package is now running on a major it does not support.

**Bound the key to the vulnerable range from the advisory** — `"minimatch@>=7 <11.0.1"`, not `"minimatch@>=7"`.
It still matches every range that can resolve to a vulnerable version, and it stops matching once the ecosystem moves past it.

## Problem 3: you break the parent's contract

A dependency range is a statement from the package's maintainers: _we have tested with this_.
An override that crosses a major boundary throws that statement away.
Linters, test runners and code generators are the usual victims — exactly the tools whose subtle misbehaviour is easy to miss, because nobody writes tests for the linter.

You can check thoroughly today — run the full suite, compare the linter's resolved rules file by file — and that is worth doing.
But **nobody repeats that check** when the parent is upgraded next month, and the override is still forcing the same version under it.

## Problem 4: overrides never expire

Once the alert is green, nothing reminds you that the override exists.
Dependabot will not tell you when the parent finally accepts the fix, and nothing fails when the reason for the override disappears.

Overrides accumulate.
It is common to find a mature project with a dozen or more, most without a note saying why they were added or when they can go — and every one of them is a version decision taken away from the package maintainers and from `npm update`.

## What to do instead

Work through these in order.
Most alerts are resolved before step 5.

1. **Update the parent.**
   `npm update <vulnerable-pkg>` updates a transitive dependency within the ranges its parents allow — often all it takes.
   If the parent's range is the blocker, check for a newer release of the parent and upgrade that.

2. **Check upstream — and help move it along.**
   Search the parent's issues and pull requests for the vulnerable package or the advisory ID.
   Someone has often already asked, and a pull request widening the range may be waiting for review.
   - **If there is a pull request**, run your test suite against it and report the result on the pull request — a maintainer is far more likely to merge a change that users have confirmed works.
     Add a 👍 reaction instead of a "+1" comment.
   - **If there is only an issue**, consider opening the pull request yourself.
     Widening a dependency range is frequently a one-line change plus a test run.
   - **If there is nothing**, open an issue that names the advisory, the parent's current range and the first fixed version.
   - **If it has stalled**, a short, polite question about what is blocking it often helps more than another report.

   Link whatever you find or open next to the alert.
   It tells you when to revisit, and it is the removal condition if you do end up overriding.

3. **Check whether the vulnerable code is reachable.**
   Many advisories in packages like `glob`, `minimatch` or `brace-expansion` need an attacker to control a glob pattern.
   If the only callers are your linter, test runner and bundler, running on patterns you wrote, the risk is close to zero.
   Dismiss the alert with a reason — GitHub offers _tolerable risk_ and _vulnerable code is not actually used_ — and write down what you are waiting for.

4. **Shrink what reaches production.**
   Move build-only tools to `devDependencies`, so `npm ci --omit=dev` keeps them out of the production image.
   Look for packages that end up in production only because a library lists a build tool under `dependencies` — a one-line pull request upstream often fixes that for everyone.
   Peers are less straightforward: npm still installs a package under `--omit=dev` when it is one of your `devDependencies` _and_ an optional peer of a production dependency.[^dev-optional]

5. **Override, deliberately, if none of the above works.**

## When an override is the right call

Overrides are a legitimate tool.
Use one when the situation genuinely calls for it:

- **A reachable runtime vulnerability, with no fixed parent release.**
  If attacker-controlled input can reach the vulnerable code in production, waiting for upstream is often not acceptable.
- **A patch release blocked by an exact pin.**
  A parent that pins an exact version — `"pkg": "1.2.3"` — also blocks the `1.2.4` that fixes the vulnerability.
  Overriding to `1.2.4` still steps outside what the parent declared, so run its tests against the new version — but a patch release is meant to be compatible, so the risk is far smaller than when crossing a major.
- **Deduplicating a package that must be a singleton.**
  Libraries such as React or `graphql` break in confusing ways when two copies end up in the tree.
- **A temporary fork while an upstream fix is pending**, via an alias such as `"pkg": "npm:@your-org/pkg@1.2.4-fix.1"`.

When you do, make the override as small and as temporary as possible:

```json
"overrides": {
  "some-parent": {
    "pkg@>=2 <2.3.1": "^2.3.1"
  }
}
```

- Scope it to the parent that needs it, with a nested object.
- Bound the key to the advisory's vulnerable range.
- Record why it exists and the condition for removing it next to it — `package.json` allows no comments, so use the README, a contributor guide or the commit message, and link the upstream issue.
- Verify the parent's behaviour, not just that the build is green.

## Recommendations

### For developers

- Run `npm update <pkg>` and upgrade the parent before you consider an override.
- Search the parent's issues and pull requests before you work around it.
- Test an open upstream pull request and report the result on it; open the pull request yourself when the fix is a range change.
- Check whether the vulnerable code is reachable, and whether the parent imports or bundles it, before you change anything.
- Dismiss unreachable dev-tooling alerts with a written reason instead of silencing them with an override.
- Move build-only packages to `devDependencies`.
- Bound every override key to the vulnerable range: `"pkg@>=7 <11.0.1"`, never `"pkg@>=7"`.
- Nest overrides under the one parent that needs them.
- Write down the removal condition for every override when you add it.

### For reviewers

- Treat a new override as a design decision, not a lockfile detail.
- Ask whether the vulnerable code is reachable and whether the override actually removes it.
- Ask for the link to the upstream issue or pull request that will make the override unnecessary.
- Reject open-ended keys that would also catch future majors.
- Review existing overrides when the packages they affect are upgraded, and delete the ones whose reason is gone.

### For library authors

- Bundle dependencies only when you must — a bundled copy is invisible to your users' security tooling.
- List build tools under `devDependencies`, or as optional peers, rather than under `dependencies`.
- Widen your ranges promptly when a dependency ships a security fix in a new major.
- Review and release pull requests that only widen a dependency range — they unblock every user who would otherwise reach for an override.

---

[^npm-overrides]: npm docs: [`overrides` in package.json](https://docs.npmjs.com/cli/v11/configuring-npm/package-json#overrides). Available since npm 8.3.

[^dev-optional]: npm marks such a package `devOptional`, and `--omit=dev` only leaves out packages that are needed for development alone. Reported in [npm/cli#7740](https://github.com/npm/cli/issues/7740) and [npm/cli#7772](https://github.com/npm/cli/issues/7772); still the behaviour in npm 11.19.1.

[^arborist]: npm's dependency resolver, `@npmcli/arborist`, matches an override to a dependency edge in `lib/override-set.js` with `semver.intersects(edgeSpec, ruleKeySpec)`. Checked against npm 11.19.1.
