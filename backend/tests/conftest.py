"""
Shared pytest fixtures and environment setup.

JWT_SECRET_KEY must be set before app.config is imported or the startup
check raises RuntimeError. Setting it here at module level ensures it is
present for all tests in this suite.
"""

import os

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-unit-tests-only")
