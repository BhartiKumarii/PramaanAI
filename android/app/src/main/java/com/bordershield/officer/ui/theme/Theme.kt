package com.bordershield.officer.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable

// Every role filled in explicitly — Material3's baseline defaults are a
// purple-tinted palette, and any role left unset (secondaryContainer,
// tertiary, etc.) leaks that hue into chips/switches/sliders, breaking the
// strict black/white/grayscale requirement.
private val LightColors = lightColorScheme(
    primary = Ink900,
    onPrimary = White,
    primaryContainer = Ink900,
    onPrimaryContainer = White,
    inversePrimary = White,
    secondary = Gray600,
    onSecondary = White,
    secondaryContainer = Ink900,
    onSecondaryContainer = White,
    tertiary = Gray600,
    onTertiary = White,
    tertiaryContainer = Gray200,
    onTertiaryContainer = Ink900,
    background = White,
    onBackground = Ink900,
    surface = Gray50,
    onSurface = Ink900,
    surfaceVariant = Gray100,
    onSurfaceVariant = Gray600,
    surfaceTint = Ink900,
    inverseSurface = Ink900,
    inverseOnSurface = White,
    outline = Gray300,
    outlineVariant = Gray200,
    error = Ink900,
    onError = White,
    errorContainer = Gray200,
    onErrorContainer = Ink900,
    scrim = Ink900,
)

private val DarkColors = darkColorScheme(
    primary = White,
    onPrimary = Ink900,
    primaryContainer = White,
    onPrimaryContainer = Ink900,
    inversePrimary = Ink900,
    secondary = Gray300,
    onSecondary = Ink900,
    secondaryContainer = White,
    onSecondaryContainer = Ink900,
    tertiary = Gray300,
    onTertiary = Ink900,
    tertiaryContainer = Ink700,
    onTertiaryContainer = White,
    background = Ink900,
    onBackground = White,
    surface = Ink800,
    onSurface = White,
    surfaceVariant = Ink700,
    onSurfaceVariant = Gray300,
    surfaceTint = White,
    inverseSurface = White,
    inverseOnSurface = Ink900,
    outline = Gray600,
    outlineVariant = Ink700,
    error = White,
    onError = Ink900,
    errorContainer = Ink700,
    onErrorContainer = White,
    scrim = Ink900,
)

// This is a single defined enterprise palette (white background, near-black
// accents), not an adaptive one — it deliberately doesn't follow the
// device's system dark-mode setting, matching the design spec exactly
// regardless of device theme.
@Composable
fun BorderShieldOfficerTheme(
    darkTheme: Boolean = false,
    content: @Composable () -> Unit,
) {
    val colors = if (darkTheme) DarkColors else LightColors
    MaterialTheme(colorScheme = colors, typography = BorderShieldTypography, content = content)
}
