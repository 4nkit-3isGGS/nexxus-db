"""
Unit Tests for Ingestion Payload Validator
-------------------------------------------
Tests structural validation, entity schema checks, relationship validation,
referential integrity, confidence range checks, and exception raising.
"""

import pytest
from backend.app.ingestion.validator import (
    validate_nlp_payload,
    validate_or_raise,
    PayloadValidationError,
)


class TestPayloadValidator:
    def test_valid_payload(self):
        payload = {
            "entities": [
                {"id": "P001", "type": "Person", "name": "Test Person"},
                {"id": "PH001", "type": "Phone", "number": "+919876543210"},
            ],
            "relationships": [
                {"source": "P001", "target": "PH001", "type": "OWNS_PHONE", "confidence": 0.95}
            ],
        }
        is_valid, errors = validate_nlp_payload(payload)
        assert is_valid is True
        assert len(errors) == 0

    def test_invalid_structure(self):
        is_valid, errors = validate_nlp_payload("not a dict")
        assert is_valid is False
        assert "must be a JSON object" in errors[0]

    def test_missing_entity_id_or_type(self):
        payload = {
            "entities": [
                {"type": "Person"},  # missing id
                {"id": "P002", "type": "Alien"},  # invalid type
            ],
            "relationships": [],
        }
        is_valid, errors = validate_nlp_payload(payload)
        assert is_valid is False
        assert len(errors) == 2

    def test_referential_integrity_failure(self):
        payload = {
            "entities": [
                {"id": "P001", "type": "Person"},
            ],
            "relationships": [
                # target P999 was not declared in entities!
                {"source": "P001", "target": "P999", "type": "CALLED"}
            ],
        }
        is_valid, errors = validate_nlp_payload(payload)
        assert is_valid is False
        assert any("P999" in err for err in errors)

    def test_invalid_relationship_type(self):
        payload = {
            "entities": [
                {"id": "P001", "type": "Person"},
                {"id": "P002", "type": "Person"},
            ],
            "relationships": [
                {"source": "P001", "target": "P002", "type": "HUGGED"}  # invalid rel type
            ],
        }
        is_valid, errors = validate_nlp_payload(payload)
        assert is_valid is False
        assert any("invalid 'type' 'HUGGED'" in err for err in errors)

    def test_invalid_confidence_score(self):
        payload = {
            "entities": [
                {"id": "P001", "type": "Person"},
                {"id": "P002", "type": "Person"},
            ],
            "relationships": [
                {"source": "P001", "target": "P002", "type": "CALLED", "confidence": 1.5}  # > 1.0
            ],
        }
        is_valid, errors = validate_nlp_payload(payload)
        assert is_valid is False
        assert any("confidence score" in err for err in errors)

    def test_validate_or_raise_exception(self):
        invalid_payload = {"entities": [{"type": "Person"}]}
        with pytest.raises(PayloadValidationError) as exc_info:
            validate_or_raise(invalid_payload)
        assert "Payload validation failed" in str(exc_info.value)
