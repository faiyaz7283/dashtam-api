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
    # Pattern: ATTEMPTED → (FAILED | SUCCESS)
    # All authentication actions follow attempt/outcome pattern for compliance

    # Login Events
    USER_LOGIN_ATTEMPTED = "user_login_attempted"
    """User attempted to log in.

    Context should include:
        - email: Email address used (for correlation)
        - method: Authentication method attempted (password, oauth, mfa)
    """

    USER_LOGIN_FAILED = "user_login_failed"
    """Failed login attempt (security event).

    Context should include:
        - reason: Why login failed (invalid_password, user_not_found, etc.)
        - attempts: Number of consecutive failed attempts
        - email: Email address attempted
    """

    USER_LOGIN_SUCCESS = "user_login_success"
    """User successfully authenticated.

    Context should include:
        - method: Authentication method (password, oauth, mfa)
        - mfa: Whether MFA was used (boolean)
        - remember_me: Whether "remember me" was selected
    """

    USER_LOGOUT = "user_logout"
    """User logged out (explicit logout action).
    
    Note: This is a completed event (no ATTEMPT needed - logout always succeeds).
    """

    # Registration Events
    USER_REGISTRATION_ATTEMPTED = "user_registration_attempted"
    """User attempted to register.

    Context should include:
        - email: Email address used
        - registration_method: How user attempted to register (email, oauth, invite)
    """

    USER_REGISTRATION_FAILED = "user_registration_failed"
    """User registration failed.

    Context should include:
        - email: Email address attempted
        - reason: Why registration failed (duplicate_email, weak_password, validation_error)
    """

    USER_REGISTERED = "user_registered"
    """New user account created (SUCCESS).

    Context should include:
        - registration_method: How user registered (email, oauth, invite)
        - email_verified: Whether email was verified during registration
    """

    # Password Change Events
    USER_PASSWORD_CHANGE_ATTEMPTED = "user_password_change_attempted"
    """User attempted to change password.

    Context should include:
        - initiated_by: Who initiated change (user, admin, system)
    """

    USER_PASSWORD_CHANGE_FAILED = "user_password_change_failed"
    """Password change failed.

    Context should include:
        - reason: Why failed (wrong_current_password, weak_new_password, etc.)
        - initiated_by: Who attempted change
    """

    USER_PASSWORD_CHANGED = "user_password_changed"
    """User password was changed (SUCCESS).

    Context should include:
        - initiated_by: Who initiated change (user, admin, system)
        - method: How changed (self_service, admin_reset, forced_reset)
    """

    # Password Reset Events
    USER_PASSWORD_RESET_REQUESTED = "user_password_reset_requested"
    """User requested password reset.
    
    Note: This is a completed event (request is recorded, no ATTEMPT needed).

    Context should include:
        - method: How requested (email_link, security_questions)
        - email: Email address for reset
    """

    USER_PASSWORD_RESET_FAILED = "user_password_reset_failed"
    """Password reset failed.

    Context should include:
        - reason: Why failed (invalid_token, expired_link, weak_password)
    """

    USER_PASSWORD_RESET_COMPLETED = "user_password_reset_completed"
    """Password reset was completed (SUCCESS)."""

    # Email Verification Events
    USER_EMAIL_VERIFICATION_ATTEMPTED = "user_email_verification_attempted"
    """User attempted to verify email.

    Context should include:
        - email: Email address being verified
    """

    USER_EMAIL_VERIFICATION_FAILED = "user_email_verification_failed"
    """Email verification failed.

    Context should include:
        - reason: Why failed (invalid_token, expired_token, already_verified)
    """

    USER_EMAIL_VERIFIED = "user_email_verified"
    """User email address was verified (SUCCESS)."""

    # MFA Enable Events
    USER_MFA_ENABLE_ATTEMPTED = "user_mfa_enable_attempted"
    """User attempted to enable MFA.

    Context should include:
        - mfa_method: Type of MFA attempted (totp, sms, email)
    """

    USER_MFA_ENABLE_FAILED = "user_mfa_enable_failed"
    """MFA enable failed.

    Context should include:
        - reason: Why failed (invalid_code, setup_timeout, already_enabled)
        - mfa_method: Type of MFA attempted
    """

    USER_MFA_ENABLED = "user_mfa_enabled"
    """Multi-factor authentication was enabled (SUCCESS).

    Context should include:
        - mfa_method: Type of MFA (totp, sms, email)
    """

    # MFA Disable Events
    USER_MFA_DISABLE_ATTEMPTED = "user_mfa_disable_attempted"
    """User attempted to disable MFA.

    Context should include:
        - initiated_by: Who attempted to disable (user, admin)
    """

    USER_MFA_DISABLE_FAILED = "user_mfa_disable_failed"
    """MFA disable failed.

    Context should include:
        - reason: Why failed (wrong_password, security_check_failed)
        - initiated_by: Who attempted
    """

    USER_MFA_DISABLED = "user_mfa_disabled"
    """Multi-factor authentication was disabled (SUCCESS).

    Context should include:
        - initiated_by: Who disabled MFA (user, admin)
        - reason: Why disabled (lost_device, user_request, etc.)
    """

    # =========================================================================
    # Authorization Events (SOC 2 Required)
    # =========================================================================
    # Pattern: ATTEMPTED → (DENIED | GRANTED)

    # Access Control Events
    ACCESS_ATTEMPTED = "access_attempted"
    """User attempted to access resource.

    Context should include:
        - resource: What was attempted
        - action: What action was attempted (read, write, delete)
    """

    ACCESS_DENIED = "access_denied"
    """Access to resource was denied (security event).

    Context should include:
        - resource: What was attempted
        - reason: Why denied (no_permission, suspended_account, etc.)
        - action: What action was attempted
    """

    ACCESS_GRANTED = "access_granted"
    """Access to resource was granted (SUCCESS).

    Context should include:
        - resource: What was accessed
        - permission_level: Access level granted (read, write, admin)
        - action: What action was granted
    """

    # Permission Change Events
    PERMISSION_CHANGE_ATTEMPTED = "permission_change_attempted"
    """Attempted to change user permissions.

    Context should include:
        - changed_by: Who attempted change
        - target_user_id: User whose permissions would change
        - requested_permissions: New permission set requested
    """

    PERMISSION_CHANGE_FAILED = "permission_change_failed"
    """Permission change failed.

    Context should include:
        - reason: Why failed (insufficient_privileges, invalid_permission)
        - changed_by: Who attempted change
    """

    PERMISSION_CHANGED = "permission_changed"
    """User permissions were modified (SUCCESS).

    Context should include:
        - changed_by: Who modified permissions
        - old_permissions: Previous permission set
        - new_permissions: New permission set
    """

    # Role Assignment Events
    ROLE_ASSIGNMENT_ATTEMPTED = "role_assignment_attempted"
    """Attempted to assign role to user.

    Context should include:
        - role_name: Name of role to assign
        - assigned_by: Who attempted assignment
        - target_user_id: User to receive role
    """

    ROLE_ASSIGNMENT_FAILED = "role_assignment_failed"
    """Role assignment failed.

    Context should include:
        - reason: Why failed (invalid_role, no_permission, already_assigned)
        - role_name: Name of role attempted
    """

    ROLE_ASSIGNED = "role_assigned"
    """Role was assigned to user (SUCCESS).

    Context should include:
        - role_name: Name of role assigned
        - assigned_by: Who assigned the role
    """

    # Role Revocation Events
    ROLE_REVOCATION_ATTEMPTED = "role_revocation_attempted"
    """Attempted to revoke role from user.

    Context should include:
        - role_name: Name of role to revoke
        - revoked_by: Who attempted revocation
        - target_user_id: User to lose role
    """

    ROLE_REVOCATION_FAILED = "role_revocation_failed"
    """Role revocation failed.

    Context should include:
        - reason: Why failed (last_admin_role, no_permission)
        - role_name: Name of role attempted
    """

    ROLE_REVOKED = "role_revoked"
    """Role was revoked from user (SUCCESS).

    Context should include:
        - role_name: Name of role revoked
        - revoked_by: Who revoked the role
        - reason: Why revoked
    """

    # =========================================================================
    # Data Access Events (GDPR Required)
    # =========================================================================
    # Pattern: Use ACCESS_ATTEMPTED/DENIED/GRANTED for view operations
    # Use ATTEMPTED → (FAILED | SUCCESS) for modify operations

    DATA_VIEWED = "data_viewed"
    """Personal or sensitive data was viewed (SUCCESS).
    
    Note: Use ACCESS_ATTEMPTED → ACCESS_DENIED/GRANTED for access control.
    This event records successful data access after permission check.

    Context should include:
        - data_type: Type of data viewed (profile, financial, etc.)
        - fields_accessed: Specific fields viewed
    """

    # Data Export Events
    DATA_EXPORT_ATTEMPTED = "data_export_attempted"
    """User attempted to export data.

    Context should include:
        - export_format: Requested format (json, csv, pdf)
        - data_scope: What data was requested
    """

    DATA_EXPORT_FAILED = "data_export_failed"
    """Data export failed.

    Context should include:
        - reason: Why failed (too_large, timeout, permission_denied)
        - export_format: Requested format
    """

    DATA_EXPORTED = "data_exported"
    """Data was exported (SUCCESS - GDPR right to data portability).

    Context should include:
        - export_format: Format of export (json, csv, pdf)
        - data_scope: What data was exported
        - export_reason: Why exported (user_request, backup, etc.)
        - file_size: Size of export file
    """

    # Data Deletion Events
    DATA_DELETION_ATTEMPTED = "data_deletion_attempted"
    """Attempted to delete data.

    Context should include:
        - deletion_type: Type requested (soft, hard, anonymization)
        - data_scope: What data deletion was requested
        - requested_by: Who requested deletion
    """

    DATA_DELETION_FAILED = "data_deletion_failed"
    """Data deletion failed.

    Context should include:
        - reason: Why failed (in_use, constraint_violation, insufficient_permission)
        - data_scope: What data deletion was attempted
    """

    DATA_DELETED = "data_deleted"
    """Data was deleted (SUCCESS - GDPR right to be forgotten).

    Context should include:
        - deletion_type: Type of deletion (soft, hard, anonymization)
        - data_scope: What data was deleted
        - requested_by: Who requested deletion
    """

    # Data Modification Events
    DATA_MODIFICATION_ATTEMPTED = "data_modification_attempted"
    """Attempted to modify data.

    Context should include:
        - fields_to_change: Which fields modification was attempted
        - change_reason: Why modification was attempted
    """

    DATA_MODIFICATION_FAILED = "data_modification_failed"
    """Data modification failed.

    Context should include:
        - reason: Why failed (validation_error, constraint_violation, permission_denied)
        - fields_attempted: Which fields were attempted
    """

    DATA_MODIFIED = "data_modified"
    """Personal or sensitive data was modified (SUCCESS).

    Context should include:
        - fields_changed: Which fields were modified
        - change_reason: Why data was modified
        - old_values: Previous values (if appropriate)
        - new_values: New values
    """

    # =========================================================================
    # Administrative Events (SOC 2 Required)
    # =========================================================================
    # Pattern: ATTEMPTED → (FAILED | SUCCESS)

    # Admin User Creation Events
    ADMIN_USER_CREATION_ATTEMPTED = "admin_user_creation_attempted"
    """Administrator attempted to create user account.

    Context should include:
        - created_by: Admin attempting creation
        - email: Email for new user
        - initial_role: Role to be assigned
    """

    ADMIN_USER_CREATION_FAILED = "admin_user_creation_failed"
    """Admin user creation failed.

    Context should include:
        - reason: Why failed (duplicate_email, validation_error, permission_denied)
        - created_by: Admin who attempted
    """

    ADMIN_USER_CREATED = "admin_user_created"
    """Administrator created a new user account (SUCCESS).

    Context should include:
        - created_by: Admin who created account
        - initial_role: Role assigned to new user
        - user_email: Email of created user
    """

    # Admin User Deletion Events
    ADMIN_USER_DELETION_ATTEMPTED = "admin_user_deletion_attempted"
    """Administrator attempted to delete user account.

    Context should include:
        - deleted_by: Admin attempting deletion
        - target_user_id: User to be deleted
        - reason: Why deletion was attempted
    """

    ADMIN_USER_DELETION_FAILED = "admin_user_deletion_failed"
    """Admin user deletion failed.

    Context should include:
        - reason: Why failed (in_use, constraint_violation, permission_denied)
        - deleted_by: Admin who attempted
    """

    ADMIN_USER_DELETED = "admin_user_deleted"
    """Administrator deleted a user account (SUCCESS).

    Context should include:
        - deleted_by: Admin who deleted account
        - reason: Why account was deleted
        - user_email: Email of deleted user
    """

    # Admin User Suspension Events
    ADMIN_USER_SUSPENSION_ATTEMPTED = "admin_user_suspension_attempted"
    """Administrator attempted to suspend user account.

    Context should include:
        - suspended_by: Admin attempting suspension
        - target_user_id: User to be suspended
        - reason: Why suspension was attempted
        - duration: Requested suspension duration
    """

    ADMIN_USER_SUSPENSION_FAILED = "admin_user_suspension_failed"
    """Admin user suspension failed.

    Context should include:
        - reason: Why failed (already_suspended, permission_denied, cannot_suspend_admin)
        - suspended_by: Admin who attempted
    """

    ADMIN_USER_SUSPENDED = "admin_user_suspended"
    """Administrator suspended a user account (SUCCESS).

    Context should include:
        - suspended_by: Admin who suspended account
        - reason: Why account was suspended
        - duration: Suspension duration (if temporary)
    """

    # Admin Config Change Events
    ADMIN_CONFIG_CHANGE_ATTEMPTED = "admin_config_change_attempted"
    """Administrator attempted to change system configuration.

    Context should include:
        - config_key: What configuration change was attempted
        - requested_value: New value requested
        - changed_by: Admin attempting change
    """

    ADMIN_CONFIG_CHANGE_FAILED = "admin_config_change_failed"
    """Admin config change failed.

    Context should include:
        - reason: Why failed (invalid_value, locked_config, permission_denied)
        - config_key: What configuration was attempted
        - changed_by: Admin who attempted
    """

    ADMIN_CONFIG_CHANGED = "admin_config_changed"
    """System configuration was changed by administrator (SUCCESS).

    Context should include:
        - config_key: What configuration was changed
        - old_value: Previous value
        - new_value: New value
        - changed_by: Admin who made change
    """

    ADMIN_BACKUP_CREATED = "admin_backup_created"
    """System backup was created.
    
    Note: This is a completed system event (no ATTEMPT needed).

    Context should include:
        - backup_type: Type of backup (full, incremental, differential)
        - backup_location: Where backup was stored
        - backup_size: Size of backup
        - initiated_by: Who initiated backup (system, admin)
    """

    # =========================================================================
    # Provider Events (PCI-DSS Required - Cardholder Data Access)
    # =========================================================================
    # Pattern: ATTEMPTED → (FAILED | SUCCESS)

    # Provider Connection Events
    PROVIDER_CONNECTION_ATTEMPTED = "provider_connection_attempted"
    """User attempted to connect financial provider.

    Context should include:
        - provider_name: Name of provider (schwab, chase, etc.)
        - connection_method: Method attempted (oauth, api_key, etc.)
    """

    PROVIDER_CONNECTION_FAILED = "provider_connection_failed"
    """Provider connection failed.

    Context should include:
        - provider_name: Name of provider
        - reason: Why failed (oauth_error, api_error, invalid_credentials)
        - error_code: Provider-specific error code
    """

    PROVIDER_CONNECTED = "provider_connected"
    """Financial provider was connected to user account (SUCCESS).

    Context should include:
        - provider_name: Name of provider (schwab, chase, etc.)
        - connection_method: How connected (oauth, api_key, etc.)
    """

    # Provider Disconnection Events
    PROVIDER_DISCONNECTION_ATTEMPTED = "provider_disconnection_attempted"
    """User attempted to disconnect financial provider.

    Context should include:
        - provider_name: Name of provider
        - disconnection_reason: Why disconnection requested
    """

    PROVIDER_DISCONNECTION_FAILED = "provider_disconnection_failed"
    """Provider disconnection failed.

    Context should include:
        - provider_name: Name of provider
        - reason: Why failed (api_error, pending_transactions)
    """

    PROVIDER_DISCONNECTED = "provider_disconnected"
    """Financial provider was disconnected from user account (SUCCESS).

    Context should include:
        - provider_name: Name of provider
        - disconnection_reason: Why disconnected (user_request, error, etc.)
    """

    # Provider Token Refresh Events
    PROVIDER_TOKEN_REFRESH_ATTEMPTED = "provider_token_refresh_attempted"
    """Attempted to refresh provider access token.

    Context should include:
        - provider_name: Name of provider
        - token_type: Type of token to refresh (access, refresh)
    """

    PROVIDER_TOKEN_REFRESH_FAILED = "provider_token_refresh_failed"
    """Provider token refresh failed (security event).

    Context should include:
        - provider_name: Name of provider
        - error_code: Provider error code
        - error_message: Error description
    """

    PROVIDER_TOKEN_REFRESHED = "provider_token_refreshed"
    """Provider access token was refreshed (SUCCESS).

    Context should include:
        - provider_name: Name of provider
        - token_type: Type of token refreshed (access, refresh)
    """

    # Provider Data Sync Events
    PROVIDER_DATA_SYNC_ATTEMPTED = "provider_data_sync_attempted"
    """Attempted to sync data from financial provider.

    Context should include:
        - provider_name: Name of provider
        - data_types: Types of data to sync (accounts, transactions)
    """

    PROVIDER_DATA_SYNC_FAILED = "provider_data_sync_failed"
    """Provider data sync failed.

    Context should include:
        - provider_name: Name of provider
        - reason: Why failed (api_error, network_error, rate_limit)
        - error_code: Provider error code
    """

    PROVIDER_DATA_SYNCED = "provider_data_synced"
    """Data was synced from financial provider (SUCCESS).

    Context should include:
        - provider_name: Name of provider
        - data_types: Types of data synced (accounts, transactions)
        - records_synced: Number of records synced
    """

    # Provider Data Access Events
    PROVIDER_ACCOUNT_VIEWED = "provider_account_viewed"
    """Financial account data was viewed (SUCCESS - PCI-DSS: cardholder data access).
    
    Note: Use ACCESS_ATTEMPTED → ACCESS_DENIED/GRANTED for access control.
    This event records successful data access after permission check.

    Context should include:
        - provider_name: Name of provider
        - account_type: Type of account (checking, credit_card, etc.)
        - account_mask: Last 4 digits of account number
    """

    PROVIDER_TRANSACTION_VIEWED = "provider_transaction_viewed"
    """Financial transaction data was viewed (SUCCESS - PCI-DSS: cardholder data access).
    
    Note: Use ACCESS_ATTEMPTED → ACCESS_DENIED/GRANTED for access control.
    This event records successful data access after permission check.

    Context should include:
        - provider_name: Name of provider
        - account_mask: Last 4 digits of account number
        - transaction_count: Number of transactions viewed
        - date_range: Date range of transactions
    """

    # =========================================================================
    # Rate Limit Events (Security - Abuse Prevention)
    # =========================================================================
    # Pattern: ATTEMPTED → (ALLOWED | DENIED)
    # These events track rate limit enforcement for security monitoring.

    RATE_LIMIT_CHECK_ATTEMPTED = "rate_limit_check_attempted"
    """Rate limit check was initiated.

    Context should include:
        - endpoint: Endpoint being rate limited
        - identifier: Rate limit identifier (IP, user_id)
        - scope: Rate limit scope (ip, user, user_provider, global)
        - cost: Token cost for operation
    """

    RATE_LIMIT_CHECK_ALLOWED = "rate_limit_check_allowed"
    """Request was allowed by rate limiter (SUCCESS).

    Context should include:
        - endpoint: Endpoint accessed
        - identifier: Rate limit identifier
        - scope: Rate limit scope
        - remaining_tokens: Tokens remaining in bucket
        - execution_time_ms: Rate limit check duration
    """

    RATE_LIMIT_CHECK_DENIED = "rate_limit_check_denied"
    """Request was denied by rate limiter (security event).

    Context should include:
        - endpoint: Endpoint that was rate limited
        - identifier: Rate limit identifier (IP, user_id)
        - scope: Rate limit scope (ip, user, user_provider, global)
        - retry_after: Seconds until retry allowed
        - limit: Maximum tokens (bucket capacity)
        - remaining: Current tokens (should be 0)
    """
