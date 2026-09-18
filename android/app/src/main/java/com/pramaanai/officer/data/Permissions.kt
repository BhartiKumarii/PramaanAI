package com.pramaanai.officer.data

/** Real role-based UI gating — driven by the role the backend actually
 * returned at login (see [com.pramaanai.officer.data.remote.AuthSession]),
 * never a client-chosen value. Hiding a menu item here is a UX convenience,
 * not the security boundary: the backend's own `require_role` checks are
 * what actually enforce this (see app/api/routes/registry.py), so a hidden
 * action failing server-side is still the expected/safe outcome. */
object Permissions {
    private const val SUPERVISOR = "SUPERVISOR"
    private const val IT_ADMIN = "IT_ADMIN"
    private const val IMMIGRATION_OFFICER = "IMMIGRATION_OFFICER"

    // In practice only FIELD_OFFICER ever logs into this app (Immigration
    // Officer/Supervisor/IT-Admin use the web console instead — see
    // CLAUDE.md's product decision), but these checks stay role-string-based
    // rather than assuming FIELD_OFFICER, in case a non-field account is
    // ever used here for testing.
    fun canViewAuditLog(role: String?): Boolean = role == SUPERVISOR || role == IT_ADMIN
    fun canViewSettings(role: String?): Boolean = role == SUPERVISOR || role == IT_ADMIN
    fun canEditRiskConfig(role: String?): Boolean = role == IT_ADMIN
    fun canExportHistory(role: String?): Boolean = role == SUPERVISOR || role == IT_ADMIN
    fun canManageRegistrySync(role: String?): Boolean = role == IT_ADMIN

    fun roleLabel(role: String?): String = when (role) {
        SUPERVISOR -> "Senior Officer"
        IT_ADMIN -> "Administrator"
        IMMIGRATION_OFFICER -> "Immigration Officer"
        else -> "Field Officer"
    }
}
