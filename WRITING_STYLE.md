# Writing Style Guide

## Tone
- Technical but accessible — assume a developer audience, but don't rely on jargon without explanation.
- Confident and direct, without being absolute. Especially in security contexts, prefer "often" and "frequently" over "always" and "never".

## Language
- British English spellings: *defence*, *sceptical*, *colour*, *behaviour*, etc.

## Sentences and structure
- Concise, direct sentences. Avoid padding.
- Em dashes (—) for asides and elaborations, not parentheses.
- **Bold** for key callouts and the most important takeaway in a paragraph.
- Italics for subtle emphasis within a sentence.

## Code and examples
- Always use fenced code blocks for headers, directives, and snippets.
- Label examples that are intentionally minimal or narrowly scoped (e.g. "This minimal, script-focused example…").
- Include `'report-sample'` in `script-src` when the example is meant to produce useful violation reports.

## Structure
- H2 sections with clear, action-oriented titles.
- End with a **Recommendations** section split by audience (e.g. *For our clients* / *For extension authors*).
- Use footnotes for compatibility caveats and external references rather than cluttering the body text.

## Recommendations style
- Bullet points, imperative mood: "Deploy CSP.", "Use `'strict-dynamic'` with nonces."
- Each bullet should be self-contained and actionable.
