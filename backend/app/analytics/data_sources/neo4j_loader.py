"""
neo4j_loader.py
Loads the real graph from Person 2's Neo4j instance into the same
networkx.MultiDiGraph everything else in this folder expects.

Matches Person 2's actual seed schema (2026-08-29):
  - Node labels ARE the entity type (e.g. `(:Person)`), NOT a "type"
    property -- Cypher `labels(n)[0]` gives us that string, and it already
    matches Person 4's official Title Case EntityType ("Person", "Phone",
    "Location", "Vehicle", "Organization") exactly. No normalization
    needed on this path (unlike json_loader.py, which has to handle an
    older all-caps convention).
  - Property names line up with Person 4's NodeProperties schema field
    for field: normalized_name, aliases, latitude/longitude,
    registration_number, vehicle_type, created_at/updated_at.
  - Relationship properties (source_doc, timestamp, duration, amount,
    transaction_id, role, confidence) also match EdgeProperties directly.

Connection settings default to a local Docker Neo4j instance -- override
via environment variables if Person 2's instance runs elsewhere.
"""

import os
import networkx as nx
from neo4j import GraphDatabase
from graph.data_sources.case_utils import derive_case_ids

NEO4J_URI = os.environ.get("NEO4J_URL", os.environ.get("NEO4J_URI", "bolt://127.0.0.1:7687"))
NEO4J_USER = os.environ.get("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "Arnish123")
NEO4J_DATABASE = os.environ.get("NEO4J_DATABASE", "neo4j")

# Every entity type carries an "id" property (P001, PH001, LOC001, ...) --
# that's what we key networkx nodes by, matching every other loader.
_NODE_QUERY = "MATCH (n) RETURN n AS node, labels(n)[0] AS label"
_EDGE_QUERY = """
 MATCH (a)-[r]->(b) WHERE a.id IS NOT NULL AND b.id IS NOT NULL
 RETURN a.id AS source, b.id AS target, type(r) AS rel_type, properties(r) AS props
"""

# Some entity types don't have a "name" field in Person 2's schema (Phone
# uses "number", Vehicle uses "registration_number") -- unify to "name" so
# analytics.py / schema_mapper.py can display *something* consistently,
# in addition to keeping the type-specific field for schema_mapper's
# NodeProperties mapping.
_DISPLAY_NAME_FIELD = {
    "Phone": "number",
    "Vehicle": "registration_number",
}


def load_from_neo4j(uri: str = NEO4J_URI, user: str = NEO4J_USER, password: str = NEO4J_PASSWORD) -> nx.MultiDiGraph:
    driver = GraphDatabase.driver(uri, auth=(user, password))
    G = nx.MultiDiGraph()

    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            for record in session.run(_NODE_QUERY):
                node = record["node"]
                label = record["label"]
                node_id =  node.get("id")
                if not node_id: continue
                attrs = dict(node)
                attrs["type"] = label
                if "name" not in attrs:
                    name_field = _DISPLAY_NAME_FIELD.get(label)
                    if name_field and name_field in attrs:
                        attrs["name"] = attrs[name_field]
                G.add_node(node_id, **attrs)

            for record in session.run(_EDGE_QUERY):
                props = dict(record["props"])
                props["edge_type"] = record["rel_type"]
                G.add_edge(record["source"], record["target"], **props)
    finally:
        driver.close()

    derive_case_ids(G)
    return G


if __name__ == "__main__":
    G = load_from_neo4j()
    print(f"Loaded from Neo4j: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
    for node, data in G.nodes(data=True):
        print(f"  {node}: {data}")
