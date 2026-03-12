"""
Tests for rules engine.
"""

import pytest


def test_overhang_enables_supports():
    """ModelIntent with needs_supports=True must produce supports_enabled=True."""
    pass


def test_tpu_enforces_slow_speed():
    """TPU filament must result in print_speed_mm_s <= 30."""
    pass


def test_safety_clamp_caps_speed():
    """Safety clamp must not allow speed above printer max_speed_mm_s."""
    pass
