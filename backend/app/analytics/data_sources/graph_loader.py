"""
graph_loader.py
Single entry point analytics.py and risk_engine.py call to get the graph.
Toggle DATA_SOURCE to switch between the built-in mock graph, a real
Person 1/2 JSON export, or a live Neo4j instance -- nothing else in this
folder needs to change when you switch.
"""

import os

import networkx as nx
from pathlib import Path
from graph.data_sources.mock_graph import build_mock_graph
from graph.data_sources.json_loader import load_from_json_file
from graph.data_sources.neo4j_loader import load_from_neo4j

# "mock" for the built-in test graph, "json" for Person 1/2's JSON export
# file, "neo4j" for Person 2's live graph DB.
DATA_SOURCE = os.environ.get("GRAPH_DATA_SOURCE", "neo4j")
JSON_DATA_PATH = str(Path(__file__).resolve().parent.parent / "sample_data" / "ground_truth_case.json")  # used when DATA_SOURCE == "json"


def load_graph() -> nx.MultiDiGraph:
    if DATA_SOURCE == "neo4j":
        return load_from_neo4j()  # reads NEO4J_URI/NEO4J_USER/NEO4J_PASSWORD env vars, see neo4j_loader.py
    if DATA_SOURCE == "json":
        return load_from_json_file(JSON_DATA_PATH)
    return build_mock_graph()
