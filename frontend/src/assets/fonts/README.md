# Self-hosted fonts

This directory holds the `.woff2` binary files referenced by the
`@font-face` declarations in `frontend/src/styles/tokens.css`, per
`docs/design.md` §3.4 and §12 ("Load Hind, Fraunces, and JetBrains Mono as
self-hosted font files, not a Google Fonts `<link>` at runtime").

**The binary font files are not included in this repository checkout.**
They cannot be downloaded or generated in this environment. A human must
fetch them and place them at the exact paths below before the fonts in
`tokens.css` will actually render — until then, browsers fall back to the
generic stacks declared alongside each `font-family` in
`tailwind.config.ts` (`ui-sans-serif`/`system-ui`, `ui-serif`/`Georgia`,
`ui-monospace`). This is a known, intentional gap for a human to fill, not
a silent placeholder — nothing in the app will error because of it.

## Required files

### Hind (400, 500, 600, 700) — source: [Google Fonts — Hind](https://fonts.google.com/specimen/Hind)

```
Hind/Hind-Regular.woff2      (weight 400)
Hind/Hind-Medium.woff2       (weight 500)
Hind/Hind-SemiBold.woff2     (weight 600)
Hind/Hind-Bold.woff2         (weight 700)
```

### Fraunces (400, 600) — source: [Google Fonts — Fraunces](https://fonts.google.com/specimen/Fraunces)

```
Fraunces/Fraunces-Regular.woff2    (weight 400)
Fraunces/Fraunces-SemiBold.woff2   (weight 600)
```

### JetBrains Mono (400, 500) — source: [JetBrains Mono releases](https://github.com/JetBrains/JetBrainsMono/releases) (or [Google Fonts — JetBrains Mono](https://fonts.google.com/specimen/JetBrains+Mono))

```
JetBrainsMono/JetBrainsMono-Regular.woff2    (weight 400)
JetBrainsMono/JetBrainsMono-Medium.woff2     (weight 500)
```

## How to get `.woff2` files from a Google Fonts download

Google Fonts ships `.ttf` by default. Either:

- Use [google-webfonts-helper](https://gwfh.mranftl.com/fonts) to download the
  specific weights above directly as `.woff2`, or
- Download the `.ttf` files from Google Fonts and convert them locally
  (e.g. `npx fonttools varLib.instancer` or any `ttf2woff2` CLI tool).

Place each converted file at the exact path shown above (directory names
and filenames are case-sensitive and must match `tokens.css` exactly).
