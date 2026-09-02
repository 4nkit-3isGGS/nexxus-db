"""
Integration Tests for Ingestion Pipeline
-----------------------------------------
Tests full multi-entity & multi-relationship ingestion pipeline,
including entity resolution, node creation/merging, and relationship persistence.
"""

import pytest
from backend.app.neo4j_driver import db
from backend.app.ingestion.graph_ingestor import ingest_nlp_payload


@pytest.fixture(scope="module", autouse=True)
def check_db_connection():
    """Ensures Neo4j is connected before running integration tests."""
    if not db.verify_connectivity():
        pytest.skip("Neo4j database is not reachable. Skipping integration tests.")


class TestIngestionPipeline:
    def test_ingest_nlp_payload(self):
        sample_payload = {
            "entities": [
                {
                    "id": "P101",
                    "type": "Person",
                    "source_doc": "FIR_TEST_01",
                    "name": "Test Suspect One",
                    "aliases": ["Testy"],
                },
                {
                    "id": "PH101",
                    "type": "Phone",
                    "source_doc": "FIR_TEST_01",
                    "number": "+919988776655",
                },
                {
                    "id": "LOC101",
                    "type": "Location",
                    "source_doc": "FIR_TEST_01",
                    "name": "Test Hideout Location",
                    "latitude": 28.6139,
                    "longitude": 77.2090,
                },
                {
                    "id": "VEH101",
                    "type": "Vehicle",
                    "source_doc": "FIR_TEST_01",
                    "registration_number": "DL01TEST99",
                    "vehicle_type": "SUV",
                },
                {
                    "id": "ORG101",
                    "type": "Organization",
                    "source_doc": "FIR_TEST_01",
                    "name": "Test Syndicate Corp",
                },
            ],
            "relationships": [
                {
                    "source": "P101",
                    "target": "PH101",
                    "type": "OWNS_PHONE",
                    "source_doc": "FIR_TEST_01",
                },
                {
                    "source": "P101",
                    "target": "LOC101",
                    "type": "PRESENT_AT",
                    "confidence": 0.9,
                    "source_doc": "FIR_TEST_01",
                    "timestamp": "2026-08-25T14:30:00Z",
                },
                {
                    "source": "P101",
                    "target": "ORG101",
                    "type": "MEMBER_OF",
                    "role": "Operative",
                    "source_doc": "FIR_TEST_01",
                },
            ],
        }

        result = ingest_nlp_payload(sample_payload)

        assert isinstance(result, dict)
        assert result["persons_ingested"] == 1
        assert result["phones_ingested"] == 1
        assert result["locations_ingested"] == 1
        assert result["vehicles_ingested"] == 1
        assert result["organizations_ingested"] == 1
        assert result["relationships_ingested"] >= 1
