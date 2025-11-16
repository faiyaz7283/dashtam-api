"""Audit action types for compliance tracking.

This enum defines all auditable actions in the system for PCI-DSS, SOC 2, and GDPR
compliance. Actions are organized by category for clarity and maintainability.

Architectural Decision:
    Following centralized enum pattern (see docs/architecture/directory-structure.md).
    All domain enums live in src/domain/enums/ for discoverability.

Extensibility:
    New actions can be added to enum without database schema changes.
    Action-specific context is stored in JSONB metadata field.

Categories:
    - Authentication: USER_* actions (login, logout, registration, etc.)
    - Authorization: ACCESS_* and permission-related actions
    - Data Operations: DATA_* actions (viewed, exported, deleted, modified)
    - Administrative: ADMIN_* actions (user management, config changes)
    - Provider: PROVIDER_* actions (connections, token refresh, data sync)

Usage:
    from src.domain.enums import AuditAction

    # Record audit event
    await audit.record(
        action=AuditAction.USER_LOGIN,
        user_id=user_id,
        resource_type="session",
        context={"method": "password", "mfa": True},
    )
"""

from enum import Enum


class AuditAction(str, Enum):
    """Audit action types for compliance tracking.

    This enum defines all auditable security and data access events in the system.
    Organized by category for clarity. Add new actions as needed without database
    schema changes (action-specific context goes in JSONB metadata).

    String Enum:
        Inherits from str for easy serialization and database storage.
        Values are snake_case strings for consistency.

    Categories:
        Authentication: Login, logout, registration, password changes
        Authorization: Access control, permissions, roles
        Data Operations: View, export, delete, modify operations
        Administrative: System administration and configuration
        Provider: Financial provider integration events

    Compliance:
        PCI-DSS: Authentication events, cardholder data access
        SOC 2: Security event tracking, access control
        GDPR: Personal data access, consent changes, data deletion
    """

    # =========================================================================
    # Authentication Events (PCI-DSS Required)
    # =========================================================================

    USER_LOGIN = "user_login"
    """User successfully authenticated.

    Context should include:
        - method: Authentication method (password, oauth, mfa)
        - mfa: Whether MFA was used (boolean)
        - remember_me: Whether "remember me" was selected
    """

    USER_LOGOUT = "user_logout"
    """User logged out (explicit logout action)."""

    USER_LOGIN_FAILED = "user_login_failed"
    """Failed login attempt (security event).

    Context should include:
        - reason: Why login failed (invalid_password, user_not_found, etc.)
        - attempts: Number of consecutive failed attempts
    """

    USER_REGISTERED = "user_registered"
    """New user account created.

    Context should include:
        - registration_method: How user registered (email, oauth, invite)
        - email_verified: Whether email was verified during registration
    """

    USER_PASSWORD_CHANGED = "user_password_changed"
    """User password was changed.

    Context should include:
        - initiated_by: Who initiated change (user, admin, system)
        - method: How changed (self_service, admin_reset, forced_reset)
    """

    USER_PASSWORD_RESET_REQUESTED = "user_password_reset_requested"
    """User requested password reset.

    Context should include:
        - method: How requested (email_link, security_questions)
    """

    USER_PASSWORD_RESET_COMPLETED = "user_password_reset_completed"
    """Password reset was completed."""

    USER_EMAIL_VERIFIED = "user_email_verified"
    """User email address was verified."""

    USER_MFA_ENABLED = "user_mfa_enabled"
    """Multi-factor authentication was enabled.

    Context should include:
        - mfa_method: Type of MFA (totp, sms, email)
    """

    USER_MFA_DISABLED = "user_mfa_disabled"
    """Multi-factor authentication was disabled.

    Context should include:
        - initiated_by: Who disabled MFA (user, admin)
        - reason: Why disabled (lost_device, user_request, etc.)
    """

    # =========================================================================
    # Authorization Events (SOC 2 Required)
    # =========================================================================

    ACCESS_GRANTED = "access_granted"
    """Access to resource was granted.

    Context should include:
        - resource: What was accessed
        - permission_level: Access level granted (read, write, admin)
    """

    ACCESS_DENIED = "access_denied"
    """Access to resource was denied (security event).

    Context should include:
        - resource: What was attempted
        - reason: Why denied (no_permission, suspended_account, etc.)
    """

    PERMISSION_CHANGED = "permission_changed"
    """User permissions were modified.

    Context should include:
        - changed_by: Who modified permissions
        - old_permissions: Previous permission set
        - new_permissions: New permission set
    """

    ROLE_ASSIGNED = "role_assigned"
    """Role was assigned to user.

    Context should include:
        - role_name: Name of role assigned
        - assigned_by: Who assigned the role
    """

    ROLE_REVOKED = "role_revoked"
    """Role was revoked from user.

    Context should include:
        - role_name: Name of role revoked
        - revoked_by: Who revoked the role
        - reason: Why revoked
    """

    # =========================================================================
    # Data Access Events (GDPR Required)
    # =========================================================================

    DATA_VIEWED = "data_viewed"
    """Personal or sensitive data was viewed.

    Context should include:
        - data_type: Type of data viewed (profile, financial, etc.)
        - fields_accessed: Specific fields viewed
    """

    DATA_EXPORTED = "data_exported"
    """Data was exported (GDPR right to data portability).

    Context should include:
        - export_format: Format of export (json, csv, pdf)
        - data_scope: What data was exported
        - export_reason: Why exported (user_request, backup, etc.)
    """

    DATA_DELETED = "data_deleted"
    """Data was deleted (GDPR right to be forgotten).

    Context should include:
        - deletion_type: Type of deletion (soft, hard, anonymization)
        - data_scope: What data was deleted
        - requested_by: Who requested deletion
    """

    DATA_MODIFIED = "data_modified"
    """Personal or sensitive data was modified.

    Context should include:
        - fields_changed: Which fields were modified
        - change_reason: Why data was modified
    """

    # =========================================================================
    # Administrative Events (SOC 2 Required)
    # =========================================================================

    ADMIN_USER_CREATED = "admin_user_created"
    """Administrator created a new user account.

    Context should include:
        - created_by: Admin who created account
        - initial_role: Role assigned to new user
    """

    ADMIN_USER_DELETED = "admin_user_deleted"
    """Administrator deleted a user account.

    Context should include:
        - deleted_by: Admin who deleted account
        - reason: Why account was deleted
        - user_email: Email of deleted user
    """

    ADMIN_USER_SUSPENDED = "admin_user_suspended"
    """Administrator suspended a user account.

    Context should include:
        - suspended_by: Admin who suspended account
        - reason: Why account was suspended
        - duration: Suspension duration (if temporary)
    """

    ADMIN_CONFIG_CHANGED = "admin_config_changed"
    """System configuration was changed by administrator.

    Context should include:
        - config_key: What configuration was changed
        - old_value: Previous value
        - new_value: New value
        - changed_by: Admin who made change
    """

    ADMIN_BACKUP_CREATED = "admin_backup_created"
    """System backup was created.

    Context should include:
        - backup_type: Type of backup (full, incremental, differential)
        - backup_location: Where backup was stored
        - backup_size: Size of backup
    """

    # =========================================================================
    # Provider Events (PCI-DSS Required - Cardholder Data Access)
    # =========================================================================

    PROVIDER_CONNECTED = "provider_connected"
    """Financial provider was connected to user account.

    Context should include:
        - provider_name: Name of provider (schwab, chase, etc.)
        - connection_method: How connected (oauth, api_key, etc.)
    """

    PROVIDER_DISCONNECTED = "provider_disconnected"
    """Financial provider was disconnected from user account.

    Context should include:
        - provider_name: Name of provider
        - disconnection_reason: Why disconnected (user_request, error, etc.)
    """

    PROVIDER_TOKEN_REFRESHED = "provider_token_refreshed"
    """Provider access token was refreshed.

    Context should include:
        - provider_name: Name of provider
        - token_type: Type of token refreshed (access, refresh)
    """

    PROVIDER_TOKEN_REFRESH_FAILED = "provider_token_refresh_failed"
    """Provider token refresh failed (security event).

    Context should include:
        - provider_name: Name of provider
        - error_code: Provider error code
        - error_message: Error description
    """

    PROVIDER_DATA_SYNCED = "provider_data_synced"
    """Data was synced from financial provider.

    Context should include:
        - provider_name: Name of provider
        - data_types: Types of data synced (accounts, transactions)
        - records_synced: Number of records synced
    """

    PROVIDER_ACCOUNT_VIEWED = "provider_account_viewed"
    """Financial account data was viewed (PCI-DSS: cardholder data access).

    Context should include:
        - provider_name: Name of provider
        - account_type: Type of account (checking, credit_card, etc.)
        - account_mask: Last 4 digits of account number
    """

    PROVIDER_TRANSACTION_VIEWED = "provider_transaction_viewed"
    """Financial transaction data was viewed (PCI-DSS: cardholder data access).

    Context should include:
        - provider_name: Name of provider
        - account_mask: Last 4 digits of account number
        - transaction_count: Number of transactions viewed
        - date_range: Date range of transactions
    """
