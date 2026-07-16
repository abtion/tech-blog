"""
Directive-level analysis of the CSP crawl data behind the "CSP: dropping
'unsafe-inline'" blog post and talk.

Source data: json/csp-values.json from the Crawler.Ninja Tranco Top 1 Million
crawl (dated 13 June 2026), the same dataset behind Scott Helme's "Top 1
Million Analysis -- June 2026" report.

The published report only counts 'unsafe-inline' by presence anywhere in the
policy string, which mixes in style-src-only cases and cases where a nonce,
hash, or 'strict-dynamic' is also present in the same directive (per the
CSP2+ behavior where compliant browsers ignore 'unsafe-inline' whenever one
of those is present). This script re-parses the raw data directive-by-
directive and classifies each policy by the mechanism that actually governs
its <script> execution -- strict-dynamic > nonce > hash > a live
'unsafe-inline' > 'none' > host/scheme allowlist -- for the <script> element
injection scenario used in the post. Per CSP3, that directive is
script-src-elem if present, else script-src, else default-src
(script-src-attr governs inline event-handler attributes, not <script>
elements, so it is deliberately not part of this fallback chain).

Usage: python3 scripts/analyze_csp.py
"""

import json
import re
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "json" / "csp-values.json"

# Quoted source expressions, matching how these keywords must appear in a
# real CSP directive (e.g. 'nonce-abc123', 'sha256-...', 'strict-dynamic').
UNSAFE_INLINE = "'unsafe-inline'"
NONCE_RE = re.compile(r"'nonce-")
HASH_RE = re.compile(r"'sha256-|'sha384-|'sha512-")
STRICT_DYNAMIC_RE = re.compile(r"'strict-dynamic'")
NONE_RE = re.compile(r"'none'")

# Mutually exclusive buckets describing what actually governs script
# execution for each policy, in priority order. A redundant 'unsafe-inline'
# alongside a nonce/hash/strict-dynamic is ignored by compliant browsers, so
# such policies are classified by the mechanism that actually protects them,
# not as a separate "neutralized" bucket.
CATEGORY_LABELS = {
    "no_effective_directive": "No script-src-elem/script-src/default-src at all (unrestricted)",
    "strict_dynamic": "'strict-dynamic'",
    "nonce_based": "Nonce-based",
    "hash_based": "Hash-based",
    "unsafe_inline_live": "'unsafe-inline' present, live (no nonce/hash/strict-dynamic)",
    "none_blocks_all": "'none' (blocks all scripts)",
    "allowlist_or_self_only": "Host/scheme allowlist or 'self' only",
    "other": "Other/empty directive",
}


def categorize(directive):
    """Classify a single script-governing directive by what actually
    protects it, ignoring 'unsafe-inline' whenever a nonce/hash/
    strict-dynamic is also present (browsers ignore it in that case)."""
    if not directive:
        return "no_effective_directive"

    has_ui = bool(UNSAFE_INLINE in directive)
    has_nonce = bool(NONCE_RE.search(directive))
    has_hash = bool(HASH_RE.search(directive))
    has_sd = bool(STRICT_DYNAMIC_RE.search(directive))
    has_none = bool(NONE_RE.search(directive))

    if has_sd:
        return "strict_dynamic"
    if has_nonce:
        return "nonce_based"
    if has_hash:
        return "hash_based"
    if has_ui:
        return "unsafe_inline_live"
    if has_none:
        return "none_blocks_all"
    return "allowlist_or_self_only"


def policy_string(entry):
    value = entry.get("content-security-policy", "")
    return value if isinstance(value, str) else str(value)


def split_directives(policy):
    directives = {}
    for part in policy.split(";"):
        part = part.strip()
        if not part:
            continue
        tokens = part.split()
        if not tokens:
            continue
        directives[tokens[0].lower()] = part
    return directives


def main():
    with open(DATA_FILE) as f:
        data = json.load(f)

    total_sites = 0
    total_policies = len(data)

    # Presence anywhere in the policy (what the published report counts).
    raw_unsafe_inline = 0

    # Mutually exclusive categorization of what actually governs <script>
    # execution (script-src-elem > script-src > default-src), so the
    # percentages sum to 100%.
    categories = {key: 0 for key in CATEGORY_LABELS}

    for entry in data:
        policy = policy_string(entry)
        count = entry.get("count", 0)
        total_sites += count

        if UNSAFE_INLINE in policy:
            raw_unsafe_inline += count

        directive = split_directives(policy)
        script_directive = (
            directive.get("script-src-elem")
            or directive.get("script-src")
            or directive.get("default-src")
        )
        categories[categorize(script_directive)] += count

    print(f"Total policies (unique rows): {total_policies}")
    print(f"Total sites (sum of counts): {total_sites}")
    print(
        f"Raw 'unsafe-inline' anywhere in policy: {raw_unsafe_inline} "
        f"({raw_unsafe_inline / total_sites * 100:.1f}%)"
    )

    print()
    print("What actually governs <script> execution (mutually exclusive, sums to 100%):")
    for key, label in CATEGORY_LABELS.items():
        count = categories[key]
        print(f"  {label}: {count} ({count / total_sites * 100:.1f}%)")

    unblocked = categories["no_effective_directive"] + categories["unsafe_inline_live"]
    print()
    print(
        f"Would not stop an injected <script> tag (no effective directive, or "
        f"'unsafe-inline' live): {unblocked} ({unblocked / total_sites * 100:.1f}%)"
    )


if __name__ == "__main__":
    main()
