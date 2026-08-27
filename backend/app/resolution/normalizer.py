"""
Entity Resolution - Text Normalization Module
---------------------------------------------
Standardizes suspect names and phone numbers to ensure consistent formats
before performing fuzzy matching and graph deduplication.
"""

import re



def normalize_name(name: str | None) -> str:
    """Cleans and standardizes names by lowercasing, stripping honorifics,

    removing special characters, and collapsing whitespace.
    """
    if not name:
        return ""

    name = name.casefold().strip()
    name = re.sub(r'[^a-zA-Z0-9\s]', ' ', name)

    # Match prefixes at the beginning of the string followed by a word boundary/space
    PREFIXES = r'^(mr|mrs|ms|dr|prof|shri|smt|adv|late)\b[\.\s]*'
    name = re.sub(PREFIXES, '', name, flags=re.IGNORECASE).strip()
    name = " ".join(name.split())

    return name


def normalize_phone(phone: str | None) -> str:
    """Normalizes phone numbers to standard 10-digit format for Indian numbers."""
    if not phone:
        return ""

    digits = re.sub(r'\D', '', phone)

    # If it has 11 digits (e.g. 09876543210) or 12 digits (e.g. 919876543210), extract last 10
    if len(digits) in (11, 12):
        digits = digits[-10:]

    return digits

