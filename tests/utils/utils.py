"""Utility functions for testing.

Provides helper functions for generating random test data and common operations.
"""

import random
import string
from typing import Dict


def random_lower_string(length: int = 32) -> str:
    """Generate a random lowercase string.
    
    Args:
        length: Length of the string to generate
        
    Returns:
        Random lowercase string
    """
    return "".join(random.choices(string.ascii_lowercase, k=length))


def random_email() -> str:
    """Generate a random email address for testing.
    
    Returns:
        Random email in format: random@example.com
    """
    return f"{random_lower_string(10)}@example.com"


def random_provider_key() -> str:
    """Generate a random provider key for testing.
    
    Returns:
        Random provider key (lowercase, 8 chars)
    """
    return random_lower_string(8)


def get_superuser_token_headers() -> Dict[str, str]:
    """Get authentication headers for superuser.
    
    TODO: Implement actual authentication once auth endpoints exist.
    
    Returns:
        Dict with Authorization header
    """
    return {"Authorization": "Bearer mock_superuser_token"}


def get_user_token_headers(user_id: str) -> Dict[str, str]:
    """Get authentication headers for a specific user.
    
    TODO: Implement actual authentication once auth endpoints exist.
    
    Args:
        user_id: User ID to create token for
        
    Returns:
        Dict with Authorization header
    """
    return {"Authorization": f"Bearer mock_user_token_{user_id}"}
