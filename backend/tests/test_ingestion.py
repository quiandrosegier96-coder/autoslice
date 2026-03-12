"""
Tests for ingestion layer: validator, handler, unpacker.
"""

import pytest
from pathlib import Path


# Placeholder — Phase 3 will add real fixture-based tests

def test_validator_rejects_non_3mf():
    """Files without .3mf extension must be rejected."""
    pass


def test_validator_rejects_non_zip():
    """Files that are not valid ZIP archives must be rejected."""
    pass


def test_unpacker_maps_model_file():
    """Unpacker must correctly locate 3D/3dmodel.model."""
    pass
