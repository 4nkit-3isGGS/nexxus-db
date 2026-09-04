"""
Unit Tests for Fraud Detection Engine & Review Queue
-----------------------------------------------------
Tests:
1. Vehicle cloned plate attribute conflict detection
2. Universal label-agnostic flag_for_review
3. Review queue retrieval and merge logic
"""

from unittest.mock import patch, MagicMock
import pytest

from backend.app.ingestion.graph_ingestor import (
    ingest_vehicle,
    flag_for_review,
    ingest_organization,
)
from backend.app.services.graph_service import (
    get_review_queue,
    merge_duplicate_entities,
)


class TestVehicleFraudDetection:
    @patch("backend.app.ingestion.graph_ingestor.db.query")
    def test_new_vehicle_creation_no_conflict(self, mock_query):
        # When vehicle doesn't exist in DB
        mock_query.side_effect = [
            [],  # existing check returns empty
            [{"id": "VEH-123"}],  # create returns ID
        ]
        veh_id = ingest_vehicle(
            registration_number="DL-01-AB-1234",
            vehicle_type="Motorcycle",
            source_doc="FIR_101",
        )
        assert veh_id == "VEH-123"
        # Verify MERGE query created with is_cloned_suspicious = false
        assert mock_query.call_count == 2
        create_query = mock_query.call_args_list[1][0][0]
        assert "is_cloned_suspicious = false" in create_query

    @patch("backend.app.ingestion.graph_ingestor.db.query")
    def test_vehicle_cloned_plate_type_conflict_detected(self, mock_query):
        # When vehicle already exists as "Motorcycle", but incoming is "SUV"
        mock_query.side_effect = [
            [{"id": "VEH-EXISTING", "vehicle_type": "Motorcycle"}],  # existing
            None,  # update conflict cypher
        ]
        veh_id = ingest_vehicle(
            registration_number="DL 01 AB 1234",
            vehicle_type="White SUV",
            source_doc="FIR_202",
        )
        assert veh_id == "VEH-EXISTING"
        assert mock_query.call_count == 2
        # Verify conflict update query was triggered
        conflict_query = mock_query.call_args_list[1][0][0]
        params = mock_query.call_args_list[1][0][1]
        assert "v.is_cloned_suspicious = true" in conflict_query
        assert "Type conflict" in params["conflict_msg"]
        assert "Motorcycle" in params["conflict_msg"]
        assert "White SUV" in params["conflict_msg"]

    @patch("backend.app.ingestion.graph_ingestor.db.query")
    def test_vehicle_same_type_no_conflict(self, mock_query):
        # Same vehicle type reported again -> no conflict
        mock_query.side_effect = [
            [{"id": "VEH-SAME", "vehicle_type": "SUV"}],
            None,
        ]
        veh_id = ingest_vehicle(
            registration_number="DL01AB1234",
            vehicle_type="SUV",
            source_doc="FIR_303",
        )
        assert veh_id == "VEH-SAME"
        update_query = mock_query.call_args_list[1][0][0]
        assert "is_cloned_suspicious = true" not in update_query


class TestUniversalFlagForReview:
    @patch("backend.app.ingestion.graph_ingestor.db.query")
    def test_flag_for_review_label_agnostic(self, mock_query):
        flag_for_review(
            id1="ORG-1",
            id2="ORG-2",
            confidence_score=0.88,
            reason="High org name token similarity",
            entity_type="Organization",
        )
        assert mock_query.call_count == 1
        query, params = mock_query.call_args[0]
        # Ensure it doesn't hardcode :Person
        assert ":Person" not in query
        assert "MATCH (e1 {id: $id1}), (e2 {id: $id2})" in query
        assert params["entity_type"] == "Organization"
        assert params["confidence_score"] == 0.88


class TestReviewQueueAndMerge:
    @patch("backend.app.services.graph_service.db.query")
    def test_get_review_queue(self, mock_query):
        mock_query.return_value = [
            {
                "entity1_id": "ORG-1",
                "entity1_name": "Shubh Laxmi Finance",
                "entity2_id": "ORG-2",
                "entity2_name": "Subh Laxmi Financial Services",
                "confidence_score": 0.85,
                "entity_type": "Organization",
                "match_reason": "High name similarity",
            }
        ]
        queue = get_review_queue()
        assert len(queue) == 1
        assert queue[0]["entity_type"] == "Organization"
        assert queue[0]["confidence_score"] == 0.85

    @patch("backend.app.services.graph_service.db.query")
    def test_merge_duplicate_entities(self, mock_query):
        mock_query.return_value = [{"merged": True}]
        result = merge_duplicate_entities("ORG-1", "ORG-2")
        assert result["success"] is True
        assert result["target_id"] == "ORG-1"
        assert result["merged_duplicate_id"] == "ORG-2"
        assert mock_query.call_count == 1
        cypher = mock_query.call_args[0][0]
        assert "DETACH DELETE dup" in cypher


class TestEntityApiRoutes:
    @patch("backend.app.api.entity_routes.get_review_queue")
    def test_get_review_queue_route(self, mock_queue):
        from backend.app.api.entity_routes import entity_review_queue
        mock_queue.return_value = [
            {"entity1_id": "P-1", "entity2_id": "P-2", "confidence_score": 0.9}
        ]
        result = entity_review_queue()
        assert len(result) == 1
        assert result[0]["confidence_score"] == 0.9

    @patch("backend.app.api.entity_routes.merge_duplicate_entities")
    def test_merge_route_success(self, mock_merge):
        from backend.app.api.entity_routes import entity_merge, MergeEntitiesRequest
        mock_merge.return_value = {"success": True, "target_id": "P-1", "merged_duplicate_id": "P-2"}
        req = MergeEntitiesRequest(target_id="P-1", duplicate_id="P-2")
        result = entity_merge(req)
        assert result["success"] is True
        assert result["target_id"] == "P-1"

    @patch("backend.app.api.entity_routes.merge_duplicate_entities")
    def test_merge_route_failure(self, mock_merge):
        from fastapi import HTTPException
        from backend.app.api.entity_routes import entity_merge, MergeEntitiesRequest
        mock_merge.return_value = {"success": False, "error": "Entity not found"}
        req = MergeEntitiesRequest(target_id="NONEXISTENT", duplicate_id="DUP")
        with pytest.raises(HTTPException) as exc_info:
            entity_merge(req)
        assert exc_info.value.status_code == 400
        assert "Entity not found" in exc_info.value.detail
