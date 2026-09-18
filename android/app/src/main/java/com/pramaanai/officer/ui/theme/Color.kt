package com.pramaanai.officer.ui.theme

import androidx.compose.ui.graphics.Color

// Surfaces (card/secondary/border/sidebar) were lifted a step toward grey on
// the user's request — at the reference's near-black values components were
// indistinguishable from the canvas. Canvas, text and accent colors are
// unchanged.
// Exact palette ported from the reference dashboard design
// (sales-ops-dashboard's dark oklch tokens, converted to sRGB hex) so the
// Android app, web console, and landing page share one brand — the user
// explicitly asked for the reference colors verbatim, not an adapted
// navy/blue scheme. Dark is the primary/default theme (both reference
// templates force dark); a light fallback exists so the app doesn't
// break under a forced system light theme, but isn't the intended look.
val BackgroundDark = Color(0xFF020203)
val CardDark = Color(0xFF15171A)
val SidebarDark = Color(0xFF0E1013)
val SecondaryDark = Color(0xFF1E2126)
val BorderDark = Color(0xFF2C3036)
val ForegroundLight = Color(0xFFEEEEEE)
val MutedForeground = Color(0xFF8F8F8F)

// Brand accent — the reference dashboard's green, used for primary
// actions, active nav state, and "verified/clear" status.
val AccentGreen = Color(0xFF45BA50)
val SuccessGreen = Color(0xFF45BA50)
val WarningAmber = Color(0xFFFF8918)
val DestructiveRed = Color(0xFFF14D4C)

// Chart palette (blue / green / amber / red / purple) — same tokens the
// reference dashboard uses for its chart series.
val ChartBlue = Color(0xFF00B5EB)
val ChartGreen = Color(0xFF45BA50)
val ChartAmber = Color(0xFFFF8918)
val ChartRed = Color(0xFFF14D4C)
val ChartPurple = Color(0xFFAD87ED)

// Light-mode fallback only (system-forced light) — lighter derivatives of
// the same brand hues, not a separately designed theme.
val BackgroundLight = Color(0xFFFFFFFF)
val CardLight = Color(0xFFF7F8F8)
val ForegroundDark = Color(0xFF0A0A0A)
val BorderLight = Color(0xFFE2E4E6)

// Legacy neutral-ramp names (still imported directly, unchanged, by ~19
// screen files that predate the dark rebrand and choose their own
// bg/fg pairs rather than reading MaterialTheme.colorScheme). Every
// screen was built as a strictly monochrome UI on a WHITE canvas
// (documented intentionally: "risk level is always icon + label, never
// color alone"). Re-pointing these same names at a REVERSED ramp keeps
// every existing bg/fg pair's *relative* contrast intact while making
// the absolute values correct for the new near-black canvas — i.e. the
// old darkest-ink value now resolves to the new lightest neutral (since
// bare foreground text/dots need to be light against a dark page), and
// the old lightest/page value now resolves to the new near-black
// canvas fill. This is a deliberate monochrome-preserving remap, not a
// re-hue — screens keep their original icon+label severity signaling
// unchanged; only the absolute lightness direction flips.
val Ink900 = ForegroundLight // was darkest ink -> now the strongest light-on-dark
val Ink800 = Color(0xFFD4D4D4)
val Ink700 = Color(0xFFB0B0B0)
val Gray600 = MutedForeground
val Gray500 = Color(0xFF737373)
val Gray400 = Color(0xFF5C5C5C)
val Gray300 = Color(0xFF444444)
val Gray200 = Color(0xFF2A2A2A)
val Gray100 = SecondaryDark
val Gray50 = CardDark
val White = BackgroundDark // was the page canvas -> now the near-black canvas fill
