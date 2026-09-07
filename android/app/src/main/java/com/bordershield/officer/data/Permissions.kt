package com.bordershield.officer.data

/** Real role-based UI gating — driven by the role the backend actually
 * returned at login (see [com.bordershield.officer.data.remote.AuthSession]),
 * never a client-chosen value. Hiding a menu item here is a UX convenience,
 * not the security boundary: the backend's own `require_role` checks are
 * what actually enforce this (see app/api/routes/registry.py), so a hidden
 * action failing server-side is still the expected/safe outcome. */
object Permissions {
    private const val SUPERVISOR = "SUPERVISOR"
    private const val ADMIN = "ADMIN"

    fun canViewAuditLog(role: String?): Boolean = role == SUPERVISOR || role == ADMIN
    fun canViewSettings(role: String?): Boolean = role == SUPERVISOR || role == ADMIN
    fun canEditRiskConfig(role: String?): Boolean = role == ADMIN
    fun canExportHistory(role: String?): Boolean = role == SUPERVISOR || role == ADMIN
    fun canManageRegistrySync(role: String?): Boolean = role == ADMIN

    fun roleLabel(role: String?): String = when (role) {
        SUPERVISOR -> "Senior Officer"
        ADMIN -> "Administrator"
        else -> "Officer"
    }
}
