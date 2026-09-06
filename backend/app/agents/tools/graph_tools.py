"""
LangGraph Agent Tools: Neo4j Knowledge Graph Boundary
------------------------------------------------------
Exposes bounded, validated tools for multi-agent investigative workflows
to query and explore the Nexxus DB criminal network graph.

All tools enforce strict parameter bounds (e.g., depth bounding <= 3,
result limit bounding <= 25) to protect Neo4j database performance
and prevent LLM context-window overflow.
"""

from typing import Optional, Any, Dict, List
from pydantic import BaseModel, Field
from langchain_core.tools import tool

from backend.app.services.graph_service import (
    get_entity,
    get_neighbors,
    get_shortest_path,
    get_subgraph,
    search_entities,
)

class GetEntityInput(BaseModel):
    """Input schema for fetching an entity by its unique ID."""
    entity_id: str = Field(
        ...,
        description="Unique identifier of the entity to fetch (e.g., 'P001' for Person, 'PH002' for Phone, 'V001' for Vehicle, 'ORG001' for Organization).",
        min_length=1,
    )


@tool("get_entity", args_schema=GetEntityInput)
def get_entity_tool(entity_id: str) -> Dict[str, Any]:
    """Fetches the complete profile, node labels, and attributes of an entity by ID.

    Use this tool when you need full background information on a specific subject,
    such as Aadhaar/PAN, aliases, father's name, risk scores, phone numbers,
    or vehicle registration details.

    Args:
        entity_id: The unique entity identifier in the knowledge graph.

    Returns:
        A dictionary containing:
            - 'found': Boolean indicating if the entity was discovered.
            - 'entity_id': The requested entity ID.
            - 'result': Node attributes, labels, and connected phone numbers (if found).
            - 'message' or 'error': Explanatory message if not found or invalid.
    """
    clean_id= entity_id.strip()
    if not clean_id:
        return {
            "found": False,
            "error": "entity_id cannot be empty."
        }

    result= get_entity(clean_id)
    if result is None:
        return {
            "entity_id": clean_id,
            "found": False,
            "message": f"Entity '{clean_id}' not found in the Knowledge Graph."
        }

    return {
        "entity_id": clean_id,
        "found": True,
        "result": result
    }

#------------------------------------------------------------------------------------------

class GetNeighborsInput(BaseModel):
    """Input schema for fetching direct 1-hop connections of an entity."""
    entity_id: str = Field(
        ...,
        description="Unique identifier of the entity whose direct (1-hop) neighbors should be fetched (e.g., 'P001').",
        min_length=1,
    )


@tool("get_neighbors", args_schema=GetNeighborsInput)
def get_neighbors_tool(entity_id: str) -> Dict[str, Any]:
    """Fetches all direct 1-hop connections and relationships for an entity.

    Use this tool to discover immediate associates, owned vehicles, linked phone
    numbers, organizations, and co-locations. This reveals direct criminal ties
    and transaction conduits.

    Args:
        entity_id: The unique entity ID whose immediate perimeter to inspect.

    Returns:
        A dictionary containing:
            - 'found': Boolean indicating if the entity has any connections.
            - 'entity_id': The requested entity ID.
            - 'count': Total count of direct 1-hop connections.
            - 'result': List of neighboring nodes and relationship properties.
    """
    clean_id = entity_id.strip()
    if not clean_id:
        return {
            "found": False,
            "count": 0,
            "error": "entity_id cannot be empty."
        }

    result = get_neighbors(clean_id)
    if not result:
        return {
            "entity_id": clean_id,
            "found": False,
            "count": 0,
            "message": f"No direct neighbors found for entity '{clean_id}'."
        }

    return {
        "entity_id": clean_id,
        "found": True,
        "count": len(result),
        "result": result
    }


class GetSubgraphInput(BaseModel):
    """Input schema for multi-hop subgraph exploration around an entity."""
    entity_id: str = Field(
        ...,
        description="Center entity ID to build the local subgraph around (e.g., 'P001').",
        min_length=1,
    )
    depth: int = Field(
        default=2,
        description="Exploration radius / hops away from the center entity. Bounded between 1 and 3.",
        ge=1,
        le=3,
    )


