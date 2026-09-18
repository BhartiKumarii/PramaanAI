package com.pramaanai.officer.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

// Every role filled in explicitly — Material3's baseline defaults are a
// purple-tinted palette, and any role left unset (secondaryContainer,
// tertiary, etc.) leaks that hue into chips/switches/sliders, breaking the
// brand palette below. Dark is the primary/intended theme (matching the
// reference dashboard, which forces dark); light is a fallback only.
private val LightColors = lightColorScheme(
    primary = AccentGreen,
    onPrimary = BackgroundLight,
    primaryContainer = AccentGreen,
    onPrimaryContainer = BackgroundLight,
    inversePrimary = AccentGreen,
    secondary = ForegroundDark,
    onSecondary = BackgroundLight,
    secondaryContainer = CardLight,
    onSecondaryContainer = ForegroundDark,
    tertiary = ChartBlue,
    onTertiary = BackgroundLight,
    tertiaryContainer = CardLight,
    onTertiaryContainer = ForegroundDark,
    background = BackgroundLight,
    onBackground = ForegroundDark,
    surface = CardLight,
    onSurface = ForegroundDark,
    surfaceVariant = CardLight,
    onSurfaceVariant = MutedForeground,
    surfaceTint = AccentGreen,
    inverseSurface = ForegroundDark,
    inverseOnSurface = BackgroundLight,
    outline = BorderLight,
    outlineVariant = BorderLight,
    error = DestructiveRed,
    onError = BackgroundLight,
    errorContainer = BorderLight,
    onErrorContainer = DestructiveRed,
    scrim = ForegroundDark,
)

private val DarkColors = darkColorScheme(
    primary = AccentGreen,
    onPrimary = BackgroundDark,
    primaryContainer = AccentGreen,
    onPrimaryContainer = BackgroundDark,
    inversePrimary = AccentGreen,
    secondary = ForegroundLight,
    onSecondary = BackgroundDark,
    secondaryContainer = SecondaryDark,
    onSecondaryContainer = ForegroundLight,
    tertiary = ChartBlue,
    onTertiary = BackgroundDark,
    tertiaryContainer = SecondaryDark,
    onTertiaryContainer = ForegroundLight,
    background = BackgroundDark,
    onBackground = ForegroundLight,
    surface = CardDark,
    onSurface = ForegroundLight,
    surfaceVariant = SecondaryDark,
    onSurfaceVariant = MutedForeground,
    surfaceTint = AccentGreen,
    inverseSurface = ForegroundLight,
    inverseOnSurface = BackgroundDark,
    outline = BorderDark,
    outlineVariant = BorderDark,
    error = DestructiveRed,
    onError = ForegroundLight,
    errorContainer = SecondaryDark,
    onErrorContainer = DestructiveRed,
    scrim = BackgroundDark,
)

// Dark-only by design (matches the reference web dashboard/landing page,
// which both force dark regardless of system theme) — the user explicitly
// asked for the reference colors verbatim, not an adaptive light/dark pair.
@Composable
fun PramaanAiTheme(
    darkTheme: Boolean = true,
    content: @Composable () -> Unit,
) {
    val colors = if (darkTheme) DarkColors else LightColors
    MaterialTheme(colorScheme = colors, typography = PramaanAiTypography, content = content)
}
