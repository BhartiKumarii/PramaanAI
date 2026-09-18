package com.bordershield.officer.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

// Platform sans-serif standing in for Inter/Manrope — no bundled font asset
// in this build. Hierarchy is carried by weight/size/spacing instead.
private val AppFont = FontFamily.SansSerif

val BorderShieldTypography = Typography(
    displaySmall = TextStyle(fontFamily = AppFont, fontWeight = FontWeight.Bold, fontSize = 34.sp, letterSpacing = (-0.5).sp),
    headlineSmall = TextStyle(fontFamily = AppFont, fontWeight = FontWeight.Bold, fontSize = 22.sp, letterSpacing = (-0.2).sp),
    titleLarge = TextStyle(fontFamily = AppFont, fontWeight = FontWeight.SemiBold, fontSize = 18.sp),
    titleMedium = TextStyle(fontFamily = AppFont, fontWeight = FontWeight.SemiBold, fontSize = 15.sp),
    titleSmall = TextStyle(fontFamily = AppFont, fontWeight = FontWeight.SemiBold, fontSize = 13.sp),
    bodyLarge = TextStyle(fontFamily = AppFont, fontWeight = FontWeight.Normal, fontSize = 15.sp),
    bodyMedium = TextStyle(fontFamily = AppFont, fontWeight = FontWeight.Normal, fontSize = 13.sp),
    bodySmall = TextStyle(fontFamily = AppFont, fontWeight = FontWeight.Normal, fontSize = 12.sp),
    labelLarge = TextStyle(fontFamily = AppFont, fontWeight = FontWeight.Medium, fontSize = 13.sp, letterSpacing = 0.2.sp),
    labelMedium = TextStyle(fontFamily = AppFont, fontWeight = FontWeight.Medium, fontSize = 11.sp, letterSpacing = 0.3.sp),
    labelSmall = TextStyle(fontFamily = AppFont, fontWeight = FontWeight.SemiBold, fontSize = 10.sp, letterSpacing = 0.5.sp),
)
