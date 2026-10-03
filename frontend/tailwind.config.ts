import type { Config } from "tailwindcss";

// Task 12.2: maps every token in docs/design.md §3 into the Tailwind theme
// under matching names, so components reference tokens (e.g. `bg-paper`,
// `text-ink-soft`, `font-display`) instead of raw hex values, per
// docs/design.md §12 ("Implementation notes for Kiro").
//
// Naming/structure decisions made here (documented since design.md leaves
// the exact Tailwind wiring to the implementer):
//
// 1. Colors are wired through CSS custom properties (defined in
//    frontend/src/styles/tokens.css) rather than hardcoded hex values, and
//    `darkMode: "class"` is used so a `.dark` class on <html> swaps the
//    §3.2 dark-mode values in. Light mode (§3.1) is the default — the
//    `:root` values in tokens.css are the light palette, matching
//    design.md §2's "light paper mode is the default identity, not dark
//    mode." Because these are plain `var(--color-x)` references (no
//    `rgb(var(...) / <alpha-value>)` indirection), Tailwind's opacity
//    modifiers (e.g. `bg-paper/50`) are not supported on these tokens —
//    design.md never calls for alpha compositing on them, so this
//    tradeoff keeps tokens.css simple (plain hex custom properties).
// 2. §3.3 status colors are identical in both color modes, so they are
//    declared once in `:root` and are not overridden in `.dark`. Their
//    snake_case names in design.md (`verified_official`, etc.) are mapped
//    to kebab-case Tailwind/CSS token names (`verified-official`) to match
//    the kebab-case convention design.md itself already uses for
//    multi-word tokens (`paper-raised`, `ink-soft`, `accent-soft`).
// 3. Font sizes use the exact names design.md's §3.4 scale gives each size
//    (micro, table-body, body, base, subhead, section-head, page-head,
//    display) as Tailwind's extended `fontSize` keys, rather than
//    generic sm/md/lg scale names, so a class like `text-section-head`
//    reads the same as the design doc. Line-heights are not specified in
//    design.md, so sensible ~1.3-1.4x values were chosen per size.
// 4. Spacing: Tailwind's own default spacing scale is already 4px-based
//    and its keys already equal design.md's §3.5 scale value-for-value
//    (spacing-1=4px, 2=8px, 3=12px, 4=16px, 6=24px, 8=32px, 12=48px,
//    16=64px — assuming the standard 16px root font-size). Rather than
//    silently relying on that coincidence, the scale is restated
//    explicitly below under the same keys so the mapping is traceable to
//    §3.5 and won't silently drift if Tailwind's defaults ever change.
// 5. Border radius keys are the semantic names design.md ties the radius
//    choice to (`control`, `panel`, `table`) per §3.5's "this is how the
//    UI tells the user 'this is a record' vs 'this is a control'" rule,
//    not Tailwind's generic sm/md/lg radius scale.
// 6. A `boxShadow.elevated` token is added for the one shadow value §3.5
//    defines (`0 4px 16px rgba(28,26,22,0.16)`), reserved per §2/§5 for
//    modals, dropdowns, and toasts only — never static content.
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // §3.1 / §3.2 — light values are the :root defaults in
        // tokens.css; `.dark` overrides them. See decision #1 above.
        paper: "var(--color-paper)",
        "paper-raised": "var(--color-paper-raised)",
        ink: "var(--color-ink)",
        "ink-soft": "var(--color-ink-soft)",
        rule: "var(--color-rule)",
        accent: "var(--color-accent)",
        "accent-soft": "var(--color-accent-soft)",
        seal: "var(--color-seal)",

        // §3.3 — status colors, identical in both color modes.
        "verified-official": "var(--color-verified-official)",
        "authorized-partner": "var(--color-authorized-partner)",
        unverified: "var(--color-unverified)",
        conflicting: "var(--color-conflicting)",
        "high-risk-review": "var(--color-high-risk-review)",
      },

      // §3.4 — Hind (body/UI, incl. Hindi), Fraunces (display only),
      // JetBrains Mono (reference data only). Each lists a generic
      // fallback stack so text stays readable before the self-hosted
      // .woff2 files below are in place (see assets/fonts/README.md).
      fontFamily: {
        sans: ["Hind", "ui-sans-serif", "system-ui", "sans-serif"],
        display: ["Fraunces", "ui-serif", "Georgia", "serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
      },

      // §3.4 scale (px): 12 micro/labels, 13 table body, 14 body,
      // 16 base UI, 18 subhead, 22 section head, 28 page head,
      // 36 display (Public Lookup hero only).
      fontSize: {
        micro: ["12px", { lineHeight: "16px" }],
        "table-body": ["13px", { lineHeight: "18px" }],
        body: ["14px", { lineHeight: "20px" }],
        base: ["16px", { lineHeight: "24px" }],
        subhead: ["18px", { lineHeight: "26px" }],
        "section-head": ["22px", { lineHeight: "30px" }],
        "page-head": ["28px", { lineHeight: "36px" }],
        display: ["36px", { lineHeight: "44px" }],
      },

      // §3.5 — base unit 4px; scale: 4/8/12/16/24/32/48/64.
      // Restated explicitly (see decision #4 above) rather than relying
      // silently on Tailwind's default scale matching these values.
      spacing: {
        "4": "4px",
        "8": "8px",
        "12": "12px",
        "16": "16px",
        "24": "24px",
        "32": "32px",
        "48": "48px",
        "64": "64px",
      },

      // §3.5 — radius tied to semantic meaning, not a generic scale.
      borderRadius: {
        control: "4px", // inputs, buttons, badges
        panel: "8px", // cards/panels
        table: "0px", // tables are ledger rows — flat, not rounded
      },

      // §3.5 — reserved for modals, dropdown menus, and toasts only.
      boxShadow: {
        elevated: "0 4px 16px rgba(28, 26, 22, 0.16)",
      },
    },
  },
  plugins: [],
} satisfies Config;
