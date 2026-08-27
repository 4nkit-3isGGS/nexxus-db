"""
Unit Tests for Text Normalizer
------------------------------
Tests name standardization, honorific removal, whitespace collapsing,
and phone number normalization edge cases.
"""

import pytest
from backend.app.resolution.normalizer import normalize_name, normalize_phone



def test_normalize_name():
    cases = [
        ("Mr. Rahul Sharma", "rahul sharma"),
        ("DR. Rahul-Sharma", "rahul sharma"),
        ("  Shri  Amit   Kumar  ", "amit kumar"),
        ("Late Vikram Malhotra", "vikram malhotra"),
        ("Sameer Khan!!!", "sameer khan"),
        ("Adv. Pooja Hegde", "pooja hegde"),
        ("", ""),
        (None, ""),
    ]
    for raw_name, expected in cases:
        assert normalize_name(raw_name) == expected, f"Failed for '{raw_name}'"


def test_normalize_phone():
    cases = [
        ("+91 98765-43210", "9876543210"),
        ("09876543210", "9876543210"),
        ("919876543210", "9876543210"),
        ("+91 (98765) 43210", "9876543210"),
        ("9876543210", "9876543210"),
        ("", ""),
        (None, ""),
    ]
    for raw_phone, expected in cases:
        assert normalize_phone(raw_phone) == expected, f"Failed for '{raw_phone}'"