@tool("get_subgraph", args_schema=GetSubgraphInput)
def get_subgraph_tool(entity_id: str, depth: int = 2) -> Dict[str, Any]:
    """Retrieves a multi-hop ego-network around an entity, strictly bounded to max depth 3.

    Use this tool to uncover broader criminal syndicates, multi-layered shell companies,
    and indirect money/communication flows. Depth is bounded to prevent database
    freezes and token exhaustion.

    Args:
        entity_id: Central entity identifier.
        depth: Traversal radius (1 to 3 hops, default: 2).

    Returns:
        A dictionary containing:
            - 'found': Boolean indicating if any nodes were reached.
            - 'center_id': The central entity ID.
            - 'depth': Effective traversal depth applied.
            - 'node_count': Number of unique nodes in the cluster.
            - 'edge_count': Number of relationships linking the nodes.
            - 'result': Dict with 'nodes' and 'edges' arrays.
    """
    clean_id = entity_id.strip()
    if not clean_id:
        return {
            "found": False,
            "error": "entity_id cannot be empty."
        }

    # Bounded safeguard
    bounded_depth = max(1, min(depth, 3))
    result = get_subgraph(clean_id, depth=bounded_depth)

    nodes = result.get("nodes", [])
    edges = result.get("edges", [])

    if not nodes:
        return {
            "center_id": clean_id,
            "found": False,
            "depth": bounded_depth,
            "node_count": 0,
            "edge_count": 0,
            "message": f"No subgraph connections found around entity '{clean_id}'."
        }

    return {
        "center_id": clean_id,
        "found": True,
        "depth": bounded_depth,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "result": result
    }


# =========================================================================
# Tool 4: Get Shortest Path Between Two Entities
# =========================================================================

class GetShortestPathInput(BaseModel):
    """Input schema for shortest path detection between two entities."""
    source_id: str = Field(
        ...,
        description="Starting entity ID (e.g., primary suspect, bank account, or phone).",
        min_length=1,
    )
    target_id: str = Field(
        ...,
        description="Target entity ID to trace connections toward (e.g., associate, shell company, or victim).",
        min_length=1,
    )


@tool("get_shortest_path", args_schema=GetShortestPathInput)
def get_shortest_path_tool(source_id: str, target_id: str) -> Dict[str, Any]:
    """Finds the shortest relational chain connecting two entities in the network.

    Use this tool to test investigative hypotheses, such as proving an indirect
    financial conduit or communication link between a kingpin and an on-the-ground operative.

    Args:
        source_id: Starting entity identifier.
        target_id: Destination entity identifier.

    Returns:
        A dictionary containing:
            - 'path_found': Boolean indicating if an unbroken path exists.
            - 'source_id': Cleaned source entity ID.
            - 'target_id': Cleaned target entity ID.
            - 'length': Number of relationship hops in the shortest path.
            - 'result': Dict with 'nodes' and 'edges' tracing the path.
    """
    s_id = source_id.strip()
    t_id = target_id.strip()

    if not s_id or not t_id:
        return {
            "path_found": False,
            "error": "Both source_id and target_id must be non-empty."
        }

    if s_id == t_id:
        return {
            "source_id": s_id,
            "target_id": t_id,
            "path_found": True,
            "length": 0,
            "message": "Source and target IDs are identical (0 hops)."
        }

    result = get_shortest_path(s_id, t_id)
    nodes = result.get("nodes", [])
    edges = result.get("edges", [])

    has_path = bool(nodes and len(nodes) >= 2)
    return {
        "source_id": s_id,
        "target_id": t_id,
        "path_found": has_path,
        "length": len(edges) if has_path else 0,
        "result": result
    }



class SearchEntitiesInput(BaseModel):
    """Input schema for searching entities across the knowledge graph."""
    query: str = Field(
        ...,
        description="Search term (e.g., suspect name, alias, phone digits, vehicle plate, or organization name).",
        min_length=1,
    )
    limit: int = Field(
        default=10,
        description="Maximum number of candidate entities to return (bounded between 1 and 25).",
        ge=1,
        le=25,
    )


@tool("search_entities", args_schema=SearchEntitiesInput)
def search_entities_tool(query: str, limit: int = 10) -> Dict[str, Any]:
    """Searches knowledge graph entities by name, alias, phone number, or vehicle plate.

    Use this tool at the start of an investigation when the agent only has an unstructured
    clue (e.g., 'Find Rahul' or 'Check phone ending in 9123') and needs to identify
    concrete entity IDs for deeper graph traversal.

    Args:
        query: Substring or term to search for across node properties.
        limit: Max results to return (bounded between 1 and 25, default: 10).

    Returns:
        A dictionary containing:
            - 'found': Boolean indicating if matching entities were found.
            - 'query': The search query executed.
            - 'count': Number of matching entities returned.
            - 'result': List of matching entity profiles with their labels and phones.
    """
    clean_query = query.strip()
    if not clean_query:
        return {
            "found": False,
            "count": 0,
            "error": "Search query cannot be empty."
        }

    # Bounded safeguard
    bounded_limit = max(1, min(limit, 25))
    result = search_entities(clean_query, limit=bounded_limit)

    return {
        "query": clean_query,
        "found": bool(result),
        "count": len(result),
        "result": result
    }



# Exported Tool Registry for LangGraph Multi-Agent Workflows

GRAPH_TOOLS = [
    get_entity_tool,
    get_neighbors_tool,
    get_subgraph_tool,
    get_shortest_path_tool,
    search_entities_tool,
]
