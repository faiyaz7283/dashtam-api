"""Email service implementations.

This package contains email service adapters:
- StubEmailService: Console logging for development/testing
- AWSEmailService: AWS SES for production (future)
"""

from src.infrastructure.email.stub_email_service import StubEmailService

__all__ = [
    "StubEmailService",
]
