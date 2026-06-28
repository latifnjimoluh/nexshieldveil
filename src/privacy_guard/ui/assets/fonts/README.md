# Fonts (free licence — SIL Open Font License)

NexShieldVeil's type system uses three deliberately distinct OFL faces (see
`docs/DESIGN_TOKENS.md`). To keep the repository free of vendored binaries and avoid
any network fetch, the `.ttf`/`.otf` files are **not** committed. Drop them here and
they are picked up automatically at startup (`load_bundled_fonts()` in
`privacy_guard.ui.fonts`); if absent, Qt falls back to the families listed in
`tokens.FONT_FALLBACKS` and the app still works.

| Role | Family | Files to place here | Source (OFL) |
|---|---|---|---|
| Display | **Space Grotesk** | `SpaceGrotesk-*.ttf` | https://fonts.google.com/specimen/Space+Grotesk |
| UI / body | **Inter** | `Inter-*.ttf` | https://fonts.google.com/specimen/Inter |
| Mono / values | **JetBrains Mono** | `JetBrainsMono-*.ttf` | https://fonts.google.com/specimen/JetBrains+Mono |

All three are licensed under the SIL OFL 1.1, which permits bundling and
redistribution. Keep each font's `OFL.txt` alongside its files if you commit them in
a downstream build.
