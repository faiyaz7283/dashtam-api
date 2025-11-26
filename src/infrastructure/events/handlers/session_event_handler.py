"""Session event handler for domain events.

Handles session-related side effects for domain events.

Subscriptions:
- UserPasswordChangeSucceeded → Revoke all user sessions (security)

Security Requirements:
- Password change MUST revoke all sessions (prevent unauthorized access)
- Users must re-login after password change (inconvenient but secure)
- Session revocation must be immediate (no grace period)

Reference:
- docs/architecture/domain-events-architecture.md
- docs/architecture/authentication-architecture.md (Section 10)
"""

from src.domain.events.auth_events import UserPasswordChangeSucceeded
from src.domain.protocols.logger_protocol import LoggerProtocol


class SessionEventHandler:
    """Event handler for session revocation.

    Listens to domain events and performs session management actions.
    Revokes all user sessions when password is changed (security measure).

    Attributes:
        _logger: Logger protocol implementation (from container).

    Note:
        This handler logs the revocation action. The actual session revocation
        happens via the ConfirmPasswordResetHandler which also revokes refresh
        tokens and sessions directly. This handler provides additional logging
        and could be extended for additional side effects (e.g., push notifications).
    """

    def __init__(self, logger: LoggerProtocol) -> None:
        """Initialize session handler with logger.

        Args:
            logger: Logger protocol implementation from container.
        """
        self._logger = logger

    async def handle_user_password_change_succeeded(
        self,
        event: UserPasswordChangeSucceeded,
    ) -> None:
        """Log session revocation after password change.

        Security measure: Force re-login after password change to ensure
        no compromised sessions remain active.

        Note:
            The actual session revocation is handled by ConfirmPasswordResetHandler
            which calls refresh_token_repo.revoke_all_for_user() directly.
            This handler provides logging and could be extended for additional
            side effects like push notifications.

        Args:
            event: UserPasswordChangeSucceeded event with user_id.
        """
        self._logger.info(
            "sessions_revoked_for_password_change",
            user_id=str(event.user_id),
            event_id=str(event.event_id),
            reason="password_changed",
            initiated_by=event.initiated_by,
            security_impact="All user sessions revoked. User must re-login on all devices.",
        )
