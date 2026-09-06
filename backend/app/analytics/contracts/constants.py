"""
constants.py
Single source of truth for entity/relationship type names -- aligned to
Person 4's official schemas.py contract (see schemas.py in this folder).

Person 1, 2, and 3 should ALL import from this file instead of hardcoding
type strings, so naming mismatches happen in one place, not four codebases.
"""

# --- Canonical entity types (Title Case, matches Person 4's EntityType Literal) ---
ENTITY_TYPES = {"Person", "Phone", "Location", "Vehicle", "Organization"}

# Accepts both the old all-caps convention (seen in an early real sample from
# Person 1/2, e.g. "PERSON") and the official Title Case convention, and
# normalizes to the official form. Use this on every entity as it's loaded,
# so downstream code only ever sees "Person", "Phone", etc.
_TYPE_NORMALIZE = {
    "PERSON": "Person", "Person": "Person",
    "PHONE": "Phone", "Phone": "Phone",
    "LOCATION": "Location", "Location": "Location",
    "VEHICLE": "Vehicle", "Vehicle": "Vehicle",
    "ORGANIZATION": "Organization", "Organization": "Organization",
}


def normalize_entity_type(raw_type: str) -> str:
    """Maps any known casing variant to the official Title Case form.
    Unknown types pass through unchanged (caller should handle/flag those)."""
    return _TYPE_NORMALIZE.get(raw_type, raw_type)


# --- Relationship types ---
# CONFLICT FLAGGED 2026-08-29: Person 4's official RelationshipType Literal
# is {"CALLED", "TRANSACTED_WITH", "PRESENT_AT", "OWNS_VEHICLE", "MEMBER_OF"}
# -- it does NOT include "ASSOCIATED_WITH", which the original team plan and
# our mock graph both use for generic associations. Sending "ASSOCIATED_WITH"
# to Person 4's API will fail their Pydantic validation.
#
# Until this is resolved with Person 4 (either they add it to the Literal, or
# we stop using it), we keep it in our INTERNAL analytics graph -- it's still
# useful for community detection -- but schema_mapper.py filters it out
# before building the GraphResponse that goes to their API.
OFFICIAL_EDGE_TYPES = {"CALLED", "TRANSACTED_WITH", "PRESENT_AT", "OWNS_VEHICLE", "MEMBER_OF", "OWNS_PHONE"}
INTERNAL_ONLY_EDGE_TYPES = {"ASSOCIATED_WITH"}  # analytics-only, not sent to the API
EDGE_TYPES = OFFICIAL_EDGE_TYPES | INTERNAL_ONLY_EDGE_TYPES

# Required node properties for analytics to work
REQUIRED_PERSON_NODE_FIELDS = {
    "case_ids": "list[str] -- every case this entity appears in, used for cross-case risk signal",
}

REQUIRED_EDGE_FIELDS = {
    "CALLED": ["timestamp"],
    "TRANSACTED_WITH": ["amount", "timestamp"],
    "PRESENT_AT": ["timestamp"],
}
