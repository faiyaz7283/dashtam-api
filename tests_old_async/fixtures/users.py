"""User fixtures for testing.

This module provides factory functions and fixtures for creating test users
with various configurations following Dashtam patterns.
"""

from typing import Dict, Any


def create_user_data(**overrides: Any) -> Dict[str, Any]:
    """Create user data dictionary with defaults and overrides.

    Args:
        **overrides: Override default values

    Returns:
        Dictionary with user data for testing
    """
    defaults = {
        "email": "test@example.com",
        "name": "Test User",
        "is_verified": True,
        "last_login": None,
    }
    defaults.update(overrides)
    return defaults


def create_unverified_user_data(**overrides: Any) -> Dict[str, Any]:
    """Create unverified user data for testing email verification flows.

    Args:
        **overrides: Override default values

    Returns:
        Dictionary with unverified user data
    """
    return create_user_data(
        email="unverified@example.com",
        name="Unverified User",
        is_verified=False,
        **overrides,
    )


def create_multiple_users_data(count: int = 3) -> list[Dict[str, Any]]:
    """Create multiple user data dictionaries for bulk testing.

    Args:
        count: Number of users to create

    Returns:
        List of user data dictionaries
    """
    users = []
    for i in range(count):
        users.append(
            create_user_data(
                email=f"user{i + 1}@example.com", name=f"Test User {i + 1}"
            )
        )
    return users


def create_test_user_variants() -> Dict[str, Dict[str, Any]]:
    """Create various user test scenarios.

    Returns:
        Dictionary mapping scenario names to user data
    """
    return {
        "verified_user": create_user_data(),
        "unverified_user": create_unverified_user_data(),
        "user_with_long_name": create_user_data(
            name="Test User With A Very Long Name That Tests Field Limits"
        ),
        "user_with_special_chars": create_user_data(
            email="test+special@example.com", name="Test Üser Wïth Spëciål Chärs"
        ),
        "admin_user": create_user_data(email="admin@example.com", name="Admin User"),
    }
