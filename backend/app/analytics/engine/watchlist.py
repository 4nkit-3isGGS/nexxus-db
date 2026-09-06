"""
watchlist.py
Mock "known offenders" list -- placeholder data for the hackathon demo.
Swap KNOWN_OFFENDERS for a real lookup (NCRB records, prior FIR history,
department watchlist DB) later -- the check_watchlist() interface doesn't
need to change, only where the data comes from.
"""

# Keyed by entity_id OR exact display name -- whichever Person 1/2's data uses.
KNOWN_OFFENDERS = {
    "Suresh": "Prior conviction: extortion (2022)",
    "Amit": "Named in a prior FIR for financial fraud (2024, case closed - insufficient evidence)",
}

WATCHLIST_BOOST = 15  # flat points added to overall_risk_score on a match


def check_watchlist(entity_id: str, name: str | None = None) -> str | None:
    """Returns the watchlist reason string if this entity matches, else None."""
    if entity_id in KNOWN_OFFENDERS:
        return KNOWN_OFFENDERS[entity_id]
    if name and name in KNOWN_OFFENDERS:
        return KNOWN_OFFENDERS[name]
    return None
