package com.pramaanai.officer.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.pramaanai.officer.ui.theme.AccentGreen
import com.pramaanai.officer.ui.theme.BackgroundDark

@Composable
fun OfficerAvatar(
    name: String?,
    modifier: Modifier = Modifier,
    size: Dp = 28.dp,
    fontSize: TextUnit = 12.sp,
) {
    val initials = name
        ?.trim()
        ?.uppercase()
        ?.take(2)
        ?.ifEmpty { "?" }
        ?: "?"

    Box(
        modifier = modifier
            .size(size)
            .clip(CircleShape)
            .background(AccentGreen),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = initials,
            color = BackgroundDark,
            fontSize = fontSize,
            fontWeight = FontWeight.Bold,
        )
    }
}
